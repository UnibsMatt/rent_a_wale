"""Compose interpreter: parse + security-validate a docker-compose.yml and translate
it into provider `ServiceSpec`s. No `docker compose` CLI, no subprocess — the stack is
materialized through the Docker SDK exactly like single-image deployments.

Anything outside the supported subset is REJECTED with an explicit error, never
silently ignored: a user must know their `privileged: true` was refused, not believe
it was applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from graphlib import CycleError, TopologicalSorter

import yaml

from app.providers.base import HealthcheckSpec, ServiceSpec

MAX_SERVICES = 10
MAX_VOLUMES_PER_SERVICE = 8
MAX_PARSED_SIZE = 1_000_000  # anti YAML-bomb: cap on the expanded structure

SERVICE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
VOLUME_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DURATION_RE = re.compile(r"^(\d+)(ms|s|m|h)$")

# The full set of service keys we understand. Everything else is rejected.
ALLOWED_SERVICE_KEYS = {
    "image", "command", "entrypoint", "environment", "ports", "expose", "volumes",
    "depends_on", "restart", "healthcheck", "labels", "deploy", "working_dir", "user",
}
# Keys that are explicitly dangerous — called out with a security message.
FORBIDDEN_SERVICE_KEYS = {
    "privileged", "network_mode", "cap_add", "cap_drop", "devices", "pid", "ipc",
    "userns_mode", "security_opt", "sysctls", "cgroup_parent", "volumes_from",
    "build", "extends", "links", "external_links", "tmpfs", "extra_hosts", "dns",
    "stdin_open", "tty", "runtime", "platform", "init", "shm_size", "ulimits",
    "group_add", "device_cgroup_rules", "storage_opt", "credential_spec",
}
ALLOWED_TOP_LEVEL_KEYS = {"version", "services", "volumes", "name", "x-raw-web"}

RESTART_POLICIES = {"no", "always", "on-failure", "unless-stopped"}

DEFAULT_SERVICE_CPU = Decimal("0.5")
DEFAULT_SERVICE_MEMORY_MB = 512


@dataclass
class ParsedCompose:
    services: list[ServiceSpec] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def total_cpu(self) -> Decimal:
        return sum((s.cpu_cores for s in self.services), Decimal("0"))

    @property
    def total_memory_mb(self) -> int:
        return sum(s.memory_mb for s in self.services)


def _duration_to_seconds(value: object, default: int) -> int:
    if value is None:
        return default
    m = DURATION_RE.match(str(value).strip())
    if not m:
        return default
    n, unit = int(m.group(1)), m.group(2)
    return {"ms": max(1, n // 1000), "s": n, "m": n * 60, "h": n * 3600}[unit]


def _parse_memory(value: object) -> int | None:
    """'512M' / '1G' / '256m' / bytes int → MB."""
    if value is None:
        return None
    s = str(value).strip().lower()
    m = re.match(r"^(\d+(?:\.\d+)?)([kmg]?b?)$", s)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit.startswith("g"):
        return int(num * 1024)
    if unit.startswith("m"):
        return int(num)
    if unit.startswith("k"):
        return max(1, int(num / 1024))
    return max(1, int(num / (1024 * 1024)))  # raw bytes


def _parse_environment(raw: object, svc: str, errors: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    if raw is None:
        return env
    if isinstance(raw, dict):
        items = [(str(k), "" if v is None else str(v)) for k, v in raw.items()]
    elif isinstance(raw, list):
        items = []
        for entry in raw:
            key, _, value = str(entry).partition("=")
            items.append((key, value))
    else:
        errors.append(f"{svc}: environment must be a mapping or a list")
        return env
    for key, value in items:
        if not ENV_KEY_RE.match(key):
            errors.append(f"{svc}: invalid environment variable name {key!r}")
            continue
        if "${" in value:
            errors.append(
                f"{svc}: environment interpolation (${{...}}) is not supported — "
                "set explicit values"
            )
            continue
        env[key] = value
    return env


def _parse_ports(raw: object, svc: str, errors: list[str]) -> int | None:
    """Only the container-side port matters — nothing is ever published on the host.
    Returns the first container port (used for public routing)."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        errors.append(f"{svc}: ports must be a list")
        return None
    for entry in raw:
        if isinstance(entry, dict):  # long syntax
            target = entry.get("target")
            if isinstance(target, int) and 1 <= target <= 65535:
                return target
            errors.append(f"{svc}: invalid port mapping {entry!r}")
            return None
        parts = str(entry).split(":")
        candidate = parts[-1].split("/")[0]  # strip protocol
        if candidate.isdigit() and 1 <= int(candidate) <= 65535:
            return int(candidate)
        errors.append(f"{svc}: invalid port {entry!r}")
        return None
    return None


