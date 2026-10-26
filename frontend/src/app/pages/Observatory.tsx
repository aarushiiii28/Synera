import { lazy, Suspense } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { useFindings, useHealth, useReducedMotion } from '../../lib/hooks';
import { useUI } from '../../store';
import { EarthStatic } from '../../components/EarthStatic';
import { Readout } from '../../components/Readout';
import { Term } from '../../components/Term';
import { int } from '../../lib/format';

const Earth = lazy(() => import('../../components/Earth'));

const STAGES = [
  { key: 'discover', n: '01', title: 'DISCOVER', to: '/discovery', tone: 'var(--signal)', text: 'AI screens every pair of stressors for hidden interactions.' },
  { key: 'validate', n: '02', title: 'VALIDATE', to: '/findings', tone: 'var(--teal)', text: 'Statistics decide what survives: FDR, effect size, intervals, a second method.' },
  { key: 'verify', n: '03', title: 'VERIFY', to: '/trust', tone: 'var(--biosphere)', text: 'Every step is fingerprinted and chained in a signed ledger.' },
  { key: 'act', n: '04', title: 'ACT', to: '/risk', tone: 'var(--solar)', text: 'Validated interactions become a compound-risk brief for a city.' },
];

function PipelineStrip() {
  const reduced = useReducedMotion();
  const f = useFindings({ limit: 1 });
  const h = useHealth();
  const regionCount = useQuery({ queryKey: ['regions'], queryFn: api.riskRegions, staleTime: Infinity }).data?.length;
  const c = f.data?.counts;
  const total = f.data ? Object.values(f.data.counts).reduce((a, b) => a + b, 0) : null;
  const offline = f.isError || h.isError;
  const vals: Record<string, { v: number | null | undefined; unit: string; sub?: string }> = {
    discover: { v: total, unit: 'findings in the registry', sub: 'survived conditional selection' },
    validate: { v: c ? c.VALIDATED + c.VERIFIED : null, unit: 'validated', sub: `${c?.REJECTED ?? '—'} rejected · ${c?.CANDIDATE ?? '—'} candidate` },
    verify: { v: c?.VERIFIED, unit: 'verified', sub: `${c?.BLOCKED ?? '—'} blocked · ledger ${h.data ? int(h.data.ledger.height) : '—'} blocks` },
    act: { v: regionCount, unit: 'regions with a brief', sub: 'simulated demonstration' },
  };
  return (
    <section aria-label="Pipeline" className="relative px-6 md:px-10 pb-10">
      <div className="relative">
        <svg className="absolute left-0 right-0 top-[22px] w-full h-2 hidden md:block" preserveAspectRatio="none" viewBox="0 0 100 2" aria-hidden>
          <line x1="0" y1="1" x2="100" y2="1" stroke="var(--line-strong)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          {!reduced && [0, 1, 2].map((i) => (
            <circle key={i} r="0.5" cy="1" fill="var(--signal)">
              <animate attributeName="cx" from="0" to="100" dur="9s" begin={`${i * 3}s`} repeatCount="indefinite" />
            </circle>
          ))}
        </svg>
        <ol className="relative grid md:grid-cols-4 gap-8 m-0 p-0 list-none">
          {STAGES.map((s) => (
            <li key={s.key}>
              <Link to={s.to} className="group block">
                <div className="flex items-center gap-3 mb-3">
                  <span className="grid place-items-center w-11 h-11 rounded-full border bg-void num text-sm" style={{ borderColor: s.tone, color: s.tone, boxShadow: `0 0 18px -6px ${s.tone}` }}>{s.n}</span>
                  <span className="display font-semibold tracking-[0.12em] text-sm group-hover:underline" style={{ color: s.tone }}>{s.title}</span>
                </div>
                <p className="text-sm text-muted leading-snug mb-4 min-h-[2.6rem] max-w-[17rem]">{s.text}</p>
                {offline ? (
                  <div className="num text-xs text-alert tracking-[0.14em]">SIGNAL LOST</div>
                ) : (
                  <Readout label={vals[s.key].unit} value={vals[s.key].v} hint={vals[s.key].sub} tone={s.key === 'verify' ? 'biosphere' : s.key === 'act' ? 'solar' : s.key === 'validate' ? 'teal' : 'signal'} />
                )}
              </Link>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export default function Observatory() {
  const reduced = useReducedMotion();
  const startTour = useUI((s) => s.startTour);
  return (
    <div>
      <section className="relative overflow-hidden min-h-[calc(100vh-3rem)] lg:min-h-[640px]">
        {/* Planet bleeds off the right edge */}
        <div className="absolute pointer-events-none lg:pointer-events-auto right-[-40%] top-[4%] w-[110vmin] max-w-[1200px] aspect-square opacity-80 lg:opacity-100 lg:right-[-14%] lg:top-[0%] lg:w-[104vmin]">
          <Suspense fallback={<EarthStatic className="w-full" />}>
            <Earth reduced={reduced} className="absolute inset-0" />
          </Suspense>
        </div>

        <div className="relative z-10 px-6 md:px-10 pt-14 md:pt-20 pb-16 lg:max-w-[44%]">
          <div className="label !text-biosphere mb-5 rise">Trusted AI for multi-stressor environmental intelligence</div>
          <h1 className="display font-semibold uppercase m-0 rise text-[clamp(2.1rem,3.7vw,3.9rem)] leading-[1.04]" style={{ animationDelay: '80ms' }}>
            The environment doesn’t change <span className="serif normal-case font-normal text-sun" style={{ fontSize: '1.08em' }}>one variable</span> at a time
          </h1>
          <p className="mt-6 text-lg text-muted max-w-xl leading-relaxed rise" style={{ animationDelay: '160ms' }}>
            Heat, air pollution, drought, weather and radiation act <span className="text-signal">together</span>. The unknown isn’t just the stressor, it is what happens when stressors <Term k="interaction">interact</Term>.
            SYNERA finds those interactions with AI, tests them with statistics, and proves what it did with a tamper-evident ledger.
          </p>
          <div className="mt-8 flex flex-wrap gap-3 rise" style={{ animationDelay: '240ms' }}>
            <button onClick={startTour} className="num text-sm tracking-[0.1em] px-5 py-3 border border-signal bg-signal/10 text-signal hover:bg-signal/20">▶ TAKE THE 3-MINUTE TOUR</button>
            <Link to="/scenario" className="num text-sm tracking-[0.1em] px-5 py-3 border border-biosphere bg-biosphere/10 text-biosphere hover:bg-biosphere/20">TRY THE SCENARIO LAB →</Link>
            <Link to="/discovery" className="num text-sm tracking-[0.1em] px-5 py-3 border border-line-strong text-text hover:border-text">RUN THE ENGINE →</Link>
          </div>
          <p className="mt-10 display text-sm tracking-[0.2em] uppercase text-text/80">AI generates hypotheses. <span className="text-biosphere">Science validates them.</span></p>
        </div>
      </section>

      <PipelineStrip />

      <section className="px-6 md:px-10 pb-16 grid md:grid-cols-2 xl:grid-cols-5 gap-8 border-t border-line pt-10">
        {[
          { t: 'Track A · REAL', c: 'text-biosphere', d: 'NASA space-biology data: radiation × hindlimb unloading in mouse spleen and skin. Small samples, honest limits.', to: '/space-biology' },
          { t: 'Track C · REAL OUTCOMES', c: 'text-biosphere', d: 'CDC weekly deaths in 46 US states joined to EPA air pollution and weather. Scenario Lab: combine stressors and see the estimated consequence.', to: '/scenario' },
          { t: 'Track D · REAL, INDIA GRID', c: 'text-biosphere', d: 'Daily electricity supplied to Indian states joined to weather: a real system where the engine tests for combined effects. Grid stress, not health.', to: '/discovery' },
          { t: 'Track B · SIMULATED', c: 'text-solar', d: 'Real weather and air-quality covariates with a planted, known interaction outcome. It measures how good the engine is.', to: '/benchmark' },
          { t: 'The trust layer', c: 'text-signal', d: 'SHA-256 fingerprints, anomaly detection, a signed hash-chained ledger and a replay of every run.', to: '/trust' },
        ].map((x) => (
          <Link key={x.t} to={x.to} className="group block border-t border-line-strong pt-4">
            <div className={`num text-xs tracking-[0.16em] mb-2 ${x.c}`}>{x.t}</div>
            <p className="text-sm text-muted leading-relaxed m-0 group-hover:text-text">{x.d}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}


