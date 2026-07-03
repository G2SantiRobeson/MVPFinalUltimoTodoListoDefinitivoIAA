from app.services.curriculum_loader import load_matrix_from_xlsx
from app.services.curriculum_matrices import resolve_initial_matrix_paths


def test_loads_real_curriculum_matrix():
    path = next(
        path for path in resolve_initial_matrix_paths() if "COMPUTACION" in path.stem.upper()
    )
    matrix = load_matrix_from_xlsx(path)

    assert len(matrix.competencies) == 19
    assert len(matrix.courses) == 52
    assert sum(len(course.competency_indexes) for course in matrix.courses) == 173
    assert matrix.competencies[0].code == "U1"
    assert matrix.competencies[-1].code == "TCC3"