def _parse_volumes(raw: object, svc: str, errors: list[str]) -> list[tuple[str, str]]:
    """Named volumes only. Any bind-mount shape is a security rejection."""
    mounts: list[tuple[str, str]] = []
    if raw is None:
        return mounts
    if not isinstance(raw, list):
        errors.append(f"{svc}: volumes must be a list")
        return mounts
    if len(raw) > MAX_VOLUMES_PER_SERVICE:
        errors.append(f"{svc}: too many volumes (max {MAX_VOLUMES_PER_SERVICE})")
        return mounts
    for entry in raw:
        if isinstance(entry, dict):  # long syntax
            if entry.get("type") != "volume":
                errors.append(
                    f"{svc}: only named volumes are allowed (got type={entry.get('type')!r}) "
                    "— bind mounts are forbidden"
                )
                continue
            source, target = str(entry.get("source", "")), str(entry.get("target", ""))
        else:
            source, _, target = str(entry).partition(":")
            target = target.split(":")[0]  # strip mode suffix
        if "docker.sock" in source or "docker.sock" in target:
            errors.append(f"{svc}: mounting docker.sock is forbidden")
            continue
        if source.startswith(("/", ".", "~", "\\")) or not source:
            errors.append(
                f"{svc}: bind mount {source!r} is forbidden — use named volumes"
            )
            continue
        if not VOLUME_NAME_RE.match(source):
            errors.append(f"{svc}: invalid volume name {source!r}")
            continue
        if not target.startswith("/") or ".." in target:
            errors.append(f"{svc}: invalid mount path {target!r}")
            continue
        mounts.append((source, target))
    return mounts


def _parse_depends_on(raw: object, svc: str, errors: list[str]) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(d) for d in raw]
    if isinstance(raw, dict):
        deps = []
        for name, cond in raw.items():
            condition = (cond or {}).get("condition", "service_started") if isinstance(cond, dict) else "service_started"
            if condition not in ("service_started", "service_healthy"):
                errors.append(f"{svc}: unsupported depends_on condition {condition!r}")
            deps.append(str(name))
        return deps
    errors.append(f"{svc}: invalid depends_on")
    return []


def _parse_healthcheck(raw: object, svc: str, errors: list[str]) -> HealthcheckSpec | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append(f"{svc}: healthcheck must be a mapping")
        return None
    if raw.get("disable"):
        return None
    test = raw.get("test")
    if isinstance(test, str):
        test = ["CMD-SHELL", test]
    elif isinstance(test, list):
        test = [str(t) for t in test]
    else:
        errors.append(f"{svc}: healthcheck.test is required")
        return None
    return HealthcheckSpec(
        test=test,
        interval_s=_duration_to_seconds(raw.get("interval"), 10),
        timeout_s=_duration_to_seconds(raw.get("timeout"), 5),
        retries=int(raw.get("retries", 3)),
        start_period_s=_duration_to_seconds(raw.get("start_period"), 10),
    )


def _parse_deploy_limits(raw: object, svc: str, errors: list[str]) -> tuple[Decimal, int]:
    cpu, mem = DEFAULT_SERVICE_CPU, DEFAULT_SERVICE_MEMORY_MB
    if raw is None:
        return cpu, mem
    if not isinstance(raw, dict):
        errors.append(f"{svc}: deploy must be a mapping")
        return cpu, mem
    unknown = set(raw) - {"resources"}
    if unknown:
        errors.append(f"{svc}: unsupported deploy keys: {sorted(unknown)}")
    limits = ((raw.get("resources") or {}).get("limits") or {})
    if "cpus" in limits:
        try:
            cpu = Decimal(str(limits["cpus"]))
        except InvalidOperation:
            errors.append(f"{svc}: invalid deploy.resources.limits.cpus")
    if "memory" in limits:
        parsed = _parse_memory(limits["memory"])
        if parsed is None:
            errors.append(f"{svc}: invalid deploy.resources.limits.memory")
        else:
            mem = parsed
    return cpu, mem


