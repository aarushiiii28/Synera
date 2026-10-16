// Typed client for docs/API_CONTRACT.md. Every function maps 1:1 to a backend endpoint under /api/v1.

export type Provenance = 'REAL' | 'SIMULATED';
export type Status = 'CANDIDATE' | 'VALIDATED' | 'VERIFIED' | 'BLOCKED' | 'REJECTED';
export type InteractionType = 'SYNERGISTIC' | 'ANTAGONISTIC' | 'NONLINEAR';
export type EvidenceLevel = 'INDEPENDENT_REPLICATION' | 'CROSS_TISSUE_SAME_COHORT' | 'INTERNAL_REPLICATION' | 'HYPOTHESIS_ONLY';

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// Empty in dev and docker (same-origin proxy). Set VITE_API_URL to the API's public origin when the site and API are on different hosts (e.g. Vercel + Render).
const API_ORIGIN = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/+$/, '');
const BASE = `${API_ORIGIN}/api/v1`;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...init });
  } catch {
    throw new ApiError(0, 'NETWORK', 'The SYNERA API is unreachable');
  }
  if (!res.ok) {
    let msg = res.statusText;
    let code = 'ERROR';
    try {
      const j = await res.json();
      msg = j?.error?.message ?? msg;
      code = j?.error?.code ?? code;
    } catch { /* non-JSON error body */ }
    // 502/503/504 come from the dev server or proxy when nothing is listening behind it.
    if ([502, 503, 504].includes(res.status)) msg = 'The SYNERA API is not running. Start it (dev.cmd, or make api) and retry.';
    throw new ApiError(res.status, code, msg);
  }
  return res.json() as Promise<T>;
}

const get = <T,>(p: string) => req<T>(p);
const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
const qs = (o: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : '';
};

// ---------- types ----------
export interface Health {
  status: string; version: string; offline: boolean; pipeline: string;
  database: { ok: boolean; schema_version: number };
  ledger: { height: number; chain_valid: boolean; head: string | null; signer: string; issues: LedgerIssue[] };
  counts: { datasets: number; runs: number; findings: number };
}
export interface LedgerIssue { index: number; code: string; detail: string }
export interface Block {
  index: number; timestamp: string; block_type: string; prev_hash: string; merkle_root: string;
  payload: Record<string, unknown>; payload_hash: string; block_hash: string; signature: string; signer: string; artifact_count: number;
}
export interface LedgerVerify { valid: boolean; height: number; head: string | null; issues: LedgerIssue[] }
export interface MerkleProof { artifact_hash: string; block_index: number; block_type: string; merkle_root: string; merkle_proof: { side: 'L' | 'R'; hash: string }[]; verified: boolean }

export interface Dataset {
  id: string; name: string; track: 'A' | 'B'; kind: 'covariates' | 'panel' | 'factorial'; provenance: Provenance; hash: string;
  features_count: number; samples_count: number; description: string; role: string; runnable: boolean; path: string;
  summary: Record<string, unknown> & { rows?: number; cities?: number; date_start?: string; date_end?: string; available?: boolean };
  qc: Record<string, unknown>; ledger_block: number | null;
}
export interface DatasetVerify { dataset_id: string; match: boolean; expected_hash: string; actual_hash: string; ledger_block: number | null; detail: string; checked_at: string; verdict: string | null }

export interface RunEvent {
  id?: number; run_id: string; step: number; step_name: string; label: string; status: 'RUNNING' | 'DONE' | 'FAILED'; progress: number;
  message: string; duration_s: number | null; ts: number; data: Record<string, unknown>;
}
export interface Run {
  id: string; dataset_id: string; status: 'RUNNING' | 'COMPLETED' | 'BLOCKED' | 'FAILED'; created_at: number; finished_at: number | null;
  config_hash: string; dataset_hash: string; result_hash: string | null; ledger_block: number | null; src_tree_hash: string | null;
  runtime_s: number | null; error: string | null; params: Record<string, unknown>; summary: Record<string, number>;
  stage_counts: { marginal_bh: number; after_forward: number; after_backward: number } | null;
  replay: { matches: boolean; original_hash: string; replay_hash: string; seconds: number } | null;
  events?: RunEvent[]; steps?: string[];
}
export interface Check { name: string; status: 'PASS' | 'WARN' | 'FAIL'; score: number; detail: string; blocking: boolean }
export interface Gate { id: string; label: string; passed: boolean; reason: string; integrity: boolean; [k: string]: unknown }

