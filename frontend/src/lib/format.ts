// Number and text formatting used everywhere. Data is always shown in tabular monospace with units.

export const sci = (x: number | null | undefined, d = 2): string => {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  if (x === 0) return '0';
  const a = Math.abs(x);
  return a >= 0.001 && a < 1000 ? x.toPrecision(Math.max(d, 2)).replace(/\.?0+$/, '') : x.toExponential(d - 1);
};
export const fix = (x: number | null | undefined, d = 2): string => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toFixed(d));
export const pct = (x: number | null | undefined, d = 0): string => (x === null || x === undefined || Number.isNaN(x) ? '—' : `${(x * 100).toFixed(d)}%`);
export const int = (x: number | null | undefined): string => (x === null || x === undefined ? '—' : Math.round(x).toLocaleString('en-US'));
export const shortHash = (h: string | null | undefined, a = 8, b = 4): string =>
  h ? (h.length > a + b + 1 ? `${h.slice(0, a)}…${b > 0 ? h.slice(-b) : ''}` : h) : '—';
export const secs = (x: number | null | undefined): string => (x === null || x === undefined ? '—' : x < 1 ? `${Math.round(x * 1000)} ms` : x < 90 ? `${x.toFixed(1)} s` : `${(x / 60).toFixed(1)} min`);
export const utc = (ts: number | string | undefined): string => {
  if (ts === undefined) return '—';
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
};
export const titleCase = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export const TYPE_COLOR: Record<string, string> = {
  SYNERGISTIC: 'var(--biosphere)', ANTAGONISTIC: 'var(--signal)', NONLINEAR: 'var(--solar)',
};
export const TYPE_BLURB: Record<string, string> = {
  SYNERGISTIC: 'Together they do more than the sum of their parts.',
  ANTAGONISTIC: 'Together they do less than the sum of their parts.',
  NONLINEAR: 'The response switches on or bends at a threshold.',
};
export const STATUS_BLURB: Record<string, string> = {
  CANDIDATE: 'Found by the statistics, not yet fully validated.',
  VALIDATED: 'Passes significance, effect size, confidence interval and method agreement.',
  VERIFIED: 'Validated, independently replicated and computationally verified.',
  BLOCKED: 'An integrity check failed. The result is blocked from verified status.',
  REJECTED: 'Detectable, but too small to matter by the pre-specified threshold.',
};
