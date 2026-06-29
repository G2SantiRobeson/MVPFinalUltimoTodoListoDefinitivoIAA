from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uuid_str() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")

    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        back_populates="roles",
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="joined",
    )


class AcademicPeriod(Base):
    __tablename__ = "academic_periods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(40), index=True)
    curriculum_id: Mapped[str | None] = mapped_column(ForeignKey("curricula.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="empty")
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    documents: Mapped[list[Document]] = relationship(back_populates="period")
    curriculum: Mapped[Curriculum | None] = relationship(back_populates="periods")

    __table_args__ = (UniqueConstraint("name", "curriculum_id"),)


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(220), unique=True)

    curricula: Mapped[list[Curriculum]] = relationship(back_populates="program")


class Curriculum(Base):
    __tablename__ = "curricula"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"))
    year: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(80), default="PE 2025 COMPUTACION")
    display_name: Mapped[str] = mapped_column(String(160), default="")
    source_filename: Mapped[str] = mapped_column(String(260), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    program: Mapped[Program] = relationship(back_populates="curricula")
    courses: Mapped[list[Course]] = relationship(back_populates="curriculum")
    competencies: Mapped[list[Competency]] = relationship(back_populates="curriculum")
    periods: Mapped[list[AcademicPeriod]] = relationship(back_populates="curriculum")

    __table_args__ = (UniqueConstraint("program_id", "year", "version"),)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    curriculum_id: Mapped[str] = mapped_column(ForeignKey("curricula.id"))
    code: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(240), index=True)
    semester: Mapped[str] = mapped_column(String(20), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    curriculum: Mapped[Curriculum] = relationship(back_populates="courses")
    competencies: Mapped[list[CourseCompetency]] = relationship(back_populates="course")


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    curriculum_id: Mapped[str] = mapped_column(ForeignKey("curricula.id"))
    code: Mapped[str] = mapped_column(String(40), index=True)
    group: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    curriculum: Mapped[Curriculum] = relationship(back_populates="competencies")
    courses: Mapped[list[CourseCompetency]] = relationship(back_populates="competency")
    criteria: Mapped[list[EvaluationCriterion]] = relationship(back_populates="competency")

    __table_args__ = (UniqueConstraint("curriculum_id", "code"),)


class CourseCompetency(Base):
    __tablename__ = "course_competencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"))
    competency_id: Mapped[str] = mapped_column(ForeignKey("competencies.id"))

    course: Mapped[Course] = relationship(back_populates="competencies")
    competency: Mapped[Competency] = relationship(back_populates="courses")

    __table_args__ = (UniqueConstraint("course_id", "competency_id"),)


class EvaluationCriterion(Base):
    __tablename__ = "evaluation_criteria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    competency_id: Mapped[str] = mapped_column(ForeignKey("competencies.id"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    threshold: Mapped[float] = mapped_column(Float, default=0.22)

    competency: Mapped[Competency] = relationship(back_populates="criteria")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    period_id: Mapped[str] = mapped_column(ForeignKey("academic_periods.id"))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(260))
    author: Mapped[str] = mapped_column(String(180), default="")
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    period: Mapped[AcademicPeriod] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(back_populates="document")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    file_uri: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(260))
    checksum: Mapped[str] = mapped_column(String(96), index=True)
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    extraction_quality: Mapped[float] = mapped_column(Float, default=0.0)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="version")
    jobs: Mapped[list[ProcessingJob]] = relationship(back_populates="version")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    step: Mapped[str] = mapped_column(String(80), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    version: Mapped[DocumentVersion] = relationship(back_populates="jobs")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    page: Mapped[int] = mapped_column(Integer, default=1)
    section: Mapped[str] = mapped_column(String(160), default="")
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)

    version: Mapped[DocumentVersion] = relationship(back_populates="chunks")
    embedding: Mapped[ChunkEmbedding | None] = relationship(back_populates="chunk")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id"), unique=True)
    model: Mapped[str] = mapped_column(String(120), default="local-hash-embedding")
    dimensions: Mapped[int] = mapped_column(Integer, default=64)
    vector: Mapped[list[float]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chunk: Mapped[DocumentChunk] = relationship(back_populates="embedding")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    period_id: Mapped[str] = mapped_column(ForeignKey("academic_periods.id"), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id"))
    criterion_id: Mapped[str] = mapped_column(ForeignKey("evaluation_criteria.id"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"))
    semantic_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    verdict: Mapped[str] = mapped_column(String(40), default="candidate")
    observation: Mapped[str] = mapped_column(Text, default="")
    manual_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_verdict: Mapped[str | None] = mapped_column(String(40), nullable=True)
    manual_observation: Mapped[str] = mapped_column(Text, default="")
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    period_id: Mapped[str] = mapped_column(ForeignKey("academic_periods.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    criterion_id: Mapped[str] = mapped_column(ForeignKey("evaluation_criteria.id"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"))
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(40), default="ready")
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("period_id", "criterion_id", "course_id", "document_id"),)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    period_id: Mapped[str] = mapped_column(ForeignKey("academic_periods.id"))
    report_type: Mapped[str] = mapped_column(String(80), default="dashboard")
    file_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(120))
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