export interface Effect { b_AB: number; ci_low: number; ci_high: number; cohens_d: number; effect_size?: number | null; eff_ci_low?: number | null; eff_ci_high?: number | null }
export interface Finding {
  id: string; run_id: string; track: 'A' | 'B'; provenance: Provenance; evidence_level: EvidenceLevel; dataset_id: string;
  stressors: [string, string]; feature: string | null; type: InteractionType; status: Status; effect: Effect;
  stats: { p: number; q: number; n: number; df: number; p_naive?: number; p_hac?: number; q_marginal?: number; p_bilinear?: number; p_nonlinear?: number; lambda_boot?: number };
  methods: { parametric: boolean; gbm: boolean; nid: boolean; gbm_rank?: number | null; nid_rank?: number | null };
  replication: { evidence_level: string; replicated: boolean; replication_rate: number; detail?: string; halves?: Record<string, { cities: string[]; p: number; direction: number }> } | null;
  security: { status: string; checks: Check[] };
  confidence: { score: number; components: Record<string, number> } | null;
  gates: Gate[]; history: string[]; has_surface: boolean; q_value: number; effect_size: number;
}
export interface FindingList { total: number; items: Finding[]; counts: Record<Status, number> }
export interface FindingBundle extends Finding {
  dataset: Omit<Dataset, 'qc'> | null;
  run: { id: string; status: string; config_hash: string; result_hash: string | null; dataset_hash: string; ledger_block: number | null;
         replay: Run['replay']; params: Record<string, unknown>; stage_counts: Run['stage_counts']; runtime_s: number | null } | null;
}
export interface VerifyResult { id: string; previous_status: Status; new_status: Status; allowed: boolean; reasons: string[]; gates: Gate[]; verdict: string | null }
export interface Surface { a: string; b: string; grid_a: number[]; grid_b: number[]; z_additive: number[][]; z_full: number[][]; z_gap: number[][]; units: string; type: InteractionType; provenance: Provenance }
export interface Forest { studies: { name: string; effect: number | null; ci_low: number | null; ci_high: number | null; unit: string; p?: number }[]; methods: Finding['methods']; evidence_level: string }

export interface MatrixCell {
  a: string; b: string; category: 'selected' | 'explained_away' | 'not_significant'; type: InteractionType | null; status: Status | null;
  finding_id: string | null; effect_size: number | null; q_marginal: number; p_conditional: number | null; gbm_rank: number | null; nid_rank: number | null;
  methods: Finding['methods'] | null; p_naive: number;
}
export interface InteractionMatrix { dataset_id: string; run_id: string; stressors: string[]; cells: MatrixCell[]; explanation: Record<string, string> }
export interface NetworkGraph {
  dataset_id: string; run_id: string;
  nodes: { id: string; label: string; unit?: string; group: string; about?: string; degree: number; in_finding: boolean }[];
  edges: { source: string; target: string; value: number; type: InteractionType; status: Status; finding_id: string }[];
}
export type StressorInfo = Record<string, { label: string; unit: string; group: string; about: string }>;

export interface SpaceOverview {
  provenance: 'REAL'; source: string; evidence_level: EvidenceLevel; genes_tested: number; best_q: number; fdr_alpha: number; fdr_line_p: number; fdr_line_note: string; statement: string;
  studies: { id: string; role: string; tissue: string; organism: string; samples: number; genes_tested: number; design_2x2: { control: number; radiation: number; unloading: number; both: number } }[];
  factors: { radiation: string; microgravity: string }; expression_variant: string; expression_filter: Record<string, number>;
  moderation: { method: string; prior_df_discovery: number; prior_df_replication: number };
  interaction_counts: { SYNERGISTIC: number; ANTAGONISTIC: number; NONLINEAR: number };
  top_exploratory: { gene: string; b_AB: number; p: number; q: number }[];
  consistency: { caveat: string; animals_discovery: number; animals_replication: number; animals_shared: number; genes_shared_after_filter: number; fdr_hits_discovery: number; fdr_hits_replication: number; exploratory_top100_sign_concordance: number; exploratory_top100_binomial_p_vs_half: number; interaction_effect_spearman_rho_all_shared_genes: number; interpretation: string };
  power: { minimum_detectable_log2_80pct_power: number | null; note: string | null; provenance: string; by_log2_effect: Record<string, { power_mean: number; power_range: [number, number] }> };
  positive_controls: Record<string, unknown>;
  null_calibration: { n_permutations: number; frac_p_lt_05_median: number; lambda_median: number; lambda_range: [number, number]; mean_hits_q05_per_permutation: number; frac_permutations_with_a_hit: number; pooled_p_histogram_10bins: number[] };
  pc1: Record<string, unknown>;
}
export interface Gene { ensembl_id: string; gene_symbol: string; name: string; b_AB: number; p: number; q: number; neg_log10_p: number; neg_log10_q: number; type: 'none' | 'SYNERGISTIC' | 'ANTAGONISTIC'; replication_b_AB: number | null; replication_p: number | null; same_sign_in_replication: boolean | null; passed_filter_both: boolean }
export interface CompactGenes { total: number; columns: string[]; rows: [string, number, number, string, number][] }

