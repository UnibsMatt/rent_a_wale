"""Deterministic names and labels for every Docker object we create.

All platform-managed objects carry MANAGED_LABEL so the reconciler and admin tooling
select by label, never by name pattern."""

from __future__ import annotations

MANAGED_LABEL = "raw.managed"
DEPLOYMENT_LABEL = "raw.deployment_id"
SERVICE_LABEL = "raw.service"
OWNER_LABEL = "raw.owner_ns"


def short_id(deployment_id: str) -> str:
    return deployment_id.replace("-", "")[:12]


def network_name(deployment_id: str) -> str:
    return f"raw_dep_{short_id(deployment_id)}"


def volume_name(deployment_id: str, name: str) -> str:
    return f"raw_{short_id(deployment_id)}_{name}"


def container_name(owner_ns: str, slug: str, service: str, *, single: bool) -> str:
    # Single-container deployments: user12-myapp. Stacks: user12-myapp-db.
    return f"{owner_ns}-{slug}" if single else f"{owner_ns}-{slug}-{service}"


def base_labels(deployment_id: str, owner_ns: str) -> dict[str, str]:
    return {
        MANAGED_LABEL: "true",
        DEPLOYMENT_LABEL: deployment_id,
        OWNER_LABEL: owner_ns,
    }


def traefik_labels(deployment_id: str, slug: str, domain: str, port: int, tls: bool) -> dict[str, str]:
    router = f"dep-{short_id(deployment_id)}"
    labels = {
        "traefik.enable": "true",
        "traefik.docker.network": "raw_ingress",
        f"traefik.http.routers.{router}.rule": f"Host(`{slug}.{domain}`)",
        f"traefik.http.services.{router}.loadbalancer.server.port": str(port),
    }
    if tls:
        labels[f"traefik.http.routers.{router}.entrypoints"] = "websecure"
        labels[f"traefik.http.routers.{router}.tls.certresolver"] = "letsencrypt"
    else:
        labels[f"traefik.http.routers.{router}.entrypoints"] = "web"
    return labels
