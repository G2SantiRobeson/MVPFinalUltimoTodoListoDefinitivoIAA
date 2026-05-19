from app.services.llm_comments import _json_from_model_output


def test_json_from_model_output_accepts_plain_json():
    payload = _json_from_model_output(
        '{"justification": "Texto trazable.", "suggested_action": "Revisar evidencia."}'
    )

    assert payload["justification"] == "Texto trazable."
    assert payload["suggested_action"] == "Revisar evidencia."


def test_json_from_model_output_accepts_fenced_json():
    payload = _json_from_model_output(
        '```json\n{"justification": "Texto", "suggested_action": "Accion"}\n```'
    )

    assert payload["justification"] == "Texto"
    assert payload["suggested_action"] == "Accion"
