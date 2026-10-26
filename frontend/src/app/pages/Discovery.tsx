import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, api, type MatrixCell, type Run } from '../../lib/api';
import { useDatasets, useReducedMotion, useRunStream, useStressors } from '../../lib/hooks';
import { useUI } from '../../store';
import { fix, int, secs, sci, TYPE_COLOR } from '../../lib/format';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { Term } from '../../components/Term';
import { Explainer, Caveat } from '../../components/Explainer';
import { StatusChip } from '../../components/StatusChip';
import { ProvenanceTag } from '../../components/Provenance';
import { Async, EmptyState, ErrorState, Skeleton } from '../../components/States';
import { DiscoveryOrbit } from '../../components/charts/DiscoveryOrbit';
import { DiscoveryMatrix } from '../../components/charts/DiscoveryMatrix';
import { DiscoveryConstellation } from '../../components/charts/DiscoveryConstellation';
import { DiscoveryCurves, TypeGlyph } from '../../components/charts/DiscoveryCurves';
import { ResponseSurface } from '../../components/charts/ResponseSurface';
import { ScreenAuditView } from '../../components/charts/ScreenAudit';
import { CrossCheck } from '../../components/charts/CrossCheck';

const INDIA_PAIR: Record<string, string> = { india_grid: 'india_grid_b', india_grid_b: 'india_grid' };
import { explainedAway, funnelStages, overallProgress, runBanner, stepViews, type StepView } from '../../components/charts/discoveryLogic';

const FLOW = [
  { t: 'Environmental data', s: 'Daily heat, air-pollution and weather readings, plus one health-style outcome.' },
  { t: 'Intelligence engine', s: 'Statistics and two machine-learning second opinions score every pair of stressors.' },
  { t: 'Interaction discovery', s: 'Pairs whose combined effect is not just the sum of their parts are flagged.' },
  { t: 'Statistical validation', s: 'Significance, effect size, confidence intervals, multiple-testing correction and replication.' },
  { t: 'Candidate finding', s: 'Only what survives becomes a finding in the registry, with its evidence attached.' },
];

function FlowStrip() {
  return (
    <section aria-label="How discovery works" className="px-6 md:px-10 pb-8">
      <ol className="list-none m-0 p-0 grid md:grid-cols-5 gap-y-6">
        {FLOW.map((f, i) => (
          <li key={f.t} className="relative md:pr-6">
            <div className="flex items-center gap-3 mb-2">
              <span className="grid place-items-center w-9 h-9 rounded-full border border-signal/70 num text-[13px] text-signal bg-void">{i + 1}</span>
              {i < FLOW.length - 1 && <span className="hidden md:block flex-1 h-px bg-gradient-to-r from-signal/50 to-line relative" aria-hidden><span className="absolute -right-0.5 -top-[3px] w-1.5 h-1.5 border-t border-r border-signal/70 rotate-45" /></span>}
            </div>
            <h3 className="display text-[13px] font-semibold uppercase tracking-[0.1em] m-0 mb-1">{f.t}</h3>
            <p className="text-[13.5px] text-muted leading-snug m-0 max-w-[15rem]">{f.s}</p>
          </li>
        ))}
      </ol>
      <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-4">
        <span className="label">Example</span>
        <span className="display text-[17px]">Heat <span className="text-faint">+</span> Air pollution <span className="text-signal">&rarr;</span> amplified response?</span>
        <span className="num text-[10px] tracking-[0.14em] text-signal border border-signal/70 px-2 py-0.5">CANDIDATE INTERACTION</span>
      </div>
    </section>
  );
}

function StateGlyph({ s }: { s: StepView['state'] }) {
  const c = s === 'DONE' ? 'var(--teal)' : s === 'FAILED' ? 'var(--alert)' : s === 'RUNNING' ? 'var(--signal)' : 'var(--faint)';
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className="shrink-0 mt-0.5">
      {s === 'DONE' && <><circle cx="8" cy="8" r="6.5" fill="none" stroke={c} /><path d="M5 8.2l2 2 4-4.4" fill="none" stroke={c} strokeWidth="1.6" /></>}
      {s === 'FAILED' && <><circle cx="8" cy="8" r="6.5" fill="none" stroke={c} /><path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke={c} strokeWidth="1.6" /></>}
      {s === 'RUNNING' && <circle cx="8" cy="8" r="5" fill={c} className="pulse-soft" />}
      {s === 'PENDING' && <circle cx="8" cy="8" r="5.5" fill="none" stroke={c} strokeDasharray="2 3" />}
    </svg>
  );
}

