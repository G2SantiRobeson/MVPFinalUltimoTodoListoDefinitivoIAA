from datetime import datetime

from app.api.routes.health import health_check


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[object] = []

    def execute(self, statement: object) -> None:
        self.executed.append(statement)


def test_health_check_reports_database_contract():
    # Arrange
    db = FakeSession()

    # Act
    payload = health_check(db)

    # Assert
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert datetime.fromisoformat(payload["timestamp"])
    assert len(db.executed) == 1
