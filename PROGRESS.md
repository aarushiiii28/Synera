# PROGRESS

Status after the full review of Parts 1–8 and completion of Part 9. Every number below was measured by the code in this repository (see `artifacts/results/`), none was typed in.

## What the review found, and what was done

The earlier log reported the project as complete through Part 8. Auditing the repository showed that several "completed" pieces were stubs or fabricated:

| Area | Found | Fixed |
|---|---|---|
| Orchestrator | nine `time.sleep(1)` calls with canned messages; nothing was executed | `pipeline/orchestrator.py`: nine real steps with measured durations, real integrity check, scan, discovery, validation, replication, ledger block, post-check, replay, finalize |
| Second opinions | LightGBM-SHAP and neural "detectors" returned a hand-set matrix / zeros | real LightGBM + SHAP interaction values and a seeded PyTorch neural-interaction detector |
| Reproducibility replay | returned `replay_hash = original_hash` whenever the source hash matched | re-executes the analysis and compares output digests; fails on any difference |
| Model verification | compared only a file hash | hash + hold-out metric + probe-prediction hash |
| Benchmark | very high FDR from a misspecified model (omitted main effects, city/season); "bootstrap λ = 1.000" was a reference value, not a measurement | `discovery/panel.py`: city fixed effects, seasonality, all other stressors as covariates, HAC and block-bootstrap-calibrated inference, forward/backward conditional selection; 50 seeds × 4 SNR levels, 100 null simulations, 200 moderation simulations, 600 security trials |
| Security detectors | MCD, autoencoder and label-flip raised alarms on 100% of clean data | baseline-calibrated thresholds, binomial alarm rule, honest "not informative" reporting; clean false alarms are measured on held-out data: 2-5% per statistical detector, 10% any-warning (an earlier version tested on the baseline's own rows and reported 0% by construction) |
| Physical-range check | applied raw-unit limits to z-scored data and could block a run | applies only to columns in physical units |
| API | hard-coded surface, forest, matrix, network, risk tier "HIGH", `samples_total: 42`, dataset verify always `match: true`, `VERIFIED` assigned with no checks | every endpoint computes from data; eight live gates; tamper results computed from real hashes |
| Ledger | two diverging chains (one inside the application database), signing key in `configs/`, absolute `D:/…` paths in the manifest, `verify()` crashed on corrupted JSON | one ledger at `artifacts/ledger.db`, key in `artifacts/keys`, portable relative manifest, robust `verify()` |
| Data | a unit-test fixture had written a fake `OSD-999` study into `data/processed`; harmonizer hard-coded 6/6/3/6, tissue and batch | removed; harmonizer reads everything from the ISA/expression files and fails loudly; tests write to temporary directories |
| Frontend | generic dark dashboard, mock/fallback numbers, a Space Biology banner calling REAL data a "simulated demonstration" | new design system (NASA Earth observatory, guided tour, glossary tooltips, explainers); every number from the API |
| Tests / notebooks | notebooks were two-cell stubs; one test imported a deleted script | nine real executed notebooks; 75 Python tests, 45 frontend tests, Playwright e2e |

## Parts 1–9 status

| Part | Status | Notes |
|---|---|---|
| 1 Environment, structure | done | `make check`, config, ledger paths, Docker, CI |
| 2 Provenance ledger | done | signed, hash-chained, append-only; Merkle proofs; tamper cases tested |
| 3 Data | done | real OSDR files (manual download), 8-city environmental panel, symbols map, manifest; second `make data` is offline |
| 4 Discovery and validation | done | panel engine + factorial engine; Track A null calibration, power and cross-tissue consistency |
| 5 Benchmark and security | done | measured report card; tamper simulator incl. model swap and ledger tamper |
| 6 Pipeline and backend | done | nine-step orchestrator, SSE, versioned DB, eight gates, risk module |
| 7 Design system and shell | done | see `docs/DESIGN_SYSTEM.md` |
| 8 Pages | done | every page reads the real API with designed empty states |
| 9 Integration and hardening | done | `make demo`, `make reproduce`, Docker, CI, docs, demo script |

## Headline measured results

* Engine (Track B, SIMULATED): full stack recall 90–97% of planted interactions; strict FDR 6.2% / 0.7% / 0% / 0% at SNR 1 / 2 / 5 / 20. The marginal pairwise screen alone is ~92% false; conditional selection removes it.
* Null calibration λ: naive 4.11, HAC 14.32, block bootstrap 1.38 (7.6% of p-values < 0.05 at nominal 5%).
* Track A (REAL): 24,688 genes tested, best q = 0.45, **0 findings**; null λ = 0.96; 43% power at 1.5 log2, 80% power only at ~4 log2; 20 of 21 animals shared between tissues.
* Security: hash 100% of 600 attack trials; statistical detectors missed all subtle in-range edits and label flips; clean false alarms on held-out data 2-5% per statistical detector (10% any warning); MCD and autoencoder never fired on any attack.
* Findings today: 3 VALIDATED (simulated, capped), 0 VERIFIED, 0 BLOCKED.

## Known limitations (also in the README)

VERIFIED ≠ biologically proven; no finding is verified; Track B is semi-synthetic; Track A is underpowered; non-linear surfaces are typed correctly only 26–44% of the time at low SNR; the bootstrap-calibrated test is slightly anti-conservative; HAC is reported only as a sensitivity check; statistical detectors are advisory; the ledger is permissioned and not anchored publicly; code edits after a run trigger the G4 drift gate by design.

## BLOCKED / needs user

None. (Optional: a second independent space-biology study with the same factors would be the only route to a VERIFIED real finding; the hallmark GMT file for pathway-level tests was not supplied and that analysis was not performed.)
