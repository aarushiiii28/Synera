"""Background execution of pipeline runs. Events are persisted as they happen so SSE can replay and resume."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlmodel import Session, select
from synera_core.pipeline.orchestrator import config_hash, default_params, execute_run
from synera_core.pipeline.registry import ensure_benchmark_dataset, get_spec
from synera_core.provenance.hashing import sha256_file
from synera_core.provenance.ledger import Ledger

from backend.app.core.config import MAX_CONCURRENT_RUNS
from backend.app.db.database import engine
from backend.app.db.models import Run, RunEvent
from backend.app.services.persist import persist_run

logger = logging.getLogger("synera.runs")


class RunConflict(Exception):
    pass


class RunManager:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RUNS, thread_name_prefix="synera-run")

    def start(self, session: Session, ledger: Ledger, dataset_id: str, overrides: dict[str, Any], force: bool,
              inline: bool = False) -> tuple[str, bool]:
        """Create a run (or return an identical finished one). Returns ``(run_id, reused)``.

        ``inline=True`` executes in the calling thread (used by the seeding script and tests).
        """
        spec = get_spec(dataset_id)
        if not spec.runnable:
            raise ValueError(f"'{dataset_id}' has no outcome variable and cannot be analysed")
        if dataset_id == "benchmark_track_b":
            ensure_benchmark_dataset(ledger)
        params = {**default_params(dataset_id, quick=bool(overrides.pop("quick", False))), **overrides}
        chash = config_hash(dataset_id, params)
        dhash = sha256_file(spec.abs_path)
        if not force:
            done = session.exec(select(Run).where(Run.dataset_id == dataset_id, Run.config_hash == chash,
                                                  Run.dataset_hash == dhash, Run.status == "COMPLETED")
                                .order_by(Run.created_at.desc())).first()
            if done:
                return done.id, True
        busy = session.exec(select(Run).where(Run.dataset_id == dataset_id, Run.status == "RUNNING")).first()
        if busy:
            raise RunConflict(f"a run for '{dataset_id}' is already in progress ({busy.id})")
        run_id = f"run_{chash[:8]}_{int(time.time())}"
        session.add(Run(id=run_id, dataset_id=dataset_id, status="RUNNING", created_at=time.time(), config_hash=chash,
                        dataset_hash=dhash, params=params))
        session.commit()
        if inline:
            self._job(run_id, dataset_id, params)
        else:
            self.executor.submit(self._job, run_id, dataset_id, params)
        return run_id, False

    @staticmethod
    def _emit(ev: dict) -> None:
        with Session(engine) as s:
            s.add(RunEvent(run_id=ev["run_id"], step=ev["step"], step_name=ev["step_name"], label=ev.get("label", ""),
                           status=ev["status"], progress=ev["progress"], message=ev["message"], duration_s=ev.get("duration_s"),
                           ts=ev["ts"], data=ev.get("data") or {}))
            s.commit()

    def _job(self, run_id: str, dataset_id: str, params: dict) -> None:
        try:
            result = execute_run(dataset_id, params, emit=self._emit, run_id=run_id)
            with Session(engine) as s:
                persist_run(s, result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("run %s failed", run_id)
            with Session(engine) as s:
                run = s.get(Run, run_id)
                if run:
                    run.status, run.error, run.finished_at = "FAILED", f"{type(exc).__name__}: {exc}", time.time()
                    s.add(run)
                    s.commit()


manager = RunManager()
