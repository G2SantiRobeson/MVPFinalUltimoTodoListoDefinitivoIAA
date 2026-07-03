from io import BytesIO

import xlsxwriter
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AcademicPeriod, Competency, Course, CourseCompetency, EvaluationCriterion
from app.services.analysis import build_cell_detail, build_period_analysis


LOW_SCORE_CUTOFF = 55
HIGH_SCORE_CUTOFF = 75

PENDING_SCORE_COLOR = "#f8faf8"
HIGH_SCORE_COLOR = "#78b66b"
MEDIUM_SCORE_COLOR = "#f4ce7a"
LOW_SCORE_COLOR = "#f1c7bf"
NOT_APPLICABLE_COLOR = "#e1e7e2"
NOT_APPLICABLE_FILL = "#dfe7e1"


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


def export_periods_to_excel(db: Session, period_ids: list[str] | None = None) -> bytes:
    """Genera un archivo Excel con múltiples hojas de análisis por período.

    Incluye resumen, mapa de calor, detalle por curso y competencia,
    y brechas críticas.

    Args:
        db: Sesión de base de datos.
        period_ids: Lista de IDs de períodos a exportar (None = todos).

    Returns:
        Bytes del archivo Excel generado.
    """
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    # Formats
    header_format = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#17201c",
            "font_color": "#ffffff",
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
            "border": 1,
        }
    )

    title_format = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "font_color": "#0f766e",
            "bottom": 2,
            "bottom_color": "#0f766e",
        }
    )

    subtitle_format = workbook.add_format(
        {
            "bold": True,
            "font_size": 12,
            "font_color": "#17201c",
            "top": 1,
            "bottom": 1,
        }
    )

    def _center_cell_format(bg_color: str, bold: bool = False, **overrides: object) -> object:
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

    cell_formats = {
        "Pendiente": _center_cell_format(_score_color(None)),
        "Alta": _center_cell_format(_score_color(80), bold=True),
        "Media": _center_cell_format(_score_color(60), bold=True),
        "Baja": _center_cell_format(_score_color(40), bold=True),
        "N/A": _center_cell_format(
            NOT_APPLICABLE_COLOR,
            pattern=3,
            fg_color=NOT_APPLICABLE_FILL,
        ),
    }

    text_wrap_format = workbook.add_format(
        {
            "text_wrap": True,
            "valign": "top",
            "border": 1,
        }
    )

    bold_wrap_format = workbook.add_format(
        {
            "bold": True,
            "text_wrap": True,
            "valign": "top",
            "border": 1,
            "bg_color": "#eef3ef",
        }
    )

    # Disable LLM globally for the export to ensure fast generation
    settings = get_settings()
    original_llm_state = settings.llm_comments_enabled
    settings.llm_comments_enabled = False

    try:
        query = db.query(AcademicPeriod).order_by(AcademicPeriod.name.desc())
        if period_ids:
            query = query.filter(AcademicPeriod.id.in_(period_ids))
        periods = query.all()

        for period in periods:
            # Create a valid sheet name (Excel limits to 31 chars, no brackets etc)
            safe_name = str(period.name)[:31].replace(":", "").replace("/", "-").replace("\\", "-")
            ws = workbook.add_worksheet(safe_name)

            # 1. Fetch data
            analysis = build_period_analysis(db, period.id)
            metrics = analysis.get("metrics", {})
            cells_data = analysis.get("cells", [])

            # Map cells by (course_id, competency_id)
            score_map = {(c["course_id"], c["competency_id"]): c for c in cells_data}

            # 2. Write General Metrics
            report_title = f"Reporte de Validación de Perfil de Egreso - Período: {period.name}"
            ws.write("A1", report_title, title_format)
            ws.merge_range("A1:G1", report_title, title_format)
            
            ws.write("A3", "Métricas Generales", subtitle_format)
            ws.merge_range("A3:C3", "Métricas Generales", subtitle_format)
            
            ws.write("A4", "Promedio global:")
            ws.write("B4", f"{metrics.get('average', 0)}%")
            ws.write("A5", "Evidencia Alta:")
            ws.write("B5", metrics.get("high", 0))
            ws.write("A6", "Evidencia Media:")
            ws.write("B6", metrics.get("medium", 0))
            ws.write("A7", "Brechas (Baja):")
            ws.write("B7", metrics.get("gaps", 0))

            # 3. Build Heatmap Matrix
            ws.write("A10", "Mapa de Calor de Tributación", subtitle_format)
            ws.merge_range("A10:G10", "Mapa de Calor de Tributación", subtitle_format)

            # Fetch all mapped courses and competencies to build headers and rows
            curriculum_id = period.curriculum_id
            curriculum_courses = (
                db.query(Course)
                .filter(Course.curriculum_id == curriculum_id)
                .order_by(Course.sort_order)
                .all()
            )
            curriculum_competencies = (
                db.query(Competency)
                .filter(Competency.curriculum_id == curriculum_id)
                .order_by(Competency.sort_order)
                .all()
            )
            
            course_comp_links = (
                db.query(CourseCompetency)
                .join(Course)
                .filter(Course.curriculum_id == curriculum_id)
                .all()
            )
            valid_course_ids = {link.course_id for link in course_comp_links}
            valid_comp_ids = {link.competency_id for link in course_comp_links}

            visible_courses = [c for c in curriculum_courses if c.id in valid_course_ids]
            visible_comps = [c for c in curriculum_competencies if c.id in valid_comp_ids]

            start_row = 11
            
            # Header row for Heatmap
            ws.write(start_row, 0, "Ramo / Competencia", header_format)
            ws.set_column(0, 0, 40)  # Course column width

            for col_idx, comp in enumerate(visible_comps):
                ws.write(start_row, col_idx + 1, f"{comp.code}\n{comp.group}", header_format)
                ws.set_column(col_idx + 1, col_idx + 1, 15)  # Competency columns width
            
            current_row = start_row + 1
            for course in visible_courses:
                course_label = f"{course.code} - {course.title}"
                ws.write(current_row, 0, course_label, bold_wrap_format)
                
                course_tributes = {link.competency_id for link in course.competencies}
                
                for col_idx, comp in enumerate(visible_comps):
                    if comp.id not in course_tributes:
                        ws.write(current_row, col_idx + 1, "", cell_formats["N/A"])
                        continue
                    
                    cell_info = score_map.get((course.id, comp.id))
                    if not cell_info or cell_info["score"] is None:
                        ws.write(current_row, col_idx + 1, "Pend.", cell_formats["Pendiente"])
                    else:
                        score = cell_info["score"]
                        level = _score_level(score)
                        ws.write(current_row, col_idx + 1, f"{score}%", cell_formats[level])
                
                current_row += 1

            # 4. Detailed Evidence List
            detail_start = current_row + 2
            ws.write(detail_start, 0, "Detalle Trazable por Celda", subtitle_format)
            ws.merge_range(
                f"A{detail_start + 1}:G{detail_start + 1}",
                "Detalle Trazable por Celda",
                subtitle_format,
            )

            headers = [
                "Curso", "Competencia", "Puntaje", "Nivel", 
                "Justificación IA", "Comentario General", 
                "Evidencia Extraída", "Documento Origen"
            ]
            
            detail_row = detail_start + 2
            for col_idx, header in enumerate(headers):
                ws.write(detail_row, col_idx, header, header_format)

            ws.set_column(4, 6, 50)  # Make text columns wider
            ws.set_column(7, 7, 30)

            detail_row += 1
            for cell_info in cells_data:
                score = cell_info["score"]
                level = _score_level(score)
                course_id = cell_info["course_id"]
                comp_id = cell_info["competency_id"]
                
                try:
                    detail = build_cell_detail(db, period.id, course_id, comp_id)
                except Exception:
                    detail = {}

                course_label = f"{cell_info['course_code']} - {cell_info['course_title']}"
                ws.write(detail_row, 0, course_label, text_wrap_format)
                ws.write(detail_row, 1, cell_info["competency_code"], text_wrap_format)
                score_text = f"{score}%" if score is not None else "Pendiente"
                score_format = (
                    cell_formats[level] if score is not None else cell_formats["Pendiente"]
                )
                ws.write(detail_row, 2, score_text, score_format)
                ws.write(detail_row, 3, level, score_format)
                ws.write(detail_row, 4, detail.get("justification", ""), text_wrap_format)
                ws.write(detail_row, 5, detail.get("general_comment", ""), text_wrap_format)
                ws.write(detail_row, 6, detail.get("evidence_text", ""), text_wrap_format)
                origin_text = detail.get("evidence_origin", "")
                page = detail.get("evidence_page")
                if page is not None:
                    origin_text += f" (Pág {page})"
                ws.write(detail_row, 7, origin_text, text_wrap_format)
                
                detail_row += 1

    finally:
        # Restore settings
        settings.llm_comments_enabled = original_llm_state

    workbook.close()
    return output.getvalue()