function Timeline({ views }: { views: StepView[] }) {
  return (
    <ol className="list-none m-0 p-0 relative">
      {views.map((v, i) => (
        <li key={v.step} className="relative flex gap-3 pb-3">
          {i < views.length - 1 && <span className="absolute left-[7.5px] top-5 bottom-0 w-px bg-line" aria-hidden />}
          <StateGlyph s={v.state} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className={`text-[14px] ${v.state === 'PENDING' ? 'text-faint' : 'text-text'}`}><span className="num text-faint mr-1.5">{String(v.step).padStart(2, '0')}</span>{v.label}</span>
              <span className="num text-[10px] tracking-[0.14em] text-faint">{v.state}</span>
              {v.duration !== null && <span className="num text-[12px] text-signal ml-auto">{secs(v.duration)}</span>}
            </div>
            {v.message && v.state !== 'PENDING' && <p className="text-[12.5px] text-muted leading-snug m-0 mt-0.5 break-words">{v.message}</p>}
            {v.counts.length > 0 && (
              <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
                {v.counts.map((c) => <span key={c.k} className="num text-[11px] text-muted"><span className="text-text">{c.v}</span> {c.k}</span>)}
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function Funnel({ run }: { run: Run }) {
  const stages = funnelStages(run);
  if (!stages) {
    return (
      <div className="text-[13.5px] text-muted leading-snug">
        This run tested genes rather than stressor pairs, so there is no pair funnel. Findings recorded:{' '}
        {(['CANDIDATE', 'VALIDATED', 'VERIFIED', 'BLOCKED', 'REJECTED'] as const).map((k) => <span key={k} className="num mr-3">{k.toLowerCase()} <span className="text-text">{run.summary?.[k] ?? 0}</span></span>)}
      </div>
    );
  }
  const max = Math.max(1, stages[0].value);
  const removed = explainedAway(stages);
  return (
    <div>
      <ul className="list-none p-0 m-0 grid gap-3" aria-label="Discovery funnel">
        {stages.map((s, i) => (
          <li key={s.key}>
            <div className="flex items-baseline gap-3">
              <span className="num text-3xl leading-none w-14 text-right" style={{ color: i === stages.length - 1 ? 'var(--teal)' : 'var(--text)' }}>{s.value}</span>
              <span className="text-[14px]">{s.label}</span>
              <span className="text-[12px] text-faint hidden sm:inline">{s.note}</span>
            </div>
            <div className="ml-[4.25rem] mt-1 h-1.5 bg-line/60"><div className="h-full" style={{ width: `${(s.value / max) * 100}%`, background: i === stages.length - 1 ? 'var(--teal)' : 'var(--signal)', opacity: 1 - i * 0.15 }} /></div>
          </li>
        ))}
      </ul>
      <Explainer className="mt-5" tone="solar" title="Why pairs get explained away">
        <span className="num">{removed}</span> of the {stages[1].value} pairs that looked significant on their own were removed. Most of them are
        <Term k="proxy"> proxies</Term>: they only look like an interaction because one of their stressors travels with a truly interacting pair
        (heat index and temperature, for example). <Term k="conditional">Conditional selection</Term> accepts the strongest pair, puts it in the model, and re-tests the rest.
        {stages[2].value === 0 ? ' Nothing remained, which is a valid result.' : ` ${stages[2].value} stood on their own.`}
      </Explainer>
    </div>
  );
}

export default function Discovery() {
  const reduced = useReducedMotion();
  const qc = useQueryClient();
  const selectPair = useUI((s) => s.selectPair);
  const ds = useDatasets();
  const stressors = useStressors();
  const steps = useQuery({ queryKey: ['run-steps'], queryFn: api.runSteps, staleTime: Infinity });
  const runnable = useMemo(() => (ds.data ?? []).filter((d) => d.runnable), [ds.data]);
  const [chosen, setChosen] = useState<string | null>(null);
  const dsId = chosen ?? runnable.find((d) => d.id === 'benchmark_track_b')?.id ?? runnable[0]?.id ?? null;
  const dataset = runnable.find((d) => d.id === dsId);
  const geneLevel = dataset?.kind === 'factorial';
  const [quick, setQuick] = useState(true);
  const [force, setForce] = useState(false);
  const [active, setActive] = useState<{ id: string; reused: boolean; ds: string } | null>(null);
  const [tab, setTab] = useState<'matrix' | 'network'>('matrix');
  const [pick, setPick] = useState<string | null>(null);

  const start = useMutation({
    mutationFn: () => api.createRun({ dataset_id: dsId as string, quick, force }),
    onSuccess: (r) => setActive({ id: r.run_id, reused: r.reused, ds: dsId as string }),
  });

  const activeHere = active && active.ds === dsId ? active : null;
  const live = !!activeHere && !activeHere.reused;
  const stream = useRunStream(live ? activeHere.id : null);

  const history = useQuery({ queryKey: ['runs', dsId], queryFn: () => api.runs({ dataset_id: dsId as string }), enabled: !!dsId });
  const latest = history.data?.find((r) => r.status !== 'RUNNING');
  const shownId = activeHere?.id ?? latest?.id ?? null;
  const detail = useQuery({
    queryKey: ['run', shownId, live ? stream.done : 'rec'], queryFn: () => api.run(shownId as string),
    enabled: !!shownId && (!live || stream.done),
  });

  useEffect(() => {
    if (live && stream.done) {
      qc.invalidateQueries({ queryKey: ['matrix'] });
      qc.invalidateQueries({ queryKey: ['network'] });
      qc.invalidateQueries({ queryKey: ['findings'] });
      qc.invalidateQueries({ queryKey: ['runs'] });
    }
  }, [live, stream.done, qc]);

  const events = live ? stream.events : (detail.data?.events ?? []);
  const views = steps.data ? stepViews(events, steps.data) : [];
  const status: Run['status'] | null = live ? (stream.done ? (detail.data?.status ?? null) : 'RUNNING') : (detail.data?.status ?? null);
  const progress = status === 'COMPLETED' ? 1 : overallProgress(events) ?? 0;
  const orbitState = status === 'RUNNING' ? 'running' : status === 'COMPLETED' ? 'done' : status === 'FAILED' || status === 'BLOCKED' ? 'failed' : 'idle';
  const banner = runBanner(status, detail.data?.error);
  const run = detail.data;

  // matrix / network for the dataset
  const matrix = useQuery({ queryKey: ['matrix', dsId], queryFn: () => api.matrix(dsId as string), enabled: !!dsId && !geneLevel, retry: false });
  const otherId = dsId ? INDIA_PAIR[dsId] : undefined;
  const otherMatrix = useQuery({ queryKey: ['matrix', otherId], queryFn: () => api.matrix(otherId as string), enabled: !!otherId, retry: false });
  const network = useQuery({ queryKey: ['network', dsId], queryFn: () => api.network(dsId as string), enabled: !!dsId && !geneLevel, retry: false });
  const strongest = useMemo(() => {
    const sel = (matrix.data?.cells ?? []).filter((c) => c.category === 'selected' && c.finding_id);
    return sel.sort((a, b) => (b.effect_size ?? 0) - (a.effect_size ?? 0))[0]?.finding_id ?? null;
  }, [matrix.data]);
  const findingId = pick && matrix.data?.cells.some((c) => c.finding_id === pick) ? pick : strongest;
  const finding = useQuery({ queryKey: ['finding', findingId], queryFn: () => api.finding(findingId as string), enabled: !!findingId });
  const surface = useQuery({ queryKey: ['surface', findingId], queryFn: () => api.surface(findingId as string), enabled: !!findingId });

  const choose = (a: string, b: string, id: string | null) => {
    if (!id) return;
    setPick(id);
    selectPair([a, b]);
    window.setTimeout(() => document.getElementById('surface')?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' }), 30);
  };
  const onCell = (c: MatrixCell) => choose(c.a, c.b, c.finding_id);
  const noRun = (q: { isError: boolean; error: unknown }) => q.isError && q.error instanceof ApiError && q.error.status === 404;
  const runPanelRef = () => document.getElementById('engine')?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
  const nm = (k: string) => stressors.data?.[k]?.label ?? k;

  const spaceLink = <Link to="/space-biology" className="num text-xs border border-signal text-signal px-4 py-2 hover:bg-signal/10">OPEN SPACE BIOLOGY</Link>;
  const emptyMatrix = geneLevel ? (
    <EmptyState title="This dataset has genes, not stressor pairs" action={spaceLink}>
      <b>{dataset?.name}</b> is a gene-level 2x2 experiment (radiation x microgravity), so there is no pair-by-pair stressor map to draw here. Its interaction results, one test per gene, are on the Space Biology page.
    </EmptyState>
  ) : (
    <EmptyState title="No completed run for this dataset yet" action={<button type="button" onClick={runPanelRef} className="num text-xs border border-signal text-signal px-4 py-2 hover:bg-signal/10">GO TO THE RUN PANEL</button>}>
      The interaction matrix is drawn from a finished run. Run the engine on <b>{dataset?.name ?? 'a dataset'}</b> above and this panel fills in with every stressor pair and what the statistics concluded.
    </EmptyState>
  );
  return (
    <div className="pb-16">
      <PageHeader index="01" kicker="DISCOVER" title="Discovery Lab"
        standfirst="Give SYNERA a dataset and watch it test every pair of environmental stressors for effects that are not just additive, then watch the statistics try to knock each candidate down." />
      <FlowStrip />

      {/* RUN THE ENGINE */}
      <div id="engine" className="px-6 md:px-10 scroll-mt-16">
        <Panel title="Run the engine" index="A" provenance={dataset?.provenance} variant="bracketed">
          <Async q={ds} h={220}>
            {() => (
              <div className="grid xl:grid-cols-[minmax(0,400px)_minmax(0,1fr)] gap-8">
                <div>
                  <div className="label mb-2" id="ds-label">Dataset</div>
                  <div role="radiogroup" aria-labelledby="ds-label" className="grid gap-2">
                    {runnable.map((d) => (
                      <button key={d.id} type="button" role="radio" aria-checked={d.id === dsId} onClick={() => { setChosen(d.id); setPick(null); start.reset(); }}
                        className={`text-left p-3 border bg-transparent cursor-pointer ${d.id === dsId ? 'border-signal bg-signal/5' : 'border-line hover:border-line-strong'}`}>
                        <span className="flex items-center gap-3 mb-1"><span className="text-[14px] text-text font-medium">{d.name}</span><span className="flex-1" /><ProvenanceTag provenance={d.provenance} /></span>
                        <span className="block text-[12.5px] text-muted leading-snug">{d.description}</span>
                        <span className="block num text-[11px] text-faint mt-1">{int(d.samples_count)} samples &middot; {int(d.features_count)} features</span>
                      </button>
                    ))}
                    {runnable.length === 0 && <EmptyState title="No runnable dataset">The API lists no dataset that can be analysed.</EmptyState>}
                  </div>
                  <div className="mt-4 grid gap-2 text-[14px]">
                    <label className="flex items-start gap-2.5 cursor-pointer"><input type="checkbox" checked={quick} onChange={(e) => setQuick(e.target.checked)} className="mt-1 accent-[var(--signal)]" />
                      <span>Quick run <span className="text-muted text-[12.5px]">fewer bootstrap resamples, faster, slightly coarser intervals</span></span></label>
                    <label className="flex items-start gap-2.5 cursor-pointer"><input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="mt-1 accent-[var(--signal)]" />
                      <span>Force re-run <span className="text-muted text-[12.5px]">ignore an identical earlier run and compute again</span></span></label>
                  </div>
                  <button type="button" disabled={!dsId || start.isPending || status === 'RUNNING'} onClick={() => start.mutate()}
                    className="mt-5 w-full num tracking-[0.18em] text-sm py-3 border border-signal text-signal bg-signal/10 hover:bg-signal/20 disabled:opacity-40 disabled:cursor-not-allowed">
                    {start.isPending ? 'STARTING' : status === 'RUNNING' ? 'RUN IN PROGRESS' : 'RUN THE ENGINE'}
                  </button>
                  {start.isError && <div className="mt-3"><ErrorState error={start.error} /></div>}
                  {activeHere?.reused && <p className="text-[13px] text-solar mt-3 mb-0" role="status">Showing the recorded run (an identical configuration already exists). Tick force re-run to compute it again.</p>}
                  {!activeHere && latest && <p className="text-[12.5px] text-faint mt-3 mb-0">Showing the most recent recorded run for this dataset ({latest.id.slice(0, 16)}).</p>}
                </div>

                <div className="min-w-0">
                  {banner && (
                    <div role="alert" className="hatch-alert border border-alert/60 px-4 py-3 mb-4">
                      <div className="num text-alert text-xs tracking-[0.16em]">{banner.title}</div>
                      <div className="text-sm break-words">{banner.text}</div>
                    </div>
                  )}
                  {live && stream.error && !stream.done && <div className="mb-3"><ErrorState error={new Error('The live stream was interrupted. The run continues on the server; reopen this page to see its record.')} /></div>}
                  {!shownId ? (
                    <div className="grid sm:grid-cols-[150px_1fr] gap-6 items-start">
                      <DiscoveryOrbit progress={0} state="idle" reduced={reduced} />
                      <div>
                        <div className="label mb-2">Nine steps, each measured</div>
                        {steps.data ? <Timeline views={stepViews([], steps.data)} /> : <Skeleton h={160} />}
                      </div>
                    </div>
                  ) : (
                    <div className="grid sm:grid-cols-[150px_1fr] gap-6 items-start">
                      <div className="flex sm:flex-col items-center gap-4 sm:sticky sm:top-20">
                        <DiscoveryOrbit progress={progress} state={orbitState} reduced={reduced} />
                        {run && <div className="num text-[11px] text-muted text-center leading-relaxed">
                          <div>runtime <span className="text-text">{secs(run.runtime_s)}</span></div>
                          <div>config <span className="text-text">{run.config_hash.slice(0, 8)}</span></div>
                          {run.ledger_block !== null && <div>ledger block <Link to={`/trust?block=${run.ledger_block}`} className="text-signal">{run.ledger_block}</Link></div>}
                        </div>}
                      </div>
                      <div className="min-w-0">
                        <div className="label mb-2">{live && !stream.done ? 'Live from the engine' : 'Recorded run'}</div>
                        {steps.data ? <Timeline views={views} /> : <Skeleton h={160} />}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </Async>
        </Panel>

        {run && status !== 'RUNNING' && (
          <Panel title="What survived" index="B" variant="inset" className="mt-6">
            {status === 'COMPLETED' ? <Funnel run={run} /> : <p className="text-sm text-muted m-0">No findings were recorded for this run.</p>}
          </Panel>
        )}
      </div>

      {/* MATRIX + NETWORK */}
      <div className="px-6 md:px-10 mt-12">
        <Panel variant="ruled" title="Interaction map" index="C" provenance={dataset?.provenance}
>
          <div role="tablist" aria-label="Map view" className="flex gap-1 mb-4">
              {(['matrix', 'network'] as const).map((k) => (
                <button key={k} type="button" role="tab" aria-selected={tab === k} id={`tab-${k}`} aria-controls={`panel-${k}`} onClick={() => setTab(k)}
                  className={`num text-[11px] tracking-[0.12em] px-3 py-1 border ${tab === k ? 'border-signal text-signal bg-signal/10' : 'border-line text-muted hover:text-text'}`}>{k.toUpperCase()}</button>
              ))}
            </div>
          <Explainer className="mb-5">
            Each cell is one pair of stressors. A solid diamond is an interaction that survived every test; a dashed outline looked significant but was explained away by a stronger pair;
            a faint dot shows no evidence. The constellation view draws the same survivors as arcs between stressors.
          </Explainer>
          {dsId === null ? null : geneLevel ? emptyMatrix : matrix.isLoading || network.isLoading ? <Skeleton h={320} /> : noRun(matrix) ? emptyMatrix : matrix.isError ? <ErrorState error={matrix.error} retry={() => matrix.refetch()} /> : matrix.data && (
            <>
              <div role="tabpanel" id="panel-matrix" aria-labelledby="tab-matrix" hidden={tab !== 'matrix'}>
                {tab === 'matrix' && <DiscoveryMatrix matrix={matrix.data} labels={stressors.data} selectedId={findingId} onSelect={onCell} />}
              </div>
              <div role="tabpanel" id="panel-network" aria-labelledby="tab-network" hidden={tab !== 'network'}>
                {tab === 'network' && (network.data
                  ? <DiscoveryConstellation network={network.data} labels={stressors.data} selectedId={findingId} onSelect={(id, a, b) => choose(a, b, id)} />
                  : <ErrorState error={network.error} retry={() => network.refetch()} />)}
              </div>
              <dl className="grid md:grid-cols-3 gap-4 mt-6 m-0 text-[13px]">
                {Object.entries(matrix.data.explanation).map(([k, v]) => (
                  <div key={k} className="border-t border-line pt-2"><dt className="label mb-1">{k.replace('_', ' ')}</dt><dd className="m-0 text-muted leading-snug">{v}</dd></div>
                ))}
              </dl>
            </>
          )}
        </Panel>
      </div>

      {/* RESPONSE SURFACE */}
      <div id="surface" className="px-6 md:px-10 mt-12 scroll-mt-16">
        <Panel variant="bracketed" title="Response surface" index="D" provenance={surface.data?.provenance}>
          {!findingId ? (
            noRun(matrix) || !dsId || geneLevel ? <EmptyState title="Nothing to draw yet">{geneLevel ? 'A response surface is drawn for a pair of stressors; this dataset is gene-level. Choose the engine benchmark to see one.' : 'A response surface is drawn for a selected interaction. Run the engine first.'}</EmptyState>
              : matrix.isLoading ? <Skeleton h={300} />
              : <EmptyState title="No interaction survived selection" tone="solar">The engine found no selected interaction for this run, so there is no surface to draw. Zero is a legitimate result: it means every apparent pair was explained away or too small to matter.</EmptyState>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4">
                {finding.data && (
                  <>
                    <span className="display text-xl">{nm(finding.data.stressors[0])} <span className="text-faint">x</span> {nm(finding.data.stressors[1])}</span>
                    <StatusChip status={finding.data.status} />
                    <span className="inline-flex items-center gap-1.5 num text-[10px] tracking-[0.14em]" style={{ color: TYPE_COLOR[finding.data.type] }}><TypeGlyph type={finding.data.type} size={22} />{finding.data.type}</span>
                    <span className="num text-[12px] text-muted">effect <span className="text-text">{fix(finding.data.effect.effect_size, 2)} SD</span> &middot; q <span className="text-text">{sci(finding.data.stats.q)}</span></span>
                    <Link to={`/findings/${finding.data.id}`} className="num text-[11px] tracking-[0.14em] text-signal ml-auto border border-signal/60 px-3 py-1 hover:bg-signal/10">OPEN EVIDENCE DOSSIER</Link>
                  </>
                )}
              </div>
              {surface.data?.provenance === 'SIMULATED' && <div className="mb-4"><Caveat kind="SIMULATED" /></div>}
              <Explainer className="mb-5" tone="biosphere">
                The map shows the outcome for every combination of two stressors. <b>Dashed lines</b> are what you would expect if the stressors simply added up. <b>Solid lines</b> are what the data actually show.
                The shaded gap between them is the interaction, measured in outcome standard deviations. Drag on the map, or use the slider, to slice through it and see the gap as a line.
              </Explainer>
              {surface.isLoading ? <Skeleton h={420} /> : surface.isError ? <ErrorState error={surface.error} retry={() => surface.refetch()} />
                : surface.data && <ResponseSurface key={findingId} surface={surface.data} labels={stressors.data} />}
            </>
          )}
        </Panel>
      </div>

      {/* DOES IT REPEAT IN OTHER STATES (India grid panels) */}
      {dsId && INDIA_PAIR[dsId] && matrix.data && (
        <div className="px-6 md:px-10 mt-12">
          <Panel variant="ruled" title="Does it repeat in other states?" index="G" provenance={dataset?.provenance}>
            {otherMatrix.isLoading ? <Skeleton h={120} /> : otherMatrix.data ? (
              <CrossCheck here={matrix.data} other={otherMatrix.data} hereName={dataset?.name ?? dsId} otherName={ds.data?.find((d) => d.id === INDIA_PAIR[dsId])?.name ?? INDIA_PAIR[dsId]} labels={stressors.data} />
            ) : <p className="text-sm text-muted m-0">The other panel has no completed run yet, so there is nothing to compare with.</p>}
          </Panel>
        </div>
      )}

      {/* STANDARD SCREEN VS SYNERA */}
      {dsId && !geneLevel && matrix.data && (
        <div className="px-6 md:px-10 mt-12">
          <Panel variant="ruled" title="What a standard screen would have reported" index="F" provenance={dataset?.provenance}>
            <ScreenAuditView matrix={matrix.data} labels={stressors.data} simulated={dataset?.provenance === 'SIMULATED'}
              developmentNote={dsId.startsWith('us_') ? 'On these real death records, an earlier pass that did not remove nationwide flu and weather waves had flagged ozone x UV and heat x drought; both vanished once each state was compared only with other states in the same week.' : undefined} />
          </Panel>
        </div>
      )}

      {/* TYPES */}
      <div className="px-6 md:px-10 mt-12">
        <Panel variant="ruled" title="Three kinds of interaction" index="E">
          <p className="text-[15px] text-muted max-w-2xl mt-0 mb-5">Sketches, not data. The dashed line is what you would predict by adding the separate effects; the coloured line is what a real <Term k="interaction">interaction</Term> does instead.</p>
          <DiscoveryCurves />
        </Panel>
      </div>
    </div>
  );
}

