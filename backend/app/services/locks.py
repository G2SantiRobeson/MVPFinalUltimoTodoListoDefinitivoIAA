from __future__ import annotations

from threading import RLock

from app.core.config import get_settings


class DatabaseWriteLock:
    def __init__(self) -> None:
        self._lock = RLock()
        self._enabled = get_settings().database_url.startswith("sqlite")

    def __enter__(self) -> None:
        if self._enabled:
            self._lock.acquire()

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        if self._enabled:
            self._lock.release()


# En PostgreSQL no bloqueamos a nivel de proceso; el motor maneja concurrencia.
# En SQLite queda activo para desarrollo heredado o migraciones locales.
sqlite_write_lock = DatabaseWriteLock()
