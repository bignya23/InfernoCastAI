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

app = FastAPI()

text_summary = ""
text_processor = TextProcessing()


@app.get("/")
async def root():
    return {"message": "Hello World"}


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
    

# Store active WebSocket connections
active_users = {}

@app.websocket("/ws-user")
async def websocket_endpoint_user(websocket: WebSocket):
    await websocket.accept()

    # Generate a unique user_id for this session
    user_id = str(uuid.uuid4())
    active_users[user_id] = websocket  # Store the user's connection

    user_tts_queue = queue.Queue()
    user_output_queue = queue.Queue()
    handleUser = HandelUser()
    conversation_stage = 0
    
    try:
        while True:
            user_input = await websocket.receive_text()  # Receive user input via WebSocket
            conversation_history = get_chat_history(user_id)

            handleUser.generate_agent_response(conversation_history, conversation_stage, user_output_queue)
            alex_output, conversation_stage, emma_output = user_output_queue.get()

            # Store history per user
            store_chat_history(user_id, "User", user_input, conversation_stage)
            store_chat_history(user_id, "Alex", alex_output, conversation_stage)
            store_chat_history(user_id, "Emma", emma_output, conversation_stage)

            # Generate text-to-speech for both responses
            alex_tts_thread = threading.Thread(target=handleUser.generate_tts, args=(alex_output, "male", user_tts_queue))
            emma_tts_thread = threading.Thread(target=handleUser.generate_tts, args=(emma_output, "female", user_tts_queue))

            alex_tts_thread.start()
            emma_tts_thread.start()

            alex_tts_thread.join()
            file_path_male = user_tts_queue.get()

            await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})

            emma_tts_thread.join()
            file_path_female = user_tts_queue.get()
            await websocket.receive_json()

            await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        del active_users[user_id]  



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
        
        podcast_agent.generate_alex_response("", "1", alex_response_queue, pdf_content=text_summary)
        alex_output, conversation_stage = alex_response_queue.get()
        store_chat_history(user_id, "Alex", alex_output, conversation_stage)
        await podcast_agent.generate_tts(alex_output, "male", alex_tts_queue)

        conversation_history = get_chat_history(user_id)
        podcast_agent.generate_emma_response(conversation_history, conversation_stage, emma_response_queue, pdf_content=text_summary)
        emma_output, conversation_stage = emma_response_queue.get()
        store_chat_history(user_id, "Emma", emma_output, conversation_stage)
        await podcast_agent.generate_tts(emma_output, "female", emma_tts_queue)

        conversation_history = get_chat_history(user_id)
        podcast_agent.generate_alex_response(conversation_history, conversation_stage, alex_response_queue, pdf_content=text_summary)

        while True:
            print("after")
            conversation_history = get_chat_history(user_id)

            # Generate and play Alex's response
            alex_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(alex_output, "male", alex_tts_queue))
            emma_thread = threading.Thread(target=podcast_agent.generate_emma_response, args=(conversation_history, conversation_stage, emma_response_queue, text_summary))

            alex_tts_thread.start()
            emma_thread.start()

            file_path_male = alex_tts_queue.get()
            await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})

            alex_tts_thread.join()
            emma_thread.join()

            await websocket.receive_json()
            print("first response 2")


            emma_output, conversation_stage = await emma_response_queue.get()
            store_chat_history(user_id, "Emma", emma_output, conversation_stage)

            # Generate and play Emma's response
            alex_thread = threading.Thread(target=podcast_agent.generate_alex_response, args=(conversation_history, conversation_stage, alex_response_queue, text_summary))
            emma_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(emma_output, "female", emma_tts_queue))

            alex_thread.start()
            emma_tts_thread.start()

            file_path_female = emma_tts_queue.get()
            await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})

            emma_tts_thread.join()
            alex_thread.join()

            await websocket.receive_json()
            print("second response 2")


            alex_output, conversation_stage = await alex_response_queue.get()
            store_chat_history(user_id, "Alex", alex_output, conversation_stage)

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        del active_users[user_id]