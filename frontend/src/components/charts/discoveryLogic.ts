// Pure logic for the Discovery Lab, Registry and Dossier pages. Nothing here invents data: every function maps API fields to display values.
import type { Finding, FindingBundle, InteractionType, MatrixCell, Run, RunEvent, Status, StressorInfo, Surface, VerifyResult } from '../../lib/api';
import { fix, sci } from '../../lib/format';

// ---------- run timeline ----------
export type StepState = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
export interface StepView { step: number; label: string; state: StepState; message: string; duration: number | null; counts: { k: string; v: string }[] }

const COUNT_KEYS: Record<string, string> = {
  rows: 'rows', cities: 'cities', n_pairs: 'pairs', raw_significant: 'raw p<0.05', block_length: 'block (d)', marginal_bh: 'BH-significant',
  after_forward: 'after selection', validated: 'validated', pairs: 'pairs', replicated: 'replicated', block_index: 'ledger block', findings_hashed: 'findings hashed',
  height: 'chain height', CANDIDATE: 'candidate', VALIDATED: 'validated', VERIFIED: 'verified', BLOCKED: 'blocked', REJECTED: 'rejected',
};

/** Whole-number counts worth showing next to a step, taken from the real event payload. */
export function eventCounts(ev: RunEvent | undefined): { k: string; v: string }[] {
  if (!ev || ev.status === 'RUNNING') return [];
  return Object.entries(ev.data ?? {})
    .filter(([k, v]) => k in COUNT_KEYS && typeof v === 'number' && Number.isFinite(v))
    .map(([k, v]) => ({ k: COUNT_KEYS[k], v: String(v) }));
}

/** Fold an event list into one row per pipeline step (latest event wins). */
export function stepViews(events: RunEvent[], steps: { step: number; label: string }[]): StepView[] {
  const latest = new Map<number, RunEvent>();
  for (const e of events) latest.set(e.step, e);
  return steps.map((s) => {
    const e = latest.get(s.step);
    return {
      step: s.step, label: s.label, state: e ? e.status : 'PENDING', message: e?.message ?? '', duration: e && e.status !== 'RUNNING' ? e.duration_s : null,
      counts: eventCounts(e),
    };
  });
}

/** Overall progress 0..1 from the newest event; null when nothing has arrived. */
export function overallProgress(events: RunEvent[]): number | null {
  if (!events.length) return null;
  const last = events[events.length - 1];
  return Math.max(0, Math.min(1, last.progress));
}

export interface FunnelStage { key: string; label: string; value: number; note: string }

/** Pairs screened -> significant alone -> after conditional selection -> validated, all from the run record. */
export function funnelStages(run: Pick<Run, 'stage_counts' | 'events' | 'summary'> | null | undefined): FunnelStage[] | null {
  if (!run?.stage_counts) return null;
  const ev = run.events ?? [];
  const screened = ev.find((e) => e.step_name === 'DISCOVERY' && e.status === 'DONE')?.data?.n_pairs;
  const validated = ev.find((e) => e.step_name === 'VALIDATION' && e.status === 'DONE')?.data?.validated;
  if (typeof screened !== 'number' || typeof validated !== 'number') return null;
  return [
    { key: 'screened', label: 'Pairs screened', value: screened, note: 'every pair of stressors was tested' },
    { key: 'marginal', label: 'Significant on their own', value: run.stage_counts.marginal_bh, note: 'marginal test, Benjamini-Hochberg FDR 5%' },
    { key: 'conditional', label: 'After conditional selection', value: run.stage_counts.after_backward, note: 'look-alike (proxy) pairs removed' },
    { key: 'validated', label: 'Validated', value: validated, note: 'effect gate + second-opinion methods agree' },
  ];
}

/** How many pairs were removed as proxies between the marginal screen and conditional selection. */
export const explainedAway = (s: FunnelStage[]): number => Math.max(0, s[1].value - s[2].value);

/** Banner shown for a run that did not complete. */
export function runBanner(status: string | null | undefined, error: string | null | undefined): { tone: 'alert' | 'signal' | 'teal'; title: string; text: string } | null {
  if (status === 'BLOCKED') return { tone: 'alert', title: 'RUN BLOCKED', text: error ?? 'An integrity check stopped this run before any finding was recorded.' };
  if (status === 'FAILED') return { tone: 'alert', title: 'RUN FAILED', text: error ?? 'The run ended with an error.' };
  return null;
}

