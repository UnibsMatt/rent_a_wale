"""Credits: purchase idempotency, balance summary, admin adjustments."""

from __future__ import annotations

import uuid


def test_purchase_adds_balance(client, user, user_headers):
    response = client.post(
        "/api/v1/credits/purchase",
        json={"amount": "50", "idempotency_key": uuid.uuid4().hex},
        headers=user_headers,
    )
    assert response.status_code == 201
    tx = response.json()
    assert tx["kind"] == "purchase"
    assert float(tx["amount"]) == 50
    assert float(tx["balance_after"]) == 150  # fixture starts at 100

    balance = client.get("/api/v1/credits/balance", headers=user_headers).json()
    assert float(balance["balance"]) == 150


def test_purchase_is_idempotent(client, user_headers):
    key = uuid.uuid4().hex
    first = client.post(
        "/api/v1/credits/purchase",
        json={"amount": "25", "idempotency_key": key},
        headers=user_headers,
    ).json()
    second = client.post(
        "/api/v1/credits/purchase",
        json={"amount": "25", "idempotency_key": key},
        headers=user_headers,
    ).json()
    assert first["id"] == second["id"]

    balance = client.get("/api/v1/credits/balance", headers=user_headers).json()
    assert float(balance["balance"]) == 125  # charged exactly once


def test_purchase_rejects_bad_amounts(client, user_headers):
    for amount in ("0", "-5"):
        response = client.post(
            "/api/v1/credits/purchase",
            json={"amount": amount, "idempotency_key": uuid.uuid4().hex},
            headers=user_headers,
        )
        assert response.status_code == 422


def test_transactions_paginated(client, user_headers):
    for _ in range(3):
        client.post(
            "/api/v1/credits/purchase",
            json={"amount": "10", "idempotency_key": uuid.uuid4().hex},
            headers=user_headers,
        )
    page = client.get(
        "/api/v1/credits/transactions?page=1&page_size=2", headers=user_headers
    ).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2


def test_admin_adjust_credits(client, user, admin_headers, user_headers):
    response = client.post(
        f"/api/v1/admin/users/{user.id}/credits",
        json={"amount": "-30", "reason": "abuse refund clawback"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert float(response.json()["balance_after"]) == 70

    # Cannot push a balance below zero.
    response = client.post(
        f"/api/v1/admin/users/{user.id}/credits",
        json={"amount": "-1000", "reason": "too much"},
        headers=admin_headers,
    )
    assert response.status_code == 422


def test_adjust_requires_admin(client, user, user_headers):
    response = client.post(
        f"/api/v1/admin/users/{user.id}/credits",
        json={"amount": "1000", "reason": "self enrichment"},
        headers=user_headers,
    )
    assert response.status_code == 403
