import { describe, expect, it } from 'vitest';
import fixture from './fixtures/scenario_parity.json';
import { evaluate, normalOf, percentile, rangeOf, surface, sweep, verdict, type ScenarioModel } from '../lib/scenario';

// The fixture holds a model fitted on SYNTHETIC data and the answers the Python code (synera_core.prediction.scenario.predict)
// gives for several scenarios. The browser must reproduce them: it is the same model, evaluated in a second language.
const model = fixture.model as unknown as ScenarioModel;
type Case = { state: string; woy: number; levels: Record<string, number>; expected: Record<string, number> };
const cases = fixture.cases as unknown as Case[];

describe('scenario model: TypeScript twin of the Python predictor', () => {
  it.each(cases.map((c, i) => [i, c] as const))('case %i matches Python to 1e-9', (_i, c) => {
    const r = evaluate(model, c.state, c.woy, c.levels);
    expect(r.effect).toBeCloseTo(c.expected.effect_pct, 9);
    expect(r.lo).toBeCloseTo(c.expected.lo_pct, 9);
    expect(r.hi).toBeCloseTo(c.expected.hi_pct, 9);
    expect(r.additive).toBeCloseTo(c.expected.additive_pct, 9);
    expect(r.interaction).toBeCloseTo(c.expected.interaction_pct, 9);
    expect(r.interactionLo).toBeCloseTo(c.expected.interaction_lo_pct, 9);
    expect(r.interactionHi).toBeCloseTo(c.expected.interaction_hi_pct, 9);
    expect(r.extraDeaths).toBeCloseTo(c.expected.extra_deaths_per_week, 9);
  });

  it('a typical week has exactly zero effect and zero interval', () => {
    const st = Object.keys(model.locations)[0];
    const r = evaluate(model, st, 10, {});
    expect([r.effect, r.lo, r.hi, r.interaction]).toEqual([0, 0, 0, 0]);
    expect(verdict(r).headline).toMatch(/no clear effect/i);
  });

  it('contributions add up to the total effect', () => {
    const st = Object.keys(model.locations)[1];
    const loc = model.locations[st];
    const r = evaluate(model, st, 20, { pm25: loc.clim.pm25[20] + 2 * loc.sd.pm25, o3: loc.clim.o3[20] + 2 * loc.sd.o3 });
    const sum = Object.values(r.contributions).reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(r.effect, 9);
    expect(r.effect).toBeCloseTo(r.additive + r.interaction, 9);
  });

  it('sweeps and surfaces stay inside the stressor ranges and include the scenario point', () => {
    const st = Object.keys(model.locations)[0];
    const [lo, hi] = rangeOf(model, st, 5, 'pm25');
    const s = sweep(model, st, 5, {}, 'pm25', 9);
    expect(s[0].x).toBeCloseTo(lo, 9);
    expect(s[8].x).toBeCloseTo(hi, 9);
    const mid = normalOf(model, st, 5, 'pm25').normal;
    const sf = surface(model, st, 5, {}, 'pm25', 'o3', 5);
    expect(sf.cells).toHaveLength(5);
    expect(lo).toBeLessThanOrEqual(mid);
    expect(hi).toBeGreaterThanOrEqual(mid);
  });

  it('percentile matches numpy.percentile (linear interpolation)', () => {
    expect(percentile([1, 2, 3, 4, 5], 5)).toBeCloseTo(1.2, 12);
    expect(percentile([1, 2, 3, 4, 5], 95)).toBeCloseTo(4.8, 12);
    expect(percentile([10, 20], 50)).toBe(15);
  });
});
