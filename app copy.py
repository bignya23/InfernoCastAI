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



import asyncio
import base64
# Audio recording settings
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms chunks

# Initialize WebRTC VAD for silence detection
vad = webrtcvad.Vad()
vad.set_mode(1)  # 1 = low aggressiveness, 3 = high aggressiveness

def is_speech(audio_chunk):
    """Check if the given audio chunk contains speech."""
    return vad.is_speech(audio_chunk, RATE)

async def websocket_endpoint_audio(websocket : WebSocket):
    """Receives audio chunks via WebSocket, processes them, and returns the final transcript after silence detection."""
    print("AUdio")
    client = speech.SpeechClient()
    
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US"
    )
    
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True
    )
    
    audio_queue = queue.Queue()
    silent_chunks = 0
    max_silence_chunks = 10  # Threshold for silence detection
    is_speaking = False
    
    async def request_generator():
        nonlocal is_speaking, silent_chunks
        while True:
            audio_chunk = await websocket.receive()
            
            if is_speech(audio_chunk):
                silent_chunks = 0
                is_speaking = True
                audio_queue.put(audio_chunk)
            else:
                silent_chunks += 1
            
            if silent_chunks > max_silence_chunks and is_speaking:
                print("Detected silence. Ending transcription.")
                break
            
            yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)
    
    responses = client.streaming_recognize(streaming_config, request_generator())
    
    try:
        final_transcript = ""
        async for response in responses:
            for result in response.results:
                if result.is_final:
                    final_transcript += result.alternatives[0].transcript + " "
        
        await websocket.send(final_transcript.strip()) # Send final transcription to frontend
    except Exception as e:
        print(f"Error: {e}")
        await websocket.send("Error occurred during transcription.")



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
        user_input = user_message
        conversation_history = get_chat_history(user_id)
        store_chat_history(user_id, "User", user_input, conversation_stage)
        conversation_history = get_chat_history(user_id)
        await handleUser.generate_agent_response(conversation_history, conversation_stage, user_output_queue, pdf_content = text_summary)
        alex_output, conversation_stage, emma_output = user_output_queue.get()
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
        await websocket.receive_json()

        file_path_female = user_tts_queue.get()
        await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})
        print(emma_output)
        await websocket.receive_json()

        if emma_output.endswith("[end_of_query]"):
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
        # Generate initial response
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


        while True:
            conversation_history = get_chat_history(user_id)

            # Generate and play Alex's response
            alex_tts_task = asyncio.create_task(podcast_agent.generate_tts(alex_output, "male", alex_tts_queue))
            emma_task = asyncio.create_task(podcast_agent.generate_emma_response(conversation_history, conversation_stage, emma_response_queue, text_summary))

            file_path_male = alex_tts_queue.get()
            await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})

            await alex_tts_task
            await emma_task

            response = await websocket.receive_json()
            if(response['message'] == "chunks"):
                await websocket_endpoint_audio(websocket)
                response = await websocket.receive_json()
                print(response)
                if response['message'] == "Yes":
                    await endpoint_user(user_id, response["input"], websocket)
                    print("loop ended")


            emma_output, conversation_stage = emma_response_queue.get()
            store_chat_history(user_id, "Emma", emma_output, conversation_stage)

            # Generate and play Emma's response
            alex_task = asyncio.create_task(podcast_agent.generate_alex_response(conversation_history, conversation_stage, alex_response_queue, text_summary))
            emma_tts_task = asyncio.create_task(podcast_agent.generate_tts(emma_output, "female", emma_tts_queue))

            file_path_female = emma_tts_queue.get()
            await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})

            await emma_tts_task
            await alex_task

            response = await websocket.receive_json()
            print(response)

            
            if(response['message'] == "chunks"):
                await websocket_endpoint_audio(websocket)
                response = await websocket.receive_json()
                print(response)
            # str_response = json.loads(response)
                if response['message'] == "Yes":
                    await endpoint_user(user_id, websocket)
                    print("loop ended")

            alex_output, conversation_stage = alex_response_queue.get()
            store_chat_history(user_id, "Alex", alex_output, conversation_stage)

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        del active_users[user_id]