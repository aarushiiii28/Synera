import type { InteractionMatrix, StressorInfo } from '../../lib/api';
import { fix } from '../../lib/format';
import { crossCheck } from './discoveryLogic';

/** The same engine, run on a second, disjoint set of places: which kept pairs show up in both. Computed from the two recorded runs. */
export function CrossCheck({ here, other, hereName, otherName, labels }: { here: InteractionMatrix; other: InteractionMatrix; hereName: string; otherName: string; labels: StressorInfo | undefined }) {
  const c = crossCheck(here.cells, other.cells);
  const nm = (k: string) => labels?.[k]?.label ?? k;
  const cell = (on: boolean, eff: number | null) => on ? <span className="text-teal">✓ {eff != null ? `${fix(eff, 2)} SD` : 'kept'}</span> : <span className="text-faint">not kept</span>;
  return (
    <div>
      <p className="text-[15px] text-muted max-w-3xl mt-0 mb-4 leading-relaxed">
        These two panels use <b>different states</b> from the same record, the same period and the same rules. A pair that is kept in both has repeated on states the first analysis never saw.
        It is still the same data source, so it is a check across states, not across independent datasets. Each finding&rsquo;s separate check on later data (Apr 2024 to Oct 2026) is in its evidence dossier.
      </p>
      <p className="text-[15px] m-0 mb-4 max-w-3xl leading-relaxed" role="status">
        {c.rows.length === 0 ? 'No pair was kept in either panel.'
          : <><b>{c.both}</b> pair{c.both === 1 ? '' : 's'} kept in both panels; <b>{c.onlyHere}</b> only here; <b>{c.onlyOther}</b> only in the other panel.</>}
      </p>
      {c.rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px] border-collapse min-w-[520px]">
            <thead><tr className="text-left text-faint num text-[10px] tracking-[0.14em] uppercase border-b border-line">
              <th className="py-2 pr-3 font-normal">Pair</th><th className="py-2 pr-3 font-normal">{hereName}</th><th className="py-2 font-normal">{otherName}</th></tr></thead>
            <tbody>
              {c.rows.map((r) => (
                <tr key={r.a + r.b} className="border-b border-line/60 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">{nm(r.a)} <span className="text-faint">x</span> {nm(r.b)}{r.here && r.other && <span className="num text-[10px] tracking-[0.12em] text-teal ml-2">IN BOTH</span>}</td>
                  <td className="py-2 pr-3">{cell(r.here, r.effectHere)}</td>
                  <td className="py-2">{cell(r.other, r.effectOther)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="border-l-2 border-solar pl-4 mt-5 text-[13.5px] text-muted leading-relaxed max-w-3xl">
        The outcome is stress on the power grid, not health. Sunlight, cloud cover and humidity move together, so a pair that includes them may describe a weather pattern (such as humid, cloudy monsoon days) more than a single mechanism.
        During development a second version of the outcome, with the same-day average of the panel&rsquo;s states removed, picked different pairs: these results depend on that choice.
      </div>
    </div>
  );
}
