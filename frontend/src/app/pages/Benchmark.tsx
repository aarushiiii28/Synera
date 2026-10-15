import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type Benchmark } from '../../lib/api';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { Readout } from '../../components/Readout';
import { Term } from '../../components/Term';
import { Caveat, Explainer } from '../../components/Explainer';
import { ProvenanceTag } from '../../components/Provenance';
import { EmptyState, ErrorState, Skeleton } from '../../components/States';
import { fix, int, pct, secs } from '../../lib/format';
import { BenchNullDial } from '../../components/charts/BenchNullDial';
import { BenchFunnel } from '../../components/charts/BenchFunnel';
import { BenchHist } from '../../components/charts/BenchHist';
import { BenchLines, type LineSeries } from '../../components/charts/BenchLines';
import { BenchRecall } from '../../components/charts/BenchRecall';
import { BenchFalseAlarm, BenchHeatmaps } from '../../components/charts/BenchSecurity';
import {
  SEGMENTS, VERDICT_WORD, falseAlarmClause, fdrText, fdrVerdict, funnelSentence, hasLimitations, nullHeadline, recallText, snrKeys, snrSentence, sortedKeys,
} from '../../components/charts/benchLogic';

const FDR_TARGET = 0.05;

function Section({ id, n, title, children }: { id: string; n: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <h2 id={id} className="display text-lg tracking-[0.12em] uppercase m-0 flex items-baseline gap-3">
        <span className="num text-signal text-sm">{n}</span>{title}
      </h2>
      {children}
    </section>
  );
}

