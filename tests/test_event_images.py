from io import BytesIO
from pathlib import Path

import pytest

import server


@pytest.fixture

def event_image_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATABASE_PATH", str(tmp_path / "events.db"))
    monkeypatch.setattr(server, "EVENT_UPLOAD_DIR", str(tmp_path / "event-images"))
    server.app.config.update(TESTING=True)
    server.init_db()
    client = server.app.test_client()
    with client.session_transaction() as session:
        session["admin_id"] = 1
    return client


def test_admin_can_upload_event_image_and_edit_without_replacing_it(event_image_client):
    response = event_image_client.post(
        "/admin/events/new",
        data={
            "title": "Image Test Event",
            "slug": "image-test-event",
            "summary": "An event with an image.",
            "description": "Event details.",
            "location": "Lagos",
            "event_type": "Workshop",
            "program_slug": "",
            "start_date": "2099-10-01",
            "end_date": "",
            "booking_link": "",
            "registration_label": "Register",
            "seat_limit": "0",
            "requires_registration": "1",
            "is_published": "1",
            "image_upload": (BytesIO(b"event-image-bytes"), "event.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    with server.app.app_context():
        event = server.fetch_one("SELECT * FROM events WHERE slug = ?", ("image-test-event",))
        image_url = event["image_url"]
    image_path = Path(server.EVENT_UPLOAD_DIR) / image_url.rsplit("/", 1)[1]
    assert image_path.read_bytes() == b"event-image-bytes"

    for path in ("/events", "/events/image-test-event", "/"):
        page = event_image_client.get(path)
        assert page.status_code == 200
        assert image_url.encode() in page.data

    response = event_image_client.post(
        "/admin/events/1/edit",
        data={
            "title": "Image Test Event Updated",
            "slug": "image-test-event",
            "summary": "An updated event with an image.",
            "description": "Updated event details.",
            "location": "Lagos",
            "event_type": "Workshop",
            "program_slug": "",
            "start_date": "2099-10-01",
            "end_date": "",
            "booking_link": "",
            "registration_label": "Register",
            "seat_limit": "0",
            "requires_registration": "1",
            "is_published": "1",
        },
    )

    assert response.status_code == 302
    with server.app.app_context():
        event = server.fetch_one("SELECT image_url FROM events WHERE id = 1")
    assert event["image_url"] == image_url


def test_admin_rejects_unsupported_event_image(event_image_client):
    response = event_image_client.post(
        "/admin/events/new",
        data={
            "title": "Invalid Image Event",
            "slug": "invalid-image-event",
            "summary": "An event with an unsupported image.",
            "description": "Event details.",
            "location": "Lagos",
            "start_date": "2099-10-01",
            "image_upload": (BytesIO(b"not-an-image"), "event.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"event image file type is not supported" in response.data
    with server.app.app_context():
        event = server.fetch_one("SELECT id FROM events WHERE slug = ?", ("invalid-image-event",))
    assert event is None
