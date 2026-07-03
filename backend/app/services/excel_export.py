from __future__ import annotations

import re
from collections import defaultdict
from io import BytesIO
from typing import Any

import xlsxwriter
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AcademicPeriod, Competency, Course, CourseCompetency
from app.services.analysis import build_cell_detail, build_period_analysis


LOW_SCORE_CUTOFF = 55
HIGH_SCORE_CUTOFF = 75

PENDING_SCORE_COLOR = "#f8faf8"
HIGH_SCORE_COLOR = "#78b66b"
MEDIUM_SCORE_COLOR = "#f4ce7a"
LOW_SCORE_COLOR = "#f1c7bf"
NOT_APPLICABLE_COLOR = "#e1e7e2"
NOT_APPLICABLE_FILL = "#dfe7e1"

SHEET_NAME_LIMIT = 31
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def _score_level(score: int | float | None) -> str:
    if score is None:
        return "Pendiente"
    if score >= HIGH_SCORE_CUTOFF:
        return "Alta"
    if score >= LOW_SCORE_CUTOFF:
        return "Media"
    return "Baja"


def _score_color(score: int | float | None) -> str:
    if score is None:
        return PENDING_SCORE_COLOR
    if score >= HIGH_SCORE_CUTOFF:
        return HIGH_SCORE_COLOR
    if score >= LOW_SCORE_CUTOFF:
        return MEDIUM_SCORE_COLOR
    return LOW_SCORE_COLOR


def _safe_sheet_name(base_name: str, used_names: set[str]) -> str:
    clean = INVALID_SHEET_CHARS.sub("-", base_name).strip() or "Hoja"
    clean = clean[:SHEET_NAME_LIMIT]
    candidate = clean
    suffix = 2
    while candidate in used_names:
        marker = f" {suffix}"
        candidate = f"{clean[: SHEET_NAME_LIMIT - len(marker)]}{marker}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def _period_sheet_name(base_name: str, period: AcademicPeriod, total_periods: int) -> str:
    if total_periods <= 1:
        return base_name
    period_label = str(period.name).strip()
    return f"{period_label} {base_name}"


def _formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    def center_cell(bg_color: str, bold: bool = False, **overrides: object) -> object:
        properties = {
            "bg_color": bg_color,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
        if bold:
            properties["bold"] = True
        properties.update(overrides)
        return workbook.add_format(properties)

    return {
        "title": workbook.add_format(
            {
                "bold": True,
                "font_size": 16,
                "font_color": "#0f766e",
                "bottom": 2,
                "bottom_color": "#0f766e",
            }
        ),
        "subtitle": workbook.add_format(
            {
                "bold": True,
                "font_size": 12,
                "font_color": "#17201c",
                "top": 1,
                "bottom": 1,
            }
        ),
        "header": workbook.add_format(
            {
                "bold": True,
                "bg_color": "#17201c",
                "font_color": "#ffffff",
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
                "border": 1,
            }
        ),
        "text": workbook.add_format({"text_wrap": True, "valign": "top", "border": 1}),
        "bold_text": workbook.add_format(
            {
                "bold": True,
                "text_wrap": True,
                "valign": "top",
                "border": 1,
                "bg_color": "#eef3ef",
            }
        ),
        "pending": center_cell(_score_color(None)),
        "alta": center_cell(_score_color(80), bold=True),
        "media": center_cell(_score_color(60), bold=True),
        "baja": center_cell(_score_color(40), bold=True),
        "na": center_cell(NOT_APPLICABLE_COLOR, pattern=3, fg_color=NOT_APPLICABLE_FILL),
    }


def _score_format(formats: dict[str, Any], score: int | float | None) -> object:
    level = _score_level(score).lower()
    return formats[level]


def _write_headers(
    ws: xlsxwriter.worksheet.Worksheet,
    headers: list[str],
    formats: dict[str, Any],
) -> None:
    for col_idx, header in enumerate(headers):
        ws.write(0, col_idx, header, formats["header"])
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, 0, max(len(headers) - 1, 0))


def _curriculum_axes(
    db: Session,
    curriculum_id: str | None,
) -> tuple[list[Course], list[Competency], dict[str, set[str]]]:
    if not curriculum_id:
        return [], [], {}

    courses = (
        db.query(Course)
        .filter(Course.curriculum_id == curriculum_id)
        .order_by(Course.sort_order)
        .all()
    )
    competencies = (
        db.query(Competency)
        .filter(Competency.curriculum_id == curriculum_id)
        .order_by(Competency.sort_order)
        .all()
    )
    links = (
        db.query(CourseCompetency)
        .join(Course)
        .filter(Course.curriculum_id == curriculum_id)
        .all()
    )
    tributes_by_course: dict[str, set[str]] = defaultdict(set)
    valid_course_ids = set()
    valid_competency_ids = set()
    for link in links:
        tributes_by_course[link.course_id].add(link.competency_id)
        valid_course_ids.add(link.course_id)
        valid_competency_ids.add(link.competency_id)

    visible_courses = [course for course in courses if course.id in valid_course_ids]
    visible_competencies = [comp for comp in competencies if comp.id in valid_competency_ids]
    return visible_courses, visible_competencies, tributes_by_course


