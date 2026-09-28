import os

MODEL_NAME = "gemini-2.5-flash"


def get_gemini_client():
    from google import genai
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def call_llm(prompt: str) -> str:
    client = get_gemini_client()
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text