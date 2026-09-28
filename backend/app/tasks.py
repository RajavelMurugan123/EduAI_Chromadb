import whisper

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Video, VideoStatus, TranscriptSegment, VideoChapter, QuizQuestion
from app.services.embeddings import embed_text
from app.services.vector_store import add_segment, delete_video_segments
from app.services.llm import call_llm
from app.routers.quiz_routes import generate_quiz_questions

_model = None

GENERAL_CATEGORIES = [
    "Python", "Java", "JavaScript", "AI", "Machine Learning",
    "Web Development", "Data Science", "DevOps", "Cybersecurity",
    "SQL", "Mobile Development", "Cloud Computing", "General",
]


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def detect_category(full_text: str) -> str:
    category_list = ", ".join(GENERAL_CATEGORIES)
    prompt = f"""Based on this video transcript, pick the ONE category that best
fits from this exact list — do not invent a new category, choose only from
these options:

{category_list}

Return ONLY the category name exactly as written above, nothing else.

Transcript:
{full_text[:4000]}

Category:"""
    try:
        category = call_llm(prompt).strip()
        for allowed in GENERAL_CATEGORIES:
            if allowed.lower() == category.lower():
                return allowed
        return "General"
    except Exception:
        return "General"


def generate_chapters(full_text_with_timestamps: str) -> list[dict]:
    prompt = f"""Based on this timestamped video transcript, break it into 4-8
logical chapters. For each chapter, give a short title (3-6 words) and the
timestamp in seconds where it starts.

Output ONLY lines in this exact format, one chapter per line, nothing else:

START_SECONDS|TITLE

The first chapter must start at 0. Do not add commentary or numbering.

Transcript:
{full_text_with_timestamps[:8000]}

Chapters:"""
    try:
        raw = call_llm(prompt)
    except Exception:
        return []

    chapters = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|", 1)
        if len(parts) != 2:
            continue
        start_str, title = parts
        try:
            start = float("".join(c for c in start_str if c.isdigit() or c == "."))
        except ValueError:
            continue
        title = title.strip()
        if title:
            chapters.append({"start_time": start, "title": title})

    chapters.sort(key=lambda c: c["start_time"])
    return chapters


@celery_app.task(name="transcribe_video")
def transcribe_video(video_id: str):
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return

        video.status = VideoStatus.processing
        db.commit()

        file_path = video.file_url.lstrip("/")

        model = get_model()
        result = model.transcribe(file_path, verbose=False)

        db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video.id).delete()
        delete_video_segments(str(video.id))

        all_text_parts = []
        timestamped_parts = []
        for seg in result["segments"]:
            text = seg["text"].strip()
            if not text:
                continue

            vector = embed_text(text)
            all_text_parts.append(text)
            timestamped_parts.append(f"[{int(seg['start'])}s] {text}")

            segment = TranscriptSegment(
                video_id=video.id,
                start_time=seg["start"],
                end_time=seg["end"],
                text=text,
                embedding=None,
            )
            db.add(segment)
            db.flush()

            add_segment(
                segment_id=str(segment.id),
                video_id=str(video.id),
                embedding=vector,
                text=text,
                start_time=seg["start"],
                end_time=seg["end"],
            )

        db.commit()
        print(f"Saved {len(result['segments'])} segments (Postgres text + Chroma vectors) for '{video.title}'")

        if not video.category or video.category.strip() == "":
            full_text = " ".join(all_text_parts)
            video.category = detect_category(full_text)
            print(f"Auto-detected category for '{video.title}': {video.category}")

            if video.category == "General":
                print(f"Category detection fell back to 'General' for '{video.title}' — marking as failed")
                video.status = VideoStatus.failed
                db.commit()
                return

        timestamped_text = "\n".join(timestamped_parts)

        db.query(VideoChapter).filter(VideoChapter.video_id == video.id).delete()
        chapters = generate_chapters(timestamped_text)
        for ch in chapters:
            db.add(VideoChapter(
                video_id=video.id,
                start_time=ch["start_time"],
                title=ch["title"],
            ))
        if chapters:
            print(f"Generated {len(chapters)} chapters for '{video.title}'")

        db.query(QuizQuestion).filter(QuizQuestion.video_id == video.id).delete()
        quiz_questions = generate_quiz_questions(timestamped_text)
        import json
        for q in quiz_questions:
            db.add(QuizQuestion(
                video_id=video.id,
                question=q["question"],
                options=json.dumps(q["options"]),
                correct_index=q["correct_index"],
                timestamp=q["timestamp"],
            ))
        if quiz_questions:
            print(f"Generated {len(quiz_questions)} quiz questions for '{video.title}'")

        video.status = VideoStatus.ready
        db.commit()

    except Exception as e:
        print(f"Transcription failed for {video_id}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.failed
            db.commit()
    finally:
        db.close()