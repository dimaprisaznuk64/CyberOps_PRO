from __future__ import annotations

from email.message import EmailMessage
from typing import ClassVar

import pytest
from app.models.notification import (
    CHANNEL_EMAIL,
    CHANNEL_TELEGRAM,
    CHANNEL_WEB,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    STATUS_SKIPPED,
    Notification,
)
from app.models.user import User
from app.services import notifications as notify

from tests.conftest import login
from tests.test_findings import _user_id


@pytest.fixture
def email_enabled(monkeypatch):
    monkeypatch.setattr(notify.settings, "notifications_enabled", True)
    monkeypatch.setattr(notify.settings, "smtp_enabled", True)
    monkeypatch.setattr(notify.settings, "smtp_host", "smtp.test.local")
    monkeypatch.setattr(notify.settings, "smtp_user", "mailer")
    monkeypatch.setattr(notify.settings, "smtp_password", "secret")


@pytest.fixture
def telegram_enabled(monkeypatch):
    monkeypatch.setattr(notify.settings, "notifications_enabled", True)
    monkeypatch.setattr(notify.settings, "telegram_enabled", True)
    monkeypatch.setattr(notify.settings, "telegram_bot_token", "123:ABC")
    monkeypatch.setattr(notify.settings, "telegram_chat_id", "-100500")


def _prefs(**kwargs) -> notify.ChannelPrefs:
    base = {
        "email": "sec@example.com",
        "telegram_chat_id": "-100777",
        "notify_email": True,
        "notify_telegram": True,
        "notify_min_severity": None,
    }
    base.update(kwargs)
    return notify.ChannelPrefs(**base)


# --- поріг важливості -------------------------------------------------------


def test_effective_threshold_server_is_a_floor(monkeypatch):
    monkeypatch.setattr(notify.settings, "notify_min_severity", "high")

    # користувач не може послабити серверну політику
    assert notify.effective_threshold(None) == "high"
    assert notify.effective_threshold("medium") == "high"
    # але може зробити суворіше
    assert notify.effective_threshold("critical") == "critical"


def test_effective_threshold_ignores_garbage(monkeypatch):
    monkeypatch.setattr(notify.settings, "notify_min_severity", "high")
    assert notify.effective_threshold("wtf") == "high"
    assert notify.effective_threshold("") == "high"


def test_is_severe_enough():
    assert notify.is_severe_enough("critical", "high")
    assert notify.is_severe_enough("high", "high")
    assert not notify.is_severe_enough("medium", "high")
    assert not notify.is_severe_enough(None, "high")


# --- fan-out ----------------------------------------------------------------


def test_low_severity_never_leaves_the_web(email_enabled, telegram_enabled):
    assert notify.resolve_channels("low", _prefs()) == []
    assert notify.resolve_channels(None, _prefs()) == []


def test_both_external_channels_for_critical(email_enabled, telegram_enabled):
    assert notify.resolve_channels("critical", _prefs()) == [
        (CHANNEL_EMAIL, "sec@example.com"),
        (CHANNEL_TELEGRAM, "-100777"),
    ]


def test_channel_disabled_on_server_is_skipped(email_enabled, monkeypatch):
    monkeypatch.setattr(notify.settings, "telegram_enabled", False)
    assert notify.resolve_channels("high", _prefs()) == [(CHANNEL_EMAIL, "sec@example.com")]


def test_global_kill_switch(monkeypatch, email_enabled, telegram_enabled):
    monkeypatch.setattr(notify.settings, "notifications_enabled", False)
    assert notify.resolve_channels("critical", _prefs()) == []


def test_user_toggle_and_missing_destination(email_enabled, telegram_enabled):
    assert notify.resolve_channels("high", _prefs(notify_email=False)) == [
        (CHANNEL_TELEGRAM, "-100777")
    ]
    assert notify.resolve_channels("high", _prefs(email="  ")) == [
        (CHANNEL_TELEGRAM, "-100777")
    ]


