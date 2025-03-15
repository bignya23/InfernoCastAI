from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
import asyncio
import uuid
import queue
import threading
from src.conv_history import store_chat_history, get_chat_history
from src.podcast_agent_threaded import PodcastAgent
from src.user_handeling_agent import HandelUser
from src.text_processing import TextProcessing
from pydantic import BaseModel
import shutil
import os
import janus
import numpy as np
import base64
import json
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import speech
import webrtcvad
from typing import List
import base64

app = FastAPI()

origins = [
    "http://localhost:5173", 
]

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"/Users/probindhakal/Desktop/InfernoCastAI/neurosphere-453417-a13fa049f648.json"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allow only specific origins
    allow_credentials=True,  # Allow cookies & authentication
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

text_summary = ""
text_processor = TextProcessing()


@app.get("/")
async def root():
    return {"message": "Hello World"}




# Audio Streaming Config
RATE = 16000  # Sample Rate
BUFFER_SIZE = RATE // 4  # 250ms buffer
SILENCE_THRESHOLD = 500  # RMS threshold for silence detection
SILENCE_DURATION = 50 # Seconds of silence to trigger close

client = speech.SpeechClient()
 # Thread-safe queue

def calculate_rms(chunk):
    """Calculate RMS value of audio chunk."""
    audio_data = np.frombuffer(chunk, dtype=np.int16)
    return np.sqrt(np.mean(np.square(audio_data)))

def audio_generator(audio_queue):
    """Sync generator for Google STT."""
    while True:
        chunk = audio_queue.sync_q.get()
        if chunk is None:
            break
        yield speech.StreamingRecognizeRequest(audio_content=chunk)
        audio_queue.sync_q.task_done()

async def process_audio(audio_queue, websocket : WebSocket):
    """Process audio with Google STT."""
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US"
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    response_queue = janus.Queue()

    def run_streaming():
        """Run blocking STT client."""
        try:
            responses = client.streaming_recognize(streaming_config, audio_generator(audio_queue))
            for response in responses:
                response_queue.sync_q.put(response)
            response_queue.sync_q.put(None)
        except Exception as e:
            response_queue.sync_q.put(e)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_streaming)

    try:
        while True:
            response = await response_queue.async_q.get()
            if response is None:
                break
            if isinstance(response, Exception):
                raise response

            for result in response.results:
                transcript = result.alternatives[0].transcript
                if result.is_final:
                    print(f"✅ Final: {transcript}")
                    await websocket.send_json({"Final" : transcript})
                    break
                else:
                    print(f"⏳ Interim: {transcript}", end="\r")
    except Exception as e:
        print(f"STT Error: {e}")
    


async def process_audio_stream(websocket: WebSocket):
    """WebSocket with silence detection."""
    audio_queue = janus.Queue() 
    transcription_task = asyncio.create_task(process_audio(audio_queue, websocket))
    silent_chunks = 0
    chunks_needed = int(SILENCE_DURATION / (BUFFER_SIZE / RATE))  # ~12 chunks

    try:
        while True:
            chunk = await websocket.receive_bytes()
            
            # Silence detection
            rms = calculate_rms(chunk)
            if rms < SILENCE_THRESHOLD:
                silent_chunks += 1
                print(f"🛑 Silence detected ({silent_chunks}/{chunks_needed})")
            else:
                silent_chunks = 0  # Properly reset on speech
                print("🎙️ Speech detected")

            # Close the WebSocket if sustained silence is detected
            if silent_chunks >= chunks_needed:
                print(f"🚫 {SILENCE_DURATION}s of silence detected, ending loop...")
                break  

            # Send to processing
            await audio_queue.async_q.put(chunk)

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await audio_queue.async_q.put(None)
        await transcription_task
        audio_queue.close()
        await audio_queue.wait_closed()
        print("User function Connection closed")
        
        while True:
            try:
                pending = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)
                break
                print("Flushing pending message:", pending)
            except KeyError:
                print("Received message without 'text' key; ignoring.")
            except asyncio.TimeoutError:
                break


        # final_response = await websocket.receive_json()
        # print("Received final JSON response:", final_response)


class TextInput(BaseModel):
    text: str  


@app.post("/process-text")
async def process_text(text: TextInput):
    """
    Endpoint to process plain text input.
    """
    global text_summary
    if not text.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        text_summary = text_processor.summarise(text.text)
        return {"summary": text_summary}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process-file")
