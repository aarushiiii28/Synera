// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LiveChart } from '../components/live/LiveChart';
import { SensorCard } from '../components/live/SensorCard';
import { ProvBadge } from '../components/live/Badges';
import type { LiveReading } from '../lib/live';

const reading = (seq: number, t: number | null): LiveReading => ({
  seq, device_id: 'd', time_ms: seq * 2000, received_utc: new Date(Date.UTC(2026, 9, 30, 12, 0, seq)).toISOString(), source: 'REAL_SENSOR',
  measurements: [{ sensor: 'temperature', value: t, unit: '°C', quality: t === null ? 'MISSING' : 'OK' }, { sensor: 'humidity', value: 57, unit: '%', quality: 'OK' }, { sensor: 'gas', value: 61, unit: 'ADC', quality: 'WARMING_UP' }],
});

describe('Live Stress Lab components', () => {
  it('an empty chart explains why, and draws no line or invented point', () => {
    const { container } = render(<LiveChart points={[]} unit="°C" label="Temperature" color="red" empty="Not connected." />);
    expect(screen.getByText('Not connected.')).toBeTruthy();
    expect(container.querySelector('path')).toBeNull();
    expect(container.querySelector('circle')).toBeNull();
  });
  it('a chart with only missing values is still empty, not a flat line', () => {
    const { container } = render(<LiveChart points={[{ t: 1, v: null }, { t: 2, v: null }]} unit="°C" label="Temperature" color="red" empty="No valid readings." />);
    expect(screen.getByText('No valid readings.')).toBeTruthy();
    expect(container.querySelector('path')).toBeNull();
  });
  it('a chart with data draws it and names the latest value for screen readers', () => {
    const { container } = render(<LiveChart points={[{ t: 1000, v: 25 }, { t: 3000, v: 26 }, { t: 5000, v: null }, { t: 7000, v: 27 }]} unit="°C" label="Temperature" color="red" empty="x" />);
    expect(container.querySelector('path')?.getAttribute('d')).toBeTruthy();
    expect(container.querySelector('svg')?.getAttribute('aria-label')).toContain('latest 27.0 °C');
  });
  it('a sensor card with no readings shows dashes, never a number', () => {
    render(<SensorCard k="temperature" readings={[]} test={false} />);
    expect(screen.getByText('no reading yet')).toBeTruthy();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
  it('updates when a new reading arrives and flags the gas sensor as raw and warming up', () => {
    const { rerender } = render(<SensorCard k="gas" readings={[reading(1, 25)]} test={false} />);
    expect(screen.getAllByText('61').length).toBeGreaterThan(0);                 // current, min and max are all 61
    expect(screen.getByText(/Not ppm, not AQI, not PM2.5/)).toBeTruthy();
    expect(screen.getByText('WARMING UP')).toBeTruthy();
    rerender(<SensorCard k="temperature" readings={[reading(1, 25), reading(2, 26)]} test={false} />);
    expect(screen.getAllByText('26.0').length).toBeGreaterThan(0);               // the new current value
    expect(screen.getAllByText('25.0').length).toBeGreaterThan(0);               // the previous reading, now also the minimum
  });
  it('a missing temperature is shown as missing quality, not as zero', () => {
    render(<SensorCard k="temperature" readings={[reading(1, null)]} test={false} />);
    expect(screen.getByText('MISSING')).toBeTruthy();
    expect(screen.queryByText('0.0')).toBeNull();
  });
  it('simulated test readings are labelled SIMULATED on the card', () => {
    render(<SensorCard k="humidity" readings={[{ ...reading(1, 25), source: 'SIMULATED_TEST' }]} test />);
    expect(screen.getByText('SIMULATED')).toBeTruthy();
    expect(screen.queryByText('REAL SENSOR')).toBeNull();
  });
  it('every provenance class has its own label', () => {
    render(<><ProvBadge prov="REAL SENSOR" /><ProvBadge prov="SIMULATED" /><ProvBadge prov="HISTORICAL" /><ProvBadge prov="DERIVED" /></>);
    for (const l of ['REAL SENSOR', 'SIMULATED', 'HISTORICAL', 'DERIVED']) expect(screen.getByText(l)).toBeTruthy();
  });
});
