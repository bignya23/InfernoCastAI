from extract import extract_text_from_pdf
from google import genai
import os

def summarise():
    text = extract_text_from_pdf() 

    api_key = os.getenv("GEMINI_API_KEY")  
    if not api_key:
        raise ValueError("API key not found. Set the GOOGLE_GENAI_API_KEY environment variable.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Summarize the following text in a clear and concise manner. 
    - Capture the main ideas and key points.
    - Avoid unnecessary details and repetition.
    - Ensure readability and coherence.

    Text:
    {text}
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    return response.text

summary = summarise()
print(summary)
