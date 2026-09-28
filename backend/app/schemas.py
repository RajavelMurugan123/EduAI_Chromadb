import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr

from app.models import UserRole, VideoStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.learner


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    is_active: str
    created_at: datetime

    class Config:
        from_attributes = True


class VideoOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: str
    file_url: str
    status: VideoStatus
    uploaded_by: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class VideoUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    description: str | None = None


class TranscriptSegmentOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    start_time: float
    end_time: float
    text: str

    class Config:
        from_attributes = True


class VideoChapterOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    start_time: float
    title: str

    class Config:
        from_attributes = True


class QuizQuestionOut(BaseModel):
    id: uuid.UUID
    question: str
    options: list[str]
    timestamp: float | None

    class Config:
        from_attributes = True


class QuizSubmitRequest(BaseModel):
    answers: dict[str, int]


class QuizResultOut(BaseModel):
    score: int
    total: int
    correct_answers: dict[str, int]


class QuizDashboardItem(BaseModel):
    video_id: uuid.UUID
    title: str
    category: str
    best_score: int | None
    total_questions: int | None