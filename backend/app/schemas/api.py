from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RoleOut(BaseModel):
    name: str
    description: str = ""

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    roles: list[RoleOut]

    model_config = ConfigDict(from_attributes=True)


class PeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    curriculum_id: str = Field(min_length=1)


class PeriodOut(BaseModel):
    id: str
    name: str
    curriculum_id: str | None = None
    curriculum_name: str = ""
    program: str = ""
    status: str
    analyzedAt: str
    updatedAt: str
    metrics: dict
    thesis: list[list]


class CurriculumSummaryOut(BaseModel):
    id: str
    display_name: str
    program: str
    year: int
    version: str
    source_filename: str = ""


class CompetencyOut(BaseModel):
    db_id: str
    id: str
    group: str
    name: str


class CourseOut(BaseModel):
    db_id: str
    code: str
    title: str
    semester: str
    t: list[int]


class MatrixOut(BaseModel):
    curriculum_id: str
    program: str
    version: str
    display_name: str
    competencies: list[CompetencyOut]
    courses: list[CourseOut]


class DocumentOut(BaseModel):
    id: str
    period_id: str
    title: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobOut(BaseModel):
    id: str
    version_id: str
    status: str
    step: str
    progress: int
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceOut(BaseModel):
    id: str
    period_id: str
    course_id: str
    course_code: str
    course_title: str
    related_courses: list[str] = []
    related_cells: list[dict] = []
    occurrence_count: int = 1
    competency_code: str
    competency_group: str
    criterion_id: str
    criterion_name: str
    document_title: str
    source_document_title: str = ""
    page: int
    text: str
    semantic_score: float
    confidence: float
    manual_score: int | None = None
    manual_verdict: str | None = None
    effective_score: int
    verdict: str
    observation: str
    manual_observation: str = ""
    reviewed_at: str | None = None


class EvidenceReviewIn(BaseModel):
    manual_score: int = Field(ge=0, le=100)
    manual_observation: str = Field(default="", max_length=1000)
    manual_verdict: Literal["supporting", "candidate", "false_positive"] | None = None


class HeatmapCellOut(BaseModel):
    course_id: str
    course_code: str
    course_title: str
    competency_id: str
    competency_code: str
    score: int | None
    confidence: float | None
    status: str
    evidence_count: int


class AnalysisOut(BaseModel):
    period_id: str
    status: str
    generated_at: str | None
    cells: list[HeatmapCellOut]
    metrics: dict


class CellDetailOut(BaseModel):
    period_id: str
    course_id: str
    course_code: str
    course_title: str
    competency_id: str
    competency_code: str
    competency_group: str
    competency_description: str
    score: int | None
    confidence: float | None
    justification: str
    general_comment: str
    general_document_count: int
    general_evidence_document_count: int
    general_evidence_count: int
    evidence_text: str
    evidence_origin: str
    evidence_page: int | None
    suggested_action: str
    source: str


class RunAnalysisOut(BaseModel):
    period_id: str
    status: str
    message: str
    metrics: dict


class ReportOut(BaseModel):
    id: str
    period_id: str
    report_type: str
    payload: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
