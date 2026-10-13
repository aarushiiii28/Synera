import os
import sys
import time
import json
from pathlib import Path

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.database import migrate_db, get_session
from backend.app.db.models import Dataset, Run, Finding, SecurityReport
from synera_core.provenance.hashing import sha256_obj
from sqlmodel import select

def seed():
    migrate_db()
    with next(get_session()) as session:
        # 1. Seed Datasets
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

        # 2. Delete hand-seeded findings (e.g. find_123)
        old_findings = session.exec(select(Finding).where(Finding.id == "find_123")).all()
        for f in old_findings:
            session.delete(f)
        session.commit()

        # 3. Only seed findings from artifacts/results/*.json
        results_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "../artifacts/results")))
        if results_dir.exists():
            for p in results_dir.glob("*.json"):
                if p.name in ("benchmark.json", "osdr_genes.json"):
                    continue
                try:
                    with open(p, "r") as f_in:
                        data = json.load(f_in)
                        items = data if isinstance(data, list) else data.get("findings", [])
                        for item in items:
                            clean_dict = {
                                "v1": item.get("v1"),
                                "v2": item.get("v2"),
                                "dataset_id": item.get("dataset_id"),
                                "track": item.get("track", "Track B")
                            }
                            fid = sha256_obj(clean_dict)[:12]
                            if not session.get(Finding, fid):
                                finding_obj = Finding(
                                    id=fid,
                                    dataset_id=item.get("dataset_id", "env_panel"),
                                    v1=item.get("v1"),
                                    v2=item.get("v2"),
                                    interaction_type=item.get("interaction_type", "SYNERGISTIC"),
                                    status=item.get("status", "VALIDATED"),
                                    provenance=item.get("provenance", "SIMULATED"),
                                    q_value=item.get("q_value", 0.05),
                                    effect_size=item.get("effect_size", 0.0),
                                    stats=item.get("stats", {}),
                                    methods=item.get("methods", {}),
                                    replication=item.get("replication", {}),
                                    confidence=item.get("confidence", {}),
                                    history=item.get("history", [])
                                )
                                session.add(finding_obj)
                except Exception as e:
                    print(f"Error reading {p}: {e}")

        # 4. Seed SecurityReport
        if not session.exec(select(SecurityReport).where(SecurityReport.id == "sec_123")).first():
            sr = SecurityReport(
                id="sec_123", dataset_id="env_panel",
                false_alarm_rates={"isolation_forest": 0.0, "mcd": 1.0},
                checks=[{"name": "isolation_forest", "status": "PASS", "score": 0.0, "detail": ""}]
            )
            session.add(sr)
            
        session.commit()
        print("Database seeded successfully from artifacts/results/*.")

if __name__ == "__main__":
    seed()
