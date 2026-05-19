from dataclasses import dataclass

from app.services.analysis import _cell_adjusted_score, _score_to_percent


def test_hybrid_score_is_calibrated_for_dashboard_percentages():
    assert _score_to_percent(0.0, threshold=0.22) == 25
    assert 59 <= _score_to_percent(0.22, threshold=0.22) <= 61
    assert _score_to_percent(0.35, threshold=0.22) >= 68
    assert _score_to_percent(0.55, threshold=0.22) >= 84
    assert _score_to_percent(0.8, threshold=0.22) >= 94


@dataclass(frozen=True)
class FakeRank:
    hybrid_score: float
    lexical_score: float
    semantic_score: float
    phrase_score: float
    section_score: float


def test_cell_adjusted_score_varies_by_course_signal():
    base = FakeRank(
        hybrid_score=0.35,
        lexical_score=0.30,
        semantic_score=0.35,
        phrase_score=0.1,
        section_score=0.2,
    )
    strong_course = FakeRank(
        hybrid_score=0.60,
        lexical_score=0.80,
        semantic_score=0.70,
        phrase_score=0.4,
        section_score=0.5,
    )
    weak_course = FakeRank(
        hybrid_score=0.18,
        lexical_score=0.05,
        semantic_score=0.12,
        phrase_score=0.0,
        section_score=0.0,
    )

    strong = _cell_adjusted_score(0.35, [strong_course], [base])
    weak = _cell_adjusted_score(0.35, [weak_course], [base])

    assert strong > weak
    assert strong != weak
