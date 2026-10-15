import { useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, type Risk } from '../../lib/api';
import { PageHeader } from '../../components/PageHeader';
import { Term } from '../../components/Term';
import { Explainer } from '../../components/Explainer';
import { ProvenanceTag } from '../../components/Provenance';
import { StatusChip } from '../../components/StatusChip';
import { HashRing } from '../../components/HashRing';
import { EmptyState, ErrorState, Skeleton } from '../../components/States';
import { TYPE_COLOR, utc } from '../../lib/format';
import { useStressors } from '../../lib/hooks';
import { RiskFlow } from '../../components/charts/RiskFlow';
import { RiskGlobe } from '../../components/charts/RiskGlobe';
import { RiskForecast, RiskGauge, RiskInterval } from '../../components/charts/RiskCharts';
import { SOURCE_TAG, bannerText, briefHeadline, percentileText, straddlesZero, tierColor } from '../../components/charts/riskLogic';

const PRINT_CSS = `
@media print {
  @page { size: A4; margin: 12mm; }
  :root { --text:#111; --muted:#333; --faint:#555; --void:#fff; --abyss:#fff; --hull:#fff; --hull-2:#ddd; --line:#bbb; --line-strong:#777;
          --signal:#0a5f93; --solar:#8a4f00; --sun:#8a4f00; --biosphere:#2a6e1a; --alert:#b00020; --teal:#006b52; }
  html, body { background: #fff !important; color: #111 !important; font-size: 12px; }
  main, .print-area { background: #fff !important; }
  .print-area * { background-color: transparent !important; box-shadow: none !important; text-shadow: none !important; }
  .print-area .print-banner { border: 2px solid #8a4f00 !important; color: #8a4f00 !important; position: static !important; }
  .print-area { padding: 0 !important; max-width: none !important; }
  .print-area section, .print-area figure, .print-area li { break-inside: avoid; }
}
`;

const REGION_ID = 'region-chips';

function Receipt({ r }: { r: Risk['receipt'] }) {
  if (!r.length) return <EmptyState title="No receipt" tone="solar">This brief cites no run, so there is nothing to reproduce.</EmptyState>;
  return (
    <ul className="m-0 p-0 list-none grid gap-6">
      {r.map((e) => (
        <li key={e.run_id} className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] border-t border-line-strong pt-4">
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 content-start">
            <div><span className="label block">Run id</span><span className="num text-sm break-all">{e.run_id}</span></div>
            <div className="flex flex-wrap gap-x-8 gap-y-2">
              <div><span className="label block">Ledger block</span>
                {e.ledger_block === null ? <span className="num text-sm text-muted">not on the ledger</span>
                  : <Link to={`/trust?block=${e.ledger_block}`} className="num text-sm text-signal hover:underline">#{e.ledger_block} →</Link>}
              </div>
              <div><span className="label block"><Term k="replication">Replay</Term> match</span>
                {e.replay_matches === null ? <span className="num text-sm text-muted">not replayed</span>
                  : e.replay_matches ? <span className="num text-sm text-biosphere">● SAME RESULT HASH</span>
                    : <span className="num text-sm text-alert">⃠ HASH DIFFERS</span>}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
            <HashRing hash={e.dataset_hash} label="Dataset hash" size={36} />
            <HashRing hash={e.config_hash} label="Config hash" size={36} />
            {e.result_hash ? <HashRing hash={e.result_hash} label="Result hash" size={36} /> : <div><span className="label block">Result hash</span><span className="num text-sm text-muted">not recorded</span></div>}
          </div>
        </li>
      ))}
    </ul>
  );
}

