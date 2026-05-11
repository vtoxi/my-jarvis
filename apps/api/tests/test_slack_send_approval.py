from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.slack_send_approval import mint_send_approval_token, verify_send_approval_token


def _test_settings() -> Settings:
    return Settings(
        slack_client_secret="unit-test-client-secret",
        slack_encryption_key="",
        slack_approval_secret="unit-approval-secret-for-hmac-tests",
    )


def test_mint_verify_roundtrip() -> None:
    s = _test_settings()
    text = "Exact message body for send."
    tok, exp = mint_send_approval_token(s, channel_id="C01234567", thread_ts="123.456", text=text)
    assert exp > 0
    p = verify_send_approval_token(s, token=tok, text=text)
    assert p.channel_id == "C01234567"
    assert p.thread_ts == "123.456"


def test_verify_rejects_text_change() -> None:
    s = _test_settings()
    tok, _ = mint_send_approval_token(s, channel_id="C1", thread_ts=None, text="alpha")
    try:
        verify_send_approval_token(s, token=tok, text="beta")
    except ValueError as e:
        assert "text_mismatch" in str(e) or str(e) == "text_mismatch"
    else:
        raise AssertionError("expected ValueError")


def test_slack_send_prepare_forbidden_when_write_disabled() -> None:
    from app.core.config import settings

    prev = settings.slack_write_enabled
    settings.slack_write_enabled = False
    try:
        with TestClient(create_app()) as client:
            res = client.post(
                "/slack/send/prepare",
                json={"channel_id": "C1", "thread_ts": None, "text": "hi"},
            )
            assert res.status_code == 403
    finally:
        settings.slack_write_enabled = prev
