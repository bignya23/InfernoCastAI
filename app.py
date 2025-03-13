from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import json
import uuid
import queue
import threading
from src.conv_history import store_chat_history, get_chat_history
from src.podcast_agent_threaded import PodcastAgent
from src.user_handeling_agent import HandelUser
from src.prompts import PDF_CONTENT

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello World"}

# Store active WebSocket connections
active_users = {}

@app.websocket("/ws_user")
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

    user_id = str(uuid.uuid4())  # Generate a unique user_id for each connection
    active_users[user_id] = websocket  # Store WebSocket connection

    podcast_agent = PodcastAgent()
    alex_response_queue = queue.Queue()
    emma_response_queue = queue.Queue()
    alex_tts_queue = queue.Queue()
    emma_tts_queue = queue.Queue()

    try:
        # Initial conversation setup
        podcast_agent.generate_alex_response("", "1", alex_response_queue)
        alex_output, conversation_stage = alex_response_queue.get()
        store_chat_history(user_id, "Alex", alex_output, conversation_stage)
        podcast_agent.generate_tts(alex_output, "male", alex_tts_queue)

        conversation_history = get_chat_history(user_id)
        podcast_agent.generate_emma_response(conversation_history, conversation_stage, emma_response_queue)
        emma_output, conversation_stage = emma_response_queue.get()
        store_chat_history(user_id, "Emma", emma_output, conversation_stage)
        podcast_agent.generate_tts(emma_output, "female", emma_tts_queue)

        conversation_history = get_chat_history(user_id)
        podcast_agent.generate_alex_response(conversation_history, conversation_stage, alex_response_queue)

        while True:
            conversation_history = get_chat_history(user_id)

            # Generate and play Alex's response
            alex_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(alex_output, "male", alex_tts_queue))
            emma_thread = threading.Thread(target=podcast_agent.generate_emma_response, args=(conversation_history, conversation_stage, emma_response_queue))

            alex_tts_thread.start()
            emma_thread.start()

            file_path_male = alex_tts_queue.get()
            await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})

            alex_tts_thread.join()
            emma_thread.join()

            await websocket.receive_json()

            emma_output, conversation_stage = emma_response_queue.get()
            store_chat_history(user_id, "Emma", emma_output, conversation_stage)

            # Generate and play Emma's response
            alex_thread = threading.Thread(target=podcast_agent.generate_alex_response, args=(conversation_history, conversation_stage, alex_response_queue))
            emma_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(emma_output, "female", emma_tts_queue))

            alex_thread.start()
            emma_tts_thread.start()

            file_path_female = emma_tts_queue.get()
            await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})

            emma_tts_thread.join()
            alex_thread.join()

            await websocket.receive_json()

            alex_output, conversation_stage = alex_response_queue.get()
            store_chat_history(user_id, "Alex", alex_output, conversation_stage)

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        del active_users[user_id] 