export interface Benchmark {
  available: boolean; provenance?: 'SIMULATED'; limitations: string[]; runtime_s?: number;
  discovery?: {
    seeds: number; snrs: number[]; effect_gate: number; n_boot: number;
    by_snr: Record<string, {
      stages: Record<string, { discoveries: number; true_positives: number; proxy: number; hard_decoy: number; easy_decoy: number; recall: number; precision: number | null; fdr_strict: number | null; fdr_proxy_aware: number | null; seeds_with_zero_discoveries: number; type_accuracy: number | null }>;
      gate_curve: Record<string, { recall: number; fdr_strict: number | null }>;
      recall_by_type: Record<string, Record<string, { detected: number; detected_and_typed_correctly: number }>>;
      runtime_s_mean: number; gbm_holdout_r2_mean: number; nid_holdout_r2_mean: number; block_len_median: number;
    }>;
  };
  null_calibration?: { n_simulations: number; pairs_per_simulation: number; rho: number; naive: NullCal; hac: NullCal; boot: NullCal };
  moderation?: { design: string; n_simulations: number; by_effect_sd: Record<string, Record<'none' | 'fixed_df4' | 'estimated', { power_mean: number; power_ci95: [number, number]; fdr_mean: number; fdr_ci95: [number, number] }>> };
  security?: {
    trials_per_cell: number; clean_seeds: number; contamination_levels: number[]; design_notes: string[];
    attacks: Record<string, Record<string, Record<string, number>>>; clean_false_alarm_rate: Record<string, number>; clean_false_alarm_counts?: Record<string, [number, number]>; clean_false_alarm_ci95?: Record<string, [number, number]>;
    hash_only_attacks: { mode: string; contamination: number; best_statistical_detection: number }[];
  };
}
export interface NullCal { lambda_median: number; lambda_range: [number, number]; frac_p_lt_05_median: number; frac_p_lt_05_pooled: number; p_histogram_10bins: number[] }

export interface TamperResult {
  mode: string; dataset_id: string; description: string; magnitude: number; temporary_copy: boolean; hash_match: boolean;
  original_hash: string; tampered_hash: string; detections: string[]; statistical_detections?: string[]; detectors: Check[]; scan_status?: string | null;
  hash_only?: boolean; scan_notes: string | null; verdict: string; original_untouched: boolean;
  original_file_sha?: string; tampered_file_sha?: string; original_dataframe_hash?: string; tampered_dataframe_hash?: string;
  ledger?: { target_block: number; before: { valid: boolean; height: number; head: string }; after: { valid: boolean; height: number; issues: LedgerIssue[] } };
  model?: { before: { ok: boolean; checks: { name: string; ok: boolean; detail: string }[] }; after: { ok: boolean; checks: { name: string; ok: boolean; detail: string }[] } };
}
export interface FalseAlarm { available: boolean; clean_false_alarm_rate?: Record<string, number>; clean_false_alarm_counts?: Record<string, [number, number]>; clean_false_alarm_ci95?: Record<string, [number, number]>; clean_seeds?: number; attacks?: Benchmark['security'] extends infer S ? (S extends { attacks: infer A } ? A : never) : never; hash_only_attacks?: { mode: string; contamination: number; best_statistical_detection: number }[]; trials_per_cell?: number; policy?: string }

