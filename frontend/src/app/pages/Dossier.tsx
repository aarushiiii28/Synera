import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as d3 from 'd3';
import { ApiError, api, type FindingBundle, type Forest, type Gate, type VerifyResult } from '../../lib/api';
import { useReducedMotion, useStressors } from '../../lib/hooks';
import { fix, sci, secs, TYPE_COLOR } from '../../lib/format';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { StatusChip } from '../../components/StatusChip';
import { EvidenceTag, ProvenanceTag } from '../../components/Provenance';
import { HashRing } from '../../components/HashRing';
import { Term } from '../../components/Term';
import { Caveat, Explainer } from '../../components/Explainer';
import { EmptyState, ErrorState, Skeleton } from '../../components/States';
import { ResponseSurface } from '../../components/charts/ResponseSurface';
import { TypeGlyph } from '../../components/charts/DiscoveryCurves';
import { FindingsConfidenceArc } from '../../components/charts/FindingsParts';
import { GATE_ORDER, caveatKinds, findingSentence, pInflationOrders, verdictState } from '../../components/charts/discoveryLogic';

function Row({ k, children }: { k: ReactNode; children: ReactNode }) {
  return <div className="flex justify-between gap-4 py-1.5 border-b border-line/60 text-[13.5px]"><dt className="text-muted">{k}</dt><dd className="num m-0 text-right break-all">{children}</dd></div>;
}

function ForestPlot({ forest, color }: { forest: Forest; color: string }) {
  const rows = forest.studies;
  const vals = rows.flatMap((r) => (r.effect !== null ? [r.effect, r.ci_low ?? r.effect, r.ci_high ?? r.effect, 0] : []));
  if (vals.length === 0) return <p className="text-sm text-muted m-0">The API returned no effect estimates for this finding.</p>;
  const x = d3.scaleLinear([Math.min(...vals), Math.max(...vals)], [8, 380]).nice();
  const RH = 46;
  const H = rows.length * RH + 40;
  return (
    <svg viewBox={`0 0 560 ${H}`} className="w-full h-auto" role="img" aria-label="Forest plot of effect estimates with 95 percent confidence intervals">
      <g transform="translate(12,6)">
        <line x1={x(0)} x2={x(0)} y1="0" y2={rows.length * RH} stroke="var(--line-strong)" strokeDasharray="3 3" />
        {rows.map((r, i) => (
          <g key={i} transform={`translate(0,${i * RH})`}>
            <text y="14" fontSize="12.5" fill="var(--text)">{r.name.replace(/: joint test p = .*/, '')}</text>
            {r.effect !== null && r.ci_low !== null && r.ci_high !== null ? (
              <>
                <line x1={x(r.ci_low)} x2={x(r.ci_high)} y1="30" y2="30" stroke={color} strokeWidth="2" />
                <line x1={x(r.ci_low)} x2={x(r.ci_low)} y1="25" y2="35" stroke={color} /><line x1={x(r.ci_high)} x2={x(r.ci_high)} y1="25" y2="35" stroke={color} />
                <circle cx={x(r.effect)} cy="30" r="4.5" fill={color} />
                <text x={x(r.ci_high) + 8} y="34" fontSize="11.5" className="num" fill="var(--muted)">{fix(r.effect, 2)} [{fix(r.ci_low, 2)}, {fix(r.ci_high, 2)}]</text>
              </>
            ) : (
              <text y="34" fontSize="12" className="num" fill="var(--muted)">{r.p !== undefined ? `joint test p = ${sci(r.p)}` : 'no interval'}{'cities' in r && Array.isArray((r as { cities?: string[] }).cities) ? `  ·  ${(r as { cities: string[] }).cities.join(', ')}` : ''}</text>
            )}
          </g>
        ))}
        <g transform={`translate(0,${rows.length * RH + 4})`}>
          {x.ticks(5).map((v) => <g key={v} transform={`translate(${x(v)},0)`}><line y2="5" stroke="var(--line-strong)" /><text y="19" textAnchor="middle" fontSize="11" className="num" fill="var(--muted)">{fix(v, 2)}</text></g>)}
        </g>
      </g>
    </svg>
  );
}

function GateGlyph({ passed }: { passed: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className="shrink-0 mt-0.5">
      {passed ? <><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--teal)" /><path d="M5 8.2l2 2 4-4.4" fill="none" stroke="var(--teal)" strokeWidth="1.6" /></>
        : <><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--alert)" /><path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="var(--alert)" strokeWidth="1.6" /></>}
    </svg>
  );
}

