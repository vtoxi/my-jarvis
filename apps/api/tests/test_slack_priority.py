from __future__ import annotations

from app.schemas.slack import SlackChannelPrefs
from app.services.slack_priority_engine import rank_messages


def test_priority_keywords_boost() -> None:
    prefs = SlackChannelPrefs(
        priority_channel_ids=["C1"],
        priority_keywords=["urgent", "blocker"],
        vip_user_ids=["U99"],
    )
    rows = [
        {
            "channel_id": "C1",
            "channel_name": "eng",
            "user_id": "U1",
            "ts": "1",
            "text": "please review when you can",
            "channel_importance": 1.0,
            "channel_message_volume": 5,
        },
        {
            "channel_id": "C1",
            "channel_name": "eng",
            "user_id": "U99",
            "ts": "2",
            "text": "URGENT: blocker on deploy — need you now <@U123>",
            "channel_importance": 1.0,
            "channel_message_volume": 5,
        },
    ]
    ranked = rank_messages(rows, prefs)
    assert ranked[0].score >= ranked[1].score
    assert ranked[0].user_id == "U99"
    assert any("vip" in r or "keyword" in r for r in ranked[0].reasons)


def test_slack_status_disconnected() -> None:
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import create_app

    prev = settings.slack_write_enabled
    settings.slack_write_enabled = False
    try:
        with TestClient(create_app()) as client:
            res = client.get("/slack/status")
            assert res.status_code == 200
            body = res.json()
            assert body["connected"] is False
            assert body["phase"] == "4a_read"
            assert body["write_enabled"] is False
            assert "redirect_uri" in body
            assert body["redirect_uri"]
            assert body.get("redirect_uri_ok") is True
    finally:
        settings.slack_write_enabled = prev


def test_slack_channels_requires_connection() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as client:
        res = client.get("/slack/channels")
        assert res.status_code == 401


def test_slack_pkce_challenge_s256_rfc7636_appendix_b() -> None:
    from app.services.slack_service import slack_pkce_challenge_s256

    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert slack_pkce_challenge_s256(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_slack_bot_oauth_redirect_info_rejects_custom_scheme() -> None:
    from app.services.slack_service import slack_bot_oauth_redirect_info

    info = slack_bot_oauth_redirect_info("jarvis://slack/oauth")
    assert info.ok is False
    assert info.issue and "bot scopes" in info.issue.lower()


def test_slack_bot_oauth_redirect_info_accepts_loopback_http() -> None:
    from app.services.slack_service import slack_bot_oauth_redirect_info

    info = slack_bot_oauth_redirect_info("http://127.0.0.1:8000/slack/oauth/callback")
    assert info.ok is True
    assert info.issue is None
    assert info.note is None


def test_slack_bot_oauth_redirect_info_localhost_note() -> None:
    from app.services.slack_service import slack_bot_oauth_redirect_info

    info = slack_bot_oauth_redirect_info("http://localhost:8000/slack/oauth/callback")
    assert info.ok is True
    assert info.note and "localhost" in info.note


def test_slack_connect_redirect_includes_pkce() -> None:
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import create_app

    prev_id = settings.slack_client_id
    prev_sec = settings.slack_client_secret
    settings.slack_client_id = "test-client-id-for-pkce"
    settings.slack_client_secret = "test-client-secret-for-pkce"
    try:
        with TestClient(create_app()) as client:
            res = client.get("/slack/connect", follow_redirects=False)
            assert res.status_code == 302
            loc = res.headers["location"]
            assert "code_challenge=" in loc
            assert "code_challenge_method=S256" in loc
    finally:
        settings.slack_client_id = prev_id
        settings.slack_client_secret = prev_sec
