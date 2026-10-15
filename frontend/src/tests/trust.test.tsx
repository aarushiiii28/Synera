import { describe, expect, it } from 'vitest';
import type { Check, FalseAlarm } from '../lib/api';
import {
  bannerFor, fdrLineY, hashDiff, heatModel, isHex64, linearScale, nearestPoint, summariseDetectors, toPoints, topByP, volcanoDomain,
} from '../components/charts/trustLogic';

// Throw-away fixtures: they test logic only and are never rendered.
const A = 'a'.repeat(64);
const chk = (name: string, status: Check['status'], blocking = false): Check => ({ name, status, score: 0, detail: '', blocking });

describe('hashDiff', () => {
  it('marks exactly the differing characters', () => {
    const b = 'a'.repeat(10) + 'b' + 'a'.repeat(52) + 'c';
    const d = hashDiff(A, b)!;
    expect(d.count).toBe(2);
    expect(d.chars[10]).toEqual({ c: 'b', diff: true });
    expect(d.chars[63].diff).toBe(true);
    expect(d.chars[0].diff).toBe(false);
  });
  it('is zero for identical hashes and case-insensitive', () => {
    expect(hashDiff(A, A.toUpperCase())!.count).toBe(0);
  });
  it('returns null for non-hex values such as issue codes', () => {
    expect(hashDiff(A, 'PAYLOAD_TAMPERED')).toBeNull();
    expect(isHex64('abc')).toBe(false);
  });
});

describe('detectors and banner', () => {
  const ds = [chk('a', 'PASS'), chk('b', 'WARN'), chk('c', 'FAIL', true)];
  it('counts fired detectors by blocking class', () => {
    expect(summariseDetectors(ds)).toMatchObject({ total: 3, fired: 2, blockingFired: 1, advisoryFired: 1 });
    expect(summariseDetectors([])).toMatchObject({ total: 0, fired: 0 });
  });
  const base = { mode: 'x', hash_match: false, hash_only: false, detectors: ds, verdict: 'RESULT BLOCKED FROM VERIFIED STATUS' };
  it('uses the hash-only headline when only the hash caught it', () => {
    const b = bannerFor({ ...base, hash_only: true, detectors: [chk('a', 'PASS')] });
    expect(b.kind).toBe('hash_only');
    expect(b.headline).toBe('ONLY THE CRYPTOGRAPHIC HASH CAUGHT THIS');
    expect(b.stamp).toBe('SCIENTIFIC DATA INTEGRITY FAILURE - RESULT BLOCKED FROM VERIFIED STATUS');
  });
  it('reports statistical agreement otherwise', () => {
    const b = bannerFor(base);
    expect(b.kind).toBe('statistical_and_hash');
    expect(b.sub).toContain('2 of 3');
  });
  it('does not block when hashes match', () => {
    expect(bannerFor({ ...base, hash_match: true }).blocked).toBe(false);
  });
  it('ledger mode follows the copy-after validity', () => {
    const l = { target_block: 3, before: { valid: true, height: 9, head: A }, after: { valid: false, height: 9, issues: [] } };
    expect(bannerFor({ ...base, ledger: l })).toMatchObject({ kind: 'ledger', blocked: true });
  });
});

describe('heatModel', () => {
  const far: FalseAlarm = {
    available: true, clean_false_alarm_rate: { mcd: 0.02, any_detector_warns: 0.1 },
    attacks: { row_edit: { '0.1': { mcd: 0.5, hash: 1, any_statistical: 0.6 }, '0.01': { mcd: 0.1, hash: 1, any_statistical: 0.1 } } },
  };
  it('orders levels numerically and puts hash last', () => {
    const m = heatModel(far)!;
    expect(m.levels).toEqual(['0.01', '0.1']);
    expect(m.detectors).toEqual(['mcd', 'hash', 'any_statistical']);
    expect(m.cell('mcd', 'row_edit', '0.1')).toBe(0.5);
    expect(m.cell('mcd', 'nope', '0.1')).toBeNull();
  });
  it('is null when the benchmark is unavailable', () => {
    expect(heatModel({ available: false })).toBeNull();
  });
});

describe('volcano scaling', () => {
  const pts = toPoints([['g1', 2.4, 4.5, 'none', 0.4], ['g2', -3.5, 4.0, 'none', 0.4], ['g3', 0.1, 1, 'none', 0.9]]);
  it('keeps the FDR line inside the y domain even when no gene reaches it', () => {
    const fy = fdrLineY(2.0e-6);
    expect(fy).toBeCloseTo(5.699, 2);
    const d = volcanoDomain(pts, fy);
    expect(d.yMax).toBeGreaterThan(fy);
    expect(d.xMax).toBeGreaterThanOrEqual(3.5);
  });
  it('maps linearly and inverts', () => {
    const s = linearScale(-4, 4, 0, 800);
    expect(s(0)).toBe(400);
    expect(s.invert(800)).toBe(4);
  });
  it('ranks by surprise and finds the nearest point', () => {
    expect(topByP(pts, 2).map((p) => p.gene)).toEqual(['g1', 'g2']);
    const sx = linearScale(-4, 4, 0, 800), sy = linearScale(0, 6, 300, 0);
    expect(nearestPoint(pts, sx, sy, sx(2.4) + 3, sy(4.5) - 2)?.gene).toBe('g1');
    expect(nearestPoint(pts, sx, sy, 5, 5)).toBeNull();
  });
});
