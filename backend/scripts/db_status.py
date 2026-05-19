from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.exc import OperationalError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.db.models import (  # noqa: E402
    AcademicPeriod,
    ChunkEmbedding,
    Document,
    DocumentChunk,
    DocumentVersion,
    Evidence,
    EvaluationResult,
    ProcessingJob,
)
from app.db.session import SessionLocal  # noqa: E402


def _count(db, model) -> int:
    return int(db.query(func.count()).select_from(model).scalar() or 0)


def _sqlite_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    return Path(database_url.removeprefix("sqlite:///"))


def _latest_version(document: Document) -> DocumentVersion | None:
    if not document.versions:
        return None
    return max(document.versions, key=lambda version: version.version_number)


def _version_chunk_count(db, version_id: str) -> int:
    return int(
        db.query(func.count(DocumentChunk.id))
        .filter(DocumentChunk.version_id == version_id)
        .scalar()
        or 0
    )


def _version_embedding_count(db, version_id: str) -> int:
    return int(
        db.query(func.count(ChunkEmbedding.id))
        .join(DocumentChunk, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .filter(DocumentChunk.version_id == version_id)
        .scalar()
        or 0
    )


def _last_job(db, version_id: str) -> ProcessingJob | None:
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.version_id == version_id)
        .order_by(ProcessingJob.started_at.desc(), ProcessingJob.finished_at.desc())
        .first()
    )


def print_status(limit: int) -> None:
    settings = get_settings()
    db_path = _sqlite_path(settings.database_url)

    db = SessionLocal()
    try:
        init_db(db)

        print("Base de datos de tesis")
        print("======================")
        print(f"URL: {settings.database_url}")
        if db_path:
            print(f"Archivo SQLite: {db_path.resolve()}")
            print(f"Existe: {'si' if db_path.exists() else 'no'}")
        print(f"Storage documentos: {settings.storage_dir.resolve() / 'documents'}")
        print("")

        print("Totales")
        print("-------")
        print(f"Periodos academicos: {_count(db, AcademicPeriod)}")
        print(f"Tesis/documentos: {_count(db, Document)}")
        print(f"Versiones de archivo: {_count(db, DocumentVersion)}")
        print(f"Chunks de texto: {_count(db, DocumentChunk)}")
        print(f"Embeddings: {_count(db, ChunkEmbedding)}")
        print(f"Evidencias: {_count(db, Evidence)}")
        print(f"Resultados de evaluacion: {_count(db, EvaluationResult)}")
        print("")

        documents = (
            db.query(Document)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .all()
        )
        if not documents:
            print("No hay tesis subidas todavia.")
            return

        print(f"Ultimas {len(documents)} tesis registradas")
        print("--------------------------------")
        for document in documents:
            period_name = document.period.name if document.period else "sin periodo"
            version = _latest_version(document)
            print(f"- {document.title}")
            print(f"  id: {document.id}")
            print(f"  periodo: {period_name}")
            print(f"  autor: {document.author or 'sin autor'}")
            print(f"  estado: {document.status}")
            print(f"  creada: {document.created_at}")
            if not version:
                print("  archivo: sin version registrada")
                continue

            file_path = Path(version.file_uri)
            job = _last_job(db, version.id)
            print(f"  version: {version.version_number}")
            print(f"  archivo original: {version.original_filename}")
            print(f"  ruta guardada: {file_path}")
            print(f"  archivo existe: {'si' if file_path.exists() else 'no'}")
            print(f"  paginas: {version.page_count}")
            print(f"  calidad extraccion: {version.extraction_quality:.2f}")
            print(f"  chunks: {_version_chunk_count(db, version.id)}")
            print(f"  embeddings: {_version_embedding_count(db, version.id)}")
            if job:
                print(f"  procesamiento: {job.status} / {job.step} ({job.progress}%)")
                if job.error_message:
                    print(f"  error: {job.error_message}")
            else:
                print("  procesamiento: sin job registrado")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inicializa la base local y muestra las tesis persistidas."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Cantidad maxima de tesis a listar.",
    )
    args = parser.parse_args()
    try:
        print_status(max(args.limit, 1))
    except OperationalError as exc:
        print("No se pudo conectar a la base de datos.")
        print("Si estas usando PostgreSQL local, levanta Docker Desktop y ejecuta:")
        print("  docker compose up -d db")
        print("")
        print(f"Detalle: {exc.orig}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
