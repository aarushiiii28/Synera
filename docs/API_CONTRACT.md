# SYNERA API contract (v1)

Base URL `/api/v1`. JSON everywhere except the SSE stream. Errors always use one envelope:

```json
{ "error": { "code": "NOT_FOUND", "message": "finding 'x' not found", "detail": null } }
```

Codes: `BAD_REQUEST 400`, `NOT_FOUND 404`, `CONFLICT 409`, `VALIDATION_ERROR 422`, `RATE_LIMITED 429`, `UNAVAILABLE 503`.
The OpenAPI document (`/docs`, `/openapi.json`) is generated from the code; this file explains semantics.
The TypeScript mirror is `frontend/src/lib/api.ts`.

**Principles that shape every response**

* Nothing is a constant: every number is computed from data or read from a result file written by a build script.
* `provenance` is `REAL` or `SIMULATED` on datasets, findings and risk briefs. Simulated findings are capped at `VALIDATED`.
* The ledger is **read-only** through the API. The only ledger write an endpoint can cause is the `INTEGRITY_ALERT` appended by
  `POST /datasets/{id}/verify` when a hash really mismatches.

## System and ledger

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{status, version, offline, pipeline, database:{ok,schema_version}, ledger:{height, chain_valid, head, signer, issues[]}, counts:{datasets,runs,findings}}` |
| GET | `/ledger/head` | the newest block |
| GET | `/ledger/blocks?offset&limit&order=desc\|asc&block_type` | `{total, items:[Block]}` |
| GET | `/ledger/blocks/{index}` | `Block` with full payload |
| GET | `/ledger/verify` | `{valid, height, head, issues:[{index, code, detail}]}`; codes `PREV_HASH_MISMATCH PAYLOAD_TAMPERED MERKLE_MISMATCH HASH_MISMATCH BAD_SIGNATURE` |
| GET | `/ledger/proof/{sha256}` | `{artifact_hash, block_index, block_type, merkle_root, merkle_proof:[{side:'L'\|'R', hash}], verified}`; 404 if the hash is not recorded |

`Block = {index, timestamp, block_type, prev_hash, merkle_root, payload{…, artifact_hashes[]}, payload_hash, block_hash, signature, signer, artifact_count}`.
Block types: `DATASET_REGISTERED MODEL_REGISTERED EXPERIMENT_RUN FINDING_VALIDATED FINDING_VERIFIED FINDING_REJECTED INTEGRITY_ALERT`.

## Datasets

| Method | Path | Returns |
|---|---|---|
| GET | `/datasets` | `[Dataset]` |
| GET | `/datasets/{id}` | `Dataset` |
| POST | `/datasets/{id}/verify` | `{dataset_id, match, expected_hash, actual_hash, ledger_block, detail, checked_at, verdict}` |

Ids: `env_panel` (REAL covariates, not runnable), `benchmark_track_b` (SIMULATED), `osd-211`, `osd-237` (REAL, NASA OSDR).
`Dataset = {id, name, track:'A'|'B', kind:'covariates'|'panel'|'factorial', provenance, hash, features_count, samples_count, description, role, runnable, summary{rows,cities,date_start,date_end,…}, qc{…}, ledger_block}`.

## Runs (the nine-step pipeline)

| Method | Path | Notes |
|---|---|---|
| GET | `/runs/steps` | `[{step, name, label}]` |
| POST | `/runs` | body `{dataset_id, quick?, alpha?, n_boot?(49–999), force?}` → 202 `{run_id, reused}`. An identical finished run (same dataset hash + config hash) is returned with `reused:true` unless `force`. 409 if a run for the dataset is already running; 400 if the dataset has no outcome. |
| GET | `/runs?dataset_id&status` | newest first |
| GET | `/runs/{id}` | run with `events[]`, `params`, `stage_counts{marginal_bh, after_forward, after_backward}`, `replay{matches, original_hash, replay_hash, seconds}`, `config_hash`, `result_hash`, `ledger_block` |
| GET | `/runs/{id}/events` | **SSE**. Each message is a `RunEvent`; `event: end` closes the stream. Replayed from the database, so reconnecting is safe. |

`RunEvent = {run_id, step(1–9), step_name, label, status:'RUNNING'|'DONE'|'FAILED', progress(0–1), message, duration_s, ts, data{…}}`.
Steps: `LOAD_DATA SECURITY_PRECHECK DISCOVERY VALIDATION REPLICATION PROVENANCE SECURITY_POSTCHECK REPRODUCIBILITY_REPLAY FINALIZE`.
Durations and counts are measured; there are no fixed delays.

## Findings

| Method | Path | Returns |
|---|---|---|
| GET | `/findings?status&track&type&provenance&dataset_id&q&sort&limit&offset` | `{total, items:[Finding], counts:{CANDIDATE,VALIDATED,VERIFIED,BLOCKED,REJECTED}}` (counts are global, zero when none) |
| GET | `/findings/{id}` | `Finding` + `dataset`, `run`, `config` |
| POST | `/findings/{id}/verify` | re-runs **every gate now**: `{id, previous_status, new_status, allowed, reasons[], gates[], verdict}` |
| GET | `/findings/{id}/surface` | `{a, b, grid_a[30], grid_b[30], z_additive[30][30], z_full[30][30], z_gap[30][30], units, type, provenance}`; 404 for factorial findings |
| GET | `/findings/{id}/forest` | `{studies:[{name, effect, ci_low, ci_high, unit}], methods, evidence_level}` |

`Finding = {id, run_id, track, provenance, evidence_level, dataset_id, stressors:[a,b], feature, type:'SYNERGISTIC'|'ANTAGONISTIC'|'NONLINEAR', status, effect{b_AB, ci_low, ci_high, cohens_d, effect_size, eff_ci_low, eff_ci_high}, stats{p, q, n, df, p_naive, p_hac, q_marginal, p_bilinear, p_nonlinear, lambda_boot}, methods{parametric, gbm, nid, gbm_rank, nid_rank}, replication{evidence_level, replicated, replication_rate, halves{}}, security{status, checks[]}, confidence{score, components}, gates[], history[], has_surface}`.
Finding ids are `sha256(dataset hash, pair, config)[:12]`. `effect_size` and surfaces are in outcome standard deviations.
Evidence levels: `INDEPENDENT_REPLICATION`, `CROSS_TISSUE_SAME_COHORT`, `INTERNAL_REPLICATION`, `HYPOTHESIS_ONLY`.

**Gates** (`gates[]`, each `{id, label, passed, reason, integrity}`): `G1_DATA_INTEGRITY`, `G2_LEDGER_CHAIN`, `G3_LEDGER_INCLUSION` (with `merkle_proof`),
`G4_REPRODUCIBILITY`, `G5_SECURITY_BLOCKING`, `G6_STATISTICAL_VALIDATION`, `G7_INDEPENDENT_REPLICATION`, `G8_REAL_PROVENANCE`.
`integrity: true` gates (G1–G5) block the result when they fail; G6–G8 only prevent promotion and explain why.
A SIMULATED finding therefore always shows `G8` failed with “SIMULATED provenance cap”.

## Interactions

| GET `/stressors` | description, unit and group for every stressor |
|---|---|
| GET `/interactions/matrix?dataset_id` | `{run_id, stressors[], cells:[{a, b, category:'selected'\|'explained_away'\|'not_significant', type, status, finding_id, effect_size, q_marginal, p_conditional, gbm_rank, nid_rank, methods}], explanation}` |
| GET `/interactions/network?dataset_id` | `{nodes:[{id,label,group,degree,in_finding}], edges:[{source,target,value,type,status,finding_id}]}` |

## Space biology (Track A, REAL)

| GET `/space-biology/overview` | `{studies[{id,role,tissue,samples,genes_tested,design_2x2{control,radiation,unloading,both}}], genes_tested, best_q, fdr_line_p, statement, interaction_counts, evidence_level, consistency{…}, power{minimum_detectable_log2_80pct_power, by_log2_effect}, positive_controls, null_calibration, pc1}` |
|---|---|
| GET `/space-biology/genes?sort=p\|q\|b_AB&limit&offset&search&compact` | `{total, items:[Gene]}` or, with `compact=true`, `{columns, rows:[[gene, b_AB, neg_log10_p, type, q]]}` for plotting every tested gene |

## Benchmark and experiments

| GET `/benchmark/results` | the report card exactly as measured: `{available, discovery, null_calibration, moderation, security, limitations[]}`; fields not computed are absent |
|---|---|
| GET `/experiments` | every run with `config_hash`, `result_hash`, `ledger_block`, `replay_matches` |

## Security

| GET `/security/modes` | attack modes: `bit_flip subtle_edit row_edit inject_outliers drift_units poison_labels swap_model ledger_tamper` |
|---|---|
| POST `/security/simulate-tamper` | `{dataset_id, mode, magnitude(0.001–0.5), seed}` → `{mode, hash_match, original_hash, tampered_hash, detections[], detectors[], hash_only, verdict, scan_notes, original_untouched, ledger?, model?}`. Works on a temporary copy; rate-limited to 20/min. |
| GET `/security/false-alarm-rates` | measured clean-data false-alarm rate and attack detection rate per detector |
| GET `/security/reports` · `/reports/{id}` | per-run scan results |

## India live intelligence

Live data, no simulation. A provider that fails yields `available: false` with a reason (or a `stale` last-good copy), never an invented value. Details: [INDIA_LIVE.md](INDIA_LIVE.md).

| GET `/india/cities` | `[{id, name, state, lat, lon, terrain}]` |
|---|---|
| GET `/india/overview` | `{available, reason?, generated_at, layers[{id, label, field, unit, legend, note}], cities[{id, name, state, lat, lon, temperature_c, humidity_pct, wind_kmh, wind_dir_deg, rain_24h_mm, rain_next_mm, pm25, pm10, aqi, aqi_category, aqi_level, heat_index_c, heat_category, heat_level, imd_heat, risk, risk_tier, risk_driver, completeness}], national{median_aqi, aqi_categories, hotspots_air[], hottest[], alerts[]}, sources[]}` |
| GET `/india/city/{id}` | `{available, reason?, city, as_of, metrics{name: {value, unit, label, kind, source, time}}, derived{aqi, heat_stress_c, heat_index, imd_heat, rain, uv, composite}, series{time[], now_index, ...}, daily[], fires, quality{issues, missing, completeness}, sources[], engine{scenario, grid}, recommendations[{rank, action, what_is_happening, why, who[], urgency, window, confidence{level, score, why}, basis, evidence[]}], explain{drivers, conditions, engine, basis_count, not_done}}`; 404 for an unknown city id. `kind` is `OBSERVATION`, `MODEL_ANALYSIS`, `FORECAST` or `DERIVED`; `urgency` is `INFORMATIONAL`, `ADVISORY`, `HIGH_PRIORITY` or `CRITICAL`. |

## Risk

| GET `/risk/regions` | `[{id, lat, lon}]` |
|---|---|
| GET `/risk/assessment?region` | `{region, available, simulated_only, banner, source{mode:'live'\|'cached'\|'archive_fallback'}, risk_tier, risk_percentile, interaction_uplift, uncertainty_lower, uncertainty_upper, tier_basis, uncertainty_basis, source_findings[], findings[], forecast[7]{date, additive, modelled, uplift, percentile, tier, stressors}, receipt[{run_id, config_hash, result_hash, ledger_block, replay_matches}]}`. Uses `VALIDATED`/`VERIFIED` findings only; with none, `available:false` and a message, never a made-up tier. |
