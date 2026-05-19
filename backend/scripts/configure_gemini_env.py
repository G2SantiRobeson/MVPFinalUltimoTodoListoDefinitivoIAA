from __future__ import annotations

import getpass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    ordered_keys = [
        "ENVIRONMENT",
        "DATABASE_URL",
        "STORAGE_DIR",
        "CURRICULUM_XLSX_PATH",
        "MAX_UPLOAD_MB",
        "CHUNK_WORDS",
        "CHUNK_OVERLAP_WORDS",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL_NAME",
        "EMBEDDING_DIMENSIONS",
        "EMBEDDING_MAX_SEQUENCE_LENGTH",
        "EMBEDDING_DEVICE",
        "LLM_COMMENTS_ENABLED",
        "LLM_PROVIDER",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_TIMEOUT_SECONDS",
        "EVIDENCE_THRESHOLD",
        "TOP_K_EVIDENCE",
        "DEMO_AUTH_ENABLED",
    ]
    lines = []
    seen = set()
    for key in ordered_keys:
        if key in values:
            lines.append(f"{key}={values[key]}")
            seen.add(key)
    for key in sorted(set(values) - seen):
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    values = {
        "ENVIRONMENT": "local",
        "DATABASE_URL": "postgresql+psycopg://perfil:perfil@localhost:5432/perfil_egreso",
        "STORAGE_DIR": "./storage",
        "CURRICULUM_XLSX_PATH": "../Matriz Tributación PE 2025 COMPUTACION.xlsx",
        "MAX_UPLOAD_MB": "40",
        "CHUNK_WORDS": "220",
        "CHUNK_OVERLAP_WORDS": "45",
        "EMBEDDING_PROVIDER": "bge-m3",
        "EMBEDDING_MODEL_NAME": "BAAI/bge-m3",
        "EMBEDDING_DIMENSIONS": "1024",
        "EMBEDDING_MAX_SEQUENCE_LENGTH": "8192",
        "EMBEDDING_DEVICE": "auto",
        "LLM_COMMENTS_ENABLED": "true",
        "LLM_PROVIDER": "gemini",
        "GEMINI_MODEL": "gemini-2.0-flash",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "gpt-5.5",
        "OPENAI_TIMEOUT_SECONDS": "20",
        "EVIDENCE_THRESHOLD": "0.22",
        "TOP_K_EVIDENCE": "5",
        "DEMO_AUTH_ENABLED": "true",
        **_read_env(ENV_PATH),
    }

    api_key = getpass.getpass("Pega tu GEMINI_API_KEY (no se mostrara): ").strip()
    if not api_key:
        raise SystemExit("No se guardo nada porque la key estaba vacia.")

    values["LLM_COMMENTS_ENABLED"] = "true"
    values["LLM_PROVIDER"] = "gemini"
    values["GEMINI_API_KEY"] = api_key
    values.setdefault("GEMINI_MODEL", "gemini-2.0-flash")
    _write_env(ENV_PATH, values)
    print(f"Configuracion Gemini guardada en {ENV_PATH}")


if __name__ == "__main__":
    main()
