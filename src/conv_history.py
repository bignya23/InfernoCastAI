import redis
import json
from dotenv import load_dotenv
import os

load_dotenv()

# Connect to Redis
redis_client = redis.Redis(
    host='redis-19131.c62.us-east-1-4.ec2.redns.redis-cloud.com',
    port=19131,
    decode_responses=True,
    username="default",
    password=os.getenv("REDIS_DB_PASSWORD")
)

def store_chat_history(user_id, agent_name="Agent", agent_response="", agent_conversation_stage=""):
    """Store last 30 conversations in Redis for a given user."""
    key = f"chat_history:{user_id}"

    conversation_entry = json.dumps({
        "Agent": agent_name,
        "Response": agent_response,
        "Stage": agent_conversation_stage
    })

    redis_client.lpush(key, conversation_entry)
    redis_client.ltrim(key, 0, 30)  # Keep only last 30 messages
    print("Added to Database")

def get_chat_history(user_id):
    """Retrieve the last 10 messages of a user as a single formatted string."""
    key = f"chat_history:{user_id}"
    history = redis_client.lrange(key, 0, 10)  

    # Convert JSON to dictionary and format
    messages = [json.loads(entry) for entry in history]
    messages.reverse()  # Reverse to show in correct order

    # Format messages into a readable string
    formatted_history = "\n".join(
        f"{msg['Agent']}: {msg['Response']} (Stage: {msg['Stage']})" for msg in messages
    )

    return formatted_history

if __name__ == "__main__":

    store_chat_history("user_123", "Hey!", "Hello! How can I help?")

    store_chat_history("user_123", "I'meeldffgaging a little down.", "I'm here for you. Want to talk about it?")

    history = get_chat_history("user_123")

    print("\nRecent Chat History:")
    for conv in history:
        print(f"User: {conv['user']}")
        print(f"Bot: {conv['bot']}")
        print("---")

