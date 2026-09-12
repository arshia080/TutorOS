import uuid
from datetime import date as date_

from pydantic import BaseModel, Field

from app.models.analytics import AttendanceStatus, TrendDirection


class TopicPerformanceRead(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    questions_attempted: int
    accuracy: float
    recent_accuracy: float
    historical_accuracy: float
    difficulty_adjusted_accuracy: float
    consistency_score: float
    mastery_score: float
    mastery_category: str
    trend: TrendDirection


class StudentPerformanceRead(BaseModel):
    student_id: uuid.UUID
    overall_mastery: float
    topics: list[TopicPerformanceRead]
    strengths: list[TopicPerformanceRead]
    weak_topics: list[TopicPerformanceRead]


class AttendanceMarkEntry(BaseModel):
    student_id: uuid.UUID
    status: AttendanceStatus


class AttendanceMarkRequest(BaseModel):
    date: date_
    records: list[AttendanceMarkEntry] = Field(min_length=1)


class AttendanceRecordRead(BaseModel):
    student_id: uuid.UUID
    date: date_
    status: AttendanceStatus


class StudentAttendanceRead(BaseModel):
    student_id: uuid.UUID
    total_days: int
    present_days: int
    attendance_percentage: float | None
    records: list[AttendanceRecordRead]


class AttentionPanelEntry(BaseModel):
    student_id: uuid.UUID
    student_name: str
    topic_id: uuid.UUID
    topic_name: str
    mastery_score: float
    trend: TrendDirection


class TopicSummary(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    average_mastery: float
    median_mastery: float
    high_mastery: float
    low_mastery: float
    student_count: int


class ClassPerformanceRead(BaseModel):
    average_score: float | None
    median_score: float | None
    high_score: float | None
    low_score: float | None
    score_distribution: dict[str, int]
    average_attendance_percentage: float | None
    average_mastery: float
    topics: list[TopicSummary]


class QuestionAnalyticsRead(BaseModel):
    question_id: uuid.UUID
    question_text: str
    attempts: int
    percent_correct: float | None
    avg_time_seconds: float | None
