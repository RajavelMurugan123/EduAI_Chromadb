import os
import time

MODEL_NAME = "gemini-3.8-flash"


def get_gemini_client():
    from google import genai
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def call_llm(prompt: str, max_retries: int = 5) -> str:
    client = get_gemini_client()
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            return response.text
        except Exception as e:
            last_error = e
            error_text = str(e)
            is_transient = "503" in error_text or "429" in error_text or "UNAVAILABLE" in error_text
            if is_transient and attempt < max_retries - 1:
                wait_time = 2 * (2 ** attempt)
                print(f"[LLM retry {attempt + 1}/{max_retries}] Transient error, waiting {wait_time}s: {error_text[:150]}")
                time.sleep(wait_time)
                continue
            raise

    raise last_error