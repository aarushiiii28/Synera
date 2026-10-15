# SYNERA: 3-minute demo script

Order follows the deck: **problem → discovery → trust → action**. Start with `make demo` (API on :8000, web on :5173) and open http://localhost:5173. Press **▶ 3-MIN TOUR** in the top bar to have the app navigate for you; the cues below are what to say and click if you drive it yourself.

| Time | Page | Say | Click | Expect on screen |
|---|---|---|---|---|
| 0:00 | Observatory | “The environment doesn’t change one variable at a time. Heat, pollution, drought, weather and radiation act together; the unknown is what happens when they interact.” | Hover **RADIATION**, then **HEAT** | The NASA Earth with the sunrise limb; five stressor beams converge on the green cell; each node explains itself. Under the globe the live strip shows real counts: findings in the registry, validated, **0 verified**, ledger block count. |
| 0:30 | Discovery Lab | “The engine tests every pair of stressors. Three independent methods then look at each result.” | Choose **Engine benchmark (SIMULATED)**, press **Run engine** (tick *quick run* for ~1 min) | A nine-step timeline streams in with *measured* durations. When it finishes the funnel shows 45 pairs → many significant on their own → only a few after conditional selection: “explained away” pairs are look-alikes of a real interaction. |
| 1:00 | Discovery Lab | “This is the deck’s ‘combined effect is greater than the sum’ moment.” | Click the **heat index × PM2.5** cell, drag the transect slider | Dashed contours = additive expectation, solid = fitted surface, the shaded gap is the interaction, in green because it is synergistic. Tag says SIMULATED. |
| 1:20 | Findings → dossier | “Statistics decide what survives; every gate is shown.” | Open the heat × PM2.5 finding, press **Re-verify now** | Eight gates animate in. Integrity gates pass; **G8 “SIMULATED provenance cap”** and **G7 “not independent replication”** fail, with reasons. Status stays VALIDATED: it can never be VERIFIED on simulated data. |
| 1:50 | Trust Center | “Discovery isn’t enough: can we trust the evidence? Let’s attack it.” | Dataset **osd-211**, mode **subtle edit**, press **Launch attack** | Original and modified hashes diverge (differing characters in red); detector cards show the statistical detectors did **not** fire; the highlighted line says *only the cryptographic hash caught this*; the stamp reads “RESULT BLOCKED FROM VERIFIED STATUS”. |
| 2:15 | Trust Center | “The simulation ran on a temporary copy. The real chain is untouched.” | Press **Verify entire chain**; then mode **ledger tamper** | Real ledger: VALID with its block height. The ledger-tamper copy shows PAYLOAD_TAMPERED and a broken link. |
| 2:35 | Space Biology | “Real NASA mouse data: radiation × hindlimb unloading, same animals, two tissues. We report it honestly.” | Hover a few points of the volcano | 24,688 genes; **no gene passes FDR** and the page says so; power chart shows 80% power only for very large interactions; REAL tag; CROSS-TISSUE · SAME COHORT caveat. |
| 2:50 | Risk Brief | “Validated interactions become decision support, with uncertainty, sources and a receipt.” | Pick **Delhi** | Tier with percentile, uplift ± band, 7-day chart, data-source tag, the persistent **SIMULATED DEMONSTRATION** banner, and the reproducibility receipt. |

Backup if the network is down: set `SYNERA_OFFLINE=1`; the risk page shows an OFFLINE / CACHED tag. Backup if the API is down: every page shows a designed SIGNAL LOST state, never a blank.

## Likely judge questions, answered with measured numbers only

**Why are there no verified findings?** Verification needs independent replication and real data. Track B findings are simulated, so they are capped at VALIDATED by design. Track A (real NASA data) has 24,688 genes tested and none passes FDR (best q = 0.45); with n = 6/6/3/6 the design reaches 80% power only for interactions around 4 log2. Reporting zero verified findings is the correct output here; the system exists to refuse to overclaim.

**Does the engine actually work?** On simulated data with known answers, 50 seeds per level: the full stack recovers the three planted interactions 90–97% of the time with strict false-discovery rates of 6.2% (hardest noise level), 0.7%, 0% and 0% at higher signal-to-noise. Unflattering parts are published: the marginal screen alone is ~92% false; a non-linear surface is *typed* correctly only 26–44% of the time at low SNR; the bootstrap-calibrated test still has 7.6% of null p-values below 0.05.

**Why is the naive test not good enough?** Neighbouring days are correlated. On null data the naive test’s inflation factor λ is 4.1 (1.0 is honest) and a Newey-West HAC test is 14.3; the block-bootstrap-calibrated test is 1.38. The Report Card shows the histograms.

**What does the blockchain add? Does it prove the science?** No. It is a signed, hash-chained, append-only ledger with Merkle proofs. It makes the computational provenance tamper-evident: if a dataset, model, code tree or result changes, the hash changes and the result is blocked. In our 600 attack trials the hash caught 100%; the statistical detectors alone missed all subtle in-range edits and label flips.

**How do you know the results are reproducible?** Every run is replayed from the same seed and its output digest must match; the source-tree hash is recorded, and `make reproduce` re-runs every recorded analysis and compares digests with the ledger. Change one line of code and gate G4 fails by design.

**Is the interface just a pretty wrapper with canned numbers?** No number is hard-coded: every figure comes from the API, which reads either the database filled by the pipeline or result files written by the build scripts. The tamper simulator computes real SHA-256 hashes on temporary copies; the nine pipeline steps show measured durations.

**What would you do with more time or data?** Add a second, independent space-biology study with the same factors (the only route to VERIFIED), real climate-health outcomes (Track C adapter exists), and anchor the ledger head to a public timestamping service.
