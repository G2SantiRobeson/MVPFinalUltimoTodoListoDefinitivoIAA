from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.models import Base  # noqa: E402


DEFAULT_SQLITE_PATH = BACKEND_DIR / "data" / "app.db"
DEFAULT_POSTGRES_URL = "postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso"


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve()}"


def _table_count(engine: Engine, table) -> int:
    with Session(engine) as db:
        return int(db.execute(select(func.count()).select_from(table)).scalar_one() or 0)


def _database_has_data(engine: Engine) -> bool:
    return any(_table_count(engine, table) > 0 for table in Base.metadata.sorted_tables)


def _rewrite_file_uri(
    row: dict[str, Any],
    rewrite_from: str | None,
    rewrite_to: str | None,
) -> dict[str, Any]:
    if not rewrite_from or not rewrite_to or "file_uri" not in row:
        return row
    file_uri = str(row["file_uri"])
    normalized_uri = file_uri.replace("\\", "/")
    normalized_from = rewrite_from.replace("\\", "/").rstrip("/")
    if normalized_uri.lower().startswith(normalized_from.lower()):
        suffix = normalized_uri[len(normalized_from) :].lstrip("/")
        row["file_uri"] = f"{rewrite_to.rstrip('/')}/{suffix}"
    return row


def _clear_target(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def migrate(
    source_sqlite_path: Path,
    target_url: str,
    replace: bool,
    append: bool,
    rewrite_from: str | None,
    rewrite_to: str | None,
) -> None:
    if not source_sqlite_path.exists():
        raise FileNotFoundError(f"No existe la base SQLite: {source_sqlite_path}")

    source_engine = create_engine(_sqlite_url(source_sqlite_path), future=True)
    target_connect_args = {"connect_timeout": 5} if target_url.startswith("postgresql") else {}
    target_engine = create_engine(target_url, connect_args=target_connect_args, future=True)
    Base.metadata.create_all(bind=target_engine)

    if replace:
        _clear_target(target_engine)
    elif not append and _database_has_data(target_engine):
        raise RuntimeError(
            "La base PostgreSQL ya tiene datos. Usa --replace para reemplazarla "
            "o --append para agregar sin borrar."
        )

    total = 0
    with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
        for table in Base.metadata.sorted_tables:
            rows = [dict(row) for row in source_connection.execute(select(table)).mappings()]
            if not rows:
                print(f"{table.name}: 0 filas")
                continue
            rows = [
                _rewrite_file_uri(row, rewrite_from, rewrite_to)
                if table.name == "document_versions"
                else row
                for row in rows
            ]
            target_connection.execute(insert(table), rows)
            total += len(rows)
            print(f"{table.name}: {len(rows)} filas")

    print("")
    print(f"Migracion completada: {total} filas copiadas a PostgreSQL.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migra la base SQLite local de tesis a PostgreSQL."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SQLITE_PATH,
        help="Ruta al archivo SQLite origen.",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_POSTGRES_URL,
        help="URL SQLAlchemy de PostgreSQL destino.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Borra tablas destino antes de copiar. Usar para una migracion limpia.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Agrega filas al destino sin borrar. Puede fallar si hay IDs duplicados.",
    )
    parser.add_argument(
        "--rewrite-file-uri-from",
        default=None,
        help="Prefijo de rutas a reemplazar en document_versions.file_uri.",
    )
    parser.add_argument(
        "--rewrite-file-uri-to",
        default=None,
        help="Nuevo prefijo de rutas para document_versions.file_uri.",
    )
    args = parser.parse_args()

    try:
        migrate(
            source_sqlite_path=args.source,
            target_url=args.target,
            replace=args.replace,
            append=args.append,
            rewrite_from=args.rewrite_file_uri_from,
            rewrite_to=args.rewrite_file_uri_to,
        )
    except OperationalError as exc:
        print("No se pudo conectar a PostgreSQL.")
        print("Levanta Docker Desktop y luego ejecuta:")
        print("  docker compose up -d db")
        print("")
        print(f"Detalle: {exc.orig}")
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
