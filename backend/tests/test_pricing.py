"""Pricing engine math + estimation endpoint."""

from __future__ import annotations

from decimal import Decimal

from app.billing.pricing import cost_breakdown, hourly_cost, period_cost

SNAPSHOT = {
    "plan_name": "default",
    "base_cost_per_hour": "0",
    "cpu_cost_per_core_hour": "1",
    "memory_cost_per_gb_hour": "1",
    "storage_cost_per_gb_hour": "0.05",
    "service_cost_per_hour": "0.25",
}


def test_reference_example_1cpu_2gb_is_3_per_hour():
    cost = hourly_cost(
        SNAPSHOT, cpu_cores=Decimal("1"), memory_mb=2048, storage_gb=0, service_count=1
    )
    assert cost == Decimal("3.0000")


def test_reference_example_2cpu_4gb_is_6_per_hour():
    cost = hourly_cost(
        SNAPSHOT, cpu_cores=Decimal("2"), memory_mb=4096, storage_gb=0, service_count=1
    )
    assert cost == Decimal("6.0000")


def test_extra_services_and_storage_priced():
    cost = hourly_cost(
        SNAPSHOT, cpu_cores=Decimal("1"), memory_mb=1024, storage_gb=10, service_count=3
    )
    # 1 cpu + 1 GB + 10*0.05 storage + 2*0.25 services = 3.0
    assert cost == Decimal("3.0000")


def test_period_cost_is_hourly_fraction():
    assert period_cost(Decimal("6"), 60) == Decimal("0.1000")
    assert period_cost(Decimal("6"), 3600) == Decimal("6.0000")


def test_breakdown_sums_to_hourly():
    breakdown = cost_breakdown(
        SNAPSHOT, cpu_cores=Decimal("2"), memory_mb=4096, storage_gb=20, service_count=2
    )
    total = sum(Decimal(v) for v in breakdown.values())
    assert total == hourly_cost(
        SNAPSHOT, cpu_cores=Decimal("2"), memory_mb=4096, storage_gb=20, service_count=2
    )


def test_estimate_endpoint(client, pricing_plan, user_headers):
    response = client.post(
        "/api/v1/deployments/estimate",
        json={
            "resources": {"cpu_cores": "2", "memory_mb": 4096, "storage_gb": 0},
            "service_count": 1,
        },
        headers=user_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["hourly"]) == Decimal("6.0000")
    assert Decimal(body["daily"]) == Decimal("144.0000")
    assert Decimal(body["monthly"]) == Decimal("4320.0000")
    assert body["plan_name"] == "default"


def test_estimate_without_active_plan_fails_cleanly(client, user_headers):
    response = client.post(
        "/api/v1/deployments/estimate",
        json={
            "resources": {"cpu_cores": "1", "memory_mb": 1024, "storage_gb": 1},
            "service_count": 1,
        },
        headers=user_headers,
    )
    assert response.status_code == 422
    assert "pricing" in response.json()["error"]["message"].lower()
