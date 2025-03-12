import vertexai
from vertexai.language_models import TextGenerationModel
from extract import extract_text_from_pdf 

PROJECT_ID = "neurosphere-453417"

def generate_summary(project_id, text):
    """Generates a summary using Vertex AI's text generation model."""
    
    vertexai.init(project=project_id, location="us-central1")

    parameters = {
        "temperature": 0,
        "max_output_tokens": 256,
        "top_p": 0.95,
        "top_k": 40,
    }

    model = TextGenerationModel.from_pretrained("text-bison@002")
    response = model.predict(text, **parameters)  # Pass text correctly

    print(f"Response from Model: {response.text}")
    return response.text  # Return summary for further use

def summary_generator():
    extracted_text = extract_text_from_pdf()

    # if extracted_text.strip():  # Ensure extracted text is not empty
    #     summary = generate_summary(PROJECT_ID, extracted_text)
    # else:
    #     print("No text extracted from the PDF.")

    return extracted_text

if __name__ == "__main__":
    print(summary_generator())

