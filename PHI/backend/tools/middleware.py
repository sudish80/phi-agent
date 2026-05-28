"""Middleware — request timing, request ID, structured logging, error handler."""

import time
import uuid
import logging
import traceback
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        response.headers["X-Request-Time-Ms"] = f"{elapsed*1000:.1f}"
        if elapsed > 1:
            logger.warning(f"Slow request: {request.method} {request.url.path} took {elapsed:.2f}s")
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info(f"Logging configured at {level.upper()} level")


async def global_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__},
    )


class LogLevelMiddleware(BaseHTTPMiddleware):
    _current_level = "INFO"

    @classmethod
    def set_level(cls, level: str):
        level = level.upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            return False
        logging.getLogger().setLevel(getattr(logging, level))
        cls._current_level = level
        return True

    @classmethod
    def get_level(cls):
        return cls._current_level
