from __future__ import annotations

import copy
import uuid

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from app.core.deps import AuthDep, DeploymentServiceDep
from app.core.rate_limit import deploy_limiter, read_limiter
from app.schemas.common import Message
from app.schemas.deployment import (
    ComposeValidateOut,
    ComposeValidateRequest,
    DeploymentCreate,
    DeploymentDetailOut,
    DeploymentEventOut,
    DeploymentLogLineOut,
    DeploymentOut,
    EstimateOut,
    EstimateRequest,
    ServiceStatsOut,
)

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.post("/estimate", response_model=EstimateOut, dependencies=[read_limiter])
def estimate(payload: EstimateRequest, ctx: AuthDep, service: DeploymentServiceDep) -> EstimateOut:
    return EstimateOut(**service.estimate(payload))


@router.post("/compose/validate", response_model=ComposeValidateOut, dependencies=[read_limiter])
def validate_compose(
    payload: ComposeValidateRequest, ctx: AuthDep, service: DeploymentServiceDep
) -> ComposeValidateOut:
    return ComposeValidateOut(**service.validate_compose(payload.compose_yaml))


@router.post(
    "", response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED, dependencies=[deploy_limiter],
)
def create(payload: DeploymentCreate, ctx: AuthDep, service: DeploymentServiceDep) -> DeploymentOut:
    deployment = service.create(user=ctx.user, payload=payload, ip=ctx.ip)
    return DeploymentOut.model_validate(deployment)


@router.get("", response_model=list[DeploymentOut], dependencies=[read_limiter])
def list_mine(ctx: AuthDep, service: DeploymentServiceDep) -> list[DeploymentOut]:
    return [DeploymentOut.model_validate(d) for d in service.list_for_user(ctx.user)]


@router.get("/{deployment_id}", response_model=DeploymentDetailOut, dependencies=[read_limiter])
def detail(
    deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep
) -> DeploymentDetailOut:
    deployment = service.get_authorized(user=ctx.user, deployment_id=deployment_id)
    out = DeploymentDetailOut.model_validate(deployment)
    out.total_credits_spent = service.total_spent(deployment.id)
    # Environment variables may hold user secrets — strip values from API output.
    # Deep-copy first: model_validate(from_attributes) shares the ORM row's dict.
    out.spec = copy.deepcopy(out.spec)
    for svc in out.spec.get("services", []):
        svc["env"] = {k: "•••" for k in svc.get("env", {})}
    return out


@router.get(
    "/{deployment_id}/stats", response_model=list[ServiceStatsOut], dependencies=[read_limiter]
)
def stats(
    deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep
) -> list[ServiceStatsOut]:
    return [
        ServiceStatsOut(
            service_name=s.name, cpu_percent=s.cpu_percent,
            memory_used_mb=s.memory_used_mb, memory_limit_mb=s.memory_limit_mb,
            network_rx_mb=s.network_rx_mb, network_tx_mb=s.network_tx_mb,
            status=s.status, restart_count=s.restart_count, healthy=s.healthy,
        )
        for s in service.stats(user=ctx.user, deployment_id=deployment_id)
    ]


@router.get("/{deployment_id}/logs", dependencies=[read_limiter])
def container_logs(
    deployment_id: uuid.UUID,
    ctx: AuthDep,
    service: DeploymentServiceDep,
    service_name: str | None = Query(default=None, alias="service"),
    tail: int = Query(default=200, ge=1, le=5000),
    follow: bool = Query(default=False),
) -> StreamingResponse:
    stream = service.container_logs(
        user=ctx.user, deployment_id=deployment_id,
        service=service_name, tail=tail, follow=follow,
    )
    return StreamingResponse(stream, media_type="text/plain; charset=utf-8")


@router.get(
    "/{deployment_id}/platform-logs",
    response_model=list[DeploymentLogLineOut],
    dependencies=[read_limiter],
)
def platform_logs(
    deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep
) -> list[DeploymentLogLineOut]:
    return [
        DeploymentLogLineOut.model_validate(line)
        for line in service.platform_logs(user=ctx.user, deployment_id=deployment_id)
    ]


@router.get(
    "/{deployment_id}/events",
    response_model=list[DeploymentEventOut],
    dependencies=[read_limiter],
)
def events(
    deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep
) -> list[DeploymentEventOut]:
    return [
        DeploymentEventOut.model_validate(e)
        for e in service.events(user=ctx.user, deployment_id=deployment_id)
    ]


@router.post(
    "/{deployment_id}/stop", response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED, dependencies=[deploy_limiter],
)
def stop(deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep) -> DeploymentOut:
    return DeploymentOut.model_validate(
        service.stop(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    )


@router.post(
    "/{deployment_id}/start", response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED, dependencies=[deploy_limiter],
)
def start(deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep) -> DeploymentOut:
    return DeploymentOut.model_validate(
        service.start(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    )


@router.post(
    "/{deployment_id}/restart", response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED, dependencies=[deploy_limiter],
)
def restart(deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep) -> DeploymentOut:
    return DeploymentOut.model_validate(
        service.restart(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    )


@router.post("/{deployment_id}/pause", response_model=Message, dependencies=[deploy_limiter])
def pause(deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep) -> Message:
    service.pause(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    return Message(message="Deployment paused (billing continues while resources are held)")


@router.post("/{deployment_id}/resume", response_model=Message, dependencies=[deploy_limiter])
def resume(deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep) -> Message:
    service.resume(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    return Message(message="Deployment resumed")


@router.delete(
    "/{deployment_id}", response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED, dependencies=[deploy_limiter],
)
def delete(deployment_id: uuid.UUID, ctx: AuthDep, service: DeploymentServiceDep) -> DeploymentOut:
    return DeploymentOut.model_validate(
        service.delete(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    )
