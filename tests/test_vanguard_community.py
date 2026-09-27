import pytest

import server


@pytest.fixture
def community_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATABASE_PATH", str(tmp_path / "community.db"))
    server.app.config.update(TESTING=True)
    server.init_db()
    with server.app.app_context():
        now = server.timestamp()
        for name, email in (
            ("Admin User", "admin-test@example.com"),
            ("User A", "a@example.com"),
            ("User B", "b@example.com"),
        ):
            server.execute(
                """
                INSERT INTO hub_members (
                    full_name, email, password_hash, user_type, industry_track,
                    membership_tier, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, email, server.hash_password("password123"), "PROFESSIONAL", "General", "FULL_ACCESS", now, now),
            )
        server.execute(
            "INSERT INTO admins (full_name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("Admin User", "admin-test@example.com", server.hash_password("adminpassword"), now),
        )
        ids = {row["email"]: row["id"] for row in server.fetch_all("SELECT id, email FROM hub_members")}
        admin_id = server.fetch_one("SELECT id FROM admins WHERE email = ?", ("admin-test@example.com",))["id"]

    def client(member_id=None, admin_id=None):
        test_client = server.app.test_client()
        with test_client.session_transaction() as session:
            if member_id:
                session["hub_member_id"] = member_id
            if admin_id:
                session["admin_id"] = admin_id
        return test_client

    return {
        "admin": client(ids["admin-test@example.com"], admin_id),
        "a": client(ids["a@example.com"]),
        "b": client(ids["b@example.com"]),
        "ids": ids,
    }


def test_community_post_reply_visibility_and_ownership(community_clients):
    user_a = community_clients["a"]
    user_b = community_clients["b"]
    created = user_a.post("/community/posts", json={"content": "How is the market today?"})
    assert created.status_code == 201
    post_id = created.get_json()["post"]["id"]

    assert user_b.get("/community/posts").get_json()["total"] == 1
    assert user_b.post(f"/community/posts/{post_id}/replies", json={"content": "Looking strong."}).status_code == 201
    thread = user_a.get(f"/community/posts/{post_id}").get_json()["post"]
    assert thread["reply_count"] == 1
    assert thread["replies"][0]["content"] == "Looking strong."
    assert user_b.patch(f"/community/posts/{post_id}", json={"content": "Not allowed"}).status_code == 403


def test_community_moderator_badge_and_permissions(community_clients):
    admin = community_clients["admin"]
    user_a = community_clients["a"]
    user_b = community_clients["b"]
    user_b_id = community_clients["ids"]["b@example.com"]
    post_id = user_b.post("/community/posts", json={"content": "A community post"}).get_json()["post"]["id"]

    assert user_a.post(f"/community/moderators/{user_b_id}").status_code == 302
    assert admin.post(f"/community/moderators/{user_b_id}").status_code == 201
    assert user_a.get(f"/community/posts/{post_id}").get_json()["post"]["author"]["is_moderator"] is True
    assert user_b.post(f"/community/moderators/{community_clients['ids']['a@example.com']}").status_code == 302
    assert admin.delete(f"/community/moderators/{user_b_id}").status_code == 200


def test_community_reports_search_pagination_and_soft_delete(community_clients):
    user_a = community_clients["a"]
    user_b = community_clients["b"]
    post_id = user_a.post("/community/posts", json={"content": "Searchable Nigerian community update"}).get_json()["post"]["id"]
    assert user_b.get("/community/posts?q=Nigerian&limit=1").get_json()["total"] == 1
    assert user_b.post("/community/reports", json={"post_id": post_id, "reason": "Spam"}).status_code == 201
    assert user_a.delete(f"/community/posts/{post_id}").status_code == 200
    assert user_b.get("/community/posts").get_json()["total"] == 0


def test_admin_is_identified_as_moderator_without_badge(community_clients):
    admin = community_clients["admin"]
    user_a = community_clients["a"]
    admin_post = admin.post("/community/posts", json={"content": "Admin announcement"})
    assert admin_post.status_code == 201
    post_id = admin_post.get_json()["post"]["id"]
    assert user_a.get(f"/community/posts/{post_id}").get_json()["post"]["author"]["is_moderator"] is True
