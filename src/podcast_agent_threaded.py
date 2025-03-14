from google import genai
from dotenv import load_dotenv
import os
from pydantic import BaseModel,TypeAdapter, Field
from typing import List
from .prompts import STAGES, AGENT_1_PROMPT, AGENT_2_PROMPT, USER_HANDLING_PROMPT, PDF_CONTENT
import json
from .tts import text_to_speech_male, text_to_speech_female, text_to_speech_female_hindi, text_to_speech_male_hindi
import playsound
import threading
import queue
from .conv_history import get_chat_history, store_chat_history
import uuid
# from summary import summary_generator
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class PodcastAgent:
    class Agent(BaseModel):
        conversation_stage : int = Field(description="Stage of the conversation")
        agent_output : str = Field(description="Current output of agent")

    def podcast_1(self, user_name : str = "", pdf_content : str = "", current_stage : int = "", conversation_history : str = "", user_input : str = ""):
        prompt_template = AGENT_1_PROMPT.format(
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


    def podcast_2(self, user_name = "", pdf_content : str = "", current_stage : int = "", conversation_history : str = "", user_input : str = ""):
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
                'response_schema': self.Agent,
            },
        )

        return response.text



    def generate_alex_response(self, conversation_history, conversation_stage, output_queue, pdf_content):
        alex = json.loads(self.podcast_1(pdf_content=pdf_content, conversation_history=conversation_history, current_stage=conversation_stage))
        output_queue.put((alex['agent_output'], alex['conversation_stage']))
        print(f"{alex['agent_output']}, {alex['conversation_stage']}")


    def generate_emma_response(self, conversation_history, conversation_stage, output_queue, pdf_content):
        emma = json.loads(self.podcast_2(pdf_content=pdf_content, conversation_history=conversation_history, current_stage=conversation_stage))
        output_queue.put((emma['agent_output'], emma['conversation_stage']))
        print(f"{emma['agent_output']}, {emma['conversation_stage']}")

    def generate_tts(self, text, gender, output_queue):
        if gender == "male":
            file_path = text_to_speech_male_hindi(text)
        else:
            file_path = text_to_speech_female_hindi(text)
        output_queue.put(file_path)


if __name__ == "__main__":    
    alex_response_queue = queue.Queue()
    emma_response_queue = queue.Queue()
    alex_tts_queue = queue.Queue()
    emma_tts_queue = queue.Queue()
    
    podcast_agent = PodcastAgent()
    id = uuid.uuid4()
    conversation_history = get_chat_history(user_id=id)

    # Preload Alex's first response & TTS
    podcast_agent.generate_alex_response("", "1", alex_response_queue)
    alex_output, conversation_stage = alex_response_queue.get()
    store_chat_history(user_id=id, agent_name="Alex", agent_response= alex_output, agent_conversation_stage=conversation_stage)
    print(f"Alex : {alex_output} Stage : {conversation_stage}")
    podcast_agent.generate_tts(alex_output, "male", alex_tts_queue)

    # Preload Emma's first response & TTS
    conversation_history = get_chat_history(user_id=id)
    # print(conversation_history)

    podcast_agent.generate_emma_response(conversation_history, conversation_stage, emma_response_queue)
    emma_output, conversation_stage = emma_response_queue.get()
    store_chat_history(user_id=id, agent_name="Emma", agent_response= emma_output, agent_conversation_stage=conversation_stage)
    print(f"Emma : {emma_output} Stage : {conversation_stage}")
    podcast_agent.generate_tts(emma_output, "female", emma_tts_queue)

    # Generates Alex next response
    conversation_history = get_chat_history(user_id=id)
    # print(conversation_history)
    podcast_agent.generate_alex_response(conversation_history=conversation_history, conversation_stage=conversation_stage, output_queue=alex_response_queue)
    alex_output, conversation_stage = alex_response_queue.get()
    conversation_history = store_chat_history(user_id=id, agent_name="Alex", agent_response= alex_output, agent_conversation_stage=conversation_stage)


    while True:
        # Start Playing the Alex response in queue and generate the emma response and also alex next reaponse tts
        conversation_history = get_chat_history(user_id=id)

        alex_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(alex_output, "male", alex_tts_queue))
        emma_thread = threading.Thread(target=podcast_agent.generate_emma_response, args=(conversation_history, conversation_stage, emma_response_queue))

        alex_tts_thread.start()
        emma_thread.start()

        file_path_male = alex_tts_queue.get()

        print(f"Alex: {alex_output} Stage : {conversation_stage}")
        playsound.playsound(file_path_male)

        alex_tts_thread.join()
        emma_thread.join()
        emma_output, conversation_stage = emma_response_queue.get()
        store_chat_history(user_id=id, agent_name="Emma", agent_response= emma_output, agent_conversation_stage=conversation_stage)

        # Start Playing the Emma response in queue and generate the Alex response and also emma next reaponse tts
        conversation_history = get_chat_history(user_id=id)

        alex_thread = threading.Thread(target=podcast_agent.generate_alex_response, args=(conversation_history, conversation_stage, alex_response_queue))
        emma_tts_thread = threading.Thread(target=podcast_agent.generate_tts, args=(emma_output, "female", emma_tts_queue))

        alex_thread.start()
        emma_tts_thread.start()

        file_path_female = emma_tts_queue.get()

        print(f"Emma: {emma_output} Stage : {conversation_stage}")
        playsound.playsound(file_path_female)

        emma_tts_thread.join()
        alex_thread.join()
        alex_output, conversation_stage = alex_response_queue.get()
        store_chat_history(user_id=id, agent_name="Alex", agent_response= alex_output, agent_conversation_stage=conversation_stage)

        print("\n\n")