def test_falls_back_to_server_default_chat(telegram_enabled):
    prefs = _prefs(email=None, notify_email=False, telegram_chat_id=None)
    assert notify.resolve_channels("high", prefs) == [(CHANNEL_TELEGRAM, "-100500")]


def test_build_notifications_always_creates_web_row(email_enabled, telegram_enabled):
    rows = notify.build_notifications(
        user_id=7, scan_id=42, title="Скан завершено", body="risk 80", severity="high",
        prefs=_prefs(),
    )
    assert [r.channel for r in rows] == [CHANNEL_WEB, CHANNEL_EMAIL, CHANNEL_TELEGRAM]
    assert all(r.user_id == 7 and r.scan_id == 42 for r in rows)
    assert rows[0].status == STATUS_SENT
    assert [r.status for r in rows[1:]] == [STATUS_PENDING, STATUS_PENDING]
    assert rows[1].destination == "sec@example.com"


# --- email-доставка ---------------------------------------------------------


class _FakeSMTP:
    sent: ClassVar[list[EmailMessage]] = []
    logins: ClassVar[list[tuple[str, str]]] = []
    starttls_used: ClassVar[bool] = False
    fail: ClassVar[bool] = False

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout

    def ehlo(self):
        return 250, b"ok"

    def starttls(self):
        type(self).starttls_used = True

    def login(self, user, password):
        type(self).logins.append((user, password))

    def send_message(self, message, to_addrs=None):
        if type(self).fail:
            raise OSError("connection refused")
        type(self).sent.append(message)

    def quit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fake_smtp(monkeypatch):
    _FakeSMTP.sent = []
    _FakeSMTP.logins = []
    _FakeSMTP.starttls_used = False
    _FakeSMTP.fail = False
    monkeypatch.setattr(notify.smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP


def _email_row(**kwargs) -> Notification:
    data = {
        "id": 11,
        "user_id": 7,
        "scan_id": 42,
        "title": "Виявлено знахідки високої важливості",
        "body": "Telnet з відкритим паролем",
        "severity": "critical",
        "channel": CHANNEL_EMAIL,
        "destination": "sec@example.com",
        "status": STATUS_PENDING,
    }
    data.update(kwargs)
    return Notification(**data)


async def test_send_email_success(email_enabled, fake_smtp):
    result = await notify.deliver(_email_row())

    assert result.status == STATUS_SENT
    assert result.error is None
    assert len(fake_smtp.sent) == 1
    message = fake_smtp.sent[0]
    assert message["To"] == "sec@example.com"
    assert "CyberOps" in message["Subject"]
    assert "КРИТИЧНИЙ" in message["Subject"]
    assert message["From"].endswith("<cyberops@localhost>")
    assert "Telnet" in message.get_body(("plain",)).get_content()
    assert fake_smtp.starttls_used is True
    assert fake_smtp.logins == [("mailer", "secret")]


async def test_send_email_html_part_and_scan_link(email_enabled, fake_smtp, monkeypatch):
    monkeypatch.setattr(notify.settings, "app_base_url", "http://cyberops.test/")
    await notify.deliver(_email_row())

    html_part = fake_smtp.sent[0].get_body(("html",)).get_content()
    assert "http://cyberops.test/scans/42" in html_part
    assert "КРИТИЧНИЙ" in html_part


async def test_send_email_failure_is_recorded(email_enabled, fake_smtp):
    fake_smtp.fail = True
    result = await notify.deliver(_email_row())

    assert result.status == STATUS_FAILED
    assert "connection refused" in result.error
    assert len(result.error) <= 500


async def test_email_without_destination_is_skipped(email_enabled):
    result = await notify.deliver(_email_row(destination=None))
    assert result.status == STATUS_SKIPPED
    assert "адреси" in result.error


async def test_email_when_server_disabled_is_skipped(monkeypatch, fake_smtp):
    monkeypatch.setattr(notify.settings, "smtp_enabled", False)
    result = await notify.deliver(_email_row())

    assert result.status == STATUS_SKIPPED
    assert "вимкнено" in result.error
    assert fake_smtp.sent == []


# --- telegram-доставка ------------------------------------------------------


class _FakeTelegramClient:
    calls: ClassVar[list[tuple[str, dict]]] = []
    fail: ClassVar[bool] = False

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        type(self).calls.append((url, json))
        if type(self).fail:
            raise RuntimeError("telegram unreachable")
        return _FakeResponse()


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"ok": True}


