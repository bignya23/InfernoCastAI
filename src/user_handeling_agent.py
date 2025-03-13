from prompts import USER_HANDLING_PROMPT, STAGES, PDF_CONTENT
from google import genai
from dotenv import load_dotenv
import os
from pydantic import BaseModel,TypeAdapter, Field
from typing import List
import json
import playsound
import threading
from tts import text_to_speech_male, text_to_speech_female, text_to_speech_female_hindi, text_to_speech_male_hindi
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

``
if __name__ == "__main__":
    conversation_history = ""
    conversation_stage = 0
    user_input = ""

    user_input = input("User : ")
    conversation_history += f"User: {user_input}"
    handleUser = HandelUser()
    queue = queue.Queue()
    alex = json.loads(handleUser.podcast_1(pdf_content=PDF_CONTENT, conversation_history=conversation_history,current_stage=conversation_stage, user_input=user_input, user_name="John"))
    conversation_history += f"Alex: {alex['Alex_output']}"
    conversation_stage = alex['conversation_stage']


    thread = threading.Thread(target=handleUser.generate_tts, args=(f"{alex["Emma_output"]}", "female", queue))
    print(f"Alex: {alex['Alex_output']}")
    print(f"emma: {alex['Emma_output']}")
    file_path_male = text_to_speech_male_hindi(alex['Alex_output'])
    thread.start()
    print(conversation_stage)
    playsound.playsound(sound=file_path_male)
    print("\n\n")
    
    thread.join()
    file_path_female = queue.get()
    playsound.playsound(sound=file_path_female)
    print("\n\n")
    
    
    # emma = json.loads(podcast_1(pdf_content=PDF_CONTENT, conversation_history=conversation_history,current_stage=conversation_stage, user_input=user_input, user_name="John"))
    # conversation_history += f"Emma: {emma['agent_output']}"
    # conversation_stage = emma['conversation_stage']
    # print(f"Emma: {emma['agent_output']}")
    # print(conversation_stage)
    # file_path_female = text_to_speech_female_hindi(emma['agent_output'])
    # playsound.playsound(sound=file_path_female)
    # print("\n\n")
    
    
    