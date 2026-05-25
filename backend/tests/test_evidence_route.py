from app.api.routes.evidence import _merge_duplicate_fragments


def test_merge_duplicate_fragments_groups_same_chunk_across_courses():
    base = {
        "id": "e1",
        "period_id": "p1",
        "criterion_id": "c1",
        "_chunk_id": "chunk-1",
        "course_id": "course-1",
        "course_code": "ICC5105",
        "course_title": "Software Design",
        "document_title": "Memoria ejemplo",
        "semantic_score": 0.3,
        "confidence": 0.3,
        "verdict": "supporting",
        "observation": "",
    }
    duplicate = {
        **base,
        "id": "e2",
        "course_id": "course-2",
        "course_code": "ICC5202",
        "course_title": "Software Architecture",
        "confidence": 0.4,
    }

    merged = _merge_duplicate_fragments([base, duplicate])

    assert len(merged) == 1
    assert merged[0]["occurrence_count"] == 2
    assert merged[0]["confidence"] == 0.4
    assert merged[0]["course_code"] == "Evidencia"
    assert "2 cruces asociados" in merged[0]["document_title"]
    assert [cell["course_id"] for cell in merged[0]["related_cells"]] == ["course-1", "course-2"]
