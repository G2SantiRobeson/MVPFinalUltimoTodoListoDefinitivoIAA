from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ChunkEmbedding, DocumentChunk, DocumentVersion, Evidence, ProcessingJob
from app.services.embeddings import EmbeddingService
from app.services.locks import document_processing_lock, sqlite_write_lock


PROGRESS_EXTRACTING = 10
PROGRESS_CHUNKING = 35
PROGRESS_EMBEDDING = 65
PROGRESS_DONE = 100
FAILED_PROGRESS_CAP = 99
OCR_REQUIRED_QUALITY = 0


def _extract_pdf(path: Path) -> tuple[list[tuple[int, str]], int, float]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    extracted_pages = 0
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            extracted_pages += 1
        pages.append((index, text))
    page_count = len(reader.pages)
    quality = extracted_pages / page_count if page_count else 0.0
    return pages, page_count, quality


def _extract_docx(path: Path) -> tuple[list[tuple[int, str]], int, float]:
    try:
        from docx import Document as DocxDocument
    except ImportError:
        return [(1, "")], 1, 0.0

    doc = DocxDocument(str(path))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
    return [(1, text)], 1, 1.0 if text.strip() else 0.0


def _extract_text_file(path: Path) -> tuple[list[tuple[int, str]], int, float]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [(1, text)], 1, 1.0 if text.strip() else 0.0


