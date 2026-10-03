# SYNERA: Trusted AI for Multi-Stressor Environmental Intelligence
Tagline: DISCOVER. VALIDATE. VERIFY. ACT.  Team PeakyGliders, Guru Nanak Dev University.

## Thesis
Environmental stressors (heat, air pollution, drought, extreme weather, radiation, microgravity) interact, but
most analysis treats them independently. The unknown is not just the stressor; it is what happens when stressors
interact. SYNERA uses AI to generate interaction hypotheses, classical statistics to validate them, cybersecurity
+ cryptographic provenance to verify the computational chain, and turns verified findings into decision support.
"AI generates hypotheses. Science validates them." "Blockchain does not prove the science; it makes the
computational provenance tamper-evident."

## 7 layers
01 Data -> 02 AI Discovery Engine (ML, DL, feature-interaction analysis, anomaly detection) -> 03 Scientific
Validation (significance, effect size, CIs, multiple-testing correction, cross-dataset validation) -> 04
Cybersecurity (data integrity, poisoning detection, model verification, pipeline integrity) -> 05 Provenance
(SHA-256, dataset/experiment versioning, blockchain evidence ledger) -> 06 Web Intelligence Platform (dashboard,
candidate findings, interaction & evidence graphs, validation status, confidence indicators, experiment history)
-> 07 Action (environmental risk assessment, climate resilience insights, decision support, reproducibility).

## Interaction types
Synergistic (combined > additive expectation), Antagonistic (combined < additive expectation), Nonlinear
(threshold / non-monotonic / unpredictable response).

## Finding lifecycle & Evidence Levels
CANDIDATE -> VALIDATED (stats pass) -> VERIFIED (replicated + security CLEAN + ledger chain valid + reproducibility
replay matches). BLOCKED = any integrity failure ("result blocked from verified status"). REJECTED = failed stats or
replication. VERIFIED means "statistically validated with verified computational provenance". It NEVER means
"biologically proven". The UI must say so.

Evidence levels for findings:
- INDEPENDENT_REPLICATION: Replicated in completely independent cohorts/studies.
- CROSS_TISSUE_SAME_COHORT: Replicated across different tissues from the same animals/cohort (consistency check).
- INTERNAL_REPLICATION: Replicated using subset splitting or cross-validation within a single dataset.
- HYPOTHESIS_ONLY: Cannot be statistically replicated (e.g., cross-study contrast fallback).

## Data tracks
A. Space Biology Testbed (REAL): NASA OSDR/GeneLab omics, Radiation x Microgravity -> gene-level response.
B. Engine Benchmark (SIMULATED outcome on REAL covariates): planted synergy/antagonism/nonlinear interactions to
   measure precision/recall/FDR. Every artifact and UI element derived from it is tagged provenance=SIMULATED.
C. Climate-Health (REAL, optional): heat x PM2.5 x ozone -> health outcome. Added only if data is supplied.

## Stack
Python 3.11; numpy/pandas/scipy/statsmodels/scikit-learn/LightGBM/SHAP/PyTorch(CPU); FastAPI + SQLModel(SQLite) +
SSE; Jupyter notebooks (thin, call synera_core); React 18 + Vite + TypeScript + Tailwind 3.4 + d3 + react-three-fiber
+ framer-motion + TanStack Query + Zustand.

## NON-NEGOTIABLE RULES (apply to every part)
1. Read docs/CONTEXT.md and PROGRESS.md before starting. Update PROGRESS.md when finished.
2. Never fabricate data or results. Simulated data must carry provenance=SIMULATED end to end, including the UI.
3. No TODO stubs or placeholder implementations in delivered code. If you truly need something from the user
   (e.g. a dataset), write "BLOCKED: need user: <what/where>" in PROGRESS.md, then continue with other work.
4. Type hints + docstrings on public functions; ruff-clean; pytest tests for every core module.
5. Determinism: all randomness seeded from configs/settings.yaml; no hardcoded absolute paths.
6. Science honesty: log2-scale additivity is multiplicative independence on the fold-change scale; document this.
   Small-n omics needs variance moderation; time series needs block bootstrap; state assumptions in docstrings.
7. Small, frequent git commits: "part-N: <what>".
8. Do not change public API contracts (docs/API_CONTRACT.md) silently; record changes in PROGRESS.md.
9. Do not install packages you do not use. Pin nothing blindly; use compatible ranges.