@pytest.fixture
def fake_tg(monkeypatch):
    _FakeTelegramClient.calls = []
    _FakeTelegramClient.fail = False
    monkeypatch.setattr(notify.httpx, "AsyncClient", _FakeTelegramClient)
    return _FakeTelegramClient


def _tg_row(**kwargs) -> Notification:
    data = {
        "id": 12,
        "user_id": 7,
        "scan_id": 42,
        "title": "Сканування завершено",
        "body": "10.0.0.5 · tcp · ризик 80/100 (HIGH)",
        "severity": "high",
        "channel": CHANNEL_TELEGRAM,
        "destination": "-100777",
        "status": STATUS_PENDING,
    }
    data.update(kwargs)
    return Notification(**data)


async def test_send_telegram_success(telegram_enabled, fake_tg):
    result = await notify.deliver(_tg_row())

    assert result.status == STATUS_SENT
    url, payload = fake_tg.calls[0]
    assert url == "https://api.telegram.org/bot123:ABC/sendMessage"
    assert payload["chat_id"] == "-100777"
    assert payload["parse_mode"] == "HTML"
    assert "&lt;b&gt;" not in payload["text"]
    assert "<b>Сканування завершено</b>" in payload["text"]
    assert "ВИСОКИЙ" in payload["text"]


async def test_send_telegram_escapes_html(telegram_enabled, fake_tg):
    await notify.deliver(_tg_row(body="<script>alert(1)</script>"))
    assert "<script>" not in fake_tg.calls[0][1]["text"]
    assert "&lt;script&gt;" in fake_tg.calls[0][1]["text"]


async def test_send_telegram_truncates_long_body(telegram_enabled, fake_tg, monkeypatch):
    monkeypatch.setattr(notify.settings, "telegram_max_message_length", 200)
    await notify.deliver(_tg_row(body="A" * 5000))

    text = fake_tg.calls[0][1]["text"]
    assert len(text) < 200
    assert text.endswith("…")


async def test_send_telegram_failure_is_recorded(telegram_enabled, fake_tg):
    fake_tg.fail = True
    result = await notify.deliver(_tg_row())

    assert result.status == STATUS_FAILED
    assert "telegram unreachable" in result.error


async def test_telegram_without_token_is_skipped(monkeypatch, fake_tg):
    monkeypatch.setattr(notify.settings, "telegram_enabled", True)
    monkeypatch.setattr(notify.settings, "telegram_bot_token", "")
    result = await notify.deliver(_tg_row())

    assert result.status == STATUS_SKIPPED
    assert fake_tg.calls == []


async def test_deliver_ignores_web_channel(telegram_enabled):
    result = await notify.deliver(_tg_row(channel=CHANNEL_WEB))
    assert result.status == STATUS_SKIPPED
    assert "зовнішнім" in result.error


# --- API --------------------------------------------------------------------