def extract_pages(path: Path, mime_type: str) -> tuple[list[tuple[int, str]], int, float]:
    """Extrae páginas y texto de un archivo según su formato.

    Args:
        path: Ruta al archivo.
        mime_type: Tipo MIME del archivo.

    Returns:
        Tupla (lista de (página, texto), total_páginas, calidad_extracción).
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf" or "pdf" in mime_type:
        return _extract_pdf(path)
    if suffix == ".docx":
        return _extract_docx(path)
    return _extract_text_file(path)


def chunk_pages(pages: list[tuple[int, str]]) -> list[tuple[int, str, int, int, int]]:
    """Segmenta páginas en fragmentos (chunks) con superposición.

    Cada fragmento tiene un tamaño definido en palabras y un
    solapamiento configurable entre chunks consecutivos.

    Args:
        pages: Lista de tuplas (página, texto).

    Returns:
        Lista de tuplas (página, texto, inicio, fin, token_count).
    """
    settings = get_settings()
    chunks: list[tuple[int, str, int, int, int]] = []
    size = settings.chunk_words
    overlap = min(settings.chunk_overlap_words, size // 2)

    for page, text in pages:
        words = text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(start + size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append((page, chunk, start, end, end - start))
            if end >= len(words):
                break
            start = max(end - overlap, start + 1)
    return chunks


def _mark_processing_failed(
    db: Session,
    version_id: str,
    job_id: str | None,
    error: Exception,
) -> ProcessingJob:
    db.rollback()
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise ValueError(f"No existe document_version {version_id}") from error

    job = db.get(ProcessingJob, job_id) if job_id else None
    if not job:
        job = ProcessingJob(version_id=version_id, started_at=datetime.utcnow())
        db.add(job)

    if version.document.status != "deleted":
        version.document.status = "failed"
    job.status = "failed"
    job.step = "failed"
    job.progress = min(job.progress or 0, FAILED_PROGRESS_CAP)
    job.error_message = str(error)
    job.finished_at = datetime.utcnow()
    db.commit()
    return job


def _mark_processing_skipped(db: Session, version: DocumentVersion, reason: str) -> ProcessingJob:
    job = ProcessingJob(
        version_id=version.id,
        status="skipped",
        step="skipped",
        progress=PROGRESS_DONE,
        error_message=reason,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    return job


ProgressCallback = Callable[[str, int, str], None]


def _notify(callback: ProgressCallback | None, step: str, progress: int, message: str) -> None:
    if callback:
        callback(step, progress, message)


def process_document_version(
    db: Session,
    version_id: str,
    embedding_device: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ProcessingJob:
    """Procesa una versión de documento: extracción, chunking y embeddings.

    Args:
        db: Sesión de base de datos.
        version_id: Identificador de la versión a procesar.
        embedding_device: Dispositivo para embeddings (cuda/cpu).
        progress_callback: Callback opcional para reportar progreso.

    Returns:
        Objeto ProcessingJob con el estado final del procesamiento.
    """
    with document_processing_lock:
        with sqlite_write_lock:
            return _process_document_version(db, version_id, embedding_device, progress_callback)


def _process_document_version(
    db: Session,
    version_id: str,
    embedding_device: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ProcessingJob:
    job_id: str | None = None
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise ValueError(f"No existe document_version {version_id}")
    if version.document.status == "deleted":
        return _mark_processing_skipped(db, version, "Documento eliminado antes del procesamiento.")

    try:
        job = ProcessingJob(
            version_id=version.id,
            status="running",
            step="extracting",
            progress=PROGRESS_EXTRACTING,
            started_at=datetime.utcnow(),
        )
        db.add(job)
        version.document.status = "extracting"
        db.commit()
        db.refresh(job)
        job_id = job.id
        _notify(
            progress_callback,
            "extracting",
            PROGRESS_EXTRACTING,
            f"Extrayendo texto de {version.document.title}.",
        )

        path = Path(version.file_uri)
        pages, page_count, quality = extract_pages(path, version.mime_type)
        version.page_count = page_count
        version.extraction_quality = quality
        job.step = "chunking"
        job.progress = PROGRESS_CHUNKING
        db.commit()
        _notify(
            progress_callback,
            "chunking",
            PROGRESS_CHUNKING,
            f"Segmentando tesis {version.document.title}.",
        )

        if quality == OCR_REQUIRED_QUALITY:
            version.document.status = "ocr_required"
            job.status = "failed"
            job.step = "ocr_required"
            job.error_message = "No se detecto texto seleccionable. Se requiere OCR."
            job.finished_at = datetime.utcnow()
            db.commit()
            return job

        chunks = chunk_pages(pages)
        embedding_service = EmbeddingService(device=embedding_device)
        job.step = "embedding"
        job.progress = PROGRESS_EMBEDDING
        db.commit()
        _notify(
            progress_callback,
            "embedding",
            PROGRESS_EMBEDDING,
            (
                f"Generando embeddings de {version.document.title} "
                f"en {embedding_service.device or 'auto'}."
            ),
        )

        existing_chunk_ids = [
            chunk_id
            for (chunk_id,) in db.query(DocumentChunk.id)
            .filter(DocumentChunk.version_id == version.id)
            .all()
        ]
        if existing_chunk_ids:
            db.query(Evidence).filter(Evidence.chunk_id.in_(existing_chunk_ids)).delete(
                synchronize_session=False
            )
            db.query(ChunkEmbedding).filter(ChunkEmbedding.chunk_id.in_(existing_chunk_ids)).delete(
                synchronize_session=False
            )
            db.query(DocumentChunk).filter(DocumentChunk.id.in_(existing_chunk_ids)).delete(
                synchronize_session=False
            )
            db.flush()

        for page, text, start, end, token_count in chunks:
            chunk = DocumentChunk(
                version_id=version.id,
                page=page,
                text=text,
                start_offset=start,
                end_offset=end,
                token_count=token_count,
            )
            db.add(chunk)
            db.flush()
            db.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    model=embedding_service.model_name,
                    dimensions=embedding_service.dimensions,
                    vector=embedding_service.embed(text),
                )
            )

        db.refresh(version.document)
        if version.document.status == "deleted":
            job.status = "skipped"
            job.step = "skipped"
            job.progress = PROGRESS_DONE
            job.error_message = "Documento eliminado durante el procesamiento."
            job.finished_at = datetime.utcnow()
            db.commit()
            return job

        version.document.status = "ready"
        job.status = "completed"
        job.step = "ready"
        job.progress = PROGRESS_DONE
        job.finished_at = datetime.utcnow()
        db.commit()
        _notify(
            progress_callback,
            "ready",
            PROGRESS_DONE,
            f"Tesis lista: {version.document.title}.",
        )
        return job
    except Exception as exc:
        return _mark_processing_failed(db, version_id, job_id, exc)
