import { describe, expect, it } from 'vitest';
import {
  DEFAULTS, boundedAppend, contrast, dewPointC, factorialScenarios, heatIndexC, interactionGrid, seriesStats, valueOf, windowOf, type LiveReading,
} from '../lib/live';

const rd = (seq: number, t: number | null, h: number | null, g: number, secs = seq, source: LiveReading['source'] = 'REAL_SENSOR'): LiveReading => ({
  seq, device_id: 'd', time_ms: seq * 2000, received_utc: new Date(Date.UTC(2026, 9, 30, 12, 0, secs)).toISOString(), source,
  measurements: [
    { sensor: 'temperature', value: t, unit: '°C', quality: t === null ? 'MISSING' : 'OK' },
    { sensor: 'humidity', value: h, unit: '%', quality: h === null ? 'MISSING' : 'OK' },
    { sensor: 'gas', value: g, unit: 'ADC', quality: 'OK' }],
});

describe('heat index and dew point', () => {
  // Values computed by synera_core.data.cities.calculate_heat_index (the function that built the historical panels): the two must agree.
  const PY: [number, number, number][] = [[20, 30, 18.838888889], [25, 50, 24.861111111], [26, 57, 26.143888889], [30, 40, 29.689165056], [32, 70, 40.40927368],
    [35, 50, 40.675428944], [35, 70, 50.340578056], [38, 85, 76.10020368], [27, 40, 26.86317312], [45, 20, 46.077777778]];
  it('matches the Python implementation to 6 decimals', () => { for (const [t, r, hi] of PY) expect(heatIndexC(t, r)).toBeCloseTo(hi, 6); });
  it('dew point is below the air temperature and equals it at saturation', () => {
    expect(dewPointC(26, 57)).toBeLessThan(26);
    expect(dewPointC(26, 100)).toBeCloseTo(26, 6);
    expect(dewPointC(30, 40)).toBeCloseTo(15.1, 0);
  });
});

describe('series statistics', () => {
  it('uses valid values only and reports current, previous, min and max', () => {
    const s = seriesStats([20, null, 22, 21, null]);
    expect(s).toMatchObject({ n: 3, current: 21, previous: 22, min: 20, max: 22 });
  });
  it('has no trend with too few values and an empty result with none', () => {
    expect(seriesStats([20, 21]).trend).toBeNull();
    expect(seriesStats([null, null])).toMatchObject({ n: 0, current: null, min: null, max: null, trend: null });
  });
  it('reads a rising, falling and steady trend', () => {
    expect(seriesStats([20, 20, 20, 20, 24, 24, 24, 24], 0.5).trend).toBe('rising');
    expect(seriesStats([24, 24, 24, 24, 20, 20, 20, 20], 0.5).trend).toBe('falling');
    expect(seriesStats([20, 20.1, 20, 20.1, 20, 20.1, 20, 20.1], 0.5).trend).toBe('steady');
  });
});

describe('the bounded live history', () => {
  it('appends only new readings and never exceeds its bound', () => {
    let l: LiveReading[] = [];
    for (let i = 1; i <= 30; i++) l = boundedAppend(l, [rd(i, 25, 50, 100)], 10);
    expect(l).toHaveLength(10);
    expect(l[0].seq).toBe(21);
    expect(boundedAppend(l, [rd(25, 25, 50, 100)], 10)).toBe(l);            // an old sequence number is ignored
  });
  it('keeps a missing value missing', () => {
    const l = boundedAppend([], [rd(1, null, null, 90)]);
    expect(valueOf(l[0], 'temperature')).toBeNull();
    expect(valueOf(l[0], 'gas')).toBe(90);
  });
  it('windows by time from the newest reading', () => {
    const l = Array.from({ length: 10 }, (_, i) => rd(i + 1, 25, 50, 100, i * 20));       // one every 20 s over 180 s
    expect(windowOf(l, 60)).toHaveLength(4);
    expect(windowOf(l, null)).toHaveLength(10);
    expect(windowOf([], 60)).toEqual([]);
  });
});

describe('scenario and interaction arithmetic', () => {
  it('builds the 2 x 2 example of baseline, A (both), B (temperature only), C (humidity only)', () => {
    const s = factorialScenarios(DEFAULTS, 35, 70);
    expect(s.map((x) => [x.id, x.values.temperature, x.values.humidity])).toEqual([['base', 25, 50], ['A', 35, 70], ['B', 35, 50], ['C', 25, 70]]);
  });
  it('the combined heat index exceeds the sum of the separate effects (super-additive) for 25 °C / 50 % to 35 °C / 70 %', () => {
    const c = contrast(DEFAULTS, 35, 70);
    expect(c.baseline).toBeCloseTo(24.861111, 5);
    expect(c.a).toBeCloseTo(50.340578, 5);
    expect(c.additive).toBeCloseTo(c.b + c.c - c.baseline, 9);
    expect(c.interaction).toBeCloseTo(c.a - c.additive, 9);
    expect(c.interaction).toBeGreaterThan(0.25);
    expect(c.klass).toBe('SUPER-ADDITIVE (synergistic-like)');
  });
  it('a change that does not move the conditions is exactly additive', () => {
    const c = contrast(DEFAULTS, 25, 50);
    expect(c.interaction).toBeCloseTo(0, 9);
    expect(c.klass).toBe('APPROXIMATELY ADDITIVE');
  });
  it('the gap grid is zero along the baseline row and column', () => {
    const g = interactionGrid({ temperature: 25, humidity: 50 }, [25, 35], [50, 70], 5);
    expect(g.gap[0].every((v) => Math.abs(v) < 1e-9)).toBe(true);                      // humidity at the baseline
    expect(g.gap.every((row) => Math.abs(row[0]) < 1e-9)).toBe(true);                  // temperature at the baseline
    expect(g.maxAbsGap).toBeGreaterThan(1);
  });
});