function sortGates(g: Gate[]) { return [...g].sort((a, b) => GATE_ORDER.indexOf(a.id) - GATE_ORDER.indexOf(b.id)); }

function Dossier({ f }: { f: FindingBundle }) {
  const reduced = useReducedMotion();
  const qc = useQueryClient();
  const st = useStressors();
  const forest = useQuery({ queryKey: ['forest', f.id], queryFn: () => api.forest(f.id) });
  const surface = useQuery({ queryKey: ['surface', f.id], queryFn: () => api.surface(f.id), enabled: f.has_surface });
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [shown, setShown] = useState(0);
  const timer = useRef<number | undefined>(undefined);
  const verify = useMutation({
    mutationFn: () => api.verifyFinding(f.id),
    onSuccess: (r) => {
      setResult(r);
      if (reduced) { setShown(r.gates.length); return; }
      setShown(0);
      let i = 0;
      window.clearInterval(timer.current);
      timer.current = window.setInterval(() => {
        i += 1; setShown(i);
        if (i >= r.gates.length) { window.clearInterval(timer.current); }
      }, 380);
    },
  });
  useEffect(() => () => window.clearInterval(timer.current), []);
  const done = !!result && shown >= result.gates.length;
  useEffect(() => {
    if (done) { qc.invalidateQueries({ queryKey: ['finding', f.id] }); qc.invalidateQueries({ queryKey: ['findings'] }); }
  }, [done, qc, f.id]);

  const status = done && result ? result.new_status : f.status;
  const vs = verdictState(status);
  const gates = sortGates(result ? result.gates : f.gates);
  const g3 = f.gates.find((g) => g.id === 'G3_LEDGER_INCLUSION') ?? result?.gates.find((g) => g.id === 'G3_LEDGER_INCLUSION');
  const proof = (g3?.merkle_proof as { side: 'L' | 'R'; hash: string }[] | undefined) ?? [];
  const findingHash = g3?.finding_hash as string | undefined;
  const block = (g3?.block_index as number | undefined) ?? f.run?.ledger_block ?? null;
  const nm = (k: string) => st.data?.[k]?.label ?? k;
  const color = TYPE_COLOR[f.type];
  const infl = pInflationOrders(f.stats.p, f.stats.p_naive);
  const halves = f.replication?.halves ? Object.entries(f.replication.halves) : [];
  const methodRows: [string, string, boolean][] = [
    ['Parametric interaction test', 'significant after calibration', f.methods.parametric],
    ['Gradient-boosted trees (GBM)', f.methods.gbm_rank != null ? `ranked #${f.methods.gbm_rank} of all pairs` : 'not ranked', f.methods.gbm],
    ['Neural interaction detection (NID)', f.methods.nid_rank != null ? `ranked #${f.methods.nid_rank} of all pairs` : 'not ranked', f.methods.nid],
  ];

  return (
    <div className={`pb-16 ${vs.blocked ? 'hatch-alert' : ''}`}>
      <PageHeader kicker="EVIDENCE DOSSIER" title={<>{nm(f.stressors[0])} <span className="text-faint">x</span> {nm(f.stressors[1])}</>}
        standfirst={<Link to="/findings" className="text-signal text-[14px]">&larr; back to the registry</Link>} />
      <div className="px-6 md:px-10">
        {/* verdict */}
        <section aria-label="Verdict" className={`mb-8 ${vs.blocked ? 'border border-alert/70 bg-void/70 p-5' : ''}`} role={vs.blocked ? 'alert' : undefined}>
          {vs.headline && <div className="display text-alert text-xl font-semibold tracking-[0.06em] mb-3">{vs.headline}</div>}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mb-4">
            <StatusChip status={status} large />
            <ProvenanceTag provenance={f.provenance} />
            <EvidenceTag level={f.evidence_level} />
            <span className="inline-flex items-center gap-1.5 num text-[11px] tracking-[0.14em]" style={{ color }}><TypeGlyph type={f.type} size={26} />{f.type}</span>
            <span className="num text-[11px] text-faint">ID {f.id}</span>
          </div>
          <p className="display text-[clamp(1.1rem,2vw,1.5rem)] leading-snug font-normal m-0 max-w-4xl">{findingSentence(f, st.data)}</p>
        </section>

        <div className="grid gap-3 mb-8">
          {caveatKinds(f).map((k) => <Caveat key={k} kind={k} />)}
          {status !== 'VERIFIED' && <Caveat kind="VERIFIED_MEANING" />}
        </div>

        <div className="grid xl:grid-cols-[minmax(0,1fr)_380px] gap-10 items-start">
          <div className="grid gap-10 min-w-0">
            <Panel title="Response surface" index="A" provenance={f.provenance} variant="bracketed">
              <Explainer className="mb-5" tone="biosphere">Dashed lines: what these two stressors would do if their effects simply added up. Solid lines: what the data show. The shaded difference is the interaction.</Explainer>
              {!f.has_surface ? <EmptyState title="No surface for this finding">Gene-level (factorial) findings have a 2x2 design instead of a continuous surface.</EmptyState>
                : surface.isLoading ? <Skeleton h={420} /> : surface.isError ? <ErrorState error={surface.error} retry={() => surface.refetch()} />
                : surface.data && <ResponseSurface surface={surface.data} labels={st.data} layout="stack" />}
            </Panel>

            <Panel title="Effect estimates" index="B" variant="ruled">
              <Explainer className="mb-4">Each line is one estimate with its 95% <Term k="ci">confidence interval</Term>. If the line does not touch the dashed zero, the effect is distinguishable from none.</Explainer>
              {forest.isLoading ? <Skeleton h={200} /> : forest.isError ? <ErrorState error={forest.error} retry={() => forest.refetch()} /> : forest.data && <ForestPlot forest={forest.data} color={color} />}
              <dl className="m-0 mt-4 grid md:grid-cols-2 gap-x-10">
                <Row k="Interaction coefficient b_AB">{fix(f.effect.b_AB, 3)}</Row>
                <Row k="Coefficient 95% CI">{fix(f.effect.ci_low, 3)} to {fix(f.effect.ci_high, 3)}</Row>
                <Row k={<Term k="effect">Effect size</Term>}>{fix(f.effect.effect_size, 3)} SD</Row>
                <Row k="Effect-size 95% CI">{f.effect.eff_ci_low != null && f.effect.eff_ci_high != null ? `${fix(f.effect.eff_ci_low, 3)} to ${fix(f.effect.eff_ci_high, 3)} SD` : '—'}</Row>
              </dl>
            </Panel>

            <Panel title="Replication" index="C" variant="inset" right={<EvidenceTag level={f.evidence_level} />}>
              {f.replication ? (
                <>
                  <p className="text-[14px] text-muted mt-0 mb-4 max-w-2xl">{f.replication.detail}</p>
                  <div className="grid sm:grid-cols-2 gap-6">
                    {halves.map(([k, h]) => (
                      <div key={k} className="border-t border-line-strong pt-2">
                        <div className="label mb-1">City half {k}</div>
                        <div className="num text-3xl leading-none" style={{ color: h.p < 0.05 ? 'var(--teal)' : 'var(--alert)' }}>{sci(h.p)}</div>
                        <div className="text-[12.5px] text-muted mt-1">joint <Term k="pvalue">p-value</Term>, direction {h.direction > 0 ? 'positive' : 'negative'}</div>
                        <div className="text-[12px] text-faint mt-1">{h.cities.join(', ')}</div>
                      </div>
                    ))}
                  </div>
                  <div className="num text-[12px] mt-4 text-muted">{f.replication.replicated ? 'REPLICATED' : 'NOT REPLICATED'} &middot; rate {fix(f.replication.replication_rate, 2)}</div>
                  {f.evidence_level === 'LATER_DATA_REPLICATION'
                    ? <p className="text-[13px] text-muted mt-2 mb-0">Replicated on later data: the dates differ from the data that found it (the source is the same grid operator), and the engine kept this pair again under the same pre-set rules.</p>
                    : f.evidence_level !== 'INDEPENDENT_REPLICATION' && <p className="text-[13px] text-solar mt-2 mb-0">Evidence level {f.evidence_level.replace(/_/g, ' ').toLowerCase()}: this is not an independent replication.</p>}
                </>
              ) : <p className="text-sm text-muted m-0">No replication was attempted for this finding.</p>}
            </Panel>

            <div className="grid md:grid-cols-2 gap-10">
              <Panel title="Method agreement" index="D" variant="ruled">
                <p className="text-[13.5px] text-muted mt-0 mb-3">Three different methods look at the same pair. Agreement guards against one method&rsquo;s blind spot.</p>
                <ul className="list-none p-0 m-0 grid gap-2">
                  {methodRows.map(([n, d, ok]) => (
                    <li key={n} className="flex gap-2.5 items-start"><GateGlyph passed={ok} /><div><div className="text-[14px]">{n}</div><div className="num text-[12px] text-muted">{ok ? 'AGREES' : 'DISAGREES'} &middot; {d}</div></div></li>
                  ))}
                </ul>
              </Panel>
              <Panel title="Statistics" index="E" variant="ruled">
                <dl className="m-0">
                  <Row k={<Term k="pvalue">p</Term>}>{sci(f.stats.p)}</Row>
                  <Row k={<Term k="qvalue">q (FDR)</Term>}>{sci(f.stats.q)}</Row>
                  <Row k="marginal q (screen)">{sci(f.stats.q_marginal)}</Row>
                  <Row k="n / df">{f.stats.n} / {fix(f.stats.df, 0)}</Row>
                  <Row k={<Term k="lambda">lambda (inflation)</Term>}>{fix(f.stats.lambda_boot, 2)}</Row>
                </dl>
                <div className="label mt-4 mb-2">Naive vs calibrated p (&minus;log10)</div>
                {(() => {
                  const bars = [['naive', f.stats.p_naive], ['HAC', f.stats.p_hac], ['calibrated', f.stats.p]] as const;
                  const lg = bars.map(([, p]) => (p && p > 0 ? -Math.log10(p) : 0));
                  const mx = Math.max(1, ...lg);
                  return (
                    <ul className="list-none p-0 m-0 grid gap-1.5">
                      {bars.map(([k, p], i) => (
                        <li key={k} className="grid grid-cols-[5.5rem_1fr_auto] gap-2 items-center text-[12px]">
                          <span className="text-muted">{k}</span><span className="h-1.5 bg-line/60"><span className="block h-full" style={{ width: `${(lg[i] / mx) * 100}%`, background: k === 'calibrated' ? 'var(--teal)' : 'var(--solar)' }} /></span><span className="num">{sci(p)}</span>
                        </li>
                      ))}
                    </ul>
                  );
                })()}
                {infl !== null && <p className="text-[12.5px] text-muted mt-2 mb-0">The calibrated p is {fix(infl, 0)} orders of magnitude less extreme than the naive one: neighbouring days are correlated, so the naive test is over-confident.</p>}
              </Panel>
            </div>
          </div>

          {/* trust stack */}
          <aside className="grid gap-8 min-w-0 xl:sticky xl:top-20" aria-label="Trust stack">
            <Panel title="Trust stack" index="F" variant={vs.blocked ? 'alert' : 'bracketed'}>
              <ol className="list-none m-0 p-0 grid gap-3">
                {gates.map((g, i) => {
                  const hidden = !!result && i >= shown;
                  return (
                    <li key={g.id} className="flex gap-2.5 items-start" style={{ opacity: hidden ? 0.35 : 1, transition: reduced ? 'none' : 'opacity .3s' }}>
                      {hidden ? <span className="w-4 h-4 mt-0.5 rounded-full border border-dashed border-faint shrink-0 pulse-soft" aria-hidden /> : <GateGlyph passed={g.passed} />}
                      <div className="min-w-0">
                        <div className="text-[13.5px] leading-snug"><span className="num text-[10px] tracking-[0.12em] mr-2" style={{ color: hidden ? 'var(--faint)' : g.passed ? 'var(--teal)' : 'var(--alert)' }}>{hidden ? 'CHECKING' : g.passed ? 'PASS' : 'FAIL'}</span>{g.label}</div>
                        {!hidden && <div className="text-[12.5px] text-muted leading-snug break-words">{g.reason}</div>}
                        {!hidden && g.integrity && <div className="num text-[10px] tracking-[0.12em] text-faint mt-0.5">INTEGRITY GATE</div>}
                      </div>
                    </li>
                  );
                })}
              </ol>
              <button type="button" onClick={() => verify.mutate()} disabled={verify.isPending || (!!result && !done)}
                className="mt-5 w-full num tracking-[0.16em] text-[13px] py-2.5 border border-signal text-signal bg-signal/10 hover:bg-signal/20 disabled:opacity-40">
                {verify.isPending ? 'RE-RUNNING ALL GATES' : 'RE-VERIFY NOW'}
              </button>
              {verify.isError && <div className="mt-3"><ErrorState error={verify.error} /></div>}
              {done && result && (
                <div className={`mt-4 border px-3 py-2.5 ${result.new_status === 'BLOCKED' ? 'border-alert/70' : 'border-line'}`} role="status">
                  <div className="num text-[11px] tracking-[0.12em] mb-1">{result.previous_status} &rarr; <span className="text-text">{result.new_status}</span>{result.allowed ? ' · PROMOTION ALLOWED' : ''}</div>
                  {result.new_status === 'BLOCKED' ? <div className="text-[13px] text-alert">RESULT BLOCKED FROM VERIFIED STATUS</div>
                    : result.new_status !== 'VERIFIED' && <div className="text-[13px] text-muted mb-1">Not VERIFIED because:</div>}
                  <ul className="m-0 pl-4 text-[12.5px] text-muted grid gap-1">{result.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  {result.verdict && <p className="text-[12.5px] text-text mt-2 mb-0">{result.verdict}</p>}
                </div>
              )}
            </Panel>

            <Panel title="Fingerprints and ledger" index="G" variant="inset">
              <div className="grid gap-4">
                {(f.dataset?.hash || f.run?.dataset_hash) && <HashRing label="dataset hash" hash={(f.run?.dataset_hash ?? f.dataset?.hash) as string} size={36} />}
                {findingHash && <HashRing label="finding hash" hash={findingHash} size={36} />}
                {proof.length > 0 && (
                  <div>
                    <div className="label mb-2"><Term k="merkle">Merkle proof</Term> path</div>
                    <ol className="list-none m-0 p-0 grid gap-2 border-l border-line pl-3">
                      {proof.map((p, i) => <li key={i} className="flex items-center gap-2"><span className="num text-[10px] text-signal w-4">{p.side}</span><HashRing hash={p.hash} size={24} /></li>)}
                    </ol>
                  </div>
                )}
                {block !== null && <Link to={`/trust?block=${block}`} className="num text-[11px] tracking-[0.14em] text-signal border border-signal/60 px-3 py-1.5 w-fit hover:bg-signal/10">LEDGER BLOCK {block}</Link>}
              </div>
            </Panel>

            <Panel title="Run receipt" index="H" variant="ruled">
              {f.run ? (
                <dl className="m-0">
                  <Row k="run">{f.run.id}</Row>
                  <Row k="status">{f.run.status}</Row>
                  <Row k="runtime">{secs(f.run.runtime_s)}</Row>
                  <Row k="replay matches">{f.run.replay ? (f.run.replay.matches ? 'YES' : 'NO') : '—'}</Row>
                </dl>
              ) : <p className="text-sm text-muted m-0">No run record.</p>}
              {f.run && <div className="grid gap-3 mt-3">
                <HashRing label="config hash" hash={f.run.config_hash} size={28} />
                {f.run.result_hash && <HashRing label="result hash" hash={f.run.result_hash} size={28} />}
              </div>}
              {f.confidence && (
                <div className="mt-5 flex items-center gap-3"><FindingsConfidenceArc score={f.confidence.score} components={f.confidence.components} size={52} />
                  <div className="text-[12px] text-muted leading-snug">confidence {fix(f.confidence.score, 2)}<br />{Object.entries(f.confidence.components).map(([k, v]) => `${k} ${fix(v, 2)}`).join(' · ')}</div></div>
              )}
            </Panel>

            <Panel title="History" index="I" variant="ruled">
              {f.history.length === 0 ? <p className="text-sm text-muted m-0">No recorded events.</p> : (
                <ol className="list-none m-0 p-0 grid gap-2 text-[12.5px] text-muted">{f.history.map((h, i) => <li key={i} className="num break-words">{h}</li>)}</ol>
              )}
            </Panel>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default function DossierPage() {
  const { id = '' } = useParams();
  const q = useQuery({ queryKey: ['finding', id], queryFn: () => api.finding(id), retry: false });
  if (q.isLoading) return <div className="p-10"><Skeleton h={320} label="OPENING DOSSIER" /></div>;
  if (q.isError && q.error instanceof ApiError && q.error.status === 404) {
    return (
      <div>
        <PageHeader kicker="EVIDENCE DOSSIER" title="Finding not found" standfirst="No finding in the registry has this id." />
        <div className="px-6 md:px-10"><EmptyState title={`No finding "${id}"`} tone="solar" action={<Link to="/findings" className="num text-xs border border-signal text-signal px-4 py-2">BROWSE THE REGISTRY</Link>}>
          Finding ids are 12-character fingerprints of the dataset, the stressor pair and the run configuration. A new run with different settings creates new ids.
        </EmptyState></div>
      </div>
    );
  }
  if (q.isError) return <div className="p-10"><ErrorState error={q.error} retry={() => q.refetch()} /></div>;
  return q.data ? <Dossier f={q.data} /> : null;
}

