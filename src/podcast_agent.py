from google import genai
from dotenv import load_dotenv
import os
from pydantic import BaseModel,TypeAdapter, Field
from typing import List
from prompts import STAGES, AGENT_1_PROMPT, AGENT_2_PROMPT, USER_HANDLING_PROMPT, PDF_CONTENT
import json
from tts import text_to_speech_male, text_to_speech_female
import playsound
from src.text_processing import summary_generator
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class Agent(BaseModel):
    conversation_stage : int = Field(description="Stage of the conversation")
    agent_output : str = Field(description="Current output of agent")

def podcast_1(user_name : str = "", pdf_content : str = "", current_stage : int = "", conversation_history : str = "", user_input : str = ""):
    prompt_template = AGENT_1_PROMPT.format(
        conversation_history=conversation_history,
        current_stage=current_stage,
        user_input=user_input,
        pdf_content=pdf_content,
        stages=STAGES,
        user_name=user_name)


    # print(prompt_template)

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt_template,
        config={
            'response_mime_type': 'application/json',
            'response_schema': Agent,
        },
    )

    return response.text


def podcast_2(user_name = "", pdf_content : str = "", current_stage : int = "", conversation_history : str = "", user_input : str = ""):
    prompt_template = AGENT_2_PROMPT.format(
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
            'response_schema': Agent,
        },
    )

    return response.text



if __name__ == "__main__":
    conversation_history = ""
    conversation_stage = 1
    cnt = 0
    # summary = summary_generator()
    # print(summary)
    while True:
        alex = json.loads(podcast_1(pdf_content=PDF_CONTENT, conversation_history=conversation_history, current_stage=conversation_stage))
        conversation_history += f"Alex: {alex['agent_output']}"
        conversation_stage = alex['conversation_stage']
        print(f"Alex: {alex['agent_output']}")
        print(conversation_stage)
        file_path_male = text_to_speech_male(alex['agent_output'])
        playsound.playsound(sound=file_path_male)
        print("\n\n")
        emma = json.loads(podcast_2(pdf_content=PDF_CONTENT, conversation_history=conversation_history, current_stage=conversation_stage))
        conversation_history += f"Emma: {emma['agent_output']}"
        conversation_stage = emma['conversation_stage']
        print(f"Emma: {emma['agent_output']}")
        print(conversation_stage)
        file_path_female = text_to_speech_female(emma['agent_output'])
        playsound.playsound(sound=file_path_female)
        print("\n\n")



