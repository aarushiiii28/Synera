// Pure logic for the Benchmark page: headline sentences, tier formatting and "not computed" handling.
// Nothing here invents a number. Every value is read from the API payload; absent fields stay absent.
import type { Benchmark, NullCal } from '../../lib/api';
import { fix, pct } from '../../lib/format';

export type BenchDiscovery = NonNullable<Benchmark['discovery']>;
export type BenchSnr = BenchDiscovery['by_snr'][string];
export type BenchStage = BenchSnr['stages'][string];

/** Funnel order requested for the page. (marginal_hac is also in the report; it is shown as a footnote line.) */
export const FUNNEL_ORDER = ['marginal_naive', 'marginal_boot', 'conditional', 'effect_gate', 'full_stack'] as const;

export const STAGE_LABEL: Record<string, { short: string; long: string }> = {
  marginal_naive: { short: 'Pairwise · naive', long: 'Every pair tested alone with ordinary p-values' },
  marginal_hac: { short: 'Pairwise · HAC', long: 'Pairwise screen with autocorrelation-robust p-values' },
  marginal_boot: { short: 'Pairwise · bootstrap', long: 'Pairwise screen with block-bootstrap p-values' },
  conditional: { short: 'Conditional selection', long: 'Look-alike pairs removed by re-testing with the best pair in the model' },
  effect_gate: { short: 'Effect-size gate', long: 'Tiny effects removed by the minimum-effect threshold' },
  full_stack: { short: 'Full stack', long: 'Everything combined: what SYNERA would report' },
};

export const SEGMENTS = [
  { key: 'true_positives', label: 'True interaction', color: 'var(--biosphere)', note: 'a planted interaction' },
  { key: 'proxy', label: 'Proxy', color: 'var(--solar)', note: 'a look-alike of a planted pair' },
  { key: 'hard_decoy', label: 'Hard decoy', color: 'var(--alert)', note: 'a null pair that shares a stressor with a planted pair' },
  { key: 'easy_decoy', label: 'Easy decoy', color: 'var(--faint)', note: 'a null pair unrelated to any planted pair' },
] as const;
export type SegKey = (typeof SEGMENTS)[number]['key'];

export const NOT_COMPUTED = 'not computed';
export const NA_NULL = 'n/a (no discoveries)';

/** Strict / proxy-aware FDR for display. null means the stage made no discoveries: shown as n/a, never as 0%. */
export const fdrText = (x: number | null | undefined, d = 1): string => {
  if (x === undefined) return NOT_COMPUTED;
  if (x === null) return NA_NULL;
  return pct(x, d);
};

export const recallText = (x: number | null | undefined, d = 0): string => (x === null || x === undefined ? NOT_COMPUTED : pct(x, d));

/** Honest tone for an FDR against the nominal target. Over target is never drawn as a success. */
export type Verdict = 'meets' | 'exceeds' | 'na';
export const fdrVerdict = (x: number | null | undefined, target: number): Verdict => (x === null || x === undefined ? 'na' : x <= target ? 'meets' : 'exceeds');
export const VERDICT_TONE: Record<Verdict, string> = { meets: 'var(--teal)', exceeds: 'var(--alert)', na: 'var(--faint)' };
export const VERDICT_WORD: Record<Verdict, string> = { meets: 'within target', exceeds: 'ABOVE target', na: 'n/a' };

/** Calibration verdict for lambda: 1.0 is honest. */
export type CalClass = 'overconfident' | 'conservative' | 'calibrated';
export const calClass = (l: number, tol = 0.2): CalClass => (l > 1 + tol ? 'overconfident' : l < 1 - tol ? 'conservative' : 'calibrated');
export const CAL_TONE: Record<CalClass, string> = { overconfident: 'var(--alert)', conservative: 'var(--solar)', calibrated: 'var(--teal)' };
export const CAL_WORD: Record<CalClass, string> = { overconfident: 'over-confident', conservative: 'conservative', calibrated: 'close to honest' };

export const lambdaFactor = (l: number): string => `${fix(l, l >= 10 ? 0 : 1)}×`;

/** One clause per method, generated from lambda. */
export function lambdaClause(name: string, l: number): string {
  const c = calClass(l);
  if (c === 'overconfident') return `${name} is over-confident by a factor of ${lambdaFactor(l)}`;
  if (c === 'conservative') return `${name} is conservative (λ ${fix(l, 2)}, it under-reports significance)`;
  return `${name} is close to honest (λ ${fix(l, 2)})`;
}

