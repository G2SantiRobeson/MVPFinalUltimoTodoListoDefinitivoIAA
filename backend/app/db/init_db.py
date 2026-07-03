from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import engine
from app.services.seed import seed_demo_data


def init_db(db: Session) -> None:
    ensure_pgvector_extension(db)
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility(db)
    seed_demo_data(db)


def ensure_pgvector_extension(db: Session) -> None:
    if engine.dialect.name != "postgresql":
        return
    db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    db.commit()


def ensure_schema_compatibility(db: Session) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "curricula" in table_names:
        _add_missing_columns(
            db,
            "curricula",
            {
                "display_name": "VARCHAR(160)",
                "source_filename": "VARCHAR(260)",
                "created_at": "TIMESTAMP",
            },
        )

    if "academic_periods" in table_names:
        _add_missing_columns(db, "academic_periods", {"curriculum_id": "VARCHAR(36)"})
        _replace_legacy_period_name_index(db)

    if "evidence" in table_names:
        _add_missing_columns(
            db,
            "evidence",
            {
                "manual_score": "FLOAT",
                "manual_verdict": "VARCHAR(40)",
                "manual_observation": "TEXT",
                "reviewed_by_id": "VARCHAR(36)",
                "reviewed_at": "TIMESTAMP",
            },
        )

    if "chunk_embeddings" in table_names:
        _ensure_chunk_embedding_vector_type(db)

    db.commit()


def _add_missing_columns(db: Session, table_name: str, columns: dict[str, str]) -> None:
    existing_columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def _replace_legacy_period_name_index(db: Session) -> None:
    dialect = engine.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        return
    db.execute(text("DROP INDEX IF EXISTS ix_academic_periods_name"))
    db.execute(
        text("CREATE INDEX IF NOT EXISTS ix_academic_periods_name ON academic_periods (name)")
    )


def _ensure_chunk_embedding_vector_type(db: Session) -> None:
    if engine.dialect.name != "postgresql":
        return

    columns = inspect(engine).get_columns("chunk_embeddings")
    vector_column = next((column for column in columns if column["name"] == "vector"), None)
    if not vector_column:
        return

    column_type = str(vector_column["type"]).lower()
    if column_type.startswith("vector"):
        return

    dimensions = int(get_settings().embedding_dimensions)
    db.execute(
        text(
            "ALTER TABLE chunk_embeddings "
            f"ALTER COLUMN vector TYPE vector({dimensions}) "
            "USING CASE "
            "WHEN vector IS NULL THEN NULL "
            f"ELSE vector::text::vector({dimensions}) "
            "END"
        )
    )
