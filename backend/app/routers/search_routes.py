import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import User, Video, VideoStatus
from app.auth import get_current_user
from app.services.embeddings import embed_text
from app.services.vector_store import query_segments

router = APIRouter(prefix="/search", tags=["search"])

MIN_RELEVANCE_SCORE = 0.35


@router.get("")
def search(
    q: str = Query(..., min_length=1),
    video_id: Optional[uuid.UUID] = None,
    top_k: int = 8,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query_vector = embed_text(q)
    video_id_str = str(video_id) if video_id else None

    results = query_segments(query_vector, video_id=video_id_str, top_k=50)

    ids = results["ids"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]
    documents = results["documents"][0]

    scored = []
    for seg_id, dist, meta, doc in zip(ids, distances, metadatas, documents):
        score = 1 / (1 + dist)
        if score >= MIN_RELEVANCE_SCORE:
            scored.append((score, seg_id, meta, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    if video_id:
        top = scored[:top_k]
        return [
            {
                "video_id": str(video_id),
                "start_time": meta["start_time"],
                "end_time": meta["end_time"],
                "text": doc,
                "score": round(score, 4),
            }
            for score, seg_id, meta, doc in top
        ]
    else:
        best_per_video = {}
        for score, seg_id, meta, doc in scored:
            vid = meta["video_id"]
            if vid not in best_per_video or score > best_per_video[vid][0]:
                best_per_video[vid] = (score, meta, doc)

        results_list = sorted(best_per_video.items(), key=lambda x: x[1][0], reverse=True)[:top_k]

        output = []
        for vid, (score, meta, doc) in results_list:
            video = db.query(Video).filter(Video.id == vid, Video.status == VideoStatus.ready).first()
            if not video:
                continue
            output.append({
                "video_id": vid,
                "title": video.title,
                "category": video.category,
                "best_match_timestamp": meta["start_time"],
                "matched_text": doc,
                "score": round(score, 4),
            })
        return output 