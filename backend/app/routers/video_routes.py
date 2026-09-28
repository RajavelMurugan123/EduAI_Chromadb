import os
import uuid
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Video, VideoStatus, TranscriptSegment, VideoChapter, QuizQuestion, QuizAttempt, ChatMessage
from app.schemas import VideoOut, VideoUpdate, TranscriptSegmentOut, VideoChapterOut
from app.auth import require_admin, get_current_user
from app.tasks import transcribe_video
from app.services.vector_store import delete_video_segments

router = APIRouter(prefix="/videos", tags=["videos"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


@router.get("", response_model=list[VideoOut])
def list_videos(
    category: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Video).filter(Video.status == VideoStatus.ready)
    if category:
        query = query.filter(Video.category == category)
    return query.order_by(Video.created_at.desc()).all()


@router.get("/{video_id}", response_model=VideoOut)
def get_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.status != VideoStatus.ready and current_user.role != UserRole.admin:
        raise HTTPException(status_code=404, detail="Video not found")

    return video


@router.get("/{video_id}/transcript", response_model=list[TranscriptSegmentOut])
def get_video_transcript(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or (video.status != VideoStatus.ready and current_user.role != UserRole.admin):
        raise HTTPException(status_code=404, detail="Video not found")

    return (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.start_time)
        .all()
    )


@router.get("/{video_id}/chapters", response_model=list[VideoChapterOut])
def get_video_chapters(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or (video.status != VideoStatus.ready and current_user.role != UserRole.admin):
        raise HTTPException(status_code=404, detail="Video not found")

    return (
        db.query(VideoChapter)
        .filter(VideoChapter.video_id == video_id)
        .order_by(VideoChapter.start_time)
        .all()
    )


@router.get("/admin/all", response_model=list[VideoOut])
def admin_list_all_videos(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return db.query(Video).order_by(Video.created_at.desc()).all()


@router.post("/upload", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
def upload_video(
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    video_id = uuid.uuid4()
    saved_filename = f"{video_id}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    video = Video(
        id=video_id,
        title=title,
        description=description,
        category=category,
        file_url=f"/uploads/{saved_filename}",
        status=VideoStatus.uploading,
        uploaded_by=admin.id,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    transcribe_video.delay(str(video.id))

    return video


@router.patch("/{video_id}", response_model=VideoOut)
def update_video(
    video_id: uuid.UUID,
    payload: VideoUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if payload.title is not None:
        video.title = payload.title
    if payload.category is not None:
        video.category = payload.category
    if payload.description is not None:
        video.description = payload.description

    db.commit()
    db.refresh(video)
    return video


@router.post("/{video_id}/reupload", response_model=VideoOut)
def reupload_video(
    video_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    old_path = video.file_url.lstrip("/")
    if os.path.exists(old_path):
        os.remove(old_path)

    saved_filename = f"{video_id}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video_id).delete()
    delete_video_segments(str(video_id))
    db.query(VideoChapter).filter(VideoChapter.video_id == video_id).delete()
    db.query(QuizQuestion).filter(QuizQuestion.video_id == video_id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.video_id == video_id).delete()
    db.query(ChatMessage).filter(ChatMessage.video_id == video_id).delete()

    video.file_url = f"/uploads/{saved_filename}"
    video.status = VideoStatus.uploading
    db.commit()
    db.refresh(video)

    transcribe_video.delay(str(video.id))

    return video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video_id).delete()
    delete_video_segments(str(video_id))
    db.query(VideoChapter).filter(VideoChapter.video_id == video_id).delete()
    db.query(QuizQuestion).filter(QuizQuestion.video_id == video_id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.video_id == video_id).delete()
    db.query(ChatMessage).filter(ChatMessage.video_id == video_id).delete()

    file_path = video.file_url.lstrip("/")
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(video)
    db.commit()
    return None