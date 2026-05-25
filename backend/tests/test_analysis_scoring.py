from dataclasses import dataclass

from app.services.analysis import (
    _cell_adjusted_score,
    _evidence_candidate_limit,
    _ranked_above_threshold,
    _score_to_percent,
)


@dataclass(frozen=True)
class FakeRank:
    hybrid_score: float
    lexical_score: float
    semantic_score: float
    phrase_score: float
    section_score: float


def test_hybrid_score_is_calibrated_for_dashboard_percentages():
    assert _score_to_percent(0.0, threshold=0.22) == 25
    assert 59 <= _score_to_percent(0.22, threshold=0.22) <= 61
    assert _score_to_percent(0.35, threshold=0.22) >= 68
    assert _score_to_percent(0.55, threshold=0.22) >= 84
    assert _score_to_percent(0.8, threshold=0.22) >= 94


def test_evidence_candidate_limit_uses_ratio_after_threshold_filter():
    assert _evidence_candidate_limit(100, ratio=0.30) == 30
    assert _evidence_candidate_limit(12, ratio=0.30) == 4
    assert _evidence_candidate_limit(3, ratio=0.30) == 1
    assert _evidence_candidate_limit(0, ratio=0.30) == 0


def test_ranked_above_threshold_keeps_only_relevant_fragments():
    chunks = [
        FakeRank(0.30, 0.0, 0.0, 0.0, 0.0),
        FakeRank(0.24, 0.0, 0.0, 0.0, 0.0),
        FakeRank(0.25, 0.0, 0.0, 0.0, 0.0),
    ]

    assert _ranked_above_threshold(chunks, 0.25) == [chunks[0], chunks[2]]


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
