export const API_BASE = 'http://localhost:8000/api/v1';

export interface HealthResponse {
  status: string;
  version: string;
  ledger: {
    height: number;
    chain_valid: boolean;
  };
}

export interface LedgerBlock {
  index: number;
  timestamp: number;
  block_type: string;
  prev_hash: string;
  merkle_root: string;
  payload_hash: string;
  signature: string;
}

export interface Dataset {
  id: string;
  name: string;
  provenance: 'REAL' | 'SIMULATED';
  hash: string;
  features_count: number;
  samples_count: number;
  created_at: number;
}

export interface Finding {
  id: string;
  v1: string;
  v2: string;
  interaction_type: 'SYNERGISTIC' | 'ANTAGONISTIC' | 'NONLINEAR';
  status: 'CANDIDATE' | 'VALIDATED' | 'VERIFIED' | 'BLOCKED' | 'REJECTED';
  provenance: 'REAL' | 'SIMULATED';
  q_value: number;
  effect_size: number;
}

export interface FindingsResponse {
  total: number;
  items: Finding[];
}

export interface SpaceBiologyOverview {
  studies: number;
  samples_total: number;
  design_2x2?: {
    sham_ground: number;
    rad_ground: number;
    sham_microg: number;
    rad_microg: number;
  };
  interaction_counts: Record<string, number>;
}

export interface SpaceBiologyGene {
  gene_symbol: string;
  ensembl_id: string;
  b_AB: number;
  neg_log10_q: number;
  type: string;
  replicated: boolean;
}

export interface RiskAssessmentResponse {
  region: string;
  simulated_only: boolean;
  risk_tier: string;
  interaction_uplift: number;
  uncertainty_lower: number;
  uncertainty_upper: number;
  source_findings: string[];
}

export async function fetchHealth(): Promise<HealthResponse> {
  const r = await fetch(`${API_BASE}/health`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchLedgerHead(): Promise<LedgerBlock> {
  const r = await fetch(`${API_BASE}/ledger/head`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchDatasets(): Promise<Dataset[]> {
  const r = await fetch(`${API_BASE}/datasets`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchRuns() {
  const r = await fetch(`${API_BASE}/runs`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchFindings(params?: Record<string, string>): Promise<FindingsResponse> {
  const q = new URLSearchParams(params).toString();
  const r = await fetch(`${API_BASE}/findings?${q}`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchFinding(id: string) {
  const r = await fetch(`${API_BASE}/findings/${id}`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function verifyFinding(id: string) {
  const r = await fetch(`${API_BASE}/findings/${id}/verify`, { method: 'POST' });
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchSpaceBiologyOverview(): Promise<SpaceBiologyOverview> {
  const r = await fetch(`${API_BASE}/space-biology/overview`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchSpaceBiologyGenes(): Promise<SpaceBiologyGene[]> {
  const r = await fetch(`${API_BASE}/space-biology/genes`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchRiskAssessment(region: string): Promise<RiskAssessmentResponse> {
  const r = await fetch(`${API_BASE}/risk/assessment?region=${encodeURIComponent(region)}`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function simulateTamper(payload: Record<string, unknown>) {
  const r = await fetch(`${API_BASE}/security/simulate-tamper`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchBenchmarkResults() {
  const r = await fetch(`${API_BASE}/benchmark/results`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchLedgerBlocks() {
  const r = await fetch(`${API_BASE}/ledger/blocks`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function verifyLedger() {
  const r = await fetch(`${API_BASE}/ledger/verify`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function postRun(payload: any) {
  const r = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchInteractionMatrix(datasetId: string) {
  const r = await fetch(`${API_BASE}/interactions/matrix?dataset_id=${encodeURIComponent(datasetId)}`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchInteractionNetwork(datasetId: string) {
  const r = await fetch(`${API_BASE}/interactions/network?dataset_id=${encodeURIComponent(datasetId)}`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}

export async function fetchFindingSurface(findingId: string) {
  const r = await fetch(`${API_BASE}/findings/${encodeURIComponent(findingId)}/surface`);
  if (!r.ok) throw new Error('API down');
  return r.json();
}
