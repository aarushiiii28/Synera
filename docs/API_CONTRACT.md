# SYNERA API Contract v1

This document specifies the exact JSON schemas for the FastAPI backend serving the Web Intelligence Platform frontend. All endpoints are prefixed with `/api/v1`.

## Core Conventions
- **Error Shape**: All `4xx` and `5xx` errors return:
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Invalid input provided.",
      "detail": "Field 'alpha' must be between 0 and 1."
    }
  }
  ```
- **Provenance Tags**: Objects like datasets and findings carry a `provenance` tag of either `"REAL"` or `"SIMULATED"`.
- **CORS**: Configured via `.env` to allow frontend access.

## 1. System & Ledger

### `GET /health`
Returns service status and cryptographic chain integrity.
**Response (200)**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "ledger": {
    "height": 42,
    "chain_valid": true
  }
}
```

### `GET /ledger/head`
Returns the latest block in the ledger.
**Response (200)**:
```json
{
  "index": 41,
  "timestamp": 1690000000.0,
  "block_type": "FINDING_VERIFIED",
  "prev_hash": "a1b2...",
  "merkle_root": "c3d4...",
  "payload_hash": "e5f6...",
  "signature": "g7h8..."
}
```

### `GET /ledger/blocks`
**Query Params**: `offset=0`, `limit=50`
**Response (200)**: Array of block objects.

### `GET /ledger/verify`
Triggers a full cryptographic walk of the chain.
**Response (200)**:
```json
{
  "valid": true,
  "blocks_checked": 42,
  "errors": []
}
```

### `GET /ledger/proof/{artifact_hash}`
**Response (200)**:
```json
{
  "artifact_hash": "a1b2...",
  "block_index": 12,
  "merkle_proof": [
    {"hash": "c3d4...", "position": "left"}
  ],
  "root": "e5f6...",
  "verified": true
}
```

## 2. Datasets

### `GET /datasets`
**Response (200)**:
```json
[
  {
    "id": "osd-211-processed",
    "name": "OSD-211 RNA-Seq",
    "provenance": "REAL",
    "hash": "a1b2...",
    "features_count": 12000,
    "samples_count": 21,
    "created_at": 1690000000.0
  }
]
```

### `GET /datasets/{id}`
**Response (200)**: Dataset object.

### `POST /datasets/{id}/verify`
Runs the IntegrityGuard check.
**Response (200)**:
```json
{
  "dataset_id": "osd-211-processed",
  "match": true,
  "expected_hash": "a1b2...",
  "actual_hash": "a1b2...",
  "alert_block_index": null
}
```

## 3. Orchestration & Runs

### `POST /runs`
**Request**:
```json
{
  "dataset_id": "osd-211-processed",
  "stressor_pairs": [["radiation", "hlu"]],
  "methods": ["continuous", "gbm"],
  "alpha": 0.05,
  "force": false
}
```
*Note*: `stressor_pairs` can be `"all"`.
**Response (202 Accepted)**:
```json
{
  "run_id": "run_123456"
}
```

### `GET /runs`
**Response (200)**:
```json
[
  {
    "run_id": "run_123456",
    "dataset_id": "osd-211-processed",
    "status": "COMPLETED",
    "created_at": 1690000000.0
  }
]
```

### `GET /runs/{id}`
**Response (200)**: Run object with details.

### `GET /runs/{id}/events`
Server-Sent Events (SSE) streaming progress.
**Stream Format**:
```text
data: {"run_id": "run_123456", "step": 3, "status": "DISCOVERY", "progress": 0.45, "message": "Fitting OLS...", "ts": 1690000000.0}
```

## 4. Findings

### `GET /findings`
**Query Params**: `status`, `track`, `type`, `q`, `sort`, `limit`, `offset`
**Response (200)**:
```json
{
  "total": 1,
  "items": [
    {
      "id": "find_123",
      "v1": "heat_index",
      "v2": "pm25",
      "interaction_type": "SYNERGISTIC",
      "status": "VALIDATED",
      "provenance": "SIMULATED",
      "q_value": 0.001,
      "effect_size": 0.52
    }
  ]
}
```

### `GET /findings/{id}`
**Response (200)**: Full evidence bundle including `stats`, `methods`, `replication`, and `confidence`.

