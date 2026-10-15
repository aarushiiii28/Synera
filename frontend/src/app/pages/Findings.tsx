import { useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import type { Finding, Status } from '../../lib/api';
import { useFindings, useStressors } from '../../lib/hooks';
import { fix, sci, TYPE_COLOR } from '../../lib/format';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { StatusChip } from '../../components/StatusChip';
import { EvidenceTag, ProvenanceTag } from '../../components/Provenance';
import { Term } from '../../components/Term';
import { EmptyState, ErrorState, Skeleton } from '../../components/States';
import { TypeGlyph } from '../../components/charts/DiscoveryCurves';
import { FindingsConfidenceArc, FindingsMiniForest } from '../../components/charts/FindingsParts';
import { activeFilterCount, filtersToParams, forestSpan, nextSort, PAGE_SIZE, pageCount, parseFilters, toApiQuery, type FindingFilters } from '../../components/charts/discoveryLogic';

const STATUSES: Status[] = ['CANDIDATE', 'VALIDATED', 'VERIFIED', 'BLOCKED', 'REJECTED'];
const SEL = 'bg-void border border-line px-2 py-1.5 text-[13px] text-text min-w-0 focus-visible:outline-signal';

export default function Findings() {
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const f = useMemo(() => parseFilters(sp), [sp]);
  const set = (patch: Partial<FindingFilters>) => setSp(filtersToParams({ ...f, page: 1, ...patch }), { replace: true });
  const q = useFindings(toApiQuery(f));
  const st = useStressors();
  const nm = (k: string) => st.data?.[k]?.label ?? k;
  const items = q.data?.items ?? [];
  const maxHi = Math.max(0, ...items.map((i) => forestSpan(i)?.hi ?? 0));
  const counts = q.data?.counts;
  const registryTotal = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : null;
  const filters = activeFilterCount(f);
  const pages = q.data ? pageCount(q.data.total) : 1;
  const arrow = (col: 'effect' | 'q' | 'status') => {
    const on = col === 'effect' ? f.sort.endsWith('effect_size') : col === 'q' ? f.sort.endsWith('q_value') : f.sort === 'status';
    return on ? (f.sort.startsWith('-') ? ' ▾' : ' ▴') : '';
  };
  const th = (label: string, col: 'effect' | 'q' | 'status') => (
    <th scope="col" className="text-left font-normal py-2 pr-4" aria-sort={(col === 'effect' ? f.sort.endsWith('effect_size') : col === 'q' ? f.sort.endsWith('q_value') : f.sort === 'status') ? 'other' : 'none'}>
      <button type="button" onClick={() => set({ sort: nextSort(f.sort, col) })} className="label bg-transparent border-0 p-0 cursor-pointer hover:!text-text">{label}{arrow(col)}</button>
    </th>
  );
  const open = (r: Finding) => nav(`/findings/${r.id}`);

  const empty = q.data && q.data.total === 0 && (
    registryTotal === 0 ? (
      <EmptyState title="The registry is empty">
        No run has produced a finding yet. Run the engine in the Discovery Lab and every interaction that survives selection will appear here with its evidence.
        <span className="block mt-2">Zero <b>VERIFIED</b> is also the expected state for simulated data and for single-dataset results: <Link to="/guide" className="text-signal">see how a finding earns that status</Link>.</span>
      </EmptyState>
    ) : (
      <EmptyState title="No findings match these filters" tone="solar" action={<button type="button" onClick={() => setSp({}, { replace: true })} className="num text-xs border border-signal text-signal px-4 py-2 hover:bg-signal/10">CLEAR ALL FILTERS</button>}>
        {registryTotal} finding{registryTotal === 1 ? '' : 's'} exist in the registry, none with {[f.status && `status ${f.status}`, f.type && `type ${f.type}`, f.track && `track ${f.track}`, f.provenance && `${f.provenance} data`, f.q && `"${f.q}" in the name`].filter(Boolean).join(', ')}.
        {f.status === 'VERIFIED' && <span className="block mt-2">No finding is VERIFIED because that needs REAL data and independent replication. <Link to="/guide" className="text-signal">Why?</Link></span>}
      </EmptyState>
    )
  );

  return (
    <div className="pb-16">
      <PageHeader index="02" kicker="VALIDATE" title="Findings registry"
        standfirst={<>Every interaction the engine has kept, with how far it got: <Term k="interaction">candidates</Term> are found by the statistics, <b>validated</b> findings passed every statistical test, and <Term k="verified">verified</Term> ones also have independent replication and intact provenance.</>} />

      {/* counts bar */}
      <section aria-label="Registry counts" className="px-6 md:px-10 mb-8">
        <ul className="list-none m-0 p-0 grid grid-cols-2 md:grid-cols-5 border-y border-line">
          {STATUSES.map((s) => (
            <li key={s} className="border-r border-line last:border-r-0 first:border-l-0">
              <button type="button" aria-pressed={f.status === s} onClick={() => set({ status: f.status === s ? '' : s })}
                className={`w-full text-left px-4 py-3 bg-transparent border-0 cursor-pointer ${f.status === s ? 'bg-signal/10' : 'hover:bg-hull/40'}`}>
                <StatusChip status={s} />
                <div className="num text-4xl leading-none mt-2" style={{ color: counts && counts[s] === 0 ? 'var(--faint)' : 'var(--text)' }}>{counts ? counts[s] : '—'}</div>
              </button>
            </li>
          ))}
        </ul>
        {counts && counts.VERIFIED === 0 && <p className="text-[13px] text-muted mt-2 mb-0">0 verified is expected here: VERIFIED needs REAL data and independent replication. <Link to="/guide" className="text-signal">How a finding earns it</Link>.</p>}
      </section>

      {/* instrument strip */}
      <section aria-label="Filters" className="px-6 md:px-10 mb-6">
        <div className="flex flex-wrap items-end gap-x-5 gap-y-3 border-b border-line pb-4">
          {([
            ['status', 'Status', STATUSES], ['type', 'Type', ['SYNERGISTIC', 'ANTAGONISTIC', 'NONLINEAR']], ['track', 'Track', ['A', 'B']], ['provenance', 'Provenance', ['REAL', 'SIMULATED']],
          ] as const).map(([k, label, opts]) => (
            <label key={k} className="grid gap-1"><span className="label">{label}</span>
              <select className={SEL} value={f[k]} onChange={(e) => set({ [k]: e.target.value })}>
                <option value="">All</option>{opts.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
          ))}
          <label className="grid gap-1 flex-1 min-w-[12rem]"><span className="label">Search stressor or gene</span>
            <input type="search" className={SEL} value={f.q} maxLength={60} placeholder="e.g. heat" onChange={(e) => set({ q: e.target.value })} />
          </label>
          <button type="button" disabled={filters === 0} onClick={() => setSp({}, { replace: true })} className="num text-[11px] tracking-[0.12em] border border-line px-3 py-2 text-muted enabled:hover:text-text disabled:opacity-40">CLEAR{filters ? ` (${filters})` : ''}</button>
        </div>
        <div className="num text-[12px] text-muted mt-2" role="status">{q.data ? `${q.data.total} finding${q.data.total === 1 ? '' : 's'}${filters ? ' match' : ''}` : ''}</div>
      </section>

      <div className="px-6 md:px-10">
        {q.isLoading ? <Skeleton h={260} /> : q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : empty ? empty : (
          <Panel variant="bare" padded={false}>
            {/* desktop table */}
            <table className="hidden md:table w-full border-collapse text-[13.5px]">
              <caption className="sr-only">Findings registry</caption>
              <thead><tr className="border-b border-line-strong">
                {th('Status', 'status')}
                <th scope="col" className="label text-left font-normal pr-4">Type</th>
                <th scope="col" className="label text-left font-normal pr-4">Stressor pair</th>
                {th('Effect (SD) and 95% CI', 'effect')}
                {th('q-value', 'q')}
                <th scope="col" className="label text-left font-normal pr-4">Confidence</th>
                <th scope="col" className="label text-left font-normal">Data and evidence</th>
              </tr></thead>
              <tbody>
                {items.map((r) => {
                  const span = forestSpan(r);
                  return (
                    <tr key={r.id} onClick={() => open(r)} className="border-b border-line hover:bg-hull/50 cursor-pointer">
                      <td className="py-3 pr-4"><StatusChip status={r.status} /></td>
                      <td className="pr-4"><span className="inline-flex items-center gap-2 num text-[11px] tracking-[0.1em]" style={{ color: TYPE_COLOR[r.type] }}><TypeGlyph type={r.type} size={24} />{r.type}</span></td>
                      <td className="pr-4">
                        <Link to={`/findings/${r.id}`} onClick={(e) => e.stopPropagation()} className="text-text hover:text-signal font-medium">{nm(r.stressors[0])} <span className="text-faint">x</span> {nm(r.stressors[1])}</Link>
                        {r.feature && <div className="num text-[11px] text-muted">{r.feature}</div>}
                      </td>
                      <td className="pr-4">
                        <div className="flex items-center gap-3"><span className="num w-10">{fix(r.effect.effect_size, 2)}</span>
                          {span && <FindingsMiniForest point={span.point} lo={span.lo} hi={span.hi} max={maxHi} label={`Effect ${fix(span.point, 2)}, interval ${fix(span.lo, 2)} to ${fix(span.hi, 2)}`} />}</div>
                      </td>
                      <td className="num pr-4">{sci(r.stats.q)}</td>
                      <td className="pr-4">{r.confidence && <FindingsConfidenceArc score={r.confidence.score} components={r.confidence.components} />}</td>
                      <td><div className="grid gap-1 justify-items-start"><ProvenanceTag provenance={r.provenance} /><EvidenceTag level={r.evidence_level} /></div></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* mobile cards */}
            <ul className="md:hidden list-none m-0 p-0 grid gap-3">
              {items.map((r) => {
                const span = forestSpan(r);
                return (
                  <li key={r.id} className="border border-line bg-hull/30 p-4">
                    <div className="flex items-center justify-between mb-2"><StatusChip status={r.status} /><ProvenanceTag provenance={r.provenance} /></div>
                    <Link to={`/findings/${r.id}`} className="display text-[17px] text-text">{nm(r.stressors[0])} <span className="text-faint">x</span> {nm(r.stressors[1])}</Link>
                    <div className="mt-1 inline-flex items-center gap-2 num text-[11px] tracking-[0.1em]" style={{ color: TYPE_COLOR[r.type] }}><TypeGlyph type={r.type} size={22} />{r.type}</div>
                    <div className="flex items-center gap-4 mt-3">
                      <div><div className="label">effect SD</div><div className="num">{fix(r.effect.effect_size, 2)}</div></div>
                      <div><div className="label">q</div><div className="num">{sci(r.stats.q)}</div></div>
                      {r.confidence && <FindingsConfidenceArc score={r.confidence.score} components={r.confidence.components} />}
                    </div>
                    {span && <div className="mt-2"><FindingsMiniForest point={span.point} lo={span.lo} hi={span.hi} max={maxHi} width={160} label={`Effect ${fix(span.point, 2)}`} /></div>}
                    <div className="mt-2"><EvidenceTag level={r.evidence_level} /></div>
                  </li>
                );
              })}
            </ul>

            {pages > 1 && (
              <nav aria-label="Pagination" className="flex items-center gap-4 mt-5 num text-[12px]">
                <button type="button" disabled={f.page <= 1} onClick={() => set({ page: f.page - 1 })} className="border border-line px-3 py-1.5 disabled:opacity-40">PREV</button>
                <span>page {f.page} of {pages} <span className="text-faint">({PAGE_SIZE} per page)</span></span>
                <button type="button" disabled={f.page >= pages} onClick={() => set({ page: f.page + 1 })} className="border border-line px-3 py-1.5 disabled:opacity-40">NEXT</button>
              </nav>
            )}
          </Panel>
        )}
      </div>
    </div>
  );
}
