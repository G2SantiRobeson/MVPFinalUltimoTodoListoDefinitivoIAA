from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "Validacion Perfil de Egreso API"
    api_prefix: str = "/api/v1"
    environment: str = "local"

    database_url: str = "postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso"
    storage_dir: Path = BACKEND_DIR / "storage"
    matrices_dir: Path = PROJECT_DIR / "matrices_tributacion"
    curriculum_xlsx_path: Path = matrices_dir / "Matriz Tributacion PE 2025 COMPUTACION.xlsx"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "null",
    ]

    max_upload_mb: int = 40
    chunk_words: int = 220
    chunk_overlap_words: int = 45
    embedding_provider: str = "bge-m3"
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024
    embedding_max_sequence_length: int = 8192
    embedding_device: str = "cuda"
    llm_comments_enabled: bool = True
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"
    openai_timeout_seconds: int = 20
    evidence_threshold: float = 0.22
    evidence_sample_ratio: float = 0.30
    evidence_relevance_threshold: float = 0.25

    demo_auth_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.matrices_dir.mkdir(parents=True, exist_ok=True)
    (BACKEND_DIR / "data").mkdir(parents=True, exist_ok=True)
    return settings
