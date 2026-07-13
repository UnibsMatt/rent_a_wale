"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.routers import admin, auth, credits, deployments, health, templates, users

log = get_logger("app")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("startup", environment=settings.environment, domain=settings.platform_domain)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rent-a-Whale API",
        version="1.0.0",
        description=(
            "Container rental platform: deploy Docker images or Compose stacks, "
            "pay with credits, get a public URL."
        ),
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # bearer tokens, not cookies — CSRF-immune by design
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    for router in (
        auth.router, users.router, credits.router,
        deployments.router, templates.router, admin.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
