from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any


_progress_lock = Lock()
_analysis_progress: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.utcnow().isoformat()


def _log(message: str) -> None:
    print(f"[IAAPLICADA] {message}", flush=True)


def start_analysis_progress(period_id: str, total_documents: int, device: str) -> dict[str, Any]:
    payload = {
        "period_id": period_id,
        "status": "running",
        "step": "starting",
        "ui_step": 0,
        "progress": 0,
        "device": device,
        "current_document_id": None,
        "current_document_title": "",
        "current_index": 0,
        "total_documents": total_documents,
        "message": f"Preparando analisis de {total_documents} tesis.",
        "started_at": _now(),
        "updated_at": _now(),
        "finished_at": None,
        "error": None,
    }
    with _progress_lock:
        _analysis_progress[period_id] = payload
    _log(f"Periodo {period_id}: inicio de analisis ({total_documents} tesis, device={device}).")
    return payload


def update_analysis_progress(period_id: str, **changes: Any) -> dict[str, Any]:
    with _progress_lock:
        payload = _analysis_progress.setdefault(
            period_id,
            {
                "period_id": period_id,
                "status": "running",
                "step": "starting",
                "ui_step": 0,
                "progress": 0,
                "device": "auto",
                "current_document_id": None,
                "current_document_title": "",
                "current_index": 0,
                "total_documents": 0,
                "message": "",
                "started_at": _now(),
                "updated_at": _now(),
                "finished_at": None,
                "error": None,
            },
        )
        payload.update(changes)
        payload["updated_at"] = _now()
        snapshot = dict(payload)

    message = snapshot.get("message") or snapshot.get("step") or "actualizacion"
    _log(f"Periodo {period_id}: {message} ({snapshot.get('progress', 0)}%).")
    return snapshot


def finish_analysis_progress(
    period_id: str,
    status: str,
    message: str,
    error: str | None = None,
) -> dict[str, Any]:
    return update_analysis_progress(
        period_id,
        status=status,
        step=status,
        ui_step=4,
        progress=100 if status == "completed" else 0,
        message=message,
        error=error,
        current_document_id=None,
        current_document_title="",
        finished_at=_now(),
    )


def get_analysis_progress(period_id: str) -> dict[str, Any]:
    with _progress_lock:
        payload = _analysis_progress.get(period_id)
        if payload:
            return dict(payload)
    return {
        "period_id": period_id,
        "status": "idle",
        "step": "idle",
        "ui_step": -1,
        "progress": 0,
        "device": "auto",
        "current_document_id": None,
        "current_document_title": "",
        "current_index": 0,
        "total_documents": 0,
        "message": "No hay analisis en ejecucion.",
        "started_at": None,
        "updated_at": None,
        "finished_at": None,
        "error": None,
    }