async def process_file(file: UploadFile = File(...)):
    """
    Endpoint to process a PDF file and extract text.
    """
    try:
        global text_summary
        temp_file_path = f"src/pdf_{uuid.uuid4()}.pdf"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        extracted_text = text_processor.extract_text_from_pdf(temp_file_path)

        os.remove(temp_file_path)

        text_summary = text_processor.summarise(extracted_text)
        return {"summary": text_summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

active_users = {}


async def endpoint_user(user_id, user_message,  websocket : WebSocket):

    user_tts_queue = queue.Queue()
    user_output_queue = queue.Queue()
    handleUser = HandelUser()
    conversation_stage = 0
    
    
    while True:
        print("user called ")
        end_of_query_a = False
        end_of_query_b = False
        user_input = user_message
        conversation_history = get_chat_history(user_id)
        store_chat_history(user_id, "User", user_input, conversation_stage)
        conversation_history = get_chat_history(user_id)
        await handleUser.generate_agent_response(conversation_history, conversation_stage, user_output_queue, pdf_content = text_summary)
        alex_output, conversation_stage, emma_output = user_output_queue.get()
        
        
        if alex_output.endswith("[end_of_query]"):
            end_of_query_a = True
            alex_output = alex_output.removesuffix("[end_of_query]").rstrip()
            print(alex_output) 
             
        if emma_output.endswith("[end_of_query]"):
            end_of_query_b = True
            emma_output = emma_output.removesuffix("[end_of_query]").rstrip()
            print(emma_output)  
       
        # Store history per user
        store_chat_history(user_id, "Alex", alex_output, conversation_stage)
        store_chat_history(user_id, "Emma", emma_output, conversation_stage)
        # Generate text-to-speech for both responses
        alex_tts_task = asyncio.create_task(handleUser.generate_tts(text = alex_output, gender= "male", output_queue=user_tts_queue) )
        
        
        await alex_tts_task
        file_path_male = user_tts_queue.get()
        print(alex_output)
        await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})
        emma_tts_task = asyncio.create_task(handleUser.generate_tts(text = emma_output, gender= "female", output_queue=user_tts_queue) )

        print("alex done")
        await emma_tts_task
        response = await websocket.receive_json()
        print(response)
        
        if response['message'] == "chunks":
            await process_audio_stream(websocket) 
            print("audio procesing ended")# Process audio properly
                # await websocket.send_json({"FINAL": final_text})
            response1 = await websocket.receive_json()
            print(response1)
            if response1['message'] == "Yes":
                print(response1['input'])
                await endpoint_user(user_id, response1['input'], websocket)
                print("Loop ended")
                break
        
        if end_of_query_a == True:
            break

        file_path_female = user_tts_queue.get()
        await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})
        print(emma_output)
        response = await websocket.receive_json()
        print(response)
        
        if response['message'] == "chunks":
         
            await process_audio_stream(websocket) 
            print("audio procesing ended")# Process audio properly
                # await websocket.send_json({"FINAL": final_text})
            response1 = await websocket.receive_json()
            print(response1)
            if response1['message'] == "Yes":
                print(response1['input'])
                await endpoint_user(user_id, response1['input'], websocket)
                print("Loop ended")
                break
        
        if end_of_query_b == True:
            break


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = str(uuid.uuid4())  
    active_users[user_id] = websocket  

    podcast_agent = PodcastAgent()
    alex_response_queue = queue.Queue()
    emma_response_queue = queue.Queue()
    alex_tts_queue = queue.Queue()
    emma_tts_queue = queue.Queue()

    try:
        # Generate initial AI response
        await podcast_agent.generate_alex_response("", "1", alex_response_queue, pdf_content=text_summary)
        alex_output, conversation_stage = alex_response_queue.get()
        store_chat_history(user_id, "Alex", alex_output, conversation_stage)
        await podcast_agent.generate_tts(alex_output, "male", alex_tts_queue)

        conversation_history = get_chat_history(user_id)
        await podcast_agent.generate_emma_response(conversation_history, conversation_stage, emma_response_queue, pdf_content=text_summary)
        emma_output, conversation_stage = emma_response_queue.get()
        store_chat_history(user_id, "Emma", emma_output, conversation_stage)
        await podcast_agent.generate_tts(emma_output, "female", emma_tts_queue)

        conversation_history = get_chat_history(user_id)
        await podcast_agent.generate_alex_response(conversation_history, conversation_stage, alex_response_queue, pdf_content=text_summary)
        alex_output, conversation_stage = alex_response_queue.get()
        store_chat_history(user_id, "Alex", alex_output, conversation_stage)
        
        while True:
            conversation_history = get_chat_history(user_id)
            # Play Alex's response
            alex_tts_task = asyncio.create_task(podcast_agent.generate_tts(alex_output, "male", alex_tts_queue))
            emma_task = asyncio.create_task(podcast_agent.generate_emma_response(conversation_history, conversation_stage, emma_response_queue, text_summary))

            file_path_male = alex_tts_queue.get()
            await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})

            await alex_tts_task
            await emma_task

            response = await websocket.receive_json()

            # If user sends "chunks", start audio processing
            if response['message'] == "chunks":
                
                await process_audio_stream(websocket) 
                print("audio procesing ended")# Process audio properly
                # await websocket.send_json({"FINAL": final_text})
                response1 = await websocket.receive_json()
                print(response1)
                if response1['message'] == "Yes":
                    print(response1['input'])
                    await endpoint_user(user_id, response1['input'], websocket)
                    print("Loop ended")

            emma_output, conversation_stage = emma_response_queue.get()
            store_chat_history(user_id, "Emma", emma_output, conversation_stage)

            conversation_history = get_chat_history(user_id)

            # Play Emma's response
            alex_task = asyncio.create_task(podcast_agent.generate_alex_response(conversation_history, conversation_stage, alex_response_queue, text_summary))
            emma_tts_task = asyncio.create_task(podcast_agent.generate_tts(emma_output, "female", emma_tts_queue))

            file_path_female = emma_tts_queue.get()
            await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})

            await emma_tts_task
            await alex_task

            response = await websocket.receive_json()

            if response['message'] == "chunks":
                await process_audio_stream(websocket) 
                print("audio procesing ended")# Process audio properly
                # await websocket.send_json({"FINAL": final_text})
                response1 = await websocket.receive_json()
                print(response1)
                if response1['message'] == "Yes":
                    print(response1['input'])
                    await endpoint_user(user_id, response1['input'], websocket)
                    print("Loop ended")

            alex_output, conversation_stage = alex_response_queue.get()
            store_chat_history(user_id, "Alex", alex_output, conversation_stage)

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        del active_users[user_id]