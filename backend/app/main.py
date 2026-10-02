"""FastAPI entry point for the SYNERA Web Intelligence Platform."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from synera_core.config import get_settings

app = FastAPI(
    title="SYNERA Web Intelligence API",
    description="Backend API supporting interaction discovery, provenance ledger verification, and decision support.",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Root metadata endpoint."""
    return {
        "service": "SYNERA Intelligence Platform",
        "status": "operational",
        "version": "0.1.0",
    }


@app.get("/api/v1/health")
def health_check():
    """Health status and configuration verification."""
    settings = get_settings()
    return {
        "status": "healthy",
        "global_seed": settings.seeds.global_seed,
        "alpha": settings.alpha,
        "repo_root": str(settings.repo_root),
    }
