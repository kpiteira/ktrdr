"""Unit tests for TrainingService worker error message helpers."""

from ktrdr.api.services.training_service import (
    _build_worker_start_error_message,
    _extract_worker_http_error_detail,
)


class _DummyResponse:
    def __init__(self, *, payload=None, text: str = ""):
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_extract_worker_http_error_detail_prefers_json_detail():
    response = _DummyResponse(
        payload={"detail": "database auth failed"}, text="ignored"
    )

    detail = _extract_worker_http_error_detail(response)

    assert detail == "database auth failed"


def test_extract_worker_http_error_detail_falls_back_to_text():
    response = _DummyResponse(payload=ValueError("not json"), text="plain text error")

    detail = _extract_worker_http_error_detail(response)

    assert detail == "plain text error"


def test_build_worker_start_error_message_adds_1password_hint_for_db_auth():
    message = _build_worker_start_error_message(
        worker_id="training-worker-1",
        remote_url="http://host.docker.internal:5002",
        status_code=500,
        detail='password authentication failed for user "ktrdr"',
    )

    assert "HTTP 500" in message
    assert "training-worker-1" in message
    assert "kinfra local-prod start-training-host" in message
