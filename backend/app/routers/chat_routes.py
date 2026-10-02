import os
import json
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database import get_db, SessionLocal
from app.models import User, TranscriptSegment, Video, VideoStatus, ChatMessage
from app.auth import get_current_user
from app.services.embeddings import embed_text
from app.services.vector_store import query_segments, get_collection
from app.services.llm import call_llm, stream_llm, get_client, MODEL_NAME

router = APIRouter(prefix="/videos", tags=["chat"])

HISTORY_TURNS = 6
MIN_RELEVANCE_SCORE = 0.35

INTENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "summarize_video",
            "description": "Call this ONLY when the user explicitly wants an overview, summary, or TL;DR of the entire video's content — not for a question about a specific detail or moment.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_related_videos",
            "description": "Call this ONLY when the user wants recommendations for OTHER videos related to or similar to this one — not for a question about the content of this video itself.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_questions",
            "description": "Call this ONLY when the user is asking WHAT they could ask about this video (e.g. 'what should I ask', 'give me some question ideas') — not when they're asking an actual question themselves.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def classify_intent(message: str) -> str:
    client = get_client()
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": message}],
            tools=INTENT_TOOLS,
            tool_choice="auto",
        )
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            name = tool_calls[0].function.name
            if name == "summarize_video":
                return "summarize"
            if name == "find_related_videos":
                return "related"
            if name == "suggest_questions":
                return "suggest_questions"
    except Exception as e:
        print(f"[intent classification failed]: {e}")
    return "answer"


class ChatRequest(BaseModel):
    message: str
    current_timestamp: float | None = None