def _validate_dependency_graph(services: list[ServiceSpec], errors: list[str]) -> None:
    names = {s.name for s in services}
    graph = {s.name: set(s.depends_on) for s in services}
    for svc in services:
        for dep in svc.depends_on:
            if dep not in names:
                errors.append(f"{svc.name}: depends_on references unknown service {dep!r}")
    try:
        tuple(TopologicalSorter(graph).static_order())
    except CycleError:
        errors.append("depends_on contains a cycle")


def parse_compose(yaml_text: str) -> ParsedCompose:
    result = ParsedCompose()
    err = result.errors

    try:
        doc = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        err.append(f"Invalid YAML: {exc}")
        return result
    if not isinstance(doc, dict):
        err.append("Compose file must be a YAML mapping")
        return result
    if len(repr(doc)) > MAX_PARSED_SIZE:
        err.append("Compose file expands to an unreasonably large structure")
        return result

    unknown_top = set(doc) - ALLOWED_TOP_LEVEL_KEYS
    if unknown_top:
        err.append(f"Unsupported top-level keys: {sorted(unknown_top)}")

    raw_services = doc.get("services")
    if not isinstance(raw_services, dict) or not raw_services:
        err.append("Compose file must define at least one service")
        return result
    if len(raw_services) > MAX_SERVICES:
        err.append(f"Too many services (max {MAX_SERVICES})")
        return result

    declared_volumes = doc.get("volumes") or {}
    if not isinstance(declared_volumes, dict):
        err.append("Top-level volumes must be a mapping")
        declared_volumes = {}
    for vol_name, vol_def in declared_volumes.items():
        if isinstance(vol_def, dict) and (vol_def.get("external") or vol_def.get("driver_opts")):
            err.append(f"volume {vol_name!r}: external volumes and driver_opts are forbidden")

    web_override = str(doc.get("x-raw-web", "")) or None

    for name, body in raw_services.items():
        svc_name = str(name)
        if not SERVICE_NAME_RE.match(svc_name):
            err.append(f"Invalid service name {svc_name!r}")
            continue
        if not isinstance(body, dict):
            err.append(f"{svc_name}: service definition must be a mapping")
            continue

        forbidden = set(body) & FORBIDDEN_SERVICE_KEYS
        if forbidden:
            err.append(
                f"{svc_name}: forbidden for security reasons: {sorted(forbidden)}"
            )
        unknown = set(body) - ALLOWED_SERVICE_KEYS - FORBIDDEN_SERVICE_KEYS
        if unknown:
            err.append(f"{svc_name}: unsupported keys: {sorted(unknown)}")

        image = body.get("image")
        if not isinstance(image, str) or not image:
            err.append(f"{svc_name}: image is required (build is not supported)")
            continue

        cpu, mem = _parse_deploy_limits(body.get("deploy"), svc_name, err)
        restart = str(body.get("restart", "unless-stopped"))
        if restart not in RESTART_POLICIES:
            err.append(f"{svc_name}: invalid restart policy {restart!r}")
            restart = "unless-stopped"

        port = _parse_ports(body.get("ports"), svc_name, err)
        if port is None and isinstance(body.get("expose"), list) and body["expose"]:
            first = str(body["expose"][0]).split("/")[0]
            if first.isdigit():
                port = int(first)

        result.services.append(
            ServiceSpec(
                name=svc_name,
                image=image.strip(),
                command=body.get("command"),
                entrypoint=body.get("entrypoint"),
                env=_parse_environment(body.get("environment"), svc_name, err),
                internal_port=port,
                volumes=_parse_volumes(body.get("volumes"), svc_name, err),
                depends_on=_parse_depends_on(body.get("depends_on"), svc_name, err),
                healthcheck=_parse_healthcheck(body.get("healthcheck"), svc_name, err),
                restart_policy=restart,
                cpu_cores=cpu,
                memory_mb=mem,
            )
        )

    _validate_dependency_graph(result.services, err)

    # Web service election: explicit x-raw-web wins, else first service with a port.
    web_candidates = [s for s in result.services if s.internal_port is not None]
    if web_override:
        chosen = next((s for s in result.services if s.name == web_override), None)
        if chosen is None:
            err.append(f"x-raw-web references unknown service {web_override!r}")
        elif chosen.internal_port is None:
            err.append(f"x-raw-web service {web_override!r} exposes no port")
        else:
            chosen.is_web = True
    elif web_candidates:
        web_candidates[0].is_web = True

    return result


def startup_order(services: list[ServiceSpec]) -> list[ServiceSpec]:
    by_name = {s.name: s for s in services}
    order = TopologicalSorter({s.name: set(s.depends_on) for s in services}).static_order()
    return [by_name[n] for n in order]