function Limitations({ items }: { items: string[] }) {
  return (
    <Panel variant="alert" title="What this report does NOT show · known limits" right={<span className="num text-[10px] tracking-[0.14em] text-solar">READ FIRST</span>}>
      <ul className="m-0 pl-0 list-none grid gap-2.5">
        {items.map((l, i) => (
          <li key={i} className="grid grid-cols-[1.4rem_1fr] gap-1 text-[15px] leading-snug text-text">
            <span className="num text-solar" aria-hidden>{String(i + 1).padStart(2, '0')}</span><span>{l}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Headline({ b }: { b: Benchmark }) {
  const nc = b.null_calibration, d = b.discovery;
  return (
    <Section id="h-head" n="01" title="Headline">
      {nc ? (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[1.15fr_1fr] items-start">
          <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
            <p className="display text-[clamp(1.2rem,2.2vw,1.7rem)] leading-snug m-0 max-w-2xl">{nullHeadline(nc)}</p>
            <Explainer>
              Weather on neighbouring days is alike, so a simple test treats the same information as if it were new data over and over. <Term k="lambda">Lambda (λ)</Term> measures how over-confident a test is when there is truly nothing to find: 1.0 is honest, 3.0 means test statistics are three times too large. The <Term k="bootstrap">block bootstrap</Term> re-samples runs of days to repair this.
            </Explainer>
            <BenchNullDial nc={nc} />
            <p className="text-[13px] text-muted m-0">
              Measured over {int(nc.n_simulations)} null simulations of {int(nc.pairs_per_simulation)} stressor pairs each, with day-to-day correlation ρ = {fix(nc.rho, 2)}. Naive: {falseAlarmClause(nc.naive)}. Bootstrap: {falseAlarmClause(nc.boot)}.
            </p>
          </div>
          <FdrBoard b={b} />
        </div>
      ) : (
        <EmptyState title="Null calibration not computed" tone="solar">This section appears when the benchmark report contains the null-calibration run.</EmptyState>
      )}
      {!d && <EmptyState title="Discovery benchmark not computed" tone="solar">The discovery stage-by-stage results are missing from this report.</EmptyState>}
    </Section>
  );
}

/** Full-stack strict FDR and recall for each SNR. Over-target values are red, never green. */
function FdrBoard({ b }: { b: Benchmark }) {
  const d = b.discovery;
  if (!d) return null;
  const snrs = snrKeys(d);
  return (
    <Panel variant="inset" title="Full stack · each signal-to-noise level" provenance="SIMULATED">
      <p className="text-[13px] text-muted mt-0 mb-4 leading-snug">
        <Term k="fdr">FDR</Term> target is {pct(FDR_TARGET, 0)}. <b className="text-text">Strict</b> counts every non-planted discovery as false. SNR is how loud the planted interaction is relative to noise.
      </p>
      <ul className="m-0 p-0 list-none grid gap-5">
        {snrs.map((s) => {
          const st = d.by_snr[s]?.stages.full_stack;
          if (!st) return <li key={s} className="num text-sm text-faint">SNR {s}: not computed</li>;
          const v = fdrVerdict(st.fdr_strict, FDR_TARGET);
          return (
            <li key={s} className="grid grid-cols-[minmax(0,1fr)] gap-2 border-t border-line pt-3">
              <div className="flex items-baseline gap-2"><span className="label">SNR</span><span className="num text-xl text-signal">{s}</span></div>
              <div className="flex flex-wrap gap-x-8 gap-y-3">
                <Readout label="Strict FDR" value={st.fdr_strict} decimals={1} display={st.fdr_strict === null ? 'n/a' : fdrText(st.fdr_strict)} tone={v === 'exceeds' ? 'alert' : v === 'meets' ? 'teal' : 'text'}
                  hint={st.fdr_strict === null ? 'No discoveries at this level, so there is nothing to be wrong about.' : `${VERDICT_WORD[v]} of ${pct(FDR_TARGET, 0)}`} />
                <Readout label="Recall" value={st.recall * 100} decimals={0} display={recallText(st.recall)} tone={st.recall >= 0.5 ? 'biosphere' : 'solar'} hint="of planted interactions found" />
              </div>
              <p className="m-0 text-[13px] text-muted leading-snug">{snrSentence(s, d.by_snr[s], FDR_TARGET)}</p>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function Funnel({ d }: { d: NonNullable<Benchmark['discovery']> }) {
  const snrs = snrKeys(d);
  const [sel, setSel] = useState<string | null>(null);
  const cur = sel && snrs.includes(sel) ? sel : snrs[0];
  const data = d.by_snr[cur];
  return (
    <Section id="h-funnel" n="02" title="Where false discoveries die">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[1fr_20rem] items-start">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-4 min-w-0">
          <Explainer>
            Think of a sieve with five meshes. The pairwise screen lets almost everything through. Each later step removes a different kind of impostor. A <Term k="proxy">proxy</Term> is a pair that only looks significant because it is correlated with a truly interacting pair, so it is counted as false in the strict score and as forgivable in the proxy-aware score.
          </Explainer>
          <div role="radiogroup" aria-label="Signal-to-noise level" className="flex flex-wrap items-center gap-2">
            <span className="label mr-2">Signal-to-noise</span>
            {snrs.map((s) => (
              <button key={s} type="button" role="radio" aria-checked={s === cur} onClick={() => setSel(s)}
                className={`num text-sm px-4 py-1.5 border ${s === cur ? 'border-signal bg-signal/15 text-signal' : 'border-line-strong text-muted hover:text-text'}`}>
                SNR {s}
              </button>
            ))}
          </div>
          {data ? (
            <>
              <p className="m-0 text-[15px] text-text/90 leading-snug max-w-2xl">{funnelSentence(cur, data.stages)}</p>
              <BenchFunnel stages={data.stages} target={FDR_TARGET} />
              <p className="num text-[11px] text-faint m-0">Counts are totals over {int(d.seeds)} simulated datasets per level; {int(d.n_boot)} bootstrap resamples; effect gate {fix(d.effect_gate, 2)} outcome SD.</p>
            </>
          ) : <EmptyState title="Not computed" tone="solar">No stage results for SNR {cur}.</EmptyState>}
        </div>
        <Panel variant="ruled" title="Legend">
          <ul className="m-0 p-0 list-none grid gap-3">
            {SEGMENTS.map((g) => (
              <li key={g.key} className="grid grid-cols-[14px_1fr] gap-3 items-start">
                <span className="mt-1 w-3.5 h-3.5" style={{ background: g.color, opacity: g.key === 'easy_decoy' ? 0.55 : 0.9 }} aria-hidden />
                <span className="text-[13px] leading-snug"><b>{g.label}</b><br /><span className="text-muted">{g.note}</span></span>
              </li>
            ))}
          </ul>
          {data && (
            <p className="text-[12px] text-faint mt-4 mb-0 leading-snug num">
              Proxy-aware FDR ignores proxies. A bar made only of green is the goal. Red FDR text means above the {pct(FDR_TARGET, 0)} target.
              {' '}Block length median {fix(data.block_len_median, 0)} days; GBM hold-out R² {fix(data.gbm_holdout_r2_mean, 2)}.
            </p>
          )}
        </Panel>
      </div>
    </Section>
  );
}

function NullHists({ nc }: { nc: NonNullable<Benchmark['null_calibration']> }) {
  return (
    <Section id="h-hist" n="03" title="Null p-values: flat means honest">
      <Explainer>
        When nothing real is planted, p-values should be spread evenly from 0 to 1, like a flat roof. A tall first bar means the test is crying wolf. Each panel pools every p-value from the null simulations.
      </Explainer>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 md:grid-cols-3">
        <BenchHist title="Naive" d={nc.naive} />
        <BenchHist title="HAC" d={nc.hac} />
        <BenchHist title="Block bootstrap" d={nc.boot} />
      </div>
    </Section>
  );
}

const MOD_COLOR = { none: 'var(--alert)', fixed_df4: 'var(--signal)', estimated: 'var(--teal)' } as const;
const MOD_LABEL = { none: 'No moderation', fixed_df4: 'Fixed prior (df 4)', estimated: 'Estimated prior' } as const;

function Moderation({ m }: { m: NonNullable<Benchmark['moderation']> }) {
  const sizes = sortedKeys(m.by_effect_sd);
  const methods = ['none', 'fixed_df4', 'estimated'] as const;
  const mk = (metric: 'power' | 'fdr'): LineSeries[] => methods.map((k) => ({
    key: k, label: MOD_LABEL[k], color: MOD_COLOR[k], points: sizes.map((s) => {
      const c = m.by_effect_sd[s]?.[k];
      if (!c) return { x: parseFloat(s), y: null };
      const [lo, hi] = metric === 'power' ? c.power_ci95 : c.fdr_ci95;
      return { x: parseFloat(s), y: metric === 'power' ? c.power_mean : c.fdr_mean, lo, hi };
    }),
  }));
  const fdrMax = Math.max(FDR_TARGET * 2, ...sizes.flatMap((s) => methods.map((k) => m.by_effect_sd[s]?.[k]?.fdr_ci95[1] ?? 0)));
  return (
    <Section id="h-mod" n="04" title="Few samples: does variance moderation help?">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[1fr_1fr] items-start">
        <Explainer>
          The space-biology data have only a handful of animals per group. <Term k="moderation">Variance moderation</Term> borrows information across thousands of genes. We planted effects of known size in simulated genes and counted how often each method found them (<Term k="power">power</Term>) and how often it was wrong (FDR). Bands are 95% intervals across {int(m.n_simulations)} simulations, design {m.design}.
        </Explainer>
        <p className="m-0 text-[13px] text-muted leading-snug self-center">An unfavourable curve is shown as measured: if a method&rsquo;s FDR rises above the dashed {pct(FDR_TARGET, 0)} line, it is over its promise.</p>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-10 md:grid-cols-2">
        <figure className="m-0 min-w-0">
          <figcaption className="display font-semibold text-[14px] mb-2">Power vs planted effect size</figcaption>
          <BenchLines series={mk('power')} xLabel="planted effect (SD of the gene's noise)" yLabel="power" xFmt={(v) => `${v} SD`} ariaLabel="Power by planted effect size for three moderation methods with 95 percent bands" />
        </figure>
        <figure className="m-0 min-w-0">
          <figcaption className="display font-semibold text-[14px] mb-2">False discovery rate vs planted effect size</figcaption>
          <BenchLines series={mk('fdr')} yMax={fdrMax} target={{ y: FDR_TARGET, label: `TARGET ${pct(FDR_TARGET, 0)}` }} xLabel="planted effect (SD of the gene's noise)" yLabel="FDR" xFmt={(v) => `${v} SD`} yFmt={(v) => `${Math.round(v * 100)}%`} ariaLabel="False discovery rate by planted effect size for three moderation methods with 95 percent bands" />
        </figure>
      </div>
    </Section>
  );
}

function Recall({ d }: { d: NonNullable<Benchmark['discovery']> }) {
  const snrs = snrKeys(d);
  const [sel, setSel] = useState<string | null>(null);
  const cur = sel && snrs.includes(sel) ? sel : snrs[0];
  const data = d.by_snr[cur];
  const gates = data ? sortedKeys(data.gate_curve) : [];
  const gateSeries: LineSeries[] = data ? [
    { key: 'recall', label: 'Recall (planted found)', color: 'var(--biosphere)', points: gates.map((g) => ({ x: parseFloat(g), y: data.gate_curve[g].recall })) },
    { key: 'fdr', label: 'Strict FDR', color: 'var(--alert)', dash: '5 3', points: gates.map((g) => ({ x: parseFloat(g), y: data.gate_curve[g].fdr_strict })) },
  ] : [];
  return (
    <Section id="h-recall" n="05" title="What gets found, and what the effect gate costs">
      <div role="radiogroup" aria-label="Signal-to-noise level for these two charts" className="flex flex-wrap items-center gap-2">
        <span className="label mr-2">Signal-to-noise</span>
        {snrs.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={s === cur} onClick={() => setSel(s)}
            className={`num text-sm px-4 py-1.5 border ${s === cur ? 'border-signal bg-signal/15 text-signal' : 'border-line-strong text-muted hover:text-text'}`}>SNR {s}</button>
        ))}
      </div>
      {data ? (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-2">
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 content-start">
            <h3 className="display font-semibold text-[14px] m-0">Recall by interaction type</h3>
            <Explainer>One interaction of each type was planted. Bars show the share of datasets where it was found, and where it was also given the right <Term k="synergistic">synergistic</Term> / <Term k="antagonistic">antagonistic</Term> / <Term k="nonlinear">non-linear</Term> label.</Explainer>
            <BenchRecall rbt={data.recall_by_type} />
          </div>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 content-start">
            <h3 className="display font-semibold text-[14px] m-0">Effect-gate curve</h3>
            <Explainer>Raising the minimum effect size discards small, unimportant hits. The cost is recall. Read where the red dashed line falls without the green line collapsing.</Explainer>
            <BenchLines series={gateSeries} xLabel="minimum effect size (outcome SD)" yLabel="share" xFmt={(v) => fix(v, 2)} ariaLabel="Recall and strict false discovery rate against effect gate threshold" />
          </div>
        </div>
      ) : <EmptyState title="Not computed" tone="solar">No recall results for SNR {cur}.</EmptyState>}
    </Section>
  );
}

function Security({ s }: { s: NonNullable<Benchmark['security']> }) {
  return (
    <Section id="h-sec" n="06" title="Can the security layer catch tampering?">
      <Explainer tone="solar">
        We damaged a copy of the weather panel in {int(Object.keys(s.attacks).length)} ways at {int(s.contamination_levels.length)} damage levels, {int(s.trials_per_cell)} trials per cell, and recorded how often each detector raised a flag. Dark = caught often, blank = rarely caught. Detectors that miss are shown as measured. A cryptographic hash catches any change at all, but says nothing about whether the data are plausible.
      </Explainer>
      <BenchHeatmaps attacks={s.attacks} levels={s.contamination_levels} />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-2 pt-2">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 content-start">
          <h3 className="display font-semibold text-[14px] m-0">False alarms on clean data ({int(s.clean_seeds)} clean replicates)</h3>
          <p className="m-0 text-[13px] text-muted leading-snug">A detector that fires on untouched data costs trust. Each clean dataset is a held-out half of the real weather panel that the detector's baseline never saw. Amber means above 5%.</p>
          <BenchFalseAlarm rates={s.clean_false_alarm_rate} counts={s.clean_false_alarm_counts} />
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 content-start">
          <h3 className="display font-semibold text-[14px] m-0">Caught by the hash only</h3>
          {s.hash_only_attacks.length === 0 ? (
            <p className="m-0 text-[14px] text-muted">Every attack cell that the hash caught was also caught by at least one statistical detector at the 50% level.</p>
          ) : (
            <>
              <p className="m-0 text-[13px] text-muted leading-snug">These attacks are invisible to every statistical detector but change the file fingerprint. This is why SYNERA hashes data on entry.</p>
              <ul className="m-0 p-0 list-none grid gap-1.5 num text-[13px]">
                {s.hash_only_attacks.map((h, i) => (
                  <li key={i} className="flex justify-between gap-3 border-t border-line pt-1.5">
                    <span>{h.mode.replace(/_/g, ' ')} at {pct(h.contamination, 0)}</span>
                    <span className="text-solar">best detector {pct(h.best_statistical_detection, 0)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <ul className="m-0 mt-3 pl-4 text-[12px] text-faint leading-snug">
            {s.design_notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      </div>
    </Section>
  );
}

function MethodNotes({ b }: { b: Benchmark }) {
  return (
    <section aria-labelledby="h-notes" className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <h2 id="h-notes" className="display text-lg tracking-[0.12em] uppercase m-0 flex items-baseline gap-3"><span className="num text-signal text-sm">07</span>Method notes</h2>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 md:grid-cols-3 text-[14px] text-muted leading-relaxed">
        <div className="border-t border-line-strong pt-3"><div className="label !text-signal mb-1">How truth is planted</div>
          Real daily weather and air quality are kept as measured. The outcome is generated by SYNERA: a few known stressor pairs are given a chosen interaction (one synergistic, one antagonistic, one non-linear) plus noise. Because we wrote the answer, we can score every discovery.
        </div>
        <div className="border-t border-line-strong pt-3"><div className="label !text-solar mb-1">What a proxy is</div>
          A <Term k="proxy">proxy</Term> is a pair that is not planted but shares a correlated stressor with one that is. It can look significant for the wrong reason. The strict score counts proxies as false; the proxy-aware score does not. Both are shown.
        </div>
        <div className="border-t border-line-strong pt-3"><div className="label !text-biosphere mb-1">What it can and cannot say</div>
          The benchmark measures the engine on data where the answer is known. It says nothing about whether any real-world interaction exists{b.discovery ? `. ${int(b.discovery.seeds)} simulated datasets were generated per signal level` : ''}. Rates from small counts are noisy.
        </div>
      </div>
    </section>
  );
}

export default function BenchmarkPage() {
  const q = useQuery({ queryKey: ['benchmark'], queryFn: api.benchmark });
  const b = q.data;
  return (
    <div>
      <PageHeader kicker="ENGINE REPORT" title="Engine report card"
        standfirst="How good is SYNERA at finding real interactions without crying wolf? We hid known answers inside real weather data and scored the engine against them. Everything on this page is simulated, and the limits come first."
        right={<ProvenanceTag provenance="SIMULATED" className="hidden md:inline-flex" />} />
      <div className="px-6 md:px-10 pb-20 grid gap-14 max-w-6xl">
        <Caveat kind="SIMULATED" />
        {q.isLoading && <Skeleton h={260} />}
        {q.isError && <ErrorState error={q.error} retry={() => q.refetch()} />}
        {b && hasLimitations(b) && <Limitations items={b.limitations} />}
        {b && !b.available && (
          <EmptyState title="The benchmark has not been run, or has not finished" tone="solar"
            action={<code className="num text-sm border border-line-strong bg-void px-4 py-2 inline-block select-all">python scripts/run_benchmark.py</code>}>
            The report card is computed, never typed in. The job takes roughly half an hour; this page fills itself in once the report exists.
          </EmptyState>
        )}
        {b?.available && (
          <>
            <Headline b={b} />
            {b.discovery && <Funnel d={b.discovery} />}
            {b.null_calibration && <NullHists nc={b.null_calibration} />}
            {b.moderation && <Moderation m={b.moderation} />}
            {b.discovery && <Recall d={b.discovery} />}
            {b.security ? <Security s={b.security} /> : <EmptyState title="Security sweep not computed" tone="solar">The report contains no security results.</EmptyState>}
            <MethodNotes b={b} />
            <footer className="border-t border-line pt-5 num text-xs text-faint leading-relaxed">
              Benchmark runtime {secs(b.runtime_s)}. This report uses semi-synthetic data: it measures the engine, not nature. Provenance: SIMULATED.
            </footer>
          </>
        )}
      </div>
    </div>
  );
}