### `POST /findings/{id}/verify`
Re-runs integrity, chain, and replay.
**Response (200)**:
```json
{
  "id": "find_123",
  "new_status": "VERIFIED",
  "reasons": ["Ledger valid", "Replay matched", "No security alerts"]
}
```

### `GET /findings/{id}/surface`
**Response (200)**:
```json
{
  "v1_grid": [0, 1, 2],
  "v2_grid": [0, 1, 2],
  "additive": [[0.0, 0.1, 0.2], [0.1, 0.2, 0.3], [0.2, 0.3, 0.4]],
  "observed": [[0.0, 0.1, 0.2], [0.1, 0.4, 0.6], [0.2, 0.6, 1.0]],
  "gap": [[0.0, 0.0, 0.0], [0.0, 0.2, 0.3], [0.0, 0.3, 0.6]]
}
```

### `GET /findings/{id}/forest`
**Response (200)**:
```json
{
  "studies": [
    {
      "name": "OSD-211",
      "effect": 0.52,
      "ci_lower": 0.4,
      "ci_upper": 0.64
    }
  ]
}
```

## 5. Interactions & Graphs

### `GET /interactions/matrix`
**Query Params**: `dataset_id`
**Response (200)**:
```json
{
  "matrix": [
    ["", "heat_index", "pm25"],
    ["heat_index", 0.0, 0.52],
    ["pm25", 0.52, 0.0]
  ],
  "types": [
    ["", "heat_index", "pm25"],
    ["heat_index", "", "SYNERGISTIC"],
    ["pm25", "SYNERGISTIC", ""]
  ]
}
```

### `GET /interactions/network`
**Query Params**: `dataset_id`
**Response (200)**:
```json
{
  "nodes": [{"id": "heat_index", "group": 1}, {"id": "pm25", "group": 2}],
  "edges": [{"source": "heat_index", "target": "pm25", "value": 0.52, "type": "SYNERGISTIC"}]
}
```

## 6. Space Biology

### `GET /space-biology/overview`
**Response (200)**:
```json
{
  "studies": 2,
  "samples_total": 42,
  "interaction_counts": {
    "SYNERGISTIC": 0,
    "ANTAGONISTIC": 0
  }
}
```

### `GET /space-biology/genes`
**Query Params**: `sort`, `limit`
**Response (200)**:
```json
[
  {
    "gene_symbol": "CD44",
    "ensembl_id": "ENSMUSG00000000001",
    "b_AB": 1.2,
    "neg_log10_q": 4.5,
    "type": "SYNERGISTIC",
    "replicated": true
  }
]
```

## 7. Benchmarks & History

### `GET /benchmark/results`
Returns exactly the JSON from `benchmark.json`.
**Response (200)**:
```json
{
  "fdr_decomposition": { },
  "null_calibration": { },
  "limitations": ["FDR is not controlled..."]
}
```

### `GET /experiments`
**Response (200)**:
```json
[
  {
    "run_id": "run_123",
    "config_hash": "a1b2...",
    "result_hash": "c3d4...",
    "status": "COMPLETED"
  }
]
```

## 8. Security & Risk

### `POST /security/simulate-tamper`
**Request**:
```json
{
  "dataset_id": "env_panel",
  "mode": "subtle_edit",
  "magnitude": 0.1
}
```
**Response (200)**:
```json
{
  "mode": "subtle_edit",
  "hash_match": false,
  "detections": ["hash_mismatch", "autoencoder"],
  "verdict": "RESULT BLOCKED FROM VERIFIED STATUS"
}
```

### `GET /security/reports/{id}`
**Response (200)**:
```json
{
  "report_id": "sec_123",
  "dataset_id": "env_panel",
  "false_alarm_rates": {
    "isolation_forest": 0.0,
    "mcd": 1.0
  },
  "checks": [
    {"name": "isolation_forest", "status": "PASS", "score": 0.0, "detail": ""}
  ]
}
```

### `GET /risk/assessment`
**Query Params**: `region=Seattle`
**Response (200)**:
```json
{
  "region": "Seattle",
  "simulated_only": true,
  "risk_tier": "HIGH",
  "interaction_uplift": 0.15,
  "uncertainty_lower": 0.10,
  "uncertainty_upper": 0.20,
  "source_findings": ["find_123"]
}
```