def _cell_details(db: Session, period: AcademicPeriod, cells: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for cell in cells:
        detail = {}
        try:
            detail = build_cell_detail(
                db,
                period.id,
                cell["course_id"],
                cell["competency_id"],
            )
        except Exception:
            detail = {}
        rows.append({**cell, "detail": detail})
    return rows


def _write_summary_sheet(
    workbook: xlsxwriter.Workbook,
    used_names: set[str],
    period: AcademicPeriod,
    analysis: dict,
    formats: dict[str, Any],
    total_periods: int,
) -> None:
    ws = workbook.add_worksheet(
        _safe_sheet_name(_period_sheet_name("Resumen", period, total_periods), used_names)
    )
    metrics = analysis.get("metrics", {})
    title = f"Reporte de Validacion de Perfil de Egreso - Periodo: {period.name}"
    ws.write("A1", title, formats["title"])
    ws.merge_range("A1:D1", title, formats["title"])

    rows = [
        ("Periodo", period.name),
        ("Estado", period.status),
        ("Promedio global", f"{metrics.get('average', 0)}%"),
        ("Trazabilidad", f"{metrics.get('traceability', 0)}%"),
        ("Cobertura del periodo", f"{metrics.get('coverage_rate', 0)}%"),
        ("Celdas evaluadas", metrics.get("evaluated_cells", 0)),
        ("Evidencia alta", metrics.get("high", 0)),
        ("Evidencia media", metrics.get("medium", 0)),
        ("Brechas / evidencia baja", metrics.get("gaps", 0)),
    ]
    ws.write("A3", "Metrica", formats["header"])
    ws.write("B3", "Valor", formats["header"])
    for row_idx, (label, value) in enumerate(rows, start=3):
        ws.write(row_idx, 0, label, formats["text"])
        ws.write(row_idx, 1, value, formats["text"])
    ws.set_column(0, 0, 28)
    ws.set_column(1, 1, 24)


def _write_heatmap_sheet(
    workbook: xlsxwriter.Workbook,
    used_names: set[str],
    db: Session,
    period: AcademicPeriod,
    cells: list[dict],
    formats: dict[str, Any],
    total_periods: int,
) -> None:
    ws = workbook.add_worksheet(
        _safe_sheet_name(_period_sheet_name("Mapa de Calor", period, total_periods), used_names)
    )
    courses, competencies, tributes_by_course = _curriculum_axes(db, period.curriculum_id)
    score_map = {(cell["course_id"], cell["competency_id"]): cell for cell in cells}

    ws.write(0, 0, "Ramo / Competencia", formats["header"])
    ws.set_column(0, 0, 40)
    for col_idx, comp in enumerate(competencies, start=1):
        ws.write(0, col_idx, f"{comp.code}\n{comp.group}", formats["header"])
        ws.set_column(col_idx, col_idx, 15)

    for row_idx, course in enumerate(courses, start=1):
        ws.write(row_idx, 0, f"{course.code} - {course.title}", formats["bold_text"])
        course_tributes = tributes_by_course.get(course.id, set())
        for col_idx, comp in enumerate(competencies, start=1):
            if comp.id not in course_tributes:
                ws.write(row_idx, col_idx, "", formats["na"])
                continue
            cell = score_map.get((course.id, comp.id))
            score = cell.get("score") if cell else None
            if score is None:
                ws.write(row_idx, col_idx, "Pend.", formats["pending"])
            else:
                ws.write(row_idx, col_idx, f"{score}%", _score_format(formats, score))
    ws.freeze_panes(1, 1)


def _detail_row(row: dict) -> list[Any]:
    detail = row.get("detail", {})
    origin = detail.get("evidence_origin", "")
    page = detail.get("evidence_page")
    if page is not None:
        origin = f"{origin} (Pag {page})"
    score = row.get("score")
    return [
        row.get("course_code", ""),
        row.get("course_title", ""),
        row.get("competency_code", ""),
        row.get("competency_group", ""),
        f"{score}%" if score is not None else "Pendiente",
        _score_level(score),
        row.get("evidence_count", 0),
        detail.get("justification", ""),
        detail.get("general_comment", ""),
        detail.get("evidence_text", ""),
        origin,
    ]


def _write_detail_sheet(
    workbook: xlsxwriter.Workbook,
    used_names: set[str],
    period: AcademicPeriod,
    rows: list[dict],
    formats: dict[str, Any],
    total_periods: int,
    by_competency: bool,
) -> None:
    base_name = "Detalle por Competencia" if by_competency else "Detalle por Curso"
    ws = workbook.add_worksheet(
        _safe_sheet_name(_period_sheet_name(base_name, period, total_periods), used_names)
    )
    headers = [
        "Curso",
        "Nombre curso",
        "Competencia",
        "Grupo",
        "Puntaje",
        "Nivel",
        "Evidencias",
        "Justificacion IA",
        "Comentario General",
        "Evidencia Extraida",
        "Documento Origen",
    ]
    _write_headers(ws, headers, formats)
    ordered_rows = sorted(
        rows,
        key=lambda item: (
            item.get("competency_code", "") if by_competency else item.get("course_code", ""),
            item.get("course_code", "") if by_competency else item.get("competency_code", ""),
        ),
    )
    for row_idx, row in enumerate(ordered_rows, start=1):
        values = _detail_row(row)
        score = row.get("score")
        for col_idx, value in enumerate(values):
            cell_format = _score_format(formats, score) if col_idx in {4, 5} else formats["text"]
            ws.write(row_idx, col_idx, value, cell_format)
    ws.set_column(0, 3, 22)
    ws.set_column(4, 6, 14)
    ws.set_column(7, 9, 50)
    ws.set_column(10, 10, 32)


def _write_gaps_sheet(
    workbook: xlsxwriter.Workbook,
    used_names: set[str],
    period: AcademicPeriod,
    rows: list[dict],
    formats: dict[str, Any],
    total_periods: int,
) -> None:
    ws = workbook.add_worksheet(
        _safe_sheet_name(_period_sheet_name("Brechas", period, total_periods), used_names)
    )
    headers = [
        "Curso",
        "Nombre curso",
        "Competencia",
        "Grupo",
        "Puntaje",
        "Nivel",
        "Evidencias",
        "Accion sugerida",
    ]
    _write_headers(ws, headers, formats)
    gap_rows = [
        row for row in rows if row.get("score") is None or row.get("score", 0) < LOW_SCORE_CUTOFF
    ]
    gap_rows = sorted(gap_rows, key=lambda item: -1 if item.get("score") is None else item["score"])
    for row_idx, row in enumerate(gap_rows, start=1):
        detail = row.get("detail", {})
        score = row.get("score")
        values = [
            row.get("course_code", ""),
            row.get("course_title", ""),
            row.get("competency_code", ""),
            row.get("competency_group", ""),
            f"{score}%" if score is not None else "Pendiente",
            _score_level(score),
            row.get("evidence_count", 0),
            detail.get("suggested_action", ""),
        ]
        for col_idx, value in enumerate(values):
            cell_format = _score_format(formats, score) if col_idx in {4, 5} else formats["text"]
            ws.write(row_idx, col_idx, value, cell_format)
    ws.set_column(0, 3, 24)
    ws.set_column(4, 6, 14)
    ws.set_column(7, 7, 60)


def export_periods_to_excel(db: Session, period_ids: list[str] | None = None) -> bytes:
    """Genera un Excel con hojas separadas de resumen, heatmap, detalles y brechas."""

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    formats = _formats(workbook)

    settings = get_settings()
    original_llm_state = settings.llm_comments_enabled
    settings.llm_comments_enabled = False

    try:
        query = db.query(AcademicPeriod).order_by(AcademicPeriod.name.desc())
        if period_ids:
            query = query.filter(AcademicPeriod.id.in_(period_ids))
        periods = query.all()
        used_names: set[str] = set()

        for period in periods:
            analysis = build_period_analysis(db, period.id)
            cells = analysis.get("cells", [])
            detail_rows = _cell_details(db, period, cells)
            total_periods = len(periods)

            _write_summary_sheet(workbook, used_names, period, analysis, formats, total_periods)
            _write_heatmap_sheet(workbook, used_names, db, period, cells, formats, total_periods)
            _write_detail_sheet(
                workbook,
                used_names,
                period,
                detail_rows,
                formats,
                total_periods,
                by_competency=False,
            )
            _write_detail_sheet(
                workbook,
                used_names,
                period,
                detail_rows,
                formats,
                total_periods,
                by_competency=True,
            )
            _write_gaps_sheet(workbook, used_names, period, detail_rows, formats, total_periods)
    finally:
        settings.llm_comments_enabled = original_llm_state

    workbook.close()
    return output.getvalue()
