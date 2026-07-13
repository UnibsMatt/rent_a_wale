"""Authentication flow tests: registration, login, refresh rotation + replay
detection, logout revocation, password change session invalidation."""

from __future__ import annotations

from tests.conftest import login


def test_register_creates_user_and_account(client, db):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "New.User@Example.com", "password": "averylongpassword"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"  # normalized
    assert body["role"] == "user"

    balance = client.post(
        "/api/v1/auth/login",
        json={"email": "new.user@example.com", "password": "averylongpassword"},
    )
    assert balance.status_code == 200


def test_register_duplicate_email_conflict(client):
    payload = {"email": "dup@example.com", "password": "averylongpassword"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_register_short_password_rejected(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "x@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_login_wrong_password_uniform_401(client, user):
    for email in (user.email, "nosuchuser@example.com"):
        response = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password!"}
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["error"]["message"]


def test_me_requires_token(client, user, user_headers):
    assert client.get("/api/v1/users/me").status_code == 401
    response = client.get("/api/v1/users/me", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_refresh_rotates_and_detects_replay(client, user):
    pair = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "s3cret-password"},
    ).json()

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["refresh_token"] != pair["refresh_token"]

    # Replaying the already-rotated token must revoke the whole session family.
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert replay.status_code == 401
    assert "reuse" in replay.json()["error"]["message"].lower()

    # The rotated descendant is dead too.
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert after.status_code == 401


def test_logout_revokes_access_and_refresh(client, user):
    pair = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "s3cret-password"},
    ).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    response = client.post(
        "/api/v1/auth/logout", json={"refresh_token": pair["refresh_token"]}, headers=headers
    )
    assert response.status_code == 200

    # Access token is denylisted immediately (before natural expiry).
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
    # Refresh token family is revoked.
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert refreshed.status_code == 401


def test_change_password_invalidates_sessions(client, user):
    headers = login(client, user.email)
    response = client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "s3cret-password", "new_password": "brand-new-password"},
        headers=headers,
    )
    assert response.status_code == 200

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "s3cret-password"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "brand-new-password"},
        ).status_code
        == 200
    )


def test_admin_route_forbidden_for_user(client, user_headers):
    response = client.get("/api/v1/admin/users", headers=user_headers)
    assert response.status_code == 403


def test_admin_route_allowed_for_admin(client, admin_headers):
    response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
