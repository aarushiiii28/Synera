"""Engine, versioned migration and session dependency for the application database.

The application database only holds *derived* state (runs, findings, reports) that can be rebuilt from the
datasets and the ledger by ``scripts/seed_db.py``. A schema-version mismatch therefore drops and recreates
the application tables; the ledger lives in its own database and is never touched here.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.core.config import DB_PATH
from backend.app.db.models import SCHEMA_VERSION, SchemaVersion

logger = logging.getLogger("synera.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False, "timeout": 30})

APP_TABLES = ["runevent", "run", "finding", "securityreport", "experimentsummary", "dataset", "schemaversion"]


def migrate_db() -> int:
    """Create tables; if the stored schema version differs, drop the derived tables and recreate them."""
    insp = inspect(engine)
    current = None
    if "schemaversion" in insp.get_table_names():
        with Session(engine) as s:
            row = s.exec(select(SchemaVersion)).first()
            current = row.version if row else None
    if current != SCHEMA_VERSION and insp.get_table_names():
        logger.info("schema %s -> %s: recreating derived tables", current, SCHEMA_VERSION)
        with engine.begin() as conn:
            for t in APP_TABLES:
                conn.execute(text(f'DROP TABLE IF EXISTS "{t}"'))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        if not s.exec(select(SchemaVersion)).first():
            s.add(SchemaVersion(version=SCHEMA_VERSION))
            s.commit()
    return SCHEMA_VERSION


def get_session():
    with Session(engine) as session:
        yield session
