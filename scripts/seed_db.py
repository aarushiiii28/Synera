import os
import sys
import time

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.database import migrate_db, get_session
from backend.app.db.models import Dataset, Run, Finding, SecurityReport
from sqlmodel import select

def seed():
    migrate_db()
    with next(get_session()) as session:
        # Seed Dataset
        if not session.exec(select(Dataset).where(Dataset.id == "env_panel")).first():
            ds = Dataset(
                id="env_panel", name="Environmental Stressor Panel",
                provenance="REAL", hash="a1b2c3d4", features_count=12,
                samples_count=518, created_at=time.time()
            )
            session.add(ds)
            
        if not session.exec(select(Dataset).where(Dataset.id == "osd-211-processed")).first():
            ds2 = Dataset(
                id="osd-211-processed", name="OSD-211 RNA-Seq",
                provenance="REAL", hash="b2c3d4e5", features_count=12000,
                samples_count=21, created_at=time.time()
            )
            session.add(ds2)

        # Seed SIMULATED Findings
        if not session.exec(select(Finding).where(Finding.id == "find_123")).first():
            f1 = Finding(
                id="find_123", dataset_id="env_panel",
                v1="heat_index", v2="pm25", interaction_type="SYNERGISTIC",
                status="VALIDATED", provenance="SIMULATED", q_value=0.001,
                effect_size=0.440,
                stats={"p_value": 0.0001}, methods={"discovery": "continuous"},
                replication={}, confidence={"score": 80}, history=[]
            )
            session.add(f1)
            
        # Seed SecurityReport
        if not session.exec(select(SecurityReport).where(SecurityReport.id == "sec_123")).first():
            sr = SecurityReport(
                id="sec_123", dataset_id="env_panel",
                false_alarm_rates={"isolation_forest": 0.0, "mcd": 1.0},
                checks=[{"name": "isolation_forest", "status": "PASS", "score": 0.0, "detail": ""}]
            )
            session.add(sr)
            
        session.commit()
        print("Database seeded successfully.")

if __name__ == "__main__":
    seed()
