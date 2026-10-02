import os
import time
from groq import Groq

MODEL_NAME = "openai/gpt-oss-120b"


def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def call_llm(prompt: str, max_retries: int = 5) -> str:
    """Non-streaming call, used by category detection, chapters, quiz,
    summary, suggested-questions — anywhere a single complete answer is needed."""
    client = get_client()
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            error_text = str(e)
            is_transient = "429" in error_text or "503" in error_text or "rate_limit" in error_text.lower()
            if is_transient and attempt < max_retries - 1:
                wait_time = 2 * (2 ** attempt)
                print(f"[LLM retry {attempt + 1}/{max_retries}] Transient error, waiting {wait_time}s: {error_text[:150]}")
                time.sleep(wait_time)
                continue
            raise

    raise last_error


def stream_llm(prompt: str):
    """Yields text chunks as they arrive, used only by the live chat endpoint."""
    client = get_client()
    stream = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta