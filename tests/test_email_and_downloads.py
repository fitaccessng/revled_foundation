from pathlib import Path

import server


def test_blank_database_email_setting_uses_server_default(monkeypatch):
    monkeypatch.delenv("REVLED_EMAIL_PASSWORD", raising=False)
    monkeypatch.setattr(server, "get_app_setting", lambda setting_key, default="": "")

    assert server.resolve_runtime_value(
        "REVLED_EMAIL_PASSWORD",
        server.RUNTIME_DEFAULTS["REVLED_EMAIL_PASSWORD"],
    ) == server.RUNTIME_DEFAULTS["REVLED_EMAIL_PASSWORD"]


def test_volunteer_notifications_go_to_volunteers_mailbox(monkeypatch):
    sent = []

    def capture_email(recipient, subject, plain_text, html_text=None):
        sent.append((recipient, subject, plain_text, html_text))

    monkeypatch.setattr(server, "send_email_message", capture_email)
    application = {
        "full_name": "Volunteer User",
        "email": "volunteer@example.com",
        "phone": "08000000000",
        "involvement_type": "Open to either",
        "skill_area": "Digital Skills",
        "availability": ["Weekends"],
    }

    server.send_volunteer_submission_email("Vanguard", application)
    server.send_volunteer_submission_email("Catalyst", application)

    assert [message[0] for message in sent] == [
        "volunteers@revledfoundation.org",
        "volunteers@revledfoundation.org",
    ]
    assert sent[0][1] == "New Vanguard volunteer application"
    assert sent[1][1] == "New Catalyst volunteer application"


def test_welcome_email_uses_registered_recipient_and_attachment(tmp_path, monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["connection"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, message):
            sent["message"] = message

    welcome_kit = tmp_path / "welcome.pdf"
    welcome_kit.write_bytes(b"%PDF-test")
    monkeypatch.setattr(server.smtplib, "SMTP_SSL", FakeSMTP)

    with server.app.test_request_context("/"):
        server.send_trial_welcome_email(
            "Registered User",
            "registered@example.com",
            "2026-10-14 00:00:00",
            str(welcome_kit),
        )

    message = sent["message"]
    assert message["To"] == "registered@example.com"
    assert message["Subject"] == "Welcome to Revled Vanguard Hub"
    assert "Thank you so much for registering for Revled Vanguard" in message.get_body(preferencelist=("plain",)).get_content()
    assert "We're genuinely thrilled to have you with us" in message.get_body(preferencelist=("plain",)).get_content()
    assert "Warm regards" in message.get_body(preferencelist=("html",)).get_content()
    assert message.get_payload()[-1].get_filename() == "welcome.pdf"


def test_public_resource_download_returns_attachment(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "RESOURCE_UPLOAD_DIR", str(tmp_path))
    (tmp_path / "guide.pdf").write_bytes(b"public-resource")

    response = server.app.test_client().get("/downloads/resources/guide.pdf")

    assert response.status_code == 200
    assert response.data == b"public-resource"
    assert "attachment" in response.headers["Content-Disposition"]


def test_private_hub_resource_download_returns_attachment(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATABASE_PATH", str(tmp_path / "hub.db"))
    monkeypatch.setattr(server, "HUB_UPLOAD_DIR", str(tmp_path / "private"))
    server.app.config.update(TESTING=True)
    server.init_db()
    Path(server.HUB_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    with server.app.app_context():
        now = server.timestamp()
        server.execute(
            """
            INSERT INTO hub_members (full_name, email, password_hash, membership_tier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Download User", "download@example.com", server.hash_password("password123"), "FULL_ACCESS", now, now),
        )
        member_id = server.fetch_one("SELECT id FROM hub_members WHERE email = ?", ("download@example.com",))["id"]
        server.execute(
            """
            INSERT INTO hub_content (
                content_type, slug, title, summary, description, uploaded_file, uploaded_file_name,
                access_tier, is_published, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("resources", "download-test", "Download Test", "Summary", "Description", "stored.pdf", "Original Guide.pdf", "ALL", 1, now, now),
        )
        item_id = server.fetch_one("SELECT id FROM hub_content WHERE slug = ?", ("download-test",))["id"]

    (Path(server.HUB_UPLOAD_DIR) / "stored.pdf").write_bytes(b"private-resource")
    client = server.app.test_client()
    with client.session_transaction() as session:
        session["hub_member_id"] = member_id

    response = client.get(f"/hub/resources/{item_id}/download")

    assert response.status_code == 200
    assert response.data == b"private-resource"
    assert "Original Guide.pdf" in response.headers["Content-Disposition"]


def test_forgot_password_handles_email_failure_without_500(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATABASE_PATH", str(tmp_path / "hub.db"))
    server.app.config.update(TESTING=True)
    server.init_db()

    with server.app.app_context():
        now = server.timestamp()
        server.execute(
            """
            INSERT INTO hub_members (full_name, email, password_hash, membership_tier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Reset User", "reset@example.com", server.hash_password("password123"), "FULL_ACCESS", now, now),
        )

    def fail_to_send(*args, **kwargs):
        raise server.smtplib.SMTPAuthenticationError(535, b"Incorrect authentication data")

    monkeypatch.setattr(server, "send_email_message", fail_to_send)
    response = server.app.test_client().post(
        "/hub/forgot-password",
        data={"email": "reset@example.com"},
    )

    assert response.status_code == 200
    assert b"could not send the reset email" in response.data
    with server.app.app_context():
        assert server.fetch_one("SELECT COUNT(*) AS total FROM password_reset_tokens WHERE used_at IS NULL")["total"] == 0


def test_forgot_password_sends_reset_email_and_creates_token(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATABASE_PATH", str(tmp_path / "hub.db"))
    server.app.config.update(TESTING=True)
    server.init_db()

    with server.app.app_context():
        now = server.timestamp()
        server.execute(
            """
            INSERT INTO hub_members (full_name, email, password_hash, membership_tier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Reset User", "reset@example.com", server.hash_password("password123"), "FULL_ACCESS", now, now),
        )

    sent = {}

    def capture_email(recipient, subject, plain_text, html_text=None):
        sent.update(recipient=recipient, subject=subject, plain_text=plain_text, html_text=html_text)

    monkeypatch.setattr(server, "send_email_message", capture_email)
    response = server.app.test_client().post(
        "/hub/forgot-password",
        data={"email": "reset@example.com"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/hub/login")
    assert sent["recipient"] == "reset@example.com"
    assert "Reset your Revled Vanguard Hub password" == sent["subject"]
    assert "reset-password/" in sent["plain_text"]
    with server.app.app_context():
        token = server.fetch_one(
            "SELECT token FROM password_reset_tokens WHERE member_id = 1 AND used_at IS NULL"
        )
        assert token is not None
        assert token["token"] in sent["plain_text"]


def test_signup_sends_welcome_email_to_submitted_address(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATABASE_PATH", str(tmp_path / "hub.db"))
    server.app.config.update(TESTING=True)
    server.init_db()
    sent = {}

    def capture_welcome(full_name, email, trial_end_at, welcome_kit_path=None):
        sent.update(full_name=full_name, email=email, trial_end_at=trial_end_at)

    monkeypatch.setattr(server, "send_trial_welcome_email", capture_welcome)
    response = server.app.test_client().post(
        "/vanguard-hub/signup",
        data={
            "full_name": "New Member",
            "email": "new.member@example.com",
            "password": "password123",
            "user_type": "PROFESSIONAL",
            "plan": "trial",
        },
    )

    assert response.status_code == 302
    assert sent == {
        "full_name": "New Member",
        "email": "new.member@example.com",
        "trial_end_at": "",
    }


def test_free_membership_is_active_without_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATABASE_PATH", str(tmp_path / "hub.db"))
    server.app.config.update(TESTING=True)
    server.init_db()

    with server.app.app_context():
        reference, plan, _, trial_end = server.record_membership_subscription({
            "full_name": "Free Member",
            "email": "free@example.com",
            "password": "password123",
            "user_type": "PROFESSIONAL",
            "plan": "trial",
        })
        subscription = server.fetch_one(
            "SELECT status, trial_end_at FROM membership_subscriptions WHERE reference = ?",
            (reference,),
        )

    assert plan["name"] == "FREE VANGUARD ACCESS"
    assert trial_end == ""
    assert subscription["status"] == "active"
    assert subscription["trial_end_at"] == ""
