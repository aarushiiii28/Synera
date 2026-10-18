"""SYNERA Web Intelligence API."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Lets `uvicorn main:app` work when started from inside backend/app, where the repo root is not on the path.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlmodel import Session

from backend.app.api.router import api_router
from backend.app.core import errors
from backend.app.core.config import API_VERSION, cors_origins
from backend.app.core.deps import get_ledger
from backend.app.db.database import engine, migrate_db
from backend.app.services.persist import sync_datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("synera.backend")

TAGS = [
    {"name": "System", "description": "Service, database and ledger status."},
    {"name": "Ledger", "description": "Read-only signed, hash-chained evidence ledger with Merkle proofs."},
    {"name": "Datasets", "description": "Registered datasets with provenance tag (REAL / SIMULATED), hash and QC."},
    {"name": "Runs", "description": "Start the nine-step pipeline and stream its progress (SSE)."},
    {"name": "Findings", "description": "Candidate to verified findings, evidence bundles and the live VERIFIED gate."},
    {"name": "Interactions", "description": "Stressor-pair matrix and network from the latest run."},
    {"name": "Space Biology", "description": "Track A: real NASA OSDR radiation x unloading data."},
    {"name": "Scenario", "description": "Track C: effect of combined weather and air-pollution conditions on weekly deaths, learned from real US data."},
    {"name": "Benchmark", "description": "Engine report card (simulated) and experiment history."},
    {"name": "Security", "description": "Tamper simulator on temporary copies and detector reliability."},
    {"name": "Risk", "description": "Compound-risk brief from validated findings."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_db()
    ledger = get_ledger()
    v = ledger.verify()
    logger.info("ledger: height=%s chain_valid=%s", v["height"], v["valid"])
    with Session(engine) as s:
        sync_datasets(s, ledger)
    yield


app = FastAPI(title="SYNERA Web Intelligence API", version=API_VERSION, openapi_tags=TAGS, lifespan=lifespan,
              description="DISCOVER. VALIDATE. VERIFY. ACT. Every number is computed from data; simulated data is tagged SIMULATED end to end.")
app.add_middleware(GZipMiddleware, minimum_size=2000)
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=False, allow_methods=["GET", "POST"],
                   allow_headers=["*"], expose_headers=["x-request-id"])
errors.install(app)
app.include_router(api_router, prefix="/api/v1")
