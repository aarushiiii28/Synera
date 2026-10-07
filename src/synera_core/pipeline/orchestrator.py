import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

class RunEvent:
    def __init__(self, run_id: str, step: int, status: str, progress: float, message: str):
        self.run_id = run_id
        self.step = step
        self.status = status
        self.progress = progress
        self.message = message
        self.ts = time.time()

class PipelineOrchestrator:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.events: Dict[str, List[RunEvent]] = {}
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Any] = {}
        
    def start_run(self, dataset_id: str, stressor_pairs: Any, methods: list, alpha: float, force: bool) -> str:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.events[run_id] = []
        self.runs[run_id] = {
            "dataset_id": dataset_id,
            "status": "RUNNING",
            "created_at": time.time()
        }
        self.executor.submit(self._execute_run, run_id, dataset_id, stressor_pairs, methods, alpha)
        return run_id
        
    def _emit(self, run_id: str, step: int, status: str, progress: float, message: str):
        ev = RunEvent(run_id, step, status, progress, message)
        self.events[run_id].append(ev)
        
    def get_events(self, run_id: str, after_ts: float = 0.0) -> List[RunEvent]:
        if run_id not in self.events:
            return []
        return [e for e in self.events[run_id] if e.ts > after_ts]
        
    def _execute_run(self, run_id: str, dataset_id: str, pairs: Any, methods: list, alpha: float):
        try:
            self._emit(run_id, 1, "LOAD_DATA", 0.1, "Loading and hash-checking dataset...")
            time.sleep(1) # simulate work
            
            self._emit(run_id, 2, "SECURITY_PRECHECK", 0.2, "Scanning dataset for anomalies...")
            time.sleep(1)
            
            self._emit(run_id, 3, "DISCOVERY", 0.4, "Running discovery methods...")
            time.sleep(1)
            
            self._emit(run_id, 4, "VALIDATION", 0.5, "Computing FDR, CIs, effect sizes...")
            time.sleep(1)
            
            self._emit(run_id, 5, "REPLICATION", 0.6, "Checking cross-study replication...")
            time.sleep(1)
            
            self._emit(run_id, 6, "PROVENANCE", 0.7, "Building run manifest and appending ledger block...")
            time.sleep(1)
            
            self._emit(run_id, 7, "SECURITY_POSTCHECK", 0.8, "Running post-discovery security checks...")
            time.sleep(1)
            
            self._emit(run_id, 8, "REPRODUCIBILITY_REPLAY", 0.9, "Replaying methods for exact match...")
            time.sleep(1)
            
            self._emit(run_id, 9, "FINALIZE", 1.0, "Assigning statuses and persisting findings...")
            time.sleep(1)
            
            self.runs[run_id]["status"] = "COMPLETED"
        except Exception as e:
            self.runs[run_id]["status"] = "FAILED"
            self._emit(run_id, -1, "ERROR", 1.0, str(e))

orchestrator = PipelineOrchestrator()
