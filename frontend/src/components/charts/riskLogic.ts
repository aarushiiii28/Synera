// Pure logic for the Risk Brief: tier styling, banner rules, headline text. No invented values.
import type { Risk, RiskDay } from '../../lib/api';
import { fix } from '../../lib/format';

export const TIER_ORDER = ['LOW', 'MODERATE', 'HIGH', 'SEVERE'] as const;
export const TIER_TONE: Record<string, string> = { LOW: 'var(--teal)', MODERATE: 'var(--signal)', HIGH: 'var(--solar)', SEVERE: 'var(--alert)' };
export const TIER_NONE = 'no data';

/** Null or unknown tiers are shown as 'no data'. A tier is never guessed. */
export const tierLabel = (t: string | null | undefined): string => (t ? t : TIER_NONE);
export const tierColor = (t: string | null | undefined): string => (t ? TIER_TONE[t] ?? 'var(--muted)' : 'var(--faint)');

/** The persistent banner appears whenever the response is simulated-only, using the API text. */
export function bannerText(r: Pick<Risk, 'simulated_only' | 'banner'>): string | null {
  if (!r.simulated_only) return null;
  return r.banner && r.banner.trim() ? r.banner : 'SIMULATED DEMONSTRATION: no verified real-world interaction supports this brief.';
}

export const SOURCE_TAG: Record<Risk['source']['mode'], { label: string; tone: string; text: string }> = {
  live: { label: 'LIVE FORECAST', tone: 'var(--biosphere)', text: 'Fetched from the Open-Meteo forecast and air-quality services just now.' },
  cached: { label: 'CACHED FORECAST', tone: 'var(--signal)', text: 'A recent forecast stored on this machine.' },
  archive_fallback: { label: 'ARCHIVE FALLBACK', tone: 'var(--solar)', text: 'No live or cached forecast was available; the last days of the stored archive are shown instead.' },
};

/** Percentile arrives as a 0-1 fraction. Shown as an ordinal rank: "84th". */
export function ordinal(n: number): string {
  const v = Math.round(n);
  const s = ['th', 'st', 'nd', 'rd'], m = v % 100;
  return v + (s[(m - 20) % 10] || s[m] || s[0]);
}
export const percentileText = (p: number | null | undefined): string => (p === null || p === undefined ? 'no data' : ordinal(p * 100));

export const sd = (x: number | null | undefined, d = 3): string => (x === null || x === undefined ? 'not computed' : `${x >= 0 ? '+' : ''}${fix(x, d)}`);

export function briefHeadline(r: Risk): string | null {
  if (!r.available || !r.risk_tier) return null;
  const p = percentileText(r.risk_percentile);
  const band = r.uncertainty_lower !== undefined && r.uncertainty_upper !== undefined ? ` (plausible range ${sd(r.uncertainty_lower)} to ${sd(r.uncertainty_upper)})` : '';
  const up = r.interaction_uplift;
  const dir = up === undefined ? '' : up > 0 ? 'above' : up < 0 ? 'below' : 'equal to';
  return `Today ${r.region} sits at the ${p} percentile of its own history for interaction-driven risk: tier ${r.risk_tier}. The interaction adds ${sd(up)} outcome SD${dir ? `, ${dir} what the stressors would do separately` : ''}${band}.`;
}

/** Days with a null tier or percentile are kept, just labelled. */
export const dayHasData = (d: RiskDay): boolean => d.tier !== null && d.percentile !== null;

export const dayName = (iso: string): string => {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC' });
};

/** Does the interval straddle zero? Then the sign of the uplift is not established. */
export const straddlesZero = (lo: number | undefined, hi: number | undefined): boolean => lo !== undefined && hi !== undefined && lo < 0 && hi > 0;

export const FLOW = [
  { t: 'Complex environmental data', d: 'Heat, air quality, drought, weather, radiation' },
  { t: 'Hidden interactions', d: 'Effects that only appear together' },
  { t: 'AI discovery', d: 'Screen every pair of stressors' },
  { t: 'Scientific validation', d: 'FDR, effect size, intervals, replication' },
  { t: 'Cybersecurity', d: 'Tamper and poisoning checks' },
  { t: 'Verifiable provenance', d: 'Hashes and a signed ledger' },
  { t: 'Environmental / climate resilience', d: 'Decisions that can be trusted' },
] as const;

export const OUTCOMES = ['Climate-health', 'Ecosystem resilience', 'Extreme environmental events', 'Environmental risk', 'Scientific reproducibility', 'Space biology', 'Cybersecurity'] as const;