// ---------- matrix ----------
export const pairKey = (a: string, b: string) => [a, b].sort().join('|');
export function cellLookup(cells: MatrixCell[]): Map<string, MatrixCell> {
  return new Map(cells.map((c) => [pairKey(c.a, c.b), c]));
}
/** Diamond half-diagonal from effect size (outcome SD). Cells without an effect size (not selected) get a fixed small mark. */
export function diamondRadius(effect: number | null, maxEffect: number, rMin: number, rMax: number): number {
  if (effect === null || effect === undefined || !(maxEffect > 0)) return rMin;
  return rMin + (Math.min(effect, maxEffect) / maxEffect) * (rMax - rMin);
}
export function cellAriaLabel(c: MatrixCell, la: string, lb: string): string {
  if (c.category === 'selected') return `${la} by ${lb}: selected ${c.type?.toLowerCase()} interaction, effect ${fix(c.effect_size, 2)} SD`;
  if (c.category === 'explained_away') return `${la} by ${lb}: significant on its own, explained away by a selected pair`;
  return `${la} by ${lb}: no evidence of interaction`;
}

// ---------- response surface ----------
export interface Transect { axis: 'a' | 'b'; index: number; at: number; xs: number[]; add: number[]; full: number[]; gap: number[] }

/** Surface layout from the API (numpy meshgrid): z[row = grid_b index][col = grid_a index]. */
export function zAt(z: number[][], ia: number, ib: number): number { return z[ib][ia]; }

/** A line through the surface: `axis` is the stressor that runs along the line; the other is held at grid index `index`. */
export function transect(s: Surface, axis: 'a' | 'b', index: number): Transect {
  const n = axis === 'a' ? s.grid_b.length : s.grid_a.length; // length of the held axis
  const k = Math.max(0, Math.min(n - 1, Math.round(index)));
  const xs = axis === 'a' ? s.grid_a : s.grid_b;
  const pick = (z: number[][]) => xs.map((_, i) => (axis === 'a' ? z[k][i] : z[i][k]));
  const add = pick(s.z_additive), full = pick(s.z_full);
  return { axis, index: k, at: axis === 'a' ? s.grid_b[k] : s.grid_a[k], xs, add, full, gap: full.map((f, i) => f - add[i]) };
}

/** Row/column of the line with the largest |gap|: the 'combined effect differs from the sum' moment. */
export function peakGapIndex(s: Surface, axis: 'a' | 'b'): number {
  const n = axis === 'a' ? s.grid_b.length : s.grid_a.length;
  let best = 0, bv = -1;
  for (let k = 0; k < n; k++) {
    const t = transect(s, axis, k);
    const m = Math.max(...t.gap.map(Math.abs));
    if (m > bv) { bv = m; best = k; }
  }
  return best;
}
export function peakGap(t: Transect): { i: number; x: number; gap: number } {
  let bi = 0;
  t.gap.forEach((g, i) => { if (Math.abs(g) > Math.abs(t.gap[bi])) bi = i; });
  return { i: bi, x: t.xs[bi], gap: t.gap[bi] };
}
export function surfaceRange(s: Surface): { gapMax: number; zMin: number; zMax: number } {
  const flat = (z: number[][]) => z.flat();
  const all = [...flat(s.z_additive), ...flat(s.z_full)];
  return { gapMax: Math.max(...flat(s.z_gap).map(Math.abs)), zMin: Math.min(...all), zMax: Math.max(...all) };
}
export const GAP_WORD: Record<InteractionType, string> = {
  SYNERGISTIC: 'more than the sum of the separate effects',
  ANTAGONISTIC: 'less than the sum of the separate effects',
  NONLINEAR: 'different from the sum because the response bends or switches',
};
export function transectSentence(t: Transect, la: string, lb: string, unitOf: (k: string) => string, a: string, b: string): string {
  const p = peakGap(t);
  const held = t.axis === 'a' ? lb : la, run = t.axis === 'a' ? la : lb;
  const heldKey = t.axis === 'a' ? b : a;
  const dir = p.gap >= 0 ? 'above' : 'below';
  return `With ${held} held at ${fix(t.at, 2)} ${unitOf(heldKey)}, the fitted response is ${fix(Math.abs(p.gap), 2)} outcome SD ${dir} the additive expectation at ${run} = ${fix(p.x, 2)}.`;
}

