import { describe, expect, it } from 'vitest';
import type { Finding, MatrixCell, RunEvent, Surface } from '../lib/api';
import {
  activeFilterCount, caveatKinds, crossCheck, diamondRadius, explainedAway, filtersToParams, findingSentence, forestSpan, funnelStages, nextSort, overallProgress,
  pageCount, parseFilters, peakGap, peakGapIndex, pInflationOrders, runBanner, screenAudit, stepViews, toApiQuery, transect, verdictState,
} from '../components/charts/discoveryLogic';

const ev = (step: number, status: RunEvent['status'], data: Record<string, unknown> = {}, name = 'X'): RunEvent => ({
  run_id: 'r', step, step_name: name, label: 'l', status, progress: step / 9, message: 'm', duration_s: status === 'DONE' ? 1.5 : null, ts: 0, data,
});

describe('run timeline', () => {
  const steps = [{ step: 1, label: 'A' }, { step: 2, label: 'B' }];
  it('folds events into one row per step, latest wins', () => {
    const v = stepViews([ev(1, 'RUNNING'), ev(1, 'DONE', { rows: 10, sha256: 'abc' })], steps);
    expect(v[0].state).toBe('DONE');
    expect(v[0].duration).toBe(1.5);
    expect(v[0].counts).toEqual([{ k: 'rows', v: '10' }]);
    expect(v[1].state).toBe('PENDING');
  });
  it('reports progress from the newest event or null', () => {
    expect(overallProgress([])).toBeNull();
    expect(overallProgress([ev(3, 'RUNNING')])).toBeCloseTo(1 / 3);
  });
  it('banner only for blocked or failed runs', () => {
    expect(runBanner('COMPLETED', null)).toBeNull();
    expect(runBanner('FAILED', 'boom')?.text).toBe('boom');
    expect(runBanner('BLOCKED', null)?.title).toBe('RUN BLOCKED');
  });
});

describe('funnel', () => {
  const run = {
    stage_counts: { marginal_bh: 43, after_forward: 3, after_backward: 3 }, summary: {},
    events: [ev(3, 'DONE', { n_pairs: 45 }, 'DISCOVERY'), ev(4, 'DONE', { validated: 3 }, 'VALIDATION')],
  };
  it('uses the real counts and keeps zeros', () => {
    const s = funnelStages(run)!;
    expect(s.map((x) => x.value)).toEqual([45, 43, 3, 3]);
    expect(explainedAway(s)).toBe(40);
    expect(funnelStages({ ...run, stage_counts: { marginal_bh: 0, after_forward: 0, after_backward: 0 } })![3].value).toBe(3);
  });
  it('is null when the run has no pair stages', () => {
    expect(funnelStages({ ...run, stage_counts: null })).toBeNull();
    expect(funnelStages({ ...run, events: [] })).toBeNull();
  });
});

describe('standard screen audit', () => {
  const cell = (o: Partial<MatrixCell>): MatrixCell => ({
    a: 'x', b: 'y', category: 'not_significant', type: null, status: null, finding_id: null, effect_size: null, q_marginal: 0.5,
    p_conditional: null, gbm_rank: null, nid_rank: null, methods: null, p_naive: 0.9, ...o });
  it('lists what each approach would flag and what survived', () => {
    const a = screenAudit([
      cell({ a: 'a', b: 'b', p_naive: 0.001, gbm_rank: 1, category: 'selected', status: 'VALIDATED' }),
      cell({ a: 'a', b: 'c', p_naive: 0.01, nid_rank: 3, category: 'explained_away' }),
      cell({ a: 'b', b: 'c', p_naive: 0.03 }),
      cell({ a: 'c', b: 'd' }),
    ]);
    expect(a).toMatchObject({ total: 4, plain: 3, trees: 1, neural: 1, flagged: 3, survived: 1 });
    expect(a.rows[0].survived).toBe(true);
    expect(a.rows.map((r) => r.verdict)).toEqual(expect.arrayContaining(['Copycat of a stronger pair', 'Almost certainly chance']));
  });
  it('reports zero flagged when nothing is flagged', () => {
    expect(screenAudit([cell({})])).toMatchObject({ flagged: 0, survived: 0 });
  });
});

