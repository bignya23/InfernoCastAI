from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
import asyncio
import json
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
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import speech
import webrtcvad
from typing import List, Dict, Any, Optional

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


# Audio settings
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

# Voice Activity Detector
vad = webrtcvad.Vad(2)  # 0 (aggressive) to 3 (sensitive)

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

@app.websocket("/ws")
async def unified_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection established")
    
    user_id = str(uuid.uuid4())  
    active_users[user_id] = websocket  

    # Initialize agents
    podcast_agent = PodcastAgent()
    handleUser = HandelUser()
    
    # Initialize queues
    alex_response_queue = queue.Queue()
    emma_response_queue = queue.Queue()
    alex_tts_queue = queue.Queue()
    emma_tts_queue = queue.Queue()
    user_tts_queue = queue.Queue()
    user_output_queue = queue.Queue()
    audio_queue = queue.Queue()
    
    # Speech recognition setup
    speech_client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="hi-IN"
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)
    
    # Variables for audio processing
    silence_counter = 0
    speaking = False
    buffer: List[bytes] = []
    audio_processing_active = False
    speech_processing_task = None
    conversation_stage = 0
    user_interaction_mode = False
    
    async def process_audio_stream():
        nonlocal audio_processing_active
        nonlocal speech_processing_task
        
        async def request_generator():
            while audio_processing_active:
                try:
                    chunk = audio_queue.get(timeout=1)
                    if chunk is None:
                        break
                    yield speech.StreamingRecognizeRequest(audio_content=chunk)
                except queue.Empty:
                    continue
        
        responses = speech_client.streaming_recognize(streaming_config, request_generator())
        
        final_transcription = ""
        try:
            for response in responses:
                if not audio_processing_active:
                    break
                for result in response.results:
                    if result.is_final:
                        final_transcription += result.alternatives[0].transcript + " "
                    await websocket.send_json({
                        "type": "transcription", 
                        "text": result.alternatives[0].transcript,
                        "is_final": result.is_final
                    })
        except Exception as e:
            print(f"Error processing audio response: {e}")
        
        audio_processing_active = False
        return final_transcription.strip()
    
    async def handle_audio_message(data: bytes):
        nonlocal silence_counter, speaking, audio_processing_active, speech_processing_task
        
        buffer.append(data)
        audio_queue.put(data)
        
        # Start speech processing task if not already running
        if not audio_processing_active:
            audio_processing_active = True
            speech_processing_task = asyncio.create_task(process_audio_stream())

        # Silence detection
        is_speech = vad.is_speech(data, RATE)
        if is_speech:
            speaking = True
            silence_counter = 0
        elif speaking:
            silence_counter += 1
            if silence_counter > 20:  # 2 seconds (20 * 100ms)
                print("Silence detected, ending stream...")
                audio_queue.put(None)
                audio_processing_active = False
                final_text = await speech_processing_task
                
                # Clear queue
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                    except queue.Empty:
                        break
                
                buffer.clear()
                await websocket.send_json({
                    "type": "transcription_complete",
                    "text": final_text
                })
                
                if user_interaction_mode:
                    # Process user input in user interaction mode
                    await process_user_input(final_text)
                
                return final_text
        
        return None
    
    async def process_user_input(user_input: str):
        nonlocal conversation_stage
        
        conversation_history = get_chat_history(user_id)
        store_chat_history(user_id, "User", user_input, conversation_stage)
        conversation_history = get_chat_history(user_id)
        
        await handleUser.generate_agent_response(
            conversation_history, 
            conversation_stage, 
            user_output_queue, 
            pdf_content=text_summary
        )
        
        alex_output, conversation_stage, emma_output = user_output_queue.get()
        
        # Store history per user
        store_chat_history(user_id, "Alex", alex_output, conversation_stage)
        store_chat_history(user_id, "Emma", emma_output, conversation_stage)
        
        # Generate and send Alex's response
        alex_tts_task = asyncio.create_task(
            handleUser.generate_tts(text=alex_output, gender="male", output_queue=user_tts_queue)
        )
        await alex_tts_task
        
        file_path_male = user_tts_queue.get()
        await websocket.send_json({
            "type": "agent_response",
            "speaker": "Alex", 
            "text": alex_output, 
            "audio": file_path_male, 
            "stage": conversation_stage
        })
        
        # Wait for client acknowledgment
        await wait_for_client_ready()
        
        # Generate and send Emma's response
        emma_tts_task = asyncio.create_task(
            handleUser.generate_tts(text=emma_output, gender="female", output_queue=user_tts_queue)
        )
        await emma_tts_task
        
        file_path_female = user_tts_queue.get()
        await websocket.send_json({
            "type": "agent_response",
            "speaker": "Emma", 
            "text": emma_output, 
            "audio": file_path_female, 
            "stage": conversation_stage
        })
        
        # Wait for client acknowledgment
        await wait_for_client_ready()
        
        return emma_output.endswith("[end_of_query]")
    
    async def wait_for_client_ready():
        response = await websocket.receive_json()
        return response.get('ready', False)
    
    async def start_podcast_mode():
    
        # Start the podcast conversation loop
        while True:
            conversation_history = get_chat_history(user_id)
            
            # Generate and play Alex's response
            alex_tts_task = asyncio.create_task(
                podcast_agent.generate_tts(alex_output, "male", alex_tts_queue)
            )
            emma_task = asyncio.create_task(
                podcast_agent.generate_emma_response(
                    conversation_history, conversation_stage, emma_response_queue, text_summary
                )
            )
            
            file_path_male = alex_tts_queue.get()
            await websocket.send_json({
                "type": "agent_response",
                "speaker": "Alex", 
                "text": alex_output, 
                "audio": file_path_male, 
                "stage": conversation_stage
            })
            
            await alex_tts_task
            await emma_task
            
            # Wait for client acknowledgment
            response = await websocket.receive_json()
            message_type = response.get('type', '')
            
            if message_type == 'audio_chunk':
                # Handle audio data during podcast mode
                nonlocal user_interaction_mode
                user_interaction_mode = True
                return  # Exit podcast mode, will handle audio in the main loop
            
            if response.get('message') == "Yes":
                # Switch to user interaction mode
                nonlocal user_interaction_mode
                user_interaction_mode = True
                return  # Exit podcast mode
            
            # Continue with podcast mode
            emma_output, conversation_stage = emma_response_queue.get()
            store_chat_history(user_id, "Emma", emma_output, conversation_stage)
            
            # Generate and play Emma's response
            alex_task = asyncio.create_task(
                podcast_agent.generate_alex_response(
                    conversation_history, conversation_stage, alex_response_queue, text_summary
                )
            )
            emma_tts_task = asyncio.create_task(
                podcast_agent.generate_tts(emma_output, "female", emma_tts_queue)
            )
            
            file_path_female = emma_tts_queue.get()
            await websocket.send_json({
                "type": "agent_response",
                "speaker": "Emma", 
                "text": emma_output, 
                "audio": file_path_female, 
                "stage": conversation_stage
            })
            
            await emma_tts_task
            await alex_task
            
            # Wait for client acknowledgment
            response = await websocket.receive_json()
            message_type = response.get('type', '')
            
            if message_type == 'audio_chunk':
                # Handle audio data during podcast mode
                nonlocal user_interaction_mode
                user_interaction_mode = True
                return  # Exit podcast mode, will handle audio in the main loop
                
            if response.get('message') == "Yes":
                # Switch to user interaction mode
                nonlocal user_interaction_mode
                user_interaction_mode = True
                return  # Exit podcast mode
            
            # Get Alex's next response for the loop
            alex_output, conversation_stage = alex_response_queue.get()
            store_chat_history(user_id, "Alex", alex_output, conversation_stage)
    
    try:
                # Generate initial response
        await podcast_agent.generate_alex_response(
            "", "1", alex_response_queue, pdf_content=text_summary
        )
        alex_output, conversation_stage = alex_response_queue.get()
        store_chat_history(user_id, "Alex", alex_output, conversation_stage)
        
        # Generate Emma's initial response
        conversation_history = get_chat_history(user_id)
        await podcast_agent.generate_emma_response(
            conversation_history, conversation_stage, emma_response_queue, pdf_content=text_summary
        )
        emma_output, conversation_stage = emma_response_queue.get()
        store_chat_history(user_id, "Emma", emma_output, conversation_stage)
        
        # Queue up Alex's next response
        conversation_history = get_chat_history(user_id)
        await podcast_agent.generate_alex_response(
            conversation_history, conversation_stage, alex_response_queue, pdf_content=text_summary
        )
        
        # Start in podcast mode by default
        podcast_task = asyncio.create_task(start_podcast_mode())
        
        # Main message handling loop
        while True:
            if user_interaction_mode:
                # We're now in user interaction mode after exiting podcast mode
                message = await websocket.receive()
                
                if "bytes" in message:
                    # Handle audio data
                    audio_data = message["bytes"]
                    transcription = await handle_audio_message(audio_data)
                    
                    if transcription:  # If we have a complete transcription
                        conversation_end = await process_user_input(transcription)
                        if conversation_end:
                            # Reset to podcast mode if conversation ended
                            user_interaction_mode = False
                            podcast_task = asyncio.create_task(start_podcast_mode())
                
                elif "text" in message:
                    # Handle text/JSON messages
                    try:
                        data = json.loads(message["text"])
                        message_type = data.get("type")
                        
                        if message_type == "text_input":
                            # Direct text input
                            user_input = data.get("content", "")
                            conversation_end = await process_user_input(user_input)
                            if conversation_end:
                                # Reset to podcast mode if conversation ended
                                user_interaction_mode = False
                                podcast_task = asyncio.create_task(start_podcast_mode())
                        
                        elif message_type == "ready":
                            # Client is ready for next message, do nothing here
                            pass
                    
                    except json.JSONDecodeError:
                        print("Received invalid JSON")
            else:
                # Wait for the podcast mode to complete
                await podcast_task
    
    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        if user_id in active_users:
            del active_users[user_id]
    except Exception as e:
        print(f"Error in WebSocket: {e}")
        if user_id in active_users:
            del active_users[user_id]