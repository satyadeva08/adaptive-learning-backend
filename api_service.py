import os
import base64
from google import genai
from dotenv import load_dotenv

# Load .env from the same directory as this file (project root)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(CURRENT_DIR, '.env')

load_dotenv(dotenv_path=ENV_PATH, override=True)
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print(f"CRITICAL ERROR: No API key found! I looked here: {ENV_PATH}")
    client = None
else:
    client = genai.Client(api_key=api_key)
    print("Gemini API Key loaded successfully! ✅")


def get_tutor_response(user_message, history=[], files=[], system_instruction=None):
    try:
        if not client:
            print("Gemini Error: No API client configured (missing API key)")
            return None

        if not system_instruction:
            system_instruction = "You are StudyIQ's expert AI Study Tutor."

        # Build content parts for the current message
        current_parts = [genai.types.Part.from_text(text=user_message)]

        for f in files:
            file_bytes = base64.b64decode(f["data"])
            current_parts.append(
                genai.types.Part.from_bytes(data=file_bytes, mime_type=f["mimeType"])
            )

        # Build conversation history
        contents = []
        for past_msg in history:
            contents.append(
                genai.types.Content(
                    role=past_msg["role"],
                    parts=[genai.types.Part.from_text(text=past_msg["parts"][0]["text"])]
                )
            )

        # Add current user message
        contents.append(
            genai.types.Content(role="user", parts=current_parts)
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
        return response.text

    except Exception as e:
        print(f"Gemini Error: {e}")
        return None