import { cellText, detectorKeys, detectorLabel } from './benchLogic';
import { pct } from '../../lib/format';
import { titleCase } from '../../lib/format';

type Attacks = Record<string, Record<string, Record<string, number>>>;

const cellBg = (v: number | undefined, tone: string) => (v === undefined ? 'transparent' : `color-mix(in srgb, ${tone} ${Math.round(v * 70)}%, transparent)`);

/** Detection rate heatmaps, one small matrix per detector: attack (rows) x contamination (columns). */
export function BenchHeatmaps({ attacks, levels }: { attacks: Attacks; levels: number[] }) {
  const detectors = detectorKeys(attacks);
  const modes = Object.keys(attacks);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-x-8 gap-y-8 sm:grid-cols-2 xl:grid-cols-3">
      {detectors.map((d) => {
        const tone = d === 'hash' ? 'var(--biosphere)' : d === 'any_statistical' ? 'var(--teal)' : 'var(--signal)';
        return (
          <figure key={d} className="m-0">
            <figcaption className="display font-semibold text-[13px] mb-2" style={{ color: tone }}>{detectorLabel(d)}</figcaption>
            <table className="w-full border-collapse num text-[11px]">
              <caption className="sr-only">Detection rate of {detectorLabel(d)} by attack and contamination level</caption>
              <thead>
                <tr><th scope="col" className="text-left font-normal text-faint pb-1">attack</th>
                  {levels.map((l) => <th key={l} scope="col" className="font-normal text-faint pb-1 text-right">{pct(l, 0)}</th>)}</tr>
              </thead>
              <tbody>
                {modes.map((m) => (
                  <tr key={m} className="border-t border-line">
                    <th scope="row" className="text-left font-normal text-muted py-1 pr-2 whitespace-nowrap">{titleCase(m)}</th>
                    {levels.map((l) => {
                      const v = attacks[m]?.[String(l)]?.[d];
                      return <td key={l} className="text-right py-1 px-1.5" style={{ background: cellBg(v, tone), color: v !== undefined && v > 0.55 ? 'var(--text)' : 'var(--muted)' }}>{cellText(v)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </figure>
        );
      })}
    </div>
  );
}

/** Clean-data false alarm bars: the price of each detector. High bars are bad. */
export function BenchFalseAlarm({ rates, counts }: { rates: Record<string, number>; counts?: Record<string, [number, number]> }) {
  const keys = Object.keys(rates).sort((a, b) => rates[b] - rates[a]);
  const max = Math.max(0.1, ...keys.map((k) => rates[k]));
  return (
    <ul className="m-0 p-0 list-none grid gap-2.5">
      {keys.map((k) => {
        const v = rates[k];
        const tone = v > 0.05 ? 'var(--solar)' : 'var(--teal)';
        return (
          <li key={k} className="grid grid-cols-[minmax(6rem,11rem)_1fr_3.2rem] items-center gap-3">
            <span className="text-[13px] text-muted">{detectorLabel(k)}</span>
            <span className="relative h-3 bg-hull-2/40 block" role="img" aria-label={`${detectorLabel(k)} false alarm rate ${pct(v, 1)}`}>
              <span className="absolute inset-y-0 left-0 block" style={{ width: `${(v / max) * 100}%`, background: tone, opacity: 0.85 }} />
            </span>
            <span className="num text-[13px] text-right" style={{ color: tone }} title={counts?.[k] ? ` of  clean datasets` : undefined}>{pct(v, 0)}</span>
          </li>
        );
      })}
    </ul>
  );
}