function Brief({ r }: { r: Risk }) {
  const [printedAt] = useState(() => Math.floor(Date.now() / 1000));
  const banner = bannerText(r);
  const src = SOURCE_TAG[r.source.mode];
  const st = useStressors();
  const nm = (k: string) => st.data?.[k]?.label ?? k;
  return (
    <div className="print-area grid grid-cols-[minmax(0,1fr)] gap-10">
      {banner && (
        <div role="alert" className="print-banner sticky top-0 z-30 border-2 border-solar px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-1 backdrop-blur-md" style={{ backgroundColor: 'rgba(255, 255, 255, 0.16)' }}>
          <span className="num text-[12px] tracking-[0.18em] text-solar font-semibold">SIMULATED DEMONSTRATION</span>
          <span className="text-[14px] text-text leading-snug flex-1 min-w-[16rem]">{banner}</span>
        </div>
      )}
      <div className="hidden print:block">
        <div className="display font-semibold uppercase text-xl">SYNERA risk brief · {r.region}</div>
        <div className="num text-xs">Printed {utc(printedAt)}</div>
      </div>

      {!r.available || !r.risk_tier ? (
        <EmptyState title={`No brief for ${r.region}`} tone="solar">{r.message ?? 'The API returned no assessment for this region.'} No tier is shown because none can be computed honestly.</EmptyState>
      ) : (
        <>
          <section aria-labelledby="tier-h" className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] items-start">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
              <div className="flex flex-wrap items-center gap-3">
                <h2 id="tier-h" className="label m-0">{r.region} · today · compound interaction risk</h2>
                <span className="num text-[10px] tracking-[0.14em] border px-2 py-0.5" style={{ color: src.tone, borderColor: src.tone }} title={src.text}>● {src.label}</span>
                <ProvenanceTag provenance={r.simulated_only ? 'SIMULATED' : 'REAL'} />
              </div>
              <div className="display font-semibold leading-none tracking-tight" style={{ color: tierColor(r.risk_tier), fontSize: 'clamp(3.4rem, 10vw, 7.5rem)' }} aria-label={`Risk tier ${r.risk_tier}`}>{r.risk_tier}</div>
              <p className="display text-[clamp(1.05rem,1.8vw,1.35rem)] leading-snug m-0 max-w-2xl">{briefHeadline(r)}</p>
              <p className="num text-[12px] text-faint m-0">
                Data source: {src.label.toLowerCase()}{r.source.fetched_at ? ` · fetched ${utc(r.source.fetched_at)}` : ''}. {r.source.note ?? src.text}
              </p>
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
              <div className="grid justify-items-center"><RiskGauge percentile={r.risk_percentile ?? 0} tier={r.risk_tier} />
                <p className="num text-[12px] text-muted text-center m-0 max-w-xs">{percentileText(r.risk_percentile)} percentile: more interaction-driven risk than {r.risk_percentile === undefined ? 'n/a' : `${Math.round(r.risk_percentile * 100)}%`} of days in this city&rsquo;s own history.</p>
              </div>
            </div>
          </section>

          <section aria-labelledby="up-h" className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2 items-start">
            <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
              <h3 id="up-h" className="display font-semibold text-[15px] m-0">Interaction uplift <span className="num text-[12px] text-faint font-normal">outcome SD</span></h3>
              <Explainer>
                Take what each stressor would do alone, add them up, then compare with what the validated <Term k="interaction">interactions</Term> predict. The difference is the <b>uplift</b>, in units of the outcome&rsquo;s <Term k="effect">standard deviation</Term>. The band is the plausible range.
              </Explainer>
              {r.interaction_uplift !== undefined && r.uncertainty_lower !== undefined && r.uncertainty_upper !== undefined ? (
                <>
                  <RiskInterval value={r.interaction_uplift} lower={r.uncertainty_lower} upper={r.uncertainty_upper} units={r.units} />
                  {straddlesZero(r.uncertainty_lower, r.uncertainty_upper) && <p className="num text-[12px] text-solar m-0">The band crosses zero: the direction of the uplift is not established.</p>}
                </>
              ) : <p className="num text-sm text-muted m-0">Uplift interval not computed.</p>}
              {r.units && <p className="num text-[11px] text-faint m-0">Units: {r.units}</p>}
            </div>
            <dl className="m-0 grid gap-5">
              <div className="border-t border-line-strong pt-3"><dt className="label !text-signal mb-1">How the tier is set</dt><dd className="m-0 text-[14px] text-muted leading-relaxed">{r.tier_basis ?? 'not provided by the API'}</dd></div>
              <div className="border-t border-line-strong pt-3"><dt className="label !text-solar mb-1">How the uncertainty is set</dt><dd className="m-0 text-[14px] text-muted leading-relaxed">{r.uncertainty_basis ?? 'not provided by the API'}</dd></div>
            </dl>
          </section>

          {r.forecast && r.forecast.length > 0 ? (
            <section aria-labelledby="fc-h" className="grid grid-cols-[minmax(0,1fr)] gap-3">
              <h3 id="fc-h" className="display font-semibold text-[15px] m-0">Seven days ahead</h3>
              <Explainer>The gap between the two lines is the part of the risk that only exists because stressors interact. Days where the data are incomplete are marked &ldquo;no data&rdquo; instead of guessed.</Explainer>
              <RiskForecast days={r.forecast} />
            </section>
          ) : <EmptyState title="No forecast" tone="solar">The API returned no seven-day forecast for this region.</EmptyState>}

          <section aria-labelledby="src-h" className="grid grid-cols-[minmax(0,1fr)] gap-3">
            <h3 id="src-h" className="display font-semibold text-[15px] m-0">Findings behind this brief</h3>
            {r.findings.length === 0 ? <p className="text-sm text-muted m-0">No findings listed.</p> : (
              <ul className="m-0 p-0 list-none grid gap-px">
                {r.findings.map((f) => (
                  <li key={f.id}>
                    <Link to={`/findings/${f.id}`} className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto_auto_auto] gap-x-6 gap-y-1 items-baseline py-2.5 border-t border-line hover:bg-white/[0.03]">
                      <span className="display font-semibold text-[15px]">{f.stressors.map(nm).join(' × ')} <span className="num text-[11px] text-faint font-normal">{f.id}</span></span>
                      <span className="num text-[11px] tracking-[0.12em]" style={{ color: TYPE_COLOR[f.type] }}>{f.type}</span>
                      <StatusChip status={f.status} />
                      <ProvenanceTag provenance={f.provenance} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="honest-h" className="border border-solar/70 px-4 py-3">
            <h3 id="honest-h" className="label !text-solar m-0 mb-1">An honest statement</h3>
            <p className="m-0 text-[14px] leading-relaxed">
              {r.simulated_only
                ? <>Every finding behind this brief comes from the <b>simulated</b> benchmark. No verified real-world interaction supports it{r.verified_real_findings ? ` (verified real findings used: ${r.verified_real_findings.length})` : ''}. It demonstrates how SYNERA turns validated interactions into a brief, and must not be used for real decisions.</>
                : <>This brief draws on {r.verified_real_findings?.length ?? 0} verified real findings. <Term k="verified">VERIFIED</Term> never means biologically proven.</>}
            </p>
          </section>

          <section aria-labelledby="rc-h" className="grid grid-cols-[minmax(0,1fr)] gap-3">
            <div className="flex items-center gap-3">
              <h3 id="rc-h" className="display font-semibold text-[15px] m-0">Reproducibility receipt</h3>
              <span className="flex-1" />
              <button type="button" onClick={() => window.print()} className="no-print num text-xs tracking-[0.1em] px-4 py-2 border border-signal text-signal hover:bg-signal/10">PRINT BRIEF</button>
            </div>
            <p className="m-0 text-[13px] text-muted max-w-2xl">Anyone can re-run the cited analysis and compare <Term k="hash">fingerprints</Term>. A matching result hash means the numbers above come from exactly this data and this configuration. It does not make the science true.</p>
            <Receipt r={r.receipt} />
          </section>
        </>
      )}
    </div>
  );
}

function Chips({ regions, selected, onSelect }: { regions: { id: string }[]; selected: string; onSelect: (id: string) => void }) {
  return (
    <div role="radiogroup" aria-label="Region" id={REGION_ID} className="flex flex-wrap gap-2">
      {regions.map((c) => (
        <button key={c.id} type="button" role="radio" aria-checked={c.id === selected} onClick={() => onSelect(c.id)}
          className={`num text-sm px-3.5 py-2 border ${c.id === selected ? 'border-solar bg-solar/15 text-solar' : 'border-line-strong text-muted hover:text-text hover:border-text'}`}>{c.id}</button>
      ))}
    </div>
  );
}

function Section({ children, className = '' }: { children: ReactNode; className?: string }) { return <div className={className}>{children}</div>; }

export default function RiskBriefPage() {
  const [sp, setSp] = useSearchParams();
  const regions = useQuery({ queryKey: ['regions'], queryFn: api.riskRegions, staleTime: Infinity });
  const wanted = sp.get('region');
  const selected = regions.data?.find((c) => c.id === wanted)?.id ?? regions.data?.[0]?.id ?? '';
  const risk = useQuery({ queryKey: ['risk', selected], queryFn: () => api.risk(selected), enabled: !!selected });
  return (
    <div>
      <style>{PRINT_CSS}</style>
      <Section className="no-print">
        <PageHeader index="04" kicker="ACT" title="Risk brief"
          standfirst="From environmental complexity to trusted action: pick a city and see what the validated interactions say about today and the next seven days, with the uncertainty, the sources and a receipt anyone can check." />
      </Section>
      <div className="px-6 md:px-10 pb-20 grid gap-14 max-w-6xl">
        <section aria-labelledby="flow-h" className="no-print grid gap-4">
          <h2 id="flow-h" className="label m-0">From environmental complexity to trusted action</h2>
          <RiskFlow />
          <p className="m-0 max-w-3xl display text-[clamp(1.05rem,1.8vw,1.4rem)] leading-snug">
            The future of environmental AI is not just prediction. It is <span className="serif text-sun" style={{ fontSize: '1.15em' }}>discovery that can be validated, verified and trusted.</span>
          </p>
        </section>

        <section aria-labelledby="reg-h" className="no-print grid gap-6 md:grid-cols-[auto_minmax(0,1fr)] items-center">
          <div className="justify-self-center">
            {regions.data && selected ? <RiskGlobe regions={regions.data} selected={selected} size={240} /> : <Skeleton h={240} label="LOCATING" />}
          </div>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 min-w-0">
            <h2 id="reg-h" className="display font-semibold text-lg tracking-[0.12em] uppercase m-0">Choose a city</h2>
            <Explainer>Each city has its own history. The brief says how unusual today&rsquo;s interaction-driven risk is for <em>that</em> city, not how it compares with other cities.</Explainer>
            {regions.isLoading && <Skeleton h={48} />}
            {regions.isError && <ErrorState error={regions.error} retry={() => regions.refetch()} />}
            {regions.data && <Chips regions={regions.data} selected={selected} onSelect={(id) => setSp({ region: id }, { replace: true })} />}
          </div>
        </section>

        {risk.isLoading && <Skeleton h={320} />}
        {risk.isError && <ErrorState error={risk.error} retry={() => risk.refetch()} />}
        {risk.data && <Brief r={risk.data} />}
        {!selected && !regions.isLoading && !regions.isError && <EmptyState title="No regions" tone="solar">The API listed no regions.</EmptyState>}
      </div>
    </div>
  );
}


