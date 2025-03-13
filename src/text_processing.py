from google import genai
import os
from google.api_core.client_options import ClientOptions
from google.cloud import documentai


PROJECT_ID = "neurosphere-453417"
LOCATION = "us"
PROCESSOR_ID = "9b0aee16552bdce0"
mime_type = "application/pdf"

class TextProcessing:
    def __init__(self):
        pass

    def extract_text_from_pdf(self, file_path):
        """Extracts text from a PDF using Google Document AI."""
        
        # Instantiate a Document AI client
        docai_client = documentai.DocumentProcessorServiceClient(
            client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
        )

        # Define the full resource name of the processor
        resource_name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

        # Read the file into memory
        with open(file_path, "rb") as file:
            image_content = file.read()

        # Load Binary Data into Document AI RawDocument Object
        raw_document = documentai.RawDocument(content=image_content, mime_type=mime_type)

        # Configure the process request
        request = documentai.ProcessRequest(name=resource_name, raw_document=raw_document)

        # Process the document
        result = docai_client.process_document(request=request)
        document_object = result.document

        # Return extracted text
        return document_object.text if document_object.text else "No text extracted."


    def summarise(self, text):
        api_key = os.getenv("GEMINI_API_KEY")  
        if not api_key:
            raise ValueError("API key not found. Set the GOOGLE_GENAI_API_KEY environment variable.")

        client = genai.Client(api_key=api_key)

        prompt = f"""
        Summarize the following text in depth don't remove details and make points if possible. 
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

    # def process_input(self, input_data):
    #     """
    #     Determines whether the input is a PDF file or plain text and processes accordingly.
    #     """
    #     if os.path.isfile(input_data) and input_data.endswith(".pdf"):
    #         print("Detected PDF file. Extracting text...")
    #         text = self.extract_text_from_pdf(input_data)
    #     else:
    #         print("Detected plain text input.")
    #         text = input_data  

    #     return self.summarise(text)


if __name__ == "__main__":


    file_path = ""
    text_processor = TextProcessing()
    summary = text_processor.process_input(file_path)
    
    print("\nSummarized Content:\n")
    print(summary)