// ---------- registry filters (URL state) ----------
export interface FindingFilters { status: string; type: string; track: string; provenance: string; q: string; sort: string; page: number }
export const PAGE_SIZE = 12;
export const SORT_KEYS = ['-effect_size', 'effect_size', 'q_value', '-q_value', 'status', 'created'] as const;
export const DEFAULT_SORT = '-effect_size';

const pick = <T extends string>(v: string | null, allowed: readonly T[]): string => (v && (allowed as readonly string[]).includes(v) ? v : '');

export function parseFilters(sp: URLSearchParams): FindingFilters {
  const page = Number.parseInt(sp.get('page') ?? '1', 10);
  return {
    status: pick(sp.get('status'), ['CANDIDATE', 'VALIDATED', 'VERIFIED', 'BLOCKED', 'REJECTED']),
    type: pick(sp.get('type'), ['SYNERGISTIC', 'ANTAGONISTIC', 'NONLINEAR']),
    track: pick(sp.get('track'), ['A', 'B']),
    provenance: pick(sp.get('provenance'), ['REAL', 'SIMULATED']),
    q: (sp.get('q') ?? '').slice(0, 60),
    sort: pick(sp.get('sort'), SORT_KEYS) || DEFAULT_SORT,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}
export function filtersToParams(f: FindingFilters): URLSearchParams {
  const p = new URLSearchParams();
  (['status', 'type', 'track', 'provenance', 'q'] as const).forEach((k) => { if (f[k]) p.set(k, f[k]); });
  if (f.sort !== DEFAULT_SORT) p.set('sort', f.sort);
  if (f.page > 1) p.set('page', String(f.page));
  return p;
}
export const activeFilterCount = (f: FindingFilters) => (['status', 'type', 'track', 'provenance', 'q'] as const).filter((k) => f[k]).length;
export function toApiQuery(f: FindingFilters) {
  return {
    status: f.status || undefined, type: f.type || undefined, track: f.track || undefined, provenance: f.provenance || undefined,
    q: f.q || undefined, sort: f.sort, limit: PAGE_SIZE, offset: (f.page - 1) * PAGE_SIZE,
  };
}
/** Toggle a column sort: new column starts descending for effect, ascending for q. */
export function nextSort(current: string, col: 'effect' | 'q' | 'status'): string {
  if (col === 'effect') return current === '-effect_size' ? 'effect_size' : '-effect_size';
  if (col === 'q') return current === 'q_value' ? '-q_value' : 'q_value';
  return 'status';
}
export const pageCount = (total: number) => Math.max(1, Math.ceil(total / PAGE_SIZE));

/** Effect with interval for the mini forest. Falls back from the effect-size CI to the coefficient CI; null when none exists. */
export function forestSpan(f: Pick<Finding, 'effect'>): { point: number; lo: number; hi: number; unit: 'SD' | 'coef' } | null {
  const e = f.effect;
  if (e.effect_size != null && e.eff_ci_low != null && e.eff_ci_high != null) return { point: e.effect_size, lo: e.eff_ci_low, hi: e.eff_ci_high, unit: 'SD' };
  if (e.ci_low != null && e.ci_high != null && e.b_AB != null) return { point: e.b_AB, lo: e.ci_low, hi: e.ci_high, unit: 'coef' };
  return null;
}

// ---------- dossier ----------
export const GATE_ORDER = ['G1_DATA_INTEGRITY', 'G2_LEDGER_CHAIN', 'G3_LEDGER_INCLUSION', 'G4_REPRODUCIBILITY', 'G5_SECURITY_BLOCKING', 'G6_STATISTICAL_VALIDATION', 'G7_INDEPENDENT_REPLICATION', 'G8_REAL_PROVENANCE'];

const TYPE_PHRASE: Record<InteractionType, string> = {
  SYNERGISTIC: 'together raise the outcome more than the sum of their separate effects (synergistic)',
  ANTAGONISTIC: 'together change the outcome less than the sum of their separate effects (antagonistic)',
  NONLINEAR: 'together change the outcome in a way that bends or switches and is not a straight sum (non-linear)',
};
export const GATE_PHRASE: Record<string, string> = {
  G6_STATISTICAL_VALIDATION: 'it did not pass statistical validation',
  G7_INDEPENDENT_REPLICATION: 'it has no independent replication',
  G8_REAL_PROVENANCE: 'it is built on simulated rather than real data',
};
const EVIDENCE_PHRASE: Record<string, string> = {
  INTERNAL_REPLICATION: 'It was re-found in two disjoint halves of the cities, which is internal replication only, not independent replication.',
  INDEPENDENT_REPLICATION: 'It was re-found in an independent dataset.',
  CROSS_TISSUE_SAME_COHORT: 'It agrees across tissues from the same animals, a consistency check rather than independent replication.',
  HYPOTHESIS_ONLY: 'It has no replication, so it is a hypothesis only.',
};

/** Plain-language verdict sentence built from structured fields with a fixed template (no language model). */
export function findingSentence(f: Pick<Finding, 'provenance' | 'stressors' | 'type' | 'status' | 'effect' | 'stats' | 'evidence_level' | 'gates' | 'feature'>, labels: StressorInfo | undefined): string {
  const nm = (k: string) => labels?.[k]?.label ?? k;
  const where = f.provenance === 'SIMULATED' ? 'In simulated data' : 'In real data';
  const [a, b] = f.stressors;
  const span = forestSpan(f);
  const size = span && span.unit === 'SD'
    ? `, by ${fix(span.point, 2)} outcome SDs (95% CI ${fix(span.lo, 2)} to ${fix(span.hi, 2)})`
    : f.effect.effect_size != null ? `, by ${fix(f.effect.effect_size, 2)} outcome SDs` : '';
  const head = `${where}, ${nm(a)} and ${nm(b)} ${TYPE_PHRASE[f.type]}${size}.`;
  const failed = f.gates.filter((g) => !g.passed);
  const stat = f.gates.find((g) => g.id === 'G6_STATISTICAL_VALIDATION')?.passed
    ? `It passed significance (q = ${sci(f.stats.q)}), effect-size, confidence-interval and method-agreement checks. ` : '';
  const rep = EVIDENCE_PHRASE[f.evidence_level] ?? '';
  let cap = '';
  if (f.status === 'BLOCKED') cap = ' An integrity check failed, so the result is blocked from VERIFIED status.';
  else if (f.status === 'VALIDATED' && failed.length) cap = ` It is capped at VALIDATED because ${failed.map((g) => GATE_PHRASE[g.id] ?? `${g.label.replace(/\.$/, '').toLowerCase()} did not pass`).join(' and ')}.`;
  else if (f.status === 'VERIFIED') cap = ' It is VERIFIED, which means validated with intact computational provenance, not biologically proven.';
  return `${head} ${stat}${rep}${cap}`.replace(/\s+/g, ' ').trim();
}

/** What the dossier looks like after a re-verify: alert style only when the result is BLOCKED. */
export function verdictState(status: Status): { blocked: boolean; headline: string | null } {
  return status === 'BLOCKED' ? { blocked: true, headline: 'RESULT BLOCKED FROM VERIFIED STATUS' } : { blocked: false, headline: null };
}
export function whyNotVerified(f: Pick<FindingBundle, 'status'>, v: VerifyResult | null): string[] {
  if (v) return v.reasons;
  return [];
}

/** Which caveat banners apply to a finding. */
export function caveatKinds(f: Pick<Finding, 'provenance' | 'evidence_level'>): ('SIMULATED' | 'INTERNAL_REPLICATION' | 'CROSS_TISSUE_SAME_COHORT' | 'HYPOTHESIS_ONLY')[] {
  const out: ('SIMULATED' | 'INTERNAL_REPLICATION' | 'CROSS_TISSUE_SAME_COHORT' | 'HYPOTHESIS_ONLY')[] = [];
  if (f.provenance === 'SIMULATED') out.push('SIMULATED');
  if (f.evidence_level === 'INTERNAL_REPLICATION' || f.evidence_level === 'CROSS_TISSUE_SAME_COHORT' || f.evidence_level === 'HYPOTHESIS_ONLY') out.push(f.evidence_level);
  return out;
}
/** Inflation of the naive p-value relative to the calibrated one, in orders of magnitude. */
export function pInflationOrders(p: number | undefined, pNaive: number | undefined): number | null {
  if (!p || !pNaive || p <= 0 || pNaive <= 0) return null;
  return Math.log10(p) - Math.log10(pNaive);
}