async def test_preferences_roundtrip(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/notifications/preferences", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_available"] is False  # SMTP вимкнено за замовчуванням
    assert body["telegram_available"] is False
    assert body["server_min_severity"] == "high"
    assert body["notify_min_severity"] == "high"

    resp = await client.patch(
        "/api/v1/notifications/preferences",
        json={
            "email": "analyst@example.com",
            "telegram_chat_id": "-100999",
            "notify_telegram": False,
            "notify_min_severity": "critical",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "analyst@example.com"
    assert resp.json()["effective_min_severity"] == "critical"

    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.json()["email"] == "analyst@example.com"


async def test_preferences_rejects_unknown_severity(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.patch(
        "/api/v1/notifications/preferences",
        json={"notify_min_severity": "disastrous"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_preferences_rejects_taken_email(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    admin_id = await _user_id(session_factory, "admin")

    async with session_factory() as session:
        admin = await session.get(User, admin_id)
        assert admin is not None
        admin.email = "taken@example.com"
        await session.commit()

    resp = await client.patch(
        "/api/v1/notifications/preferences",
        json={"email": "taken@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert "зайнятий" in resp.json()["detail"]


async def test_list_notifications_filters_by_channel(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id(session_factory, "analyst")

    async with session_factory() as session:
        session.add_all(
            [
                Notification(user_id=user_id, title="web-подія", channel=CHANNEL_WEB),
                Notification(
                    user_id=user_id,
                    title="лист",
                    channel=CHANNEL_EMAIL,
                    destination="a@b.c",
                    status=STATUS_SENT,
                ),
            ]
        )
        await session.commit()

    resp = await client.get("/api/v1/notifications?channel=email", headers=headers)
    assert resp.status_code == 200
    titles = [n["title"] for n in resp.json()]
    assert titles == ["лист"]
    assert resp.json()[0]["destination"] == "a@b.c"

    resp = await client.get("/api/v1/notifications?channel=unknown", headers=headers)
    assert resp.status_code == 422


async def test_test_endpoint_requires_destination(client, email_enabled):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.post(
        "/api/v1/notifications/test",
        json={"channel": "email"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "email" in resp.json()["detail"]


async def test_test_endpoint_rejects_disabled_channel(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.post(
        "/api/v1/notifications/test",
        json={"channel": "telegram"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


async def test_test_endpoint_enqueues_delivery(client, notification_queue, email_enabled):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    await client.patch(
        "/api/v1/notifications/preferences",
        json={"email": "analyst@example.com"},
        headers=headers,
    )

    resp = await client.post(
        "/api/v1/notifications/test", json={"channel": "email"}, headers=headers
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["channel"] == "email"
    assert body["status"] == STATUS_PENDING
    assert body["destination"] == "analyst@example.com"
    assert notification_queue.calls == [body["id"]]

    resp = await client.get("/api/v1/notifications?channel=email", headers=headers)
    assert [n["id"] for n in resp.json()] == [body["id"]]


async def test_retry_resets_failed_notification(client, notification_queue, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id(session_factory, "analyst")

    async with session_factory() as session:
        row = Notification(
            user_id=user_id,
            title="лист",
            channel=CHANNEL_EMAIL,
            destination="a@b.c",
            status=STATUS_FAILED,
            error="SMTP: connection refused",
        )
        session.add(row)
        await session.commit()
        row_id = row.id

    resp = await client.post(f"/api/v1/notifications/{row_id}/retry", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == STATUS_PENDING
    assert resp.json()["error"] is None
    assert notification_queue.calls == [row_id]


async def test_retry_rejected_for_web_channel(client, notification_queue, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id(session_factory, "analyst")

    async with session_factory() as session:
        row = Notification(user_id=user_id, title="web", channel=CHANNEL_WEB)
        session.add(row)
        await session.commit()
        row_id = row.id

    resp = await client.post(f"/api/v1/notifications/{row_id}/retry", headers=headers)
    assert resp.status_code == 409
    assert notification_queue.calls == []


async def test_retry_of_foreign_notification_is_hidden(client, notification_queue, session_factory):
    await client.post(
        "/api/v1/auth/register", json={"username": "viewer9", "password": "password123"}
    )
    other_token = await login(client, "viewer9", "password123")
    user_id = await _user_id(session_factory, "analyst")

    async with session_factory() as session:
        row = Notification(
            user_id=user_id,
            title="чужий лист",
            channel=CHANNEL_EMAIL,
            destination="a@b.c",
            status=STATUS_FAILED,
        )
        session.add(row)
        await session.commit()
        row_id = row.id

    resp = await client.post(
        f"/api/v1/notifications/{row_id}/retry",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404
    assert notification_queue.calls == []
