"""Compose interpreter: supported subset parsing + security rejections."""

from __future__ import annotations

from decimal import Decimal

from app.providers.docker.compose_interpreter import parse_compose

VALID_STACK = """
services:
  web:
    image: nginx:1.27
    ports: ["8080:80"]
    depends_on: [db]
    environment:
      APP_ENV: production
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
  db:
    image: postgres:16
    environment:
      - POSTGRES_PASSWORD=example
    volumes:
      - dbdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 5s
volumes:
  dbdata: {}
"""


def test_valid_stack_parses():
    parsed = parse_compose(VALID_STACK)
    assert parsed.valid, parsed.errors
    assert {s.name for s in parsed.services} == {"web", "db"}

    web = next(s for s in parsed.services if s.name == "web")
    assert web.is_web and web.internal_port == 80  # container-side port only
    assert web.cpu_cores == Decimal("0.5")
    assert web.memory_mb == 256
    assert web.depends_on == ["db"]

    db = next(s for s in parsed.services if s.name == "db")
    assert db.volumes == [("dbdata", "/var/lib/postgresql/data")]
    assert db.healthcheck is not None and db.healthcheck.interval_s == 5
    assert parsed.total_cpu == Decimal("1.0")  # 0.5 + default 0.5


def _errors_of(yaml_text: str) -> str:
    parsed = parse_compose(yaml_text)
    assert not parsed.valid
    return "\n".join(parsed.errors)


def test_privileged_rejected():
    errors = _errors_of("services:\n  app:\n    image: nginx\n    privileged: true\n")
    assert "forbidden" in errors and "privileged" in errors


def test_host_network_rejected():
    errors = _errors_of("services:\n  app:\n    image: nginx\n    network_mode: host\n")
    assert "network_mode" in errors


def test_docker_socket_mount_rejected():
    errors = _errors_of(
        "services:\n  app:\n    image: nginx\n"
        "    volumes:\n      - /var/run/docker.sock:/var/run/docker.sock\n"
    )
    assert "docker.sock" in errors.lower() or "bind mount" in errors.lower()


def test_bind_mount_rejected():
    errors = _errors_of(
        "services:\n  app:\n    image: nginx\n    volumes:\n      - /etc:/host-etc\n"
    )
    assert "bind mount" in errors.lower()


def test_capabilities_rejected():
    errors = _errors_of(
        "services:\n  app:\n    image: nginx\n    cap_add:\n      - SYS_ADMIN\n"
    )
    assert "cap_add" in errors


def test_build_rejected():
    errors = _errors_of("services:\n  app:\n    build: .\n")
    assert "build" in errors


def test_unknown_keys_rejected_not_ignored():
    errors = _errors_of(
        "services:\n  app:\n    image: nginx\n    mystery_key: 42\n"
    )
    assert "mystery_key" in errors


def test_env_interpolation_rejected():
    errors = _errors_of(
        "services:\n  app:\n    image: nginx\n    environment:\n      TOKEN: ${HOST_SECRET}\n"
    )
    assert "interpolation" in errors


def test_dependency_cycle_rejected():
    errors = _errors_of(
        "services:\n"
        "  a:\n    image: nginx\n    depends_on: [b]\n"
        "  b:\n    image: nginx\n    depends_on: [a]\n"
    )
    assert "cycle" in errors.lower()


def test_unknown_dependency_rejected():
    errors = _errors_of(
        "services:\n  a:\n    image: nginx\n    depends_on: [ghost]\n"
    )
    assert "unknown service" in errors


def test_too_many_services_rejected():
    services = "\n".join(f"  svc{i}:\n    image: nginx" for i in range(11))
    errors = _errors_of(f"services:\n{services}\n")
    assert "Too many services" in errors


def test_web_election_override():
    parsed = parse_compose(
        "x-raw-web: api\n"
        "services:\n"
        "  front:\n    image: nginx\n    ports: [\"80\"]\n"
        "  api:\n    image: node\n    ports: [\"3000\"]\n"
    )
    assert parsed.valid, parsed.errors
    web = [s.name for s in parsed.services if s.is_web]
    assert web == ["api"]


def test_compose_validate_endpoint_flags_blocked_image(client, db, user_headers):
    from app.models import ImageRule
    from app.models.enums import ImageRuleMode

    db.add(ImageRule(pattern="evil/miner", mode=ImageRuleMode.BLOCK, reason="cryptominer"))
    db.commit()

    response = client.post(
        "/api/v1/deployments/compose/validate",
        json={"compose_yaml": "services:\n  app:\n    image: evil/miner:latest\n"},
        headers=user_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any("blocked" in e for e in body["errors"])