describe('cross-check between two panels', () => {
  const c = (a: string, b: string, status: MatrixCell['status'], eff: number | null = 0.1): MatrixCell => ({
    a, b, category: status ? 'selected' : 'not_significant', type: null, status, finding_id: null, effect_size: eff, q_marginal: 0.01,
    p_conditional: null, gbm_rank: null, nid_rank: null, methods: null, p_naive: 0.01 });
  it('counts pairs kept in both, only here and only there, whatever the order of a and b', () => {
    const r = crossCheck(
      [c('t', 'r', 'VALIDATED', 0.14), c('t', 'c', 'VALIDATED'), c('w', 'c', 'CANDIDATE')],
      [c('r', 't', 'VALIDATED', 0.18), c('s', 'c', 'VALIDATED'), c('t', 'c', 'REJECTED')]);
    expect(r).toMatchObject({ both: 1, onlyHere: 1, onlyOther: 1 });
    expect(r.rows[0]).toMatchObject({ here: true, other: true, effectHere: 0.14, effectOther: 0.18 });
  });
  it('is empty when nothing was kept', () => {
    expect(crossCheck([c('a', 'b', null)], [c('a', 'b', 'CANDIDATE')]).rows).toEqual([]);
  });
});

describe('matrix helpers', () => {
  it('sizes diamonds by effect and falls back to the minimum', () => {
    expect(diamondRadius(null, 0.3, 8, 20)).toBe(8);
    expect(diamondRadius(0.3, 0.3, 8, 20)).toBe(20);
    expect(diamondRadius(0.15, 0.3, 8, 20)).toBe(14);
  });
  it('type check for cell category', () => {
    const c: MatrixCell['category'] = 'selected';
    expect(c).toBe('selected');
  });
});

