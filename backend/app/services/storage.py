from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip()
    return base or "documento"


async def store_upload(file: UploadFile, period_id: str, document_id: str) -> tuple[str, str, int]:
    settings = get_settings()
    filename = safe_filename(file.filename or "documento")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no permitido: {extension}. Formatos aceptados: PDF, DOCX, TXT.",
        )

    target_dir = settings.storage_dir / "documents" / period_id / document_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    max_bytes = settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    total = 0

    with target_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                target_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo supera el limite de {settings.max_upload_mb} MB.",
                )
            digest.update(chunk)
            output.write(chunk)

    return str(target_path), digest.hexdigest(), total