export interface RiskDay { date: string; additive: number; modelled: number; uplift: number; percentile: number | null; tier: string | null; stressors: Record<string, number | null> }
export interface Risk {
  region: string; available: boolean; simulated_only: boolean; message?: string; banner: string | null;
  source: { mode: 'live' | 'cached' | 'archive_fallback'; note?: string; fetched_at?: number };
  risk_tier: 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | null; risk_percentile?: number; interaction_uplift?: number;
  uncertainty_lower?: number; uncertainty_upper?: number; uncertainty_basis?: string; tier_basis?: string; units?: string;
  source_findings: string[]; findings: { id: string; stressors: string[]; type: InteractionType; status: Status; provenance: Provenance }[];
  forecast?: RiskDay[]; verified_real_findings?: string[];
  receipt: { run_id: string; config_hash: string; result_hash: string | null; dataset_hash: string; ledger_block: number | null; replay_matches: boolean | null }[];
}
export interface Experiment { run_id: string; dataset_id: string; status: string; config_hash: string; result_hash: string; ledger_block: number | null; runtime_s: number | null; created_at: number; replay_matches: boolean | null; summary: Record<string, number>; params: Record<string, unknown> }

// ---------- endpoints ----------
export const api = {
  health: () => get<Health>('/health'),
  ledgerHead: () => get<Block | Record<string, never>>('/ledger/head'),
  ledgerBlocks: (o: { offset?: number; limit?: number; order?: 'asc' | 'desc'; block_type?: string } = {}) => get<{ total: number; items: Block[] }>('/ledger/blocks' + qs(o)),
  ledgerBlock: (i: number) => get<Block>(`/ledger/blocks/${i}`),
  ledgerVerify: () => get<LedgerVerify>('/ledger/verify'),
  ledgerProof: (h: string) => get<MerkleProof>(`/ledger/proof/${h}`),

  datasets: () => get<Dataset[]>('/datasets'),
  dataset: (id: string) => get<Dataset>(`/datasets/${id}`),
  verifyDataset: (id: string) => post<DatasetVerify>(`/datasets/${id}/verify`),

  runSteps: () => get<{ step: number; name: string; label: string }[]>('/runs/steps'),
  createRun: (b: { dataset_id: string; quick?: boolean; force?: boolean; alpha?: number; n_boot?: number }) => post<{ run_id: string; reused: boolean }>('/runs', b),
  runs: (o: { dataset_id?: string; status?: string } = {}) => get<Run[]>('/runs' + qs(o)),
  run: (id: string) => get<Run>(`/runs/${id}`),

  findings: (o: { status?: string; track?: string; type?: string; provenance?: string; dataset_id?: string; q?: string; sort?: string; limit?: number; offset?: number } = {}) => get<FindingList>('/findings' + qs(o)),
  finding: (id: string) => get<FindingBundle>(`/findings/${id}`),
  verifyFinding: (id: string) => post<VerifyResult>(`/findings/${id}/verify`),
  surface: (id: string) => get<Surface>(`/findings/${id}/surface`),
  forest: (id: string) => get<Forest>(`/findings/${id}/forest`),

  stressors: () => get<StressorInfo>('/stressors'),
  matrix: (dataset_id = 'benchmark_track_b') => get<InteractionMatrix>('/interactions/matrix' + qs({ dataset_id })),
  network: (dataset_id = 'benchmark_track_b') => get<NetworkGraph>('/interactions/network' + qs({ dataset_id })),

  spaceOverview: () => get<SpaceOverview>('/space-biology/overview'),
  genes: (o: { sort?: string; limit?: number; offset?: number; search?: string } = {}) => get<{ total: number; items: Gene[] }>('/space-biology/genes' + qs(o)),
  genesCompact: (limit = 30000) => get<CompactGenes>('/space-biology/genes' + qs({ compact: true, limit })),

  benchmark: () => get<Benchmark>('/benchmark/results'),
  experiments: () => get<Experiment[]>('/experiments'),

  tamperModes: () => get<{ mode: string; description: string }[]>('/security/modes'),
  simulateTamper: (b: { dataset_id: string; mode: string; magnitude?: number; seed?: number }) => post<TamperResult>('/security/simulate-tamper', b),
  falseAlarms: () => get<FalseAlarm>('/security/false-alarm-rates'),

  riskRegions: () => get<{ id: string; lat: number; lon: number }[]>('/risk/regions'),
  risk: (region: string) => get<Risk>('/risk/assessment' + qs({ region })),
};

export const runEventsUrl = (runId: string) => `${BASE}/runs/${runId}/events`;
