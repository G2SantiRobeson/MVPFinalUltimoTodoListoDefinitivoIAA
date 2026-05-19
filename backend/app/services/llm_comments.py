from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class CellCommentInput:
    course_code: str
    course_title: str
    competency_code: str
    competency_group: str
    competency_description: str
    criterion_description: str
    score: int | None
    confidence: float | None
    evidence_text: str
    evidence_origin: str
    evidence_page: int | None
    general_context: str = ""
    reviewed_documents: int = 0
    evidence_documents: int = 0
    evidence_count: int = 0


@dataclass(frozen=True)
class CellComment:
    justification: str
    general_comment: str
    suggested_action: str
    source: str


def _json_from_model_output(text: str) -> dict[str, Any] | None:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        if clean.lower().startswith("json"):
            clean = clean[4:].strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end > start:
        clean = clean[start : end + 1]
    try:
        payload = json.loads(clean)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _clean_field(payload: dict[str, Any], key: str, limit: int) -> str:
    value = str(payload.get(key, "")).strip()
    value = " ".join(value.split())
    if len(value) > limit:
        value = f"{value[: limit - 1].rstrip()}..."
    return value


class LLMCellCommentService:
    """Genera redaccion con LLM usando solo evidencia ya recuperada."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        if not self.settings.llm_comments_enabled:
            return False
        if self.provider == "gemini":
            return bool(self.settings.gemini_api_key)
        if self.provider == "openai":
            return bool(self.settings.openai_api_key)
        return False

    @property
    def provider(self) -> str:
        return self.settings.llm_provider.strip().lower()

    def generate(self, data: CellCommentInput) -> CellComment | None:
        if not self.enabled:
            return None
        if self.provider == "gemini":
            return self._generate_with_gemini(data)
        if self.provider == "openai":
            return self._generate_with_openai(data)
        return None

    def _generate_with_gemini(self, data: CellCommentInput) -> CellComment | None:
        try:
            from google import genai
        except ImportError:
            return None

        client = genai.Client(api_key=self.settings.gemini_api_key)
        prompt = self._build_prompt(data)
        try:
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
            )
        except Exception:
            return None

        payload = _json_from_model_output(getattr(response, "text", "") or "")
        return self._comment_from_payload(payload, f"gemini:{self.settings.gemini_model}")

    def _generate_with_openai(self, data: CellCommentInput) -> CellComment | None:
        try:
            from openai import OpenAI
        except ImportError:
            return None

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai_timeout_seconds,
        )
        prompt = self._build_prompt(data)
        try:
            response = client.responses.create(
                model=self.settings.openai_model,
                instructions=(
                    "Eres un asistente academico para trazabilidad curricular. "
                    "Redactas en espanol claro, sobrio y verificable. "
                    "No inventes evidencia, documentos, paginas, autores ni resultados. "
                    "Usa solo los datos entregados. Si la evidencia es debil, dilo."
                ),
                input=prompt,
                max_output_tokens=760,
            )
        except Exception:
            return None

        payload = _json_from_model_output(response.output_text or "")
        return self._comment_from_payload(payload, f"openai:{self.settings.openai_model}")

    def _comment_from_payload(self, payload: dict[str, Any] | None, source: str) -> CellComment | None:
        if not payload:
            return None

        justification = _clean_field(payload, "justification", 900)
        general_comment = _clean_field(payload, "general_comment", 1400)
        action = _clean_field(payload, "suggested_action", 420)
        if not justification or not action:
            return None

        return CellComment(
            justification=justification,
            general_comment=general_comment,
            suggested_action=action,
            source=source,
        )

    def _build_prompt(self, data: CellCommentInput) -> str:
        page = data.evidence_page if data.evidence_page is not None else "sin pagina"
        score = data.score if data.score is not None else "sin score"
        confidence = f"{data.confidence:.2f}" if data.confidence is not None else "sin confianza"
        return f"""
Devuelve exclusivamente un JSON valido con esta forma:
{{
  "justification": "comentario de 2 a 4 frases",
  "general_comment": "comentario agregado de 4 a 6 frases",
  "suggested_action": "accion sugerida de 1 a 2 frases"
}}

Objetivo:
Generar la justificacion trazable de una celda curso-competencia para una plataforma
de revision de tesis/memorias academicas.

Datos de la celda:
- Curso: {data.course_code} - {data.course_title}
- Competencia: {data.competency_code} - {data.competency_group}
- Descripcion de competencia: {data.competency_description}
- Criterio academico: {data.criterion_description}
- Score de la celda: {score}
- Confianza: {confidence}

Evidencia recuperada:
- Documento: {data.evidence_origin}
- Pagina: {page}
- Fragmento: {data.evidence_text}

Resumen agregado de la competencia en el periodo:
- Tesis revisadas: {data.reviewed_documents}
- Tesis con evidencia recuperada: {data.evidence_documents}
- Evidencias unicas consideradas: {data.evidence_count}
{data.general_context}

Reglas:
- No afirmes cumplimiento total si el score o la confianza son medios o bajos.
- No menciones que falta informacion si hay fragmento recuperado; en ese caso habla del alcance de la evidencia.
- La justificacion debe explicar por que el fragmento apoya o no apoya el cruce.
- El comentario general debe englobar el conjunto de tesis/evidencias de la competencia, no depender de un unico documento.
- Si pocas tesis tienen evidencia, indicalo como limitacion del analisis.
- La accion sugerida debe ser concreta para profesor/evaluador.
- No uses markdown.
""".strip()


# Nombre retrocompatible para imports existentes.
OpenAICellCommentService = LLMCellCommentService
