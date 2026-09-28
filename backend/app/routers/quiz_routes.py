import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Video, VideoStatus, TranscriptSegment, QuizQuestion, QuizAttempt
from app.schemas import QuizQuestionOut, QuizSubmitRequest, QuizResultOut, QuizDashboardItem
from app.auth import get_current_user
from app.services.llm import call_llm

router = APIRouter(prefix="/videos", tags=["quiz"])


def generate_quiz_questions(full_text_with_timestamps: str) -> list[dict]:
    prompt = f"""Based on this timestamped video transcript, write exactly 5
multiple-choice questions testing understanding of the content.

For each question, output exactly this format on ONE line, pipe-separated:

QUESTION|OPTION_A|OPTION_B|OPTION_C|OPTION_D|CORRECT_INDEX|TIMESTAMP_SECONDS

Where CORRECT_INDEX is 0, 1, 2, or 3 (which option is correct), and
TIMESTAMP_SECONDS is roughly where in the video this is discussed.
Do not add numbering, commentary, or extra text — only the 5 lines.

Transcript:
{full_text_with_timestamps[:8000]}

Questions:"""
    try:
        raw = call_llm(prompt)
    except Exception:
        return []

    questions = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or line.count("|") < 5:
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        question_text = parts[0].strip()
        options = [p.strip() for p in parts[1:5]]
        try:
            correct_index = int("".join(c for c in parts[5] if c.isdigit()))
        except ValueError:
            continue
        if correct_index not in (0, 1, 2, 3):
            continue
        timestamp = None
        if len(parts) > 6:
            try:
                timestamp = float("".join(c for c in parts[6] if c.isdigit() or c == "."))
            except ValueError:
                timestamp = None
        questions.append({
            "question": question_text,
            "options": options,
            "correct_index": correct_index,
            "timestamp": timestamp,
        })

    return questions[:5]


def ensure_quiz_exists(db: Session, video_id: uuid.UUID) -> list[QuizQuestion]:
    """Safety net: generates questions on-demand for any video that somehow
    doesn't have them yet (e.g. uploaded before eager generation was added)."""
    existing = db.query(QuizQuestion).filter(QuizQuestion.video_id == video_id).all()
    if existing:
        return existing

    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.start_time)
        .all()
    )
    if not segments:
        return []

    timestamped_text = "\n".join(f"[{int(s.start_time)}s] {s.text}" for s in segments)
    generated = generate_quiz_questions(timestamped_text)

    for q in generated:
        db.add(QuizQuestion(
            video_id=video_id,
            question=q["question"],
            options=json.dumps(q["options"]),
            correct_index=q["correct_index"],
            timestamp=q["timestamp"],
        ))
    db.commit()

    return db.query(QuizQuestion).filter(QuizQuestion.video_id == video_id).all()


@router.get("/{video_id}/quiz", response_model=list[QuizQuestionOut])
def get_quiz(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id, Video.status == VideoStatus.ready).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found or not ready")

    questions = ensure_quiz_exists(db, video_id)
    if not questions:
        raise HTTPException(status_code=400, detail="No quiz available for this video")

    return [
        QuizQuestionOut(
            id=q.id,
            question=q.question,
            options=json.loads(q.options),
            timestamp=q.timestamp,
        )
        for q in questions
    ]


@router.post("/{video_id}/quiz/submit", response_model=QuizResultOut)
def submit_quiz(
    video_id: uuid.UUID,
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    questions = db.query(QuizQuestion).filter(QuizQuestion.video_id == video_id).all()
    if not questions:
        raise HTTPException(status_code=404, detail="No quiz found for this video")

    score = 0
    correct_answers = {}
    for q in questions:
        qid = str(q.id)
        correct_answers[qid] = q.correct_index
        submitted = payload.answers.get(qid)
        if submitted is not None and submitted == q.correct_index:
            score += 1

    attempt = QuizAttempt(
        user_id=current_user.id,
        video_id=video_id,
        score=score,
        total=len(questions),
    )
    db.add(attempt)
    db.commit()

    return QuizResultOut(score=score, total=len(questions), correct_answers=correct_answers)


@router.get("/quizzes/dashboard", response_model=list[QuizDashboardItem])
def quiz_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    videos = db.query(Video).filter(Video.status == VideoStatus.ready).order_by(Video.created_at.desc()).all()

    results = []
    for v in videos:
        total_questions = db.query(QuizQuestion).filter(QuizQuestion.video_id == v.id).count()

        best_attempt = (
            db.query(QuizAttempt)
            .filter(QuizAttempt.video_id == v.id, QuizAttempt.user_id == current_user.id)
            .order_by(QuizAttempt.score.desc())
            .first()
        )

        results.append(QuizDashboardItem(
            video_id=v.id,
            title=v.title,
            category=v.category,
            best_score=best_attempt.score if best_attempt else None,
            total_questions=best_attempt.total if best_attempt else (total_questions or None),
        ))

    return results