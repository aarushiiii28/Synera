import { useMutation } from '@tanstack/react-query';
import { api, ApiError, type LiveAnalysis } from '../../lib/api';
import { valueOf, type LiveReading } from '../../lib/live';

const MEANING = {
  SYNERGISTIC: 'Together, temperature and humidity move the gas reading more than the sum of their separate effects.',
  ANTAGONISTIC: 'Together, temperature and humidity move the gas reading less than the sum of their separate effects.',
  NONLINEAR: 'The gas reading responds to temperature and humidity together in a way that bends or switches rather than adding up.',
} as const;

const p3 = (p: number) => (p < 0.001 ? '< 0.001' : p.toFixed(3));

function Grid({ g }: { g: NonNullable<LiveAnalysis['grid']> }) {
  const vals = g.cells.flat().map((c) => c.mean).filter((x): x is number => x !== null);
  const m = Math.max(1, ...vals.map(Math.abs));
  const lab = ['low', 'mid', 'high'];
  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: 'auto repeat(3, minmax(0, 1fr))', maxWidth: 420 }} role="table" aria-label="Average gas reading by temperature and humidity">
        <div />{lab.map((l) => <div key={l} className="num text-[10px] text-faint text-center">humidity {l}</div>)}
        {g.cells.map((row, i) => (
          <div key={i} className="contents">
            <div className="num text-[10px] text-faint pr-2 self-center">temp {lab[i]}</div>
            {row.map((c, j) => (
              <div key={j} className="num text-[12px] text-center py-2" title={`${c.n} readings`}
                style={{ background: c.mean === null ? 'transparent' : `color-mix(in srgb, ${c.mean >= 0 ? 'var(--solar)' : 'var(--signal)'} ${Math.round((Math.abs(c.mean) / m) * 55)}%, transparent)`, border: '1px solid var(--line)' }}>
                {c.mean === null ? '—' : `${c.mean >= 0 ? '+' : ''}${c.mean.toFixed(1)}`}
              </div>))}
          </div>))}
      </div>
      <p className="text-[11.5px] text-faint mt-2 mb-0 max-w-md">{g.unit}.</p>
    </div>
  );
}

/** Feeds the session so far to the interaction engine: does the gas sensor's reading depend on temperature and humidity together? */
export function InteractionCheck({ readings, unavailable }: { readings: LiveReading[]; unavailable: boolean }) {
  const run = useMutation({ mutationFn: api.liveAnalyze });
  const usable = readings.filter((r) => valueOf(r, 'temperature') !== null && valueOf(r, 'humidity') !== null && r.measurements.every((m) => m.quality === 'OK')).length;
  const warming = readings.length > 0 && readings[readings.length - 1].measurements.some((m) => m.sensor === 'gas' && m.quality === 'WARMING_UP');
  const a = run.data;
  const err = run.error instanceof ApiError || run.error instanceof Error ? run.error.message : null;
  return (
    <div className="grid lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)] gap-8">
      <div>
        <p className="text-[14px] text-muted mt-0 mb-3 leading-relaxed">The interaction engine looks at the data this device has collected. MQ gas sensors are known to react to temperature and humidity, so the question is whether they act <b>together</b> on the reading.</p>
        <div className="num text-[12px] text-muted mb-3">{usable} clean readings in view · needs 300+ and enough variation</div>
        {warming && <p className="text-[12px] text-solar mt-0 mb-3">The gas sensor is still warming up. Readings from this period are left out of the analysis.</p>}
        <button type="button" onClick={() => run.mutate()} disabled={unavailable || run.isPending || usable < 20}
          className="num text-xs tracking-[0.16em] border border-signal bg-signal/10 text-signal px-4 py-2 hover:bg-signal/20 disabled:opacity-40 w-full">{run.isPending ? 'RUNNING THE ENGINE…' : 'ANALYSE MY DATA'}</button>
        {err && <p role="alert" className="text-[13px] text-alert mt-3 mb-0">{err}</p>}
      </div>
      <div className="min-w-0" aria-live="polite">
        {!a && !run.isPending && <p className="text-[13px] text-faint m-0">Collect a few minutes of readings (breathe near the sensor, open a window, anything that makes temperature and humidity move), then press the button.</p>}
        {run.isPending && <p className="text-[13px] text-muted m-0">Fitting the additive model, the interaction model and a block bootstrap on your readings…</p>}
        {a && (
          <div>
            <div className="flex flex-wrap items-center gap-3 mb-2">
              {a.status === 'INSUFFICIENT_DATA' && <span className="display text-2xl text-solar">Not enough to say yet</span>}
              {a.status === 'INTERACTION_DETECTED' && <span className="display text-2xl text-biosphere">Interaction detected</span>}
              {a.status === 'NO_INTERACTION_DETECTED' && <span className="display text-2xl text-text">No interaction detected</span>}
              <span className="num text-[10px] tracking-[0.14em] text-solar border border-solar/60 px-2 py-0.5">EXPLORATORY</span>
            </div>
            {a.status === 'INSUFFICIENT_DATA' && (
              <div className="text-[13.5px] text-muted leading-relaxed">
                <ul className="m-0 pl-5">{a.reasons?.map((r) => <li key={r}>{r}</li>)}</ul>
                <p className="mt-2 mb-0">{a.advice}</p>
              </div>)}
            {a.result && (
              <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6">
                <div className="text-[13.5px] leading-relaxed">
                  {a.status === 'INTERACTION_DETECTED' && a.result.type && <p className="m-0 mb-2 text-text"><span className="num text-[11px] tracking-[0.12em] text-solar">{a.result.type}</span> {MEANING[a.result.type]}</p>}
                  {a.status === 'NO_INTERACTION_DETECTED' && <p className="m-0 mb-2 text-muted">The data do not show the two acting together beyond their separate effects. That does not prove there is none: this much data from one room can only see fairly clear effects.</p>}
                  <dl className="m-0 grid grid-cols-2 gap-x-6 gap-y-2 text-[12.5px]">
                    <div><dt className="label">Calibrated p-value</dt><dd className="m-0 num text-text">{p3(a.result.p_calibrated)}</dd></div>
                    <div><dt className="label">Plain test would say</dt><dd className="m-0 num text-muted">{p3(a.result.p_naive)}</dd></div>
                    <div><dt className="label">Effect size</dt><dd className="m-0 num text-text">{a.result.effect_size_sd !== null ? `${a.result.effect_size_sd.toFixed(2)} SD` : 'below the 0.05 SD gate or not selected'}</dd></div>
                    <div><dt className="label">Readings used</dt><dd className="m-0 num text-muted">{a.result.n}</dd></div>
                  </dl>
                  {a.main_effects && <p className="text-[12px] text-muted mt-3 mb-0">Separately (descriptive): one standard deviation of temperature moves the gas value by {a.main_effects.per_1sd_temperature >= 0 ? '+' : ''}{a.main_effects.per_1sd_temperature.toFixed(1)}, and of humidity by {a.main_effects.per_1sd_humidity >= 0 ? '+' : ''}{a.main_effects.per_1sd_humidity.toFixed(1)}, in raw gas counts.</p>}
                </div>
                {a.grid && <Grid g={a.grid} />}
              </div>)}
            <ul className="mt-4 mb-0 pl-5 text-[12px] text-faint leading-relaxed">{a.limits.map((l) => <li key={l}>{l}</li>)}</ul>
          </div>)}
      </div>
    </div>
  );
}
