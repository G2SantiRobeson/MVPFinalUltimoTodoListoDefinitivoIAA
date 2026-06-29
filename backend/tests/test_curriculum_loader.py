from pathlib import Path

from app.services.curriculum_loader import load_matrix_from_xlsx


def test_loads_real_curriculum_matrix():
    project_root = Path(__file__).resolve().parents[2]
    path = project_root / "matrices_tributacion" / "Matriz Tributación PE 2025 COMPUTACION.xlsx"
    matrix = load_matrix_from_xlsx(path)

    assert len(matrix.competencies) == 19
    assert len(matrix.courses) == 52
    assert sum(len(course.competency_indexes) for course in matrix.courses) == 173
    assert matrix.competencies[0].code == "U1"
    assert matrix.competencies[-1].code == "TCC3"
