"""Consistent error envelope: ``{"error": {"code", "message", "detail"}}``."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("synera.api")

_CODES = {400: "BAD_REQUEST", 404: "NOT_FOUND", 409: "CONFLICT", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED", 503: "UNAVAILABLE"}


def _body(status: int, message: str, detail=None) -> dict:
    return {"error": {"code": _CODES.get(status, "ERROR"), "message": message, "detail": detail}}


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        return JSONResponse(_body(exc.status_code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exc(request: Request, exc: RequestValidationError):
        return JSONResponse(_body(422, "Request validation failed", exc.errors()), status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "-")
        logger.exception("unhandled error [%s] %s %s", rid, request.method, request.url.path)
        return JSONResponse(_body(500, "Internal server error", {"request_id": rid}), status_code=500)
