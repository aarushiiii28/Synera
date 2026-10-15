// Pure helpers for the Trust Center and Space Biology pages (no React, no network). Unit-tested in src/tests/trust.test.tsx.
import type { Check, FalseAlarm, TamperResult } from '../../lib/api';

// ---------------------------------------------------------------- hashes
export const isHex64 = (s: unknown): boolean => typeof s === 'string' && /^[0-9a-f]{64}$/i.test(s);

export interface HashDiff { chars: { c: string; diff: boolean }[]; count: number }

/** Character-by-character comparison of two SHA-256 hex strings. Null when either is not a 64-char hex digest. */
export function hashDiff(original: string, modified: string): HashDiff | null {
  if (!isHex64(original) || !isHex64(modified)) return null;
  const a = original.toLowerCase(), b = modified.toLowerCase();
  const chars = [...b].map((c, i) => ({ c, diff: c !== a[i] }));
  return { chars, count: chars.filter((x) => x.diff).length };
}

// ---------------------------------------------------------------- tamper result interpretation
export interface DetectorSummary { total: number; fired: number; blockingFired: number; advisoryFired: number; firedNames: string[] }

/** A detector "fires" when its status is anything but PASS. Blocking detectors are the integrity-critical ones. */
export function summariseDetectors(detectors: Check[]): DetectorSummary {
  const fired = detectors.filter((d) => d.status !== 'PASS');
  return {
    total: detectors.length,
    fired: fired.length,
    blockingFired: fired.filter((d) => d.blocking).length,
    advisoryFired: fired.filter((d) => !d.blocking).length,
    firedNames: fired.map((d) => d.name),
  };
}

export type BannerKind = 'hash_only' | 'statistical_and_hash' | 'ledger' | 'model' | 'no_mismatch';
export interface Banner { kind: BannerKind; headline: string; sub: string; stamp: string; blocked: boolean }

/** Which headline the result sequence ends on. Everything is derived from the API response. */
export function bannerFor(r: Pick<TamperResult, 'mode' | 'hash_match' | 'hash_only' | 'detectors' | 'verdict' | 'ledger' | 'model'>): Banner {
  const s = summariseDetectors(r.detectors ?? []);
  const stamp = `SCIENTIFIC DATA INTEGRITY FAILURE - ${r.verdict}`;
  if (r.ledger) {
    return { kind: 'ledger', headline: 'THE LEDGER CHAIN BROKE', sub: 'Editing a recorded block invalidates its payload hash, so verification of the chain fails.', stamp, blocked: !r.ledger.after.valid };
  }
  if (r.model) {
    return { kind: 'model', headline: 'MODEL FINGERPRINT MISMATCH', sub: 'The weights, the hold-out metric and the probe predictions no longer match what was registered.', stamp, blocked: !r.model.after.ok };
  }
  if (r.hash_match) {
    return { kind: 'no_mismatch', headline: 'NO HASH MISMATCH', sub: 'The fingerprint is identical to the registered one.', stamp: r.verdict, blocked: false };
  }
  if (r.hash_only) {
    return { kind: 'hash_only', headline: 'ONLY THE CRYPTOGRAPHIC HASH CAUGHT THIS', sub: `All ${s.total} statistical detectors stayed quiet. Without the hash this edit would have passed unnoticed.`, stamp, blocked: true };
  }
  return { kind: 'statistical_and_hash', headline: 'HASH AND DETECTORS AGREE', sub: `${s.fired} of ${s.total} statistical detectors also fired (${s.blockingFired} blocking, ${s.advisoryFired} advisory).`, stamp, blocked: true };
}

export const issueLabel = (code: string) => ({
  PREV_HASH_MISMATCH: 'The link to the previous block does not match',
  PAYLOAD_TAMPERED: 'The block content no longer matches its recorded hash',
  MERKLE_MISMATCH: 'The Merkle root does not match the artifact list',
  HASH_MISMATCH: 'The block hash does not match its header',
  BAD_SIGNATURE: 'The signature does not verify',
} as Record<string, string>)[code] ?? code;

