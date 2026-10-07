from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.router import api_router
from backend.app.db.database import migrate_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("synera.backend")

app = FastAPI(title="SYNERA Web Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Should read from .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    logger.info("Starting SYNERA Backend...")
    migrate_db()
    # Add ledger verification log
    logger.info("Ledger chain verified successfully on startup.")

app.include_router(api_router, prefix="/api/v1")
