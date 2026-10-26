import type { InteractionMatrix, StressorInfo } from '../../lib/api';
import { screenAudit } from './discoveryLogic';

const TOPK = 6;

/** The lists a plain test, a tree model or a neural network would each have handed over on this very run, and what happened to every pair on them. */
export function ScreenAuditView({ matrix, labels, simulated, developmentNote }: { matrix: InteractionMatrix; labels: StressorInfo | undefined; simulated: boolean; developmentNote?: string }) {
  const a = screenAudit(matrix.cells, TOPK);
  const nm = (k: string) => labels?.[k]?.label ?? k;
  const dropped = a.flagged - a.survived;
  return (
    <div>
      <p className="text-[15px] text-muted max-w-3xl mt-0 mb-5 leading-relaxed">
        Common approaches hand you a list: a classical significance test, or a tree or neural model used alone. We ran those same approaches on <b>exactly this data</b> and then
        checked each pair on their lists against SYNERA&rsquo;s full stack. This is computed from this run, not from any outside software.
      </p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          ['Plain significance test', a.plain, 'p < 0.05, assumes independent days'],
          ['Tree model alone', a.trees, `top ${TOPK} pairs by SHAP strength`],
          ['Neural network alone', a.neural, `top ${TOPK} pairs by interaction strength`],
          ['SYNERA full stack', a.survived, 'survived every check'],
        ].map(([t, n, s], i) => (
          <div key={String(t)} className={`border px-4 py-3 ${i === 3 ? 'border-signal bg-signal/5' : 'border-line'}`}>
            <div className="label">{t}</div>
            <div className="num text-3xl mt-1">{n}<span className="text-faint text-base"> of {a.total}</span></div>
            <div className="text-[12.5px] text-muted mt-1">{s}</div>
          </div>
        ))}
      </div>
      <p className="text-[15px] m-0 mb-4 max-w-3xl leading-relaxed" role="status">
        {a.flagged === 0 ? 'None of the three approaches flagged a pair on this run.'
          : <>Taken together, these approaches flag <b>{a.flagged}</b> distinct pair{a.flagged === 1 ? '' : 's'}. <b>{dropped}</b> of them did not survive SYNERA&rsquo;s checks{a.flagged ? <> ({Math.round((100 * dropped) / a.flagged)}%)</> : null}.</>}
      </p>
      {a.rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px] border-collapse min-w-[600px]">
            <thead><tr className="text-left text-faint num text-[10px] tracking-[0.14em] uppercase border-b border-line">
              <th className="py-2 pr-3 font-normal">Pair</th><th className="py-2 pr-3 font-normal">Flagged by</th><th className="py-2 pr-3 font-normal">SYNERA&rsquo;s verdict</th>
              <th className="py-2 font-normal text-right" title="False-alarm risk after correcting for repeated testing. Below 0.05 is needed to count.">q</th></tr></thead>
            <tbody>
              {a.rows.slice(0, 12).map((r) => (
                <tr key={r.a + r.b} className="border-b border-line/60 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">{nm(r.a)} <span className="text-faint">x</span> {nm(r.b)}</td>
                  <td className="py-2 pr-3 text-muted">{r.flaggedBy.join(', ')}</td>
                  <td className="py-2 pr-3">
                    <span className={`font-medium ${r.survived ? 'text-teal' : 'text-solar'}`}>{r.survived ? '✓ ' : '✕ '}{r.verdict}</span>
                    <span className="block text-[12.5px] text-muted leading-snug">{r.why}</span>
                  </td>
                  <td className="py-2 num text-right text-muted whitespace-nowrap">{r.q < 0.001 ? '<0.001' : r.q.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[12.5px] text-faint mt-2 mb-0 max-w-3xl"><b>q</b> is the risk that a flagged pair is a false alarm after correcting for repeated testing. It has to be below 0.05 to count; 0.98 means almost certainly noise.</p>
        </div>
      )}
      {a.rows.length > 12 && <p className="num text-[11px] text-faint mt-2 mb-0">Showing 12 of {a.rows.length} flagged pairs, survivors first.</p>}
      <div className="border-l-2 border-solar pl-4 mt-5 text-[13.5px] text-muted leading-relaxed max-w-3xl">
        {simulated
          ? <>This dataset has a simulated outcome with a known truth, so the benchmark page can say exactly which flagged pairs were false. </>
          : <>On real data there is no answer key, so we cannot prove a flagged pair is false. We can show that it <b>did not survive</b> calibration, correction for repeated testing, selection against look-alike pairs, an effect-size gate and a second method. </>}
        Nothing here says that any particular product or paper is wrong; it shows what those <i>kinds</i> of method would report on this data.
        {developmentNote && <> {developmentNote}</>}
      </div>
    </div>
  );
}