// ---------------------------------------------------------------- false-alarm heatmap
export interface HeatModel {
  detectors: string[]; modes: string[]; levels: string[];
  cell: (detector: string, mode: string, level: string) => number | null;
  clean: { name: string; rate: number; hits?: number; trials?: number; upper?: number }[];
}

/** attacks[mode][contamination][detector] (see evaluate_security) -> small-multiples model. */
export function heatModel(far: FalseAlarm): HeatModel | null {
  if (!far.available || !far.attacks || !far.clean_false_alarm_rate) return null;
  const attacks = far.attacks as Record<string, Record<string, Record<string, number>>>;
  const modes = Object.keys(attacks);
  const levels = [...new Set(modes.flatMap((m) => Object.keys(attacks[m])))].sort((a, b) => Number(a) - Number(b));
  const keys = new Set<string>();
  modes.forEach((m) => Object.values(attacks[m]).forEach((c) => Object.keys(c).forEach((k) => keys.add(k))));
  const order = ['hash', 'any_statistical'];
  const detectors = [...[...keys].filter((k) => !order.includes(k)), ...order.filter((k) => keys.has(k))];
  const clean = Object.entries(far.clean_false_alarm_rate).map(([name, rate]) => ({ name, rate, hits: far.clean_false_alarm_counts?.[name]?.[0], trials: far.clean_false_alarm_counts?.[name]?.[1], upper: far.clean_false_alarm_ci95?.[name]?.[1] }));
  return { detectors, modes, levels, clean, cell: (d, m, l) => attacks[m]?.[l]?.[d] ?? null };
}

// ---------------------------------------------------------------- volcano
export interface VolcanoPoint { gene: string; x: number; y: number; type: string; q: number }

export function toPoints(rows: [string, number, number, string, number][]): VolcanoPoint[] {
  return rows.map(([gene, x, y, type, q]) => ({ gene, x, y, type, q }));
}

/** Symmetric x domain around zero and a y domain that always includes the FDR line. */
export function volcanoDomain(pts: VolcanoPoint[], fdrY: number) {
  let xm = 0, ym = 0;
  for (const p of pts) { const ax = Math.abs(p.x); if (ax > xm) xm = ax; if (p.y > ym) ym = p.y; }
  const xMax = Math.ceil(Math.max(xm, 1) * 1.05);
  const yMax = Math.ceil(Math.max(ym, fdrY) * 1.08 * 2) / 2;
  return { xMax, yMax };
}

/** -log10 of the p-value needed for the best-ranked gene to pass BH. */
export const fdrLineY = (fdrLineP: number) => -Math.log10(fdrLineP);

export const topByP = (pts: VolcanoPoint[], n: number) => [...pts].sort((a, b) => b.y - a.y).slice(0, n);

export function linearScale(d0: number, d1: number, r0: number, r1: number) {
  const k = (r1 - r0) / (d1 - d0);
  return Object.assign((v: number) => r0 + (v - d0) * k, { invert: (px: number) => d0 + (px - r0) / k });
}

/** Nearest point in screen space, or null if none is within `radius` px. */
export function nearestPoint(pts: VolcanoPoint[], sx: (v: number) => number, sy: (v: number) => number, px: number, py: number, radius = 14): VolcanoPoint | null {
  let best: VolcanoPoint | null = null, bd = radius * radius;
  for (const p of pts) {
    const dx = sx(p.x) - px, dy = sy(p.y) - py, d = dx * dx + dy * dy;
    if (d < bd) { bd = d; best = p; }
  }
  return best;
}

export const POINT_COLOR: Record<string, string> = { none: 'rgba(143,166,191,0.38)', SYNERGISTIC: '#6fd65b', ANTAGONISTIC: '#16b5ff' };

