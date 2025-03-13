from .prompts import USER_HANDLING_PROMPT, STAGES, PDF_CONTENT
from google import genai
from dotenv import load_dotenv
import os
from pydantic import BaseModel,TypeAdapter, Field
from typing import List
import json
import playsound
import threading
from .tts import text_to_speech_male, text_to_speech_female, text_to_speech_female_hindi, text_to_speech_male_hindi
from .conv_history import get_chat_history, store_chat_history
# from summary import summary_generator
load_dotenv()
import queue

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class HandelUser:
    def __init__(self):
        pass


    class Agent(BaseModel):
        conversation_stage : int = Field(description="Stage of the conversation")
        Alex_output : str = Field(description="Current output of agent")
        Emma_output : str = Field(description="Current output of agent")


    def podcast_1(self, user_name : str = "", pdf_content : str = "", current_stage : int = "", conversation_history : str = "", user_input : str = ""):
        prompt_template = USER_HANDLING_PROMPT.format(
            conversation_history=conversation_history,
            current_stage=current_stage,
            user_input=user_input,
            pdf_content=pdf_content,
            stages=STAGES,
            user_name=user_name)


        # print(prompt_template)

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt_template,
            config={
                'response_mime_type': 'application/json',
                'response_schema': self.Agent,
            },
        )

        return response.text


    def generate_tts(self, text, gender, output_queue):
        if gender == "male":
            file_path = text_to_speech_male_hindi(text)
        else:
            file_path = text_to_speech_female_hindi(text)
        output_queue.put(file_path)

    def generate_agent_response(self, conversation_history, conversation_stage, output_queue):
        agent_output = json.loads(self.podcast_1(pdf_content=PDF_CONTENT, conversation_history=conversation_history, current_stage=conversation_stage))
        output_queue.put((agent_output['Alex_output'], agent_output['conversation_stage'], agent_output['Emma_output']))

    def generate_tts(self, text, gender, output_queue):
        if gender == "male":
            file_path = text_to_speech_male_hindi(text)
        else:
            file_path = text_to_speech_female_hindi(text)
        output_queue.put(file_path)

if __name__ == "__main__":
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
        playsound.playsound(sound=file_path_male)
        print("\n\n")
        
        thread.join()
        file_path_female = user_tts_queue.get()
        playsound.playsound(sound=file_path_female)
        print("\n\n")
        
        
        
        
        