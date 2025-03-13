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


# Unique user session ID
user_id = str(uuid.uuid4())


@app.websocket("/ws_user")
async def websocket_endpoint_user(websocket: WebSocket):
    await websocket.accept()
    
    user_tts_queue = queue.Queue()
    user_output_queue = queue.Queue()
    handleUser = HandelUser()
    conversation_stage = 0
    while True:
        user_input = input("User : ")
        conversation_history = get_chat_history(user_id="id")
        handleUser.generate_agent_response(conversation_history, conversation_stage, user_output_queue)
        alex_output, conversation_stage, emma_output = user_output_queue.get()

        store_chat_history(user_id="id", agent_name="user", agent_response=user_input, agent_conversation_stage=conversation_stage)
        store_chat_history(user_id="id", agent_name="Alex", agent_response=alex_output, agent_conversation_stage=conversation_stage)
        store_chat_history(user_id="id", agent_name="Emma", agent_response=emma_output, agent_conversation_stage=conversation_stage)


        thread = threading.Thread(target=handleUser.generate_tts, args=(emma_output, "female", user_tts_queue))
        print(f"Alex: {alex_output}")
        print(f"Emma: {emma_output}")
        
        handleUser.generate_tts(alex_output, "male", user_tts_queue)
        file_path_male = user_tts_queue.get()
        thread.start()
        print(conversation_stage)
        await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})
        print("\n\n")
        
        thread.join()
        file_path_female = user_tts_queue.get()
        await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})
        print("\n\n")
        

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    
    # Create PodcastAgent instance
    podcast_agent = PodcastAgent()
    
    # Queues for managing responses and TTS
    alex_response_queue = queue.Queue()
    emma_response_queue = queue.Queue()
    alex_tts_queue = queue.Queue()
    emma_tts_queue = queue.Queue()

    # Preload Alex's first response & TTS
    podcast_agent.generate_alex_response("", "1", alex_response_queue)
    alex_output, conversation_stage = alex_response_queue.get()
    store_chat_history(user_id, "Alex", alex_output, conversation_stage)
    podcast_agent.generate_tts(alex_output, "male", alex_tts_queue)

    # Preload Emma's first response & TTS
    conversation_history = get_chat_history(user_id)
    podcast_agent.generate_emma_response(conversation_history, conversation_stage, emma_response_queue)
    emma_output, conversation_stage = emma_response_queue.get()
    store_chat_history(user_id, "Emma", emma_output, conversation_stage)
    podcast_agent.generate_tts(emma_output, "female", emma_tts_queue)


    # Preload Alex's next response (for smooth flow)
    conversation_history = get_chat_history(user_id)
    podcast_agent.generate_alex_response(conversation_history, conversation_stage, alex_response_queue)


    while True:
        try:
            conversation_history = get_chat_history(user_id)

            # Play Alex's response while generating Emma's response and Alex's next TTS
            alex_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(alex_output, "male", alex_tts_queue))
            emma_thread = threading.Thread(target=podcast_agent.generate_emma_response, args=(conversation_history, conversation_stage, emma_response_queue))

            alex_tts_thread.start()
            emma_thread.start()

            file_path_male = alex_tts_queue.get()
            await websocket.send_json({"speaker": "Alex", "text": alex_output, "audio": file_path_male, "stage": conversation_stage})

            alex_tts_thread.join()
            emma_thread.join()

            emma_output, conversation_stage = emma_response_queue.get()
            store_chat_history(user_id, "Emma", emma_output, conversation_stage)

            # Play Emma's response while generating Alex's next response and Emma's next TTS
            conversation_history = get_chat_history(user_id)
            alex_thread = threading.Thread(target=podcast_agent.generate_alex_response, args=(conversation_history, conversation_stage, alex_response_queue))
            emma_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(emma_output, "female", emma_tts_queue))

            alex_thread.start()
            emma_tts_thread.start()

            file_path_female = emma_tts_queue.get()
            await websocket.send_json({"speaker": "Emma", "text": emma_output, "audio": file_path_female, "stage": conversation_stage})

            emma_tts_thread.join()
            alex_thread.join()

            alex_output, conversation_stage = alex_response_queue.get()
            store_chat_history(user_id, "Alex", alex_output, conversation_stage)

        except WebSocketDisconnect:
            print(f"User {user_id} disconnected")
            break