describe('surface transects', () => {
  // 3x3 grid, z[row = b][col = a]
  const s: Surface = {
    a: 'a', b: 'b', grid_a: [0, 1, 2], grid_b: [10, 20, 30], units: 'sd', type: 'SYNERGISTIC', provenance: 'SIMULATED',
    z_additive: [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
    z_full: [[0, 0, 0], [0, 0.1, 0], [0, 0.2, 0.9]], z_gap: [[0, 0, 0], [0, 0.1, 0], [0, 0.2, 0.9]],
  };
  it('reads rows as grid_b and columns as grid_a', () => {
    const t = transect(s, 'a', 2);
    expect(t.at).toBe(30);
    expect(t.xs).toEqual([0, 1, 2]);
    expect(t.full).toEqual([0, 0.2, 0.9]);
    const u = transect(s, 'b', 2);
    expect(u.at).toBe(2);
    expect(u.full).toEqual([0, 0, 0.9]);
  });
  it('finds the peak gap', () => {
    expect(peakGapIndex(s, 'a')).toBe(2);
    expect(peakGap(transect(s, 'a', 2))).toEqual({ i: 2, x: 2, gap: 0.9 });
  });
  it('clamps the held index', () => {
    expect(transect(s, 'a', 99).index).toBe(2);
  });
});

describe('registry URL state', () => {
  it('round-trips and drops defaults', () => {
    const f = parseFilters(new URLSearchParams('status=VALIDATED&type=NONLINEAR&q=heat&page=2&sort=q_value'));
    expect(f).toMatchObject({ status: 'VALIDATED', type: 'NONLINEAR', q: 'heat', page: 2, sort: 'q_value' });
    expect(filtersToParams(f).toString()).toBe('status=VALIDATED&type=NONLINEAR&q=heat&sort=q_value&page=2');
    expect(filtersToParams(parseFilters(new URLSearchParams())).toString()).toBe('');
  });
  it('rejects unknown values', () => {
    const f = parseFilters(new URLSearchParams('status=BOGUS&page=-4&sort=hack'));
    expect(f.status).toBe('');
    expect(f.page).toBe(1);
    expect(f.sort).toBe('-effect_size');
    expect(activeFilterCount(f)).toBe(0);
  });
  it('builds the API query with offset', () => {
    expect(toApiQuery(parseFilters(new URLSearchParams('page=3')))).toMatchObject({ limit: 12, offset: 24 });
  });
  it('toggles sorts and counts pages', () => {
    expect(nextSort('-effect_size', 'effect')).toBe('effect_size');
    expect(nextSort('effect_size', 'q')).toBe('q_value');
    expect(pageCount(0)).toBe(1);
    expect(pageCount(25)).toBe(3);
  });
  it('mini forest span needs an interval', () => {
    expect(forestSpan({ effect: { b_AB: 1, ci_low: 0, ci_high: 2, cohens_d: 1 } })).toMatchObject({ unit: 'coef' });
    expect(forestSpan({ effect: { b_AB: 1, ci_low: null as unknown as number, ci_high: null as unknown as number, cohens_d: 1 } })).toBeNull();
    expect(forestSpan({ effect: { b_AB: 1, ci_low: 0, ci_high: 2, cohens_d: 1, effect_size: 0.3, eff_ci_low: 0.2, eff_ci_high: 0.5 } })).toEqual({ point: 0.3, lo: 0.2, hi: 0.5, unit: 'SD' });
  });
});

describe('dossier text', () => {
  const f = {
    provenance: 'SIMULATED', stressors: ['heat_index', 'pm25'], type: 'SYNERGISTIC', status: 'VALIDATED', feature: null, evidence_level: 'INTERNAL_REPLICATION',
    effect: { b_AB: 0.3, ci_low: 0.2, ci_high: 0.4, cohens_d: 0.32, effect_size: 0.32, eff_ci_low: 0.25, eff_ci_high: 0.55 },
    stats: { p: 1e-9, q: 3e-8, n: 10, df: 10 },
    gates: [
      { id: 'G6_STATISTICAL_VALIDATION', label: 'Statistically validated', passed: true, reason: '', integrity: false },
      { id: 'G7_INDEPENDENT_REPLICATION', label: 'x', passed: false, reason: '', integrity: false },
      { id: 'G8_REAL_PROVENANCE', label: 'y', passed: false, reason: '', integrity: false },
    ],
  } as unknown as Finding;
  it('generates a sentence from fields, no invented numbers', () => {
    const s = findingSentence(f, { heat_index: { label: 'heat index', unit: '', group: '', about: '' }, pm25: { label: 'PM2.5', unit: '', group: '', about: '' } });
    expect(s).toContain('In simulated data, heat index and PM2.5 together raise the outcome more than the sum');
    expect(s).toContain('0.32 outcome SDs (95% CI 0.25 to 0.55)');
    expect(s).toContain('capped at VALIDATED because it has no independent replication and it is built on simulated');
  });
  it('blocked verdict switches to the alert style', () => {
    expect(verdictState('BLOCKED')).toEqual({ blocked: true, headline: 'RESULT BLOCKED FROM VERIFIED STATUS' });
    expect(verdictState('VALIDATED').blocked).toBe(false);
  });
  it('caveats follow provenance and evidence', () => {
    expect(caveatKinds({ provenance: 'SIMULATED', evidence_level: 'INTERNAL_REPLICATION' })).toEqual(['SIMULATED', 'INTERNAL_REPLICATION']);
    expect(caveatKinds({ provenance: 'REAL', evidence_level: 'INDEPENDENT_REPLICATION' })).toEqual([]);
  });
  it('p inflation in orders of magnitude', () => {
    expect(pInflationOrders(1e-5, 1e-15)).toBeCloseTo(10);
    expect(pInflationOrders(undefined, 1e-5)).toBeNull();
  });
});
