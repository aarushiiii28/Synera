"""API v1 router: composes the feature routers. Every endpoint has a response contract in docs/API_CONTRACT.md."""

from fastapi import APIRouter

from backend.app.api.v1 import benchmark, datasets, findings, india, interactions, live, risk, runs, scenario, security, space_biology, system

api_router = APIRouter()
for module in (system, datasets, runs, findings, interactions, space_biology, benchmark, security, risk, scenario, live, india):
    api_router.include_router(module.router)
