import { describe, expect, it } from 'vitest';
import type { NullCal } from '../lib/api';
import {
  FUNNEL_ORDER, NA_NULL, NOT_COMPUTED, biggestDrop, calClass, cellText, detectorKeys, fdrText, fdrVerdict, funnelSentence, hasLimitations,
  lambdaClause, nullHeadline, recallText, snrKeys, snrSentence, type BenchSnr,
} from '../components/charts/benchLogic';
import { bannerText, briefHeadline, dayHasData, ordinal, percentileText, sd, straddlesZero, tierColor, tierLabel } from '../components/charts/riskLogic';
import type { Risk } from '../lib/api';

// Small throw-away fixtures: they exercise formatting logic only and are never rendered by the app.
const cal = (l: number): NullCal => ({ lambda_median: l, lambda_range: [l / 2, l * 2], frac_p_lt_05_median: 0.05, frac_p_lt_05_pooled: 0.05, p_histogram_10bins: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1] });
const stage = (tp: number, proxy: number, hard: number, easy: number) => {
  const n = tp + proxy + hard + easy;
  return { discoveries: n, true_positives: tp, proxy, hard_decoy: hard, easy_decoy: easy, recall: tp / 3, precision: n ? tp / n : null,
    fdr_strict: n ? (n - tp) / n : null, fdr_proxy_aware: null, seeds_with_zero_discoveries: 0, type_accuracy: null };
};
const stages = {
  marginal_naive: stage(3, 5, 10, 8), marginal_boot: stage(3, 5, 8, 6), conditional: stage(3, 1, 0, 0), effect_gate: stage(3, 1, 0, 0), full_stack: stage(3, 0, 0, 0),
} as BenchSnr['stages'];

describe('benchmark headline text', () => {
  it('describes over-confident, conservative and calibrated tests from lambda', () => {
    expect(calClass(4.1)).toBe('overconfident');
    expect(calClass(0.5)).toBe('conservative');
    expect(calClass(1.05)).toBe('calibrated');
    expect(lambdaClause('the naive test', 4.114)).toBe('the naive test is over-confident by a factor of 4.1×');
    expect(lambdaClause('x', 14.3)).toContain('14×');
    expect(lambdaClause('x', 1.0)).toContain('close to honest');
  });
  it('builds the null sentence from all three methods', () => {
    const s = nullHeadline({ naive: cal(4.1), hac: cal(14.3), boot: cal(1.0) });
    expect(s).toContain('4.1×');
    expect(s).toContain('14×');
    expect(s).toContain('block-bootstrap test is close to honest');
  });
});

describe('FDR and recall formatting', () => {
  it('shows null FDR as n/a, never as zero, and zero as zero', () => {
    expect(fdrText(null)).toBe(NA_NULL);
    expect(fdrText(0)).toBe('0.0%');
    expect(fdrText(undefined)).toBe(NOT_COMPUTED);
    expect(recallText(undefined)).toBe(NOT_COMPUTED);
    expect(recallText(0)).toBe('0%');
  });
  it('never colours an over-target FDR as success', () => {
    expect(fdrVerdict(0.063, 0.05)).toBe('exceeds');
    expect(fdrVerdict(0.007, 0.05)).toBe('meets');
    expect(fdrVerdict(null, 0.05)).toBe('na');
  });
  it('writes the per-SNR sentence including the unfavourable verdict', () => {
    const snr = { stages: { ...stages, full_stack: stage(9, 1, 0, 0) } } as unknown as BenchSnr;
    expect(snrSentence('1.0', snr)).toContain('ABOVE target');
    expect(snrSentence('5.0', undefined)).toContain('not computed');
    const none = { stages: { ...stages, full_stack: stage(0, 0, 0, 0) } } as unknown as BenchSnr;
    expect(snrSentence('5.0', none)).toContain('n/a');
  });
});

describe('funnel', () => {
  it('finds the stage that removes the most false discoveries', () => {
    const d = biggestDrop(stages);
    expect(d).toEqual({ from: 'marginal_boot', to: 'conditional', removed: 18 });
    expect(funnelSentence('1.0', stages)).toContain('Conditional selection');
    expect(FUNNEL_ORDER).toHaveLength(5);
  });
  it('keeps API snr keys exactly as spelled', () => {
    expect(snrKeys({ by_snr: { '20.0': {}, '1.0': {}, '5.0': {} } } as never)).toEqual(['1.0', '5.0', '20.0']);
  });
});

describe('security helpers and limitations', () => {
  it('lists detectors with aggregate columns last and treats missing cells as not computed', () => {
    const k = detectorKeys({ a: { '0.01': { hash: 1, mcd: 0, any_statistical: 0.2, autoencoder: 0 } } });
    expect(k).toEqual(['autoencoder', 'mcd', 'hash', 'any_statistical']);
    expect(cellText(undefined)).toBe('—');
    expect(cellText(0)).toBe('0%');
  });
  it('detects when limitations must be rendered', () => {
    expect(hasLimitations({ available: false, limitations: ['x'] })).toBe(true);
    expect(hasLimitations({ available: false, limitations: [] })).toBe(false);
    expect(hasLimitations(undefined)).toBe(false);
  });
});

describe('risk brief logic', () => {
  it('shows the simulated banner whenever simulated_only is true, using the API text', () => {
    expect(bannerText({ simulated_only: true, banner: 'SIMULATED DEMONSTRATION: x' })).toBe('SIMULATED DEMONSTRATION: x');
    expect(bannerText({ simulated_only: true, banner: null })).toContain('SIMULATED DEMONSTRATION');
    expect(bannerText({ simulated_only: false, banner: null })).toBeNull();
  });
  it('labels null tiers as no data and formats percentiles', () => {
    expect(tierLabel(null)).toBe('no data');
    expect(tierColor(null)).toBe('var(--faint)');
    expect(percentileText(null)).toBe('no data');
    expect(percentileText(0.84)).toBe('84th');
    expect(ordinal(11)).toBe('11th');
    expect(ordinal(22)).toBe('22nd');
    expect(dayHasData({ date: '2026-01-01', additive: 0, modelled: 0, uplift: 0, percentile: null, tier: null, stressors: {} })).toBe(false);
  });
  it('formats signed uplift and flags intervals crossing zero', () => {
    expect(sd(0.1234)).toBe('+0.123');
    expect(sd(-0.5, 2)).toBe('-0.50');
    expect(sd(undefined)).toBe('not computed');
    expect(straddlesZero(-0.1, 0.2)).toBe(true);
    expect(straddlesZero(0.1, 0.2)).toBe(false);
  });
  it('generates the headline from numbers and refuses to invent one when unavailable', () => {
    const base = { region: 'Delhi', available: true, simulated_only: true, banner: null, source: { mode: 'live' }, source_findings: [], findings: [], receipt: [], risk_tier: null } as unknown as Risk;
    const h = briefHeadline({ ...base, risk_tier: 'HIGH', risk_percentile: 0.87, interaction_uplift: 0.2, uncertainty_lower: 0.1, uncertainty_upper: 0.3 });
    expect(h).toContain('87th');
    expect(h).toContain('HIGH');
    expect(h).toContain('+0.200');
    expect(briefHeadline({ ...base, available: false, risk_tier: null })).toBeNull();
  });
});
