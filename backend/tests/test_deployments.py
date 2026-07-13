"""Deployment API: creation gates (funds/quota/validation), lifecycle transitions,
authorization boundaries."""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.models.enums import DeploymentStatus

IMAGE_PAYLOAD = {
    "name": "my nginx",
    "kind": "image",
    "resources": {"cpu_cores": "1", "memory_mb": 2048, "storage_gb": 0},
    "image_spec": {
        "image": "nginx:1.27",
        "env": {"FOO": "bar"},
        "web_port": 80,
        "volumes": [],
        "restart_policy": "unless-stopped",
    },
}


def _create(client, headers, payload=None):
    body = {**IMAGE_PAYLOAD, **(payload or {})}
    body["resources"] = {**IMAGE_PAYLOAD["resources"], **(payload or {}).get("resources", {})}
    return client.post("/api/v1/deployments", json=body, headers=headers)


def test_create_image_deployment(client, pricing_plan, user_headers, captured_tasks):
    response = _create(client, user_headers)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert Decimal(body["estimated_hourly_cost"]) == Decimal("3.0000")  # 1 CPU + 2 GB
    assert body["slug"].startswith("my-nginx-")
    assert [s["service_name"] for s in body["services"]] == ["app"]

    provision_calls = [c for c in captured_tasks if c[0] == "provision"]
    assert provision_calls == [("provision", (body["id"],))]


def test_create_rejected_without_credits(client, pricing_plan, db, user_headers):
    # Drain the fixture account (100 credits) with an expensive request:
    # 8 CPU + 16 GB = 24/hr → fine; so use minimal balance user instead.
    from tests.conftest import login, make_user

    make_user(db, "poor@example.com", balance=Decimal("0.5"))
    headers = login(client, "poor@example.com")
    response = _create(client, headers)
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "insufficient_credits"


def test_create_rejected_over_quota(client, pricing_plan, db, user, user_headers):
    account = user.credit_account
    account.max_cpu_quota = Decimal("0.5")
    db.commit()
    response = _create(client, user_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "quota_exceeded"


def test_create_rejected_blocked_image(client, pricing_plan, db, user_headers):
    from app.models import ImageRule
    from app.models.enums import ImageRuleMode

    db.add(ImageRule(pattern="nginx", mode=ImageRuleMode.BLOCK, reason="testing"))
    db.commit()
    response = _create(client, user_headers)
    assert response.status_code == 422
    assert "blocked" in response.json()["error"]["message"]


def test_custom_hostname_conflict(client, pricing_plan, user_headers):
    assert _create(client, user_headers, {"hostname": "myapp"}).status_code == 202
    response = _create(client, user_headers, {"hostname": "myapp"})
    assert response.status_code == 409


def test_invalid_hostname_rejected(client, pricing_plan, user_headers):
    response = _create(client, user_headers, {"hostname": "Not_Valid!"})
    assert response.status_code == 422


def test_owner_isolation(client, pricing_plan, db, user_headers):
    from tests.conftest import login, make_user

    deployment_id = _create(client, user_headers).json()["id"]

    make_user(db, "other@example.com", balance=Decimal("100"))
    other_headers = login(client, "other@example.com")

    assert (
        client.get(f"/api/v1/deployments/{deployment_id}", headers=other_headers).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/deployments/{deployment_id}/stop", headers=other_headers
        ).status_code
        == 403
    )
    # Owner list does not leak to others.
    assert client.get("/api/v1/deployments", headers=other_headers).json() == []


def test_stop_only_from_running(client, pricing_plan, db, user_headers, captured_tasks):
    deployment_id = _create(client, user_headers).json()["id"]

    # pending → stop is a 409 (not running yet)
    response = client.post(f"/api/v1/deployments/{deployment_id}/stop", headers=user_headers)
    assert response.status_code == 409

    # Simulate the worker finishing provisioning.
    from app.models import Deployment

    deployment = db.get(Deployment, uuid.UUID(deployment_id))
    deployment.status = DeploymentStatus.RUNNING
    db.commit()

    response = client.post(f"/api/v1/deployments/{deployment_id}/stop", headers=user_headers)
    assert response.status_code == 202
    assert response.json()["status"] == "stopping"
    assert ("stop", (deployment_id,)) in captured_tasks


def test_start_blocked_after_exhaustion_without_topup(client, pricing_plan, db, user_headers):
    from app.models import Deployment

    deployment_id = _create(client, user_headers).json()["id"]
    deployment = db.get(Deployment, uuid.UUID(deployment_id))
    deployment.status = DeploymentStatus.CREDIT_EXHAUSTED
    from app.repositories.users import CreditAccountRepository

    acc = CreditAccountRepository(db).get_by_user(deployment.owner_id)
    acc.balance = Decimal("0")
    db.commit()

    response = client.post(f"/api/v1/deployments/{deployment_id}/start", headers=user_headers)
    assert response.status_code == 402


def test_delete_soft_deletes(client, pricing_plan, db, user_headers, captured_tasks):
    deployment_id = _create(client, user_headers).json()["id"]
    response = client.delete(f"/api/v1/deployments/{deployment_id}", headers=user_headers)
    assert response.status_code == 202
    assert response.json()["status"] == "deleting"
    assert ("delete", (deployment_id,)) in captured_tasks


def test_admin_can_stop_any(client, pricing_plan, db, user_headers, admin_headers):
    from app.models import Deployment

    deployment_id = _create(client, user_headers).json()["id"]
    deployment = db.get(Deployment, uuid.UUID(deployment_id))
    deployment.status = DeploymentStatus.RUNNING
    db.commit()

    response = client.post(
        f"/api/v1/admin/deployments/{deployment_id}/stop", headers=admin_headers
    )
    assert response.status_code == 202


def test_detail_masks_env_values(client, pricing_plan, user_headers):
    deployment_id = _create(client, user_headers).json()["id"]
    detail = client.get(f"/api/v1/deployments/{deployment_id}", headers=user_headers).json()
    env = detail["spec"]["services"][0]["env"]
    assert env == {"FOO": "•••"}  # keys visible, values never echoed back