export function nullHeadline(nc: { naive: NullCal; hac: NullCal; boot: NullCal }): string {
  return `With persistent daily weather data, ${lambdaClause('the naive test', nc.naive.lambda_median)}; ${lambdaClause('the HAC test', nc.hac.lambda_median)}; ${lambdaClause('the block-bootstrap test', nc.boot.lambda_median)}.`;
}

export const falseAlarmClause = (nc: NullCal): string =>
  `${pct(nc.frac_p_lt_05_pooled, 1)} of null p-values fell below 0.05 (a calibrated test gives 5.0%)`;

/** Full-stack sentence for one SNR. */
export function snrSentence(snr: string, s: BenchSnr | undefined, target = 0.05): string {
  const f = s?.stages.full_stack;
  if (!f) return `SNR ${snr}: full stack not computed.`;
  const v = fdrVerdict(f.fdr_strict, target);
  const fdr = f.fdr_strict === null ? 'no discoveries were made, so FDR is n/a' : `strict FDR ${pct(f.fdr_strict, 1)} (${VERDICT_WORD[v]} of ${pct(target, 0)})`;
  return `SNR ${snr}: recall ${pct(f.recall, 0)} of planted interactions, ${fdr}.`;
}

/** Where the false discoveries die: stage with the largest drop in strict false discoveries, from the data. */
export function biggestDrop(stages: BenchSnr['stages']): { from: string; to: string; removed: number } | null {
  let best: { from: string; to: string; removed: number } | null = null;
  const fp = (k: string) => stages[k] ? stages[k].proxy + stages[k].hard_decoy + stages[k].easy_decoy : null;
  for (let i = 1; i < FUNNEL_ORDER.length; i++) {
    const a = fp(FUNNEL_ORDER[i - 1]), b = fp(FUNNEL_ORDER[i]);
    if (a === null || b === null) continue;
    const removed = a - b;
    if (removed > 0 && (!best || removed > best.removed)) best = { from: FUNNEL_ORDER[i - 1], to: FUNNEL_ORDER[i], removed };
  }
  return best;
}

export function funnelSentence(snr: string, stages: BenchSnr['stages']): string | null {
  const d = biggestDrop(stages);
  const first = stages[FUNNEL_ORDER[0]], last = stages.full_stack;
  if (!first || !last) return null;
  const fp = (s: BenchStage) => s.proxy + s.hard_decoy + s.easy_decoy;
  const base = `At SNR ${snr} the naive pairwise screen reports ${first.discoveries} discoveries, ${fp(first)} of them false by the strict count. The full stack reports ${last.discoveries}, ${fp(last)} false.`;
  return d ? `${base} The largest cut comes at "${STAGE_LABEL[d.to].short}" (${d.removed} false discoveries removed).` : base;
}

/** Share a count takes of a stacked bar; zero stays zero. */
export const share = (n: number, total: number): number => (total > 0 ? n / total : 0);

export const sortedKeys = (o: Record<string, unknown>): string[] => Object.keys(o).sort((a, b) => parseFloat(a) - parseFloat(b));

/** Log-scale position in [0,1]. */
export const logPos = (v: number, lo: number, hi: number): number => (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo));

/** Security: detector keys present in the attack cells, excluding the aggregate columns. */
export function detectorKeys(attacks: Record<string, Record<string, Record<string, number>>>): string[] {
  const set = new Set<string>();
  Object.values(attacks).forEach((lv) => Object.values(lv).forEach((cell) => Object.keys(cell).forEach((k) => set.add(k))));
  const order = ['hash', 'any_statistical'];
  return [...[...set].filter((k) => !order.includes(k)).sort(), ...order.filter((k) => set.has(k))];
}

export const DETECTOR_LABEL: Record<string, string> = {
  hash: 'SHA-256 hash', any_statistical: 'Any statistical detector', any_detector_warns: 'Any detector warns',
  physical_range: 'Physical range', duplicates: 'Duplicates', isolation_forest: 'Isolation forest', mcd: 'Robust covariance (MCD)',
  autoencoder: 'Autoencoder', distribution_drift: 'Distribution drift', label_flip: 'Label flip',
};
export const detectorLabel = (k: string): string => DETECTOR_LABEL[k] ?? k.replace(/_/g, ' ');

/** A cell is 'not computed' when the key is missing, never zero. */
export const cellText = (v: number | undefined): string => (v === undefined ? '—' : pct(v, 0));

export function hasLimitations(b: Benchmark | undefined): b is Benchmark & { limitations: string[] } {
  return !!b && Array.isArray(b.limitations) && b.limitations.length > 0;
}

/** by_snr keys exactly as the API spells them (e.g. '1.0'), sorted numerically. String(1.0) would give '1' and miss. */
export const snrKeys = (d: BenchDiscovery): string[] => sortedKeys(d.by_snr);
