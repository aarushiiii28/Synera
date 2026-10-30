import { describe, expect, it } from 'vitest';
import { boundedAppend, heatCategory, heatIndexC, seriesStats, smokeLevel, smokeToPm25, valueOf, windowOf, type LiveReading } from '../lib/live';

const rd = (seq: number, t: number | null, h: number | null, g: number, secs = seq): LiveReading => ({
  seq, device_id: 'd', time_ms: seq * 2000, received_utc: new Date(Date.UTC(2026, 9, 30, 12, 0, secs)).toISOString(), source: 'REAL_SENSOR',
  measurements: [
    { sensor: 'temperature', value: t, unit: '°C', quality: t === null ? 'MISSING' : 'OK' },
    { sensor: 'humidity', value: h, unit: '%', quality: h === null ? 'MISSING' : 'OK' },
    { sensor: 'gas', value: g, unit: 'raw', quality: 'OK' }],
});

describe('heat index', () => {
  // Values computed by synera_core.data.cities.calculate_heat_index (the function that built the historical panels): the two must agree.
  const PY: [number, number, number][] = [[20, 30, 18.838888889], [25, 50, 24.861111111], [26, 57, 26.143888889], [30, 40, 29.689165056], [32, 70, 40.40927368],
    [35, 50, 40.675428944], [35, 70, 50.340578056], [38, 85, 76.10020368], [27, 40, 26.86317312], [45, 20, 46.077777778]];
  it('matches the Python implementation to 6 decimals', () => { for (const [t, r, hi] of PY) expect(heatIndexC(t, r)).toBeCloseTo(hi, 6); });
  it('falls in the National Weather Service categories', () => {
    expect(heatCategory(24.9).label).toBe('Comfortable');
    expect(heatCategory(29).label).toBe('Caution');
    expect(heatCategory(40.7).label).toBe('Extreme caution');
    expect(heatCategory(50.3).label).toBe('Danger');
    expect(heatCategory(60).label).toBe('Extreme danger');
  });
});

describe('series statistics', () => {
  it('uses valid values only and reports current, previous, min and max', () => {
    expect(seriesStats([20, null, 22, 21, null])).toMatchObject({ n: 3, current: 21, previous: 22, min: 20, max: 22 });
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

describe('smoke level against the room\'s own baseline', () => {
  const clean = Array.from({ length: 40 }, (_, i) => 60 + (i % 3));                       // 60..62: a quiet sensor
  it('is still learning until it has enough readings, and says how many', () => {
    const s = smokeLevel([60, 61, 62]);
    expect(s).toMatchObject({ ready: false, state: 'learning', learned: 3, needed: 30, abovePct: null });
  });
  it('reads clean air as clean', () => {
    const s = smokeLevel(clean);
    expect(s.ready && s.state).toBe('clean');
    expect(s.baseline).toBeGreaterThanOrEqual(60);
    expect(Math.abs(s.abovePct ?? 99)).toBeLessThan(15);
  });
  it('detects a sustained rise of half the baseline or more, but not one noisy spike', () => {
    expect(smokeLevel([...clean, 120, 125, 130]).state).toBe('detected');
    expect(smokeLevel([...clean, 61, 62, 130]).state).not.toBe('detected');
  });
  it('flags a moderate rise as elevated', () => {
    expect(smokeLevel([...clean, 75, 76, 77]).state).toBe('elevated');
  });
  it('ignores missing values and uses a floor so a near-zero baseline cannot inflate the percentage', () => {
    const s = smokeLevel([...Array.from({ length: 40 }, () => 2), null, 10, 10, 10]);
    expect(s.baseline).toBe(20);
    expect(s.abovePct).toBeLessThan(0);
  });
});

describe('smoke-to-PM2.5 proxy mapping', () => {
  it('returns null for missing or non-finite readings', () => {
    expect(smokeToPm25(null)).toBeNull();
    expect(smokeToPm25(NaN)).toBeNull();
  });

  it('maps clean baseline air to typical reference PM2.5 (~12 µg/m³)', () => {
    const pm = smokeToPm25(60, 60, 0);
    expect(pm).toBe(12.0);
  });

  it('scales elevated smoke into particulate concentrations', () => {
    const moderate = smokeToPm25(75, 60, 25);
    expect(moderate).toBeCloseTo(12.0 + 25 * 0.85, 1);

    const smokeDetected = smokeToPm25(120, 60, 100);
    expect(smokeDetected).toBe(97.0);
  });

  it('falls back to raw ADC scaling when baseline is still learning', () => {
    expect(smokeToPm25(55, null, null)).toBe(12.0);
    const elevatedRaw = smokeToPm25(155, null, null);
    expect(elevatedRaw).toBeCloseTo(12.0 + 100 * 0.35, 1);
  });

  it('caps extreme values to a safe upper bound', () => {
    expect(smokeToPm25(999, 50, 1000)).toBe(350.0);
  });
});