def build_context_and_prompt(db, video_id, user_id, message, top_k=10):
    query_vector = embed_text(message)
    results = query_segments(query_vector, video_id=str(video_id), top_k=top_k)

    ids = results["ids"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]
    documents = results["documents"][0]

    if not ids:
        return None, [], []

    scored = []
    for seg_id, dist, meta, doc in zip(ids, distances, metadatas, documents):
        score = 1 / (1 + dist)
        scored.append((score, meta["start_time"], doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    top_scored = scored[:top_k]
    top_segments = sorted(top_scored, key=lambda x: x[1])

    relevant_segments = [s for s in top_scored if s[0] >= MIN_RELEVANCE_SCORE]
    relevant_segments.sort(key=lambda x: x[1])

    transcript_context = "\n".join(f"[{int(start)}s] {text}" for _, start, text in top_segments)

    recent = (
        db.query(ChatMessage)
        .filter(ChatMessage.video_id == video_id, ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_TURNS)
        .all()
    )
    recent.reverse()
    history_text = "\n".join(f"{m.role.capitalize()}: {m.text}" for m in recent) if recent else "(no prior messages)"

    prompt = f"""You are a helpful assistant answering questions about a video, using ONLY the transcript excerpts below. This is an ongoing conversation — use the chat history for context (e.g. if the user says "explain that more", refer back to what was just discussed).

Format your answer using Markdown:
- Use **bold** for key terms, tool names, or concepts.
- Use bullet points when listing multiple items.
- When citing something specific, include the timestamp range in parentheses like (8:28 - 9:51), converting seconds to minutes:seconds format.
- If the answer isn't in the transcript, say so honestly rather than guessing — do not force a connection to unrelated content.

Transcript excerpts:
{transcript_context}

Recent conversation:
{history_text}

New question: {message}

Answer:"""

    class _Seg:
        def __init__(self, start_time):
            self.start_time = start_time

    relevant_seg_objs = [_Seg(start) for _, start, _ in relevant_segments]

    return prompt, top_segments, relevant_seg_objs


def get_related_videos_data(db, video_id, top_k=4):
    collection = get_collection()

    this_video_data = collection.get(where={"video_id": str(video_id)}, include=["embeddings"])
    if this_video_data["embeddings"] is None or len(this_video_data["embeddings"]) == 0:
        return []

    target_avg = np.mean(this_video_data["embeddings"], axis=0)

    other_videos = db.query(Video).filter(Video.id != video_id, Video.status == VideoStatus.ready).all()

    scored = []
    for v in other_videos:
        v_data = collection.get(where={"video_id": str(v.id)}, include=["embeddings"])
        if v_data["embeddings"] is None or len(v_data["embeddings"]) == 0:
            continue
        v_avg = np.mean(v_data["embeddings"], axis=0)
        score = float(np.dot(target_avg, v_avg) / (np.linalg.norm(target_avg) * np.linalg.norm(v_avg)))
        scored.append((score, v))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    return [
        {"video_id": str(v.id), "title": v.title, "category": v.category, "score": round(score, 4)}
        for score, v in top
    ]


@router.get("/{video_id}/chat/history")
def get_chat_history(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.video_id == video_id, ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [
        {
            "role": m.role,
            "text": m.text,
            "referenced_timestamps": json.loads(m.referenced_timestamps) if m.referenced_timestamps else [],
        }
        for m in messages
    ]


@router.delete("/{video_id}/chat/history")
def clear_chat_history(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(ChatMessage).filter(
        ChatMessage.video_id == video_id,
        ChatMessage.user_id == current_user.id,
    ).delete()
    db.commit()
    return {"cleared": True}


@router.post("/{video_id}/chat")
def chat_with_video(
    video_id: uuid.UUID,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id, Video.status == VideoStatus.ready).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found or not ready")

    prompt, top_segments, relevant_segments = build_context_and_prompt(db, video_id, current_user.id, payload.message)
    if prompt is None:
        raise HTTPException(status_code=400, detail="This video has no transcript yet")

    try:
        answer = call_llm(prompt)
    except Exception as e:
        print(f"[chat failed]: {e}")
        raise HTTPException(status_code=503, detail="Couldn't answer that right now. Please try again in a moment.")

    timestamps = [s.start_time for s in relevant_segments]

    db.add(ChatMessage(user_id=current_user.id, video_id=video_id, role="user", text=payload.message))
    db.add(ChatMessage(
        user_id=current_user.id, video_id=video_id, role="assistant",
        text=answer, referenced_timestamps=json.dumps(timestamps),
    ))
    db.commit()

    return {"answer": answer, "referenced_timestamps": timestamps}


@router.post("/{video_id}/chat/stream")
def chat_with_video_stream(
    video_id: uuid.UUID,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id, Video.status == VideoStatus.ready).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found or not ready")

    user_message = payload.message
    user_id = current_user.id

    intent = classify_intent(user_message)

    if intent == "summarize":
        if video.cached_summary:
            summary_text = video.cached_summary
        else:
            segments = (
                db.query(TranscriptSegment)
                .filter(TranscriptSegment.video_id == video_id)
                .order_by(TranscriptSegment.start_time)
                .all()
            )
            if not segments:
                summary_text = "I don't have a transcript for this video yet."
            else:
                full_text = " ".join(s.text for s in segments)
                prompt = f"""Summarize this video transcript in 3-4 short sentences aimed at a student deciding whether to watch it. Be concrete about what topics are covered.

Transcript:
{full_text[:6000]}

Summary:"""
                try:
                    summary_text = call_llm(prompt)
                    video.cached_summary = summary_text
                    db.commit()
                except Exception as e:
                    print(f"[intent-routed summary failed]: {e}")
                    summary_text = "Sorry, I couldn't generate a summary right now. Please try again in a moment."

        def generate_summary():
            yield "META:" + json.dumps({"referenced_timestamps": []}) + "\n"
            yield "RELATED:" + json.dumps([]) + "\n"
            yield summary_text

            save_db = SessionLocal()
            try:
                save_db.add(ChatMessage(user_id=user_id, video_id=video_id, role="user", text=user_message))
                save_db.add(ChatMessage(
                    user_id=user_id, video_id=video_id, role="assistant",
                    text=summary_text, referenced_timestamps=json.dumps([]),
                ))
                save_db.commit()
            finally:
                save_db.close()

        return StreamingResponse(generate_summary(), media_type="text/plain")

    if intent == "related":
        related = get_related_videos_data(db, video_id)
        reply_text = "No related videos found yet." if not related else "Here's what's related:"

        def generate_related():
            yield "META:" + json.dumps({"referenced_timestamps": []}) + "\n"
            yield "RELATED:" + json.dumps(related) + "\n"
            yield reply_text

            save_db = SessionLocal()
            try:
                save_db.add(ChatMessage(user_id=user_id, video_id=video_id, role="user", text=user_message))
                save_db.add(ChatMessage(
                    user_id=user_id, video_id=video_id, role="assistant",
                    text=reply_text, referenced_timestamps=json.dumps([]),
                ))
                save_db.commit()
            finally:
                save_db.close()

        return StreamingResponse(generate_related(), media_type="text/plain")

    if intent == "suggest_questions":
        if video.cached_suggested_questions:
            questions = json.loads(video.cached_suggested_questions)
        else:
            segments = (
                db.query(TranscriptSegment)
                .filter(TranscriptSegment.video_id == video_id)
                .order_by(TranscriptSegment.start_time)
                .all()
            )
            questions = []
            if segments:
                full_text = " ".join(s.text for s in segments)
                prompt = f"""Based on this video transcript, write exactly 3 short questions a curious viewer would naturally ask about it. Each question should be under 8 words. Return ONLY the questions, one per line, no numbering, no extra text.

Transcript:
{full_text[:6000]}

Questions:"""
                try:
                    raw = call_llm(prompt)
                    questions = [q.strip("- ").strip() for q in raw.strip().split("\n") if q.strip()][:3]
                    video.cached_suggested_questions = json.dumps(questions)
                    db.commit()
                except Exception as e:
                    print(f"[intent-routed suggested-questions failed]: {e}")

        if questions:
            reply_text = "Here are a few questions you could ask:\n\n" + "\n".join(f"- {q}" for q in questions)
        else:
            reply_text = "I don't have any suggested questions for this video yet."

        def generate_suggestions():
            yield "META:" + json.dumps({"referenced_timestamps": []}) + "\n"
            yield "RELATED:" + json.dumps([]) + "\n"
            yield reply_text

            save_db = SessionLocal()
            try:
                save_db.add(ChatMessage(user_id=user_id, video_id=video_id, role="user", text=user_message))
                save_db.add(ChatMessage(
                    user_id=user_id, video_id=video_id, role="assistant",
                    text=reply_text, referenced_timestamps=json.dumps([]),
                ))
                save_db.commit()
            finally:
                save_db.close()

        return StreamingResponse(generate_suggestions(), media_type="text/plain")

    prompt, top_segments, relevant_segments = build_context_and_prompt(db, video_id, current_user.id, user_message)
    if prompt is None:
        raise HTTPException(status_code=400, detail="This video has no transcript yet")

    timestamps = [s.start_time for s in relevant_segments]

    def generate():
        yield "META:" + json.dumps({"referenced_timestamps": timestamps}) + "\n"
        yield "RELATED:" + json.dumps([]) + "\n"

        full_answer = ""
        try:
            for delta in stream_llm(prompt):
                full_answer += delta
                yield delta
        except Exception as e:
            print(f"[chat stream failed]: {e}")
            error_message = "Sorry, I couldn't answer that right now. Please try again in a moment."
            full_answer = error_message
            yield error_message
        finally:
            save_db = SessionLocal()
            try:
                save_db.add(ChatMessage(user_id=user_id, video_id=video_id, role="user", text=user_message))
                save_db.add(ChatMessage(
                    user_id=user_id, video_id=video_id, role="assistant",
                    text=full_answer, referenced_timestamps=json.dumps(timestamps),
                ))
                save_db.commit()
            finally:
                save_db.close()

    return StreamingResponse(generate(), media_type="text/plain")


@router.get("/{video_id}/summary")
def summarize_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id, Video.status == VideoStatus.ready).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found or not ready")

    if video.cached_summary:
        return {"summary": video.cached_summary}

    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.start_time)
        .all()
    )
    if not segments:
        raise HTTPException(status_code=400, detail="This video has no transcript yet")

    full_text = " ".join(s.text for s in segments)
    prompt = f"""Summarize this video transcript in 3-4 short sentences aimed at a student deciding whether to watch it. Be concrete about what topics are covered.

Transcript:
{full_text[:6000]}

Summary:"""

    try:
        summary = call_llm(prompt)
    except Exception as e:
        print(f"[summary failed]: {e}")
        raise HTTPException(status_code=503, detail="Couldn't generate a summary right now. Please try again in a moment.")

    video.cached_summary = summary
    db.commit()
    return {"summary": summary}


@router.get("/{video_id}/related")
def related_videos(
    video_id: uuid.UUID,
    top_k: int = 4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_related_videos_data(db, video_id, top_k)


@router.get("/{video_id}/suggested-questions")
def suggested_questions(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id, Video.status == VideoStatus.ready).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found or not ready")

    if video.cached_suggested_questions:
        return {"questions": json.loads(video.cached_suggested_questions)}

    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.start_time)
        .all()
    )
    if not segments:
        return {"questions": []}

    full_text = " ".join(s.text for s in segments)
    prompt = f"""Based on this video transcript, write exactly 3 short questions a curious viewer would naturally ask about it. Each question should be under 8 words. Return ONLY the questions, one per line, no numbering, no extra text.

Transcript:
{full_text[:6000]}

Questions:"""

    try:
        raw = call_llm(prompt)
    except Exception as e:
        print(f"[suggested-questions failed]: {e}")
        return {"questions": []}

    questions = [q.strip("- ").strip() for q in raw.strip().split("\n") if q.strip()][:3]

    video.cached_suggested_questions = json.dumps(questions)
    db.commit()
    return {"questions": questions}