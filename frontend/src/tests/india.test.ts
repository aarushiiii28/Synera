import { describe, expect, it } from 'vitest';
import { color, colorRGB, compass, fmt, idw, LAYER_VALUE, type CityMarker } from '../lib/india';

const city = (o: Partial<CityMarker> = {}): CityMarker => ({
  id: 'x', name: 'X', state: 'S', lat: 28, lon: 77, temperature_c: 30, humidity_pct: 50, wind_kmh: 10, wind_dir_deg: 90, rain_24h_mm: 0, rain_next_mm: 0, pm25: 40, pm10: 80, aqi: 90,
  aqi_category: 'Satisfactory', aqi_level: 1, heat_index_c: 33, heat_category: 'Extreme caution', heat_level: 2, imd_heat: 'NORMAL', risk: 0.4, risk_tier: 'MODERATE', risk_driver: 'heat', completeness: 1, ...o,
});

describe('colour scales', () => {
  it('uses the official-looking AQI ramp: green at Good, red at Very Poor, never invents a colour for a missing value', () => {
    const [r0, g0] = colorRGB('aqi', 20), [r1, g1] = colorRGB('aqi', 350);
    expect(g0).toBeGreaterThan(r0);          // green side
    expect(r1).toBeGreaterThan(g1);          // red side
    expect(color('aqi', null)).toBe('rgba(132,147,156,0.5)');
    expect(color('aqi', undefined)).toBe(color('aqi', null));
  });
  it('clamps outside the scale and is continuous inside it', () => {
    expect(colorRGB('temperature', -40)).toEqual(colorRGB('temperature', 0));
    expect(colorRGB('temperature', 99)).toEqual(colorRGB('temperature', 48));
    const a = colorRGB('temperature', 30), b = colorRGB('temperature', 30.1);
    expect(Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) + Math.abs(a[2] - b[2])).toBeLessThan(12);
  });
  it('reads each layer from the field the legend names', () => {
    const c = city();
    expect(LAYER_VALUE.aqi(c)).toBe(90);
    expect(LAYER_VALUE.temperature(c)).toBe(30);
    expect(LAYER_VALUE.rainfall(c)).toBe(0);
    expect(LAYER_VALUE.risk(city({ risk: null }))).toBeNull();
  });
});

describe('heat-field interpolation', () => {
  const pts = [{ lon: 77, lat: 28, v: 100 }, { lon: 80, lat: 28, v: 200 }];
  it('returns the city value at the city and something in between elsewhere', () => {
    expect(idw(77, 28, pts)?.v).toBe(100);
    const mid = idw(78.5, 28, pts)!;
    expect(mid.v).toBeGreaterThan(100); expect(mid.v).toBeLessThan(200);
    expect(mid.v).toBeCloseTo(150, 0);
  });
  it('reports how far the nearest city is, so the map can fade where nothing is measured', () => {
    expect(idw(90, 10, pts)!.nearestKm).toBeGreaterThan(1500);
    expect(idw(77.01, 28, pts)!.nearestKm).toBeLessThan(2);
  });
  it('has nothing to say without cities', () => { expect(idw(77, 28, [])).toBeNull(); });
});

describe('formatting', () => {
  it('shows a dash, never a number, for missing values', () => {
    expect(fmt(null)).toBe('—'); expect(fmt(undefined)).toBe('—'); expect(fmt(NaN)).toBe('—'); expect(fmt(3.14159, 2)).toBe('3.14');
  });
  it('turns a bearing into a compass point', () => {
    expect(compass(0)).toBe('N'); expect(compass(90)).toBe('E'); expect(compass(225)).toBe('SW'); expect(compass(359)).toBe('N'); expect(compass(null)).toBe('—');
  });
});
