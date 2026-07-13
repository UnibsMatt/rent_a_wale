"""Structured logging via structlog.

Three named channels share one JSON pipeline but are separable downstream:
  app.*      application logs
  audit      security-relevant actions (also persisted to the audit_logs table)
  billing    metering decisions
Docker container logs never pass through here — they are streamed from the engine.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level, logging.INFO),
    )
    # Silence noisy third-party loggers below WARNING.
    for noisy in ("uvicorn.access", "docker", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(channel: str = "app") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(channel).bind(channel=channel)
