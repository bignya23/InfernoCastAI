import os
import queue
import pyaudio
from google.cloud import speech

# Set Google API Key (if not already set in environment)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\bigny\OneDrive\Desktop\NeuroSphereAI\New folder\NeuroSphereAI\neurosphere-453417-a13fa049f648.json"

# Audio recording settings
RATE = 16000  # Sample rate
CHUNK = int(RATE / 10)  # 100ms chunks

# Audio Stream Queue
audio_queue = queue.Queue()

def callback(in_data, frame_count, time_info, status):
    """Callback function for PyAudio stream."""
    audio_queue.put(in_data)
    return (None, pyaudio.paContinue)

def transcribe_streaming():
    """Streams microphone audio to Google Cloud Speech-to-Text API in real-time."""
    client = speech.SpeechClient()

    # Configure the speech recognition request
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US"
    )
    
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True  # Enable real-time results
    )

    # Open a microphone stream
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        stream_callback=callback
    )

    print("🎤 Listening... Speak now!")

    # Generator function to yield audio chunks
    def request_generator():
        while True:
            chunk = audio_queue.get()
            if chunk is None:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    # Send audio to Google Cloud
    responses = client.streaming_recognize(streaming_config, request_generator())

    # Process responses
    try:
        for response in responses:
            for result in response.results:
                if result.is_final:
                    print(f"✅ Final Transcript: {result.alternatives[0].transcript}")
                else:
                    print(f"⏳ Interim: {result.alternatives[0].transcript}", end="\r")
    except Exception as e:
        print(f"Error: {e}")

    # Stop stream
    stream.stop_stream()
    stream.close()
    audio.terminate()

# Run real-time speech-to-text
transcribe_streaming()
