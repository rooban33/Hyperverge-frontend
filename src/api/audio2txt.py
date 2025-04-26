import os
from urllib.parse import urlparse
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv() 

# Replace this with a secure method (like environment variable) in production
OPENAI_API_KEY = "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"

def audiofile_to_text(filename):
    client = OpenAI(api_key=OPENAI_API_KEY)

    with open(filename, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

    print("Transcribed Text:\n", transcript.text)
    return transcript.text

def get_file_path(block):
    print("Rithya check:", block)
    
    # Extract filename from URL
    audio_filename = os.path.basename(urlparse(block).path)
    
    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
    file_path = os.path.join(uploads_dir, audio_filename)

    if os.path.exists(file_path):
        description = audiofile_to_text(file_path)
        return description
    else:
        print(f"{audio_filename} is missing in uploads.")
        return ""
