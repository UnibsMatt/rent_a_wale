"""Pricing engine. All formulas run on Decimal from a plan *snapshot* (plain dict of
strings), so estimation, deployment-time freezing, and the billing tick are guaranteed
to price identically."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

QUANT = Decimal("0.0001")
HOURS_PER_DAY = Decimal("24")
HOURS_PER_MONTH = Decimal("720")


def hourly_cost(
    snapshot: dict,
    *,
    cpu_cores: Decimal,
    memory_mb: int,
    storage_gb: int,
    service_count: int = 1,
) -> Decimal:
    base = Decimal(snapshot["base_cost_per_hour"])
    cpu_price = Decimal(snapshot["cpu_cost_per_core_hour"])
    mem_price = Decimal(snapshot["memory_cost_per_gb_hour"])
    storage_price = Decimal(snapshot["storage_cost_per_gb_hour"])
    service_price = Decimal(snapshot["service_cost_per_hour"])

    memory_gb = Decimal(memory_mb) / Decimal("1024")
    extra_services = max(0, service_count - 1)

    cost = (
        base
        + cpu_price * Decimal(cpu_cores)
        + mem_price * memory_gb
        + storage_price * Decimal(storage_gb)
        + service_price * Decimal(extra_services)
    )
    return cost.quantize(QUANT, rounding=ROUND_HALF_UP)


def cost_breakdown(
    snapshot: dict,
    *,
    cpu_cores: Decimal,
    memory_mb: int,
    storage_gb: int,
    service_count: int = 1,
) -> dict[str, str]:
    memory_gb = Decimal(memory_mb) / Decimal("1024")
    return {
        "base": str(Decimal(snapshot["base_cost_per_hour"]).quantize(QUANT)),
        "cpu": str((Decimal(snapshot["cpu_cost_per_core_hour"]) * Decimal(cpu_cores)).quantize(QUANT)),
        "memory": str((Decimal(snapshot["memory_cost_per_gb_hour"]) * memory_gb).quantize(QUANT)),
        "storage": str(
            (Decimal(snapshot["storage_cost_per_gb_hour"]) * Decimal(storage_gb)).quantize(QUANT)
        ),
        "extra_services": str(
            (Decimal(snapshot["service_cost_per_hour"]) * Decimal(max(0, service_count - 1))).quantize(QUANT)
        ),
    }


def period_cost(hourly: Decimal, period_seconds: int) -> Decimal:
    return (hourly * Decimal(period_seconds) / Decimal("3600")).quantize(
        QUANT, rounding=ROUND_HALF_UP
    )
