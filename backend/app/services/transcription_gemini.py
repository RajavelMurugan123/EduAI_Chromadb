import os
import re
from google import genai
from google.genai import types


def transcribe_with_gemini(file_path: str) -> list[dict]:
    """
    Sends the video file as inline bytes (not via the Files API, which
    some projects have restricted access to). Works for files under
    roughly 20MB — fine for short course video clips.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    with open(file_path, "rb") as f:
        video_bytes = f.read()

    mime_type = _guess_mime_type(file_path)

    prompt = """Transcribe the speech in this video. The speech may switch between
Tamil and English mid-sentence (Tanglish) — transcribe exactly what is said in
whichever language/script it's actually spoken in, do not translate.

Break the transcript into short segments of roughly 3-8 seconds each.
Output ONLY lines in this exact format, one segment per line, nothing else:

START|END|TEXT

Where START and END are in seconds (numbers, e.g. 12.5), and TEXT is the
transcribed speech for that segment. Do not add any commentary, headers, or
explanation — only the pipe-separated lines."""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
            prompt,
        ],
    )

    return _parse_segments(response.text)


def _guess_mime_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
    }.get(ext, "video/mp4")


def _parse_segments(raw_text: str) -> list[dict]:
    segments = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        start_str, end_str, text = parts
        try:
            start = float(re.sub(r"[^\d.]", "", start_str))
            end = float(re.sub(r"[^\d.]", "", end_str))
        except ValueError:
            continue
        text = text.strip()
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return segments