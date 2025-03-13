# app.py
import uuid
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from podcast_agent import PodcastAgent  # your podcast file code refactored into a module
from user_handeling_agent import HandelUser    # your user handling file code refactored into a module
from conv_history import get_chat_history, store_chat_history  # assumed to exist

app = FastAPI()

# A simple ConnectionManager to track sessions.
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}  # session_id -> websocket

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        session_id = str(uuid.uuid4())
        self.active_connections[session_id] = websocket
        return session_id

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_message(self, session_id: str, message: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_text(message)

manager = ConnectionManager()

# Create a single instance of each agent/handler.
podcast_agent = PodcastAgent()
user_handler = HandelUser()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # When a client connects, assign a session id.
    session_id = await manager.connect(websocket)
    try:
        # Initialize conversation history for this session.
        conversation_history = ""
        conversation_stage = 0

        # Optionally store that the session has started.
        store_chat_history(user_id=session_id, agent_name="System",
                           agent_response="Session started", agent_conversation_stage=conversation_stage)

        # Preload Alex's initial response.
        alex_response_json = await asyncio.to_thread(
            podcast_agent.podcast_1,
            user_name="",
            pdf_content="",
            current_stage="1",
            conversation_history=conversation_history,
            user_input=""
        )
        alex_parsed = json.loads(alex_response_json)
        alex_output = alex_parsed['agent_output']
        conversation_stage = alex_parsed['conversation_stage']
        store_chat_history(user_id=session_id, agent_name="Alex",
                           agent_response=alex_output, agent_conversation_stage=conversation_stage)
        await manager.send_message(session_id, f"Alex: {alex_output} (Stage: {conversation_stage})")

        # Main loop: wait for user input and respond.
        while True:
            # Receive a message from the client.
            user_input = await websocket.receive_text()
            # Update conversation history with user input.
            conversation_history += f"User: {user_input}\n"
            
            # Use the user-handling agent to generate responses for both agents.
            user_response_json = await asyncio.to_thread(
                user_handler.podcast_1,
                user_name="User",
                pdf_content="",
                current_stage=conversation_stage,
                conversation_history=conversation_history,
                user_input=user_input
            )
            user_parsed = json.loads(user_response_json)
            alex_output = user_parsed['Alex_output']
            emma_output = user_parsed['Emma_output']
            conversation_stage = user_parsed['conversation_stage']
            
            # Update conversation history.
            conversation_history += f"Alex: {alex_output}\nEmma: {emma_output}\n"
            store_chat_history(user_id=session_id, agent_name="Alex",
                               agent_response=alex_output, agent_conversation_stage=conversation_stage)
            store_chat_history(user_id=session_id, agent_name="Emma",
                               agent_response=emma_output, agent_conversation_stage=conversation_stage)
            
            # Send responses back to the client.
            await manager.send_message(session_id, f"Alex: {alex_output} (Stage: {conversation_stage})")
            await manager.send_message(session_id, f"Emma: {emma_output} (Stage: {conversation_stage})")
            
            # (Optional) Trigger TTS generation asynchronously.
            # Instead of playing audio on the server, consider sending back a URL or file path.
            # For example:
            alex_tts_future = asyncio.to_thread(podcast_agent.generate_tts, alex_output, "male", _dummy_queue)
            emma_tts_future = asyncio.to_thread(podcast_agent.generate_tts, emma_output, "female", _dummy_queue)
            # You could wait on these and send the file paths to the client.
            # alex_tts_path = await alex_tts_future
            # emma_tts_path = await emma_tts_future
            # await manager.send_message(session_id, f"TTS paths - Alex: {alex_tts_path}, Emma: {emma_tts_path}")

    except WebSocketDisconnect:
        manager.disconnect(session_id)

# Dummy queue object for TTS; in production you might adjust the TTS generation to return values.
class DummyQueue:
    def put(self, item):
        self.item = item
    def get(self):
        return self.item
_dummy_queue = DummyQueue()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
