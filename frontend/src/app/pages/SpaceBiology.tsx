import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type SpaceOverview } from '../../lib/api';
import { useDatasets } from '../../lib/hooks';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { Readout } from '../../components/Readout';
import { Explainer, Caveat } from '../../components/Explainer';
import { Term } from '../../components/Term';
import { Async, EmptyState } from '../../components/States';
import { EvidenceTag, ProvenanceTag } from '../../components/Provenance';
import { fix, int, pct, sci, titleCase } from '../../lib/format';
import { SpaceDesign2x2, SpaceHelix } from '../../components/charts/SpaceDesign2x2';
import { SpacePower } from '../../components/charts/SpacePower';
import { SpaceVolcano } from '../../components/charts/SpaceVolcano';
import { SpaceNullHistogram } from '../../components/charts/SpaceNullHistogram';

function Section({ n, title, lead, children }: { n: string; title: ReactNode; lead?: ReactNode; children: ReactNode }) {
  return (
    <section className="px-6 md:px-10 py-9" aria-label={typeof title === 'string' ? title : undefined}>
      <div className="flex items-baseline gap-3 mb-1"><span className="num text-signal text-xs">{n}</span><h2 className="display font-semibold uppercase tracking-tight text-xl md:text-2xl m-0">{title}</h2></div>
      {lead && <p className="text-muted max-w-3xl mt-1 mb-5 leading-relaxed">{lead}</p>}
      {children}
    </section>
  );
}

function Design({ o }: { o: SpaceOverview }) {
  const ds = useDatasets();
  const [i, setI] = useState(0);
  const s = o.studies[i];
  const tissue = (id: string) => ds.data?.find((d) => d.id === id.toLowerCase())?.name.split(': ')[1] ?? null;
  if (!s) return <EmptyState title="No studies reported">The API returned no study design.</EmptyState>;
  return (
    <div>
      <div role="tablist" aria-label="Study" className="flex flex-wrap gap-2 mb-5">
        {o.studies.map((st, k) => (
          <button key={st.id} role="tab" type="button" aria-selected={i === k} onClick={() => setI(k)} className={`border px-3 py-2 text-left cursor-pointer ${i === k ? 'border-signal bg-signal/10' : 'border-line hover:border-line-strong'}`}>
            <span className="num text-sm block">{st.id}</span>
            <span className="num text-[10px] tracking-[0.1em] text-muted">{tissue(st.id) ?? st.tissue} · {st.role}</span>
          </button>
        ))}
      </div>
      <div className="grid lg:grid-cols-[minmax(0,540px)_1fr] gap-10 items-start">
        <SpaceDesign2x2 design={s.design_2x2} />
        <div className="grid gap-4 max-w-md">
          <dl className="m-0 grid grid-cols-[120px_1fr] gap-y-2 text-sm">
            <dt className="label">Organism</dt><dd className="m-0 num">{s.organism}</dd>
            <dt className="label">Samples</dt><dd className="m-0 num">{int(s.samples)}</dd>
            <dt className="label">Genes tested</dt><dd className="m-0 num">{int(s.genes_tested)}</dd>
            <dt className="label">Radiation</dt><dd className="m-0">{o.factors.radiation}</dd>
            <dt className="label">Unloading</dt><dd className="m-0">{o.factors.microgravity}</dd>
          </dl>
          <p className="text-[13px] text-muted m-0 leading-relaxed">The same animals supplied both tissues. That makes the two studies a consistency check on each other, not two independent experiments.</p>
        </div>
      </div>
    </div>
  );
}

const PRIOR: Record<string, string> = { fixed_prior_df4: 'fixed prior, df 4', estimated_prior: 'estimated prior (used here)', no_moderation: 'no moderation' };

function Controls({ pc }: { pc: Record<string, unknown> }) {
  const studies = Object.entries(pc).filter(([, v]) => typeof v === 'object' && v !== null) as [string, Record<string, Record<string, number>>][];
  return (
    <div>
      <table className="w-full text-sm border-collapse">
        <caption className="sr-only">Genes with q below 0.05 for the overall radiation and unloading effects</caption>
        <thead><tr className="label text-left"><th className="py-1.5 font-normal">Study</th><th className="font-normal">Variance prior</th><th className="font-normal text-right">Radiation</th><th className="font-normal text-right">Unloading</th></tr></thead>
        <tbody>
          {studies.flatMap(([id, priors]) => Object.entries(priors).map(([k, v], j) => (
            <tr key={id + k} className="border-t border-line num text-xs">
              <td className="py-1.5">{j === 0 ? id : ''}</td><td className="text-muted">{PRIOR[k] ?? titleCase(k)}</td>
              <td className="text-right">{int(v.radiation)}</td><td className="text-right">{int(v.hindlimb_unloading)}</td>
            </tr>
          )))}
        </tbody>
      </table>
      {typeof pc.note === 'string' && <p className="text-xs text-faint mt-2 mb-0">{pc.note}</p>}
    </div>
  );
}

function Pc1({ pc }: { pc: Record<string, unknown> }) {
  const rows = Object.entries(pc) as [string, { pc1_variance_explained: number; pc1_vs_radiation_p: number; pc1_vs_unloading_p: number; top_pc1_loading_genes: string[]; keratin_marker_genes: number; pc1_spearman_with_mean_keratin_expression: number }][];
  return (
    <ul className="m-0 p-0 list-none grid gap-3">
      {rows.map(([id, r]) => (
        <li key={id} className="border-t border-line pt-2">
          <div className="num text-xs"><span className="text-text">{id}</span> · PC1 holds {pct(r.pc1_variance_explained, 0)} of the variation · vs radiation p {sci(r.pc1_vs_radiation_p, 2)} · vs unloading p {sci(r.pc1_vs_unloading_p, 2)}</div>
          <div className="text-[12px] text-muted mt-1">
            Top genes: <span className="num">{r.top_pc1_loading_genes.slice(0, 5).join(', ')}</span>.
            {Math.abs(r.pc1_spearman_with_mean_keratin_expression) >= 0.5
              ? <> It tracks keratin genes (Spearman rho <span className="num">{fix(r.pc1_spearman_with_mean_keratin_expression, 2)}</span> across {int(r.keratin_marker_genes)} markers): the biggest difference between samples is tissue composition, not treatment.</>
              : <> Keratin marker correlation is weak (rho <span className="num">{fix(r.pc1_spearman_with_mean_keratin_expression, 2)}</span>).</>}
          </div>
        </li>
      ))}
    </ul>
  );
}

function TopTable() {
  const q = useQuery({ queryKey: ['genes-top20'], queryFn: () => api.genes({ limit: 20 }) });
  return (
    <Async q={q} h={300}>
      {(d) => (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-sm border-collapse">
            <caption className="sr-only">Top 20 genes by interaction p-value (exploratory)</caption>
            <thead><tr className="label text-left"><th className="py-2 font-normal">#</th><th className="font-normal">Gene</th><th className="font-normal">Name</th><th className="font-normal text-right"><Term k="interaction">b_AB</Term> (log2)</th><th className="font-normal text-right"><Term k="pvalue">p</Term></th><th className="font-normal text-right"><Term k="qvalue">q</Term></th><th className="font-normal text-right">Same sign in skin?</th></tr></thead>
            <tbody>
              {d.items.map((g, i) => (
                <tr key={g.ensembl_id} className="border-t border-line">
                  <td className="py-1.5 num text-xs text-faint">{i + 1}</td>
                  <td className="num">{g.gene_symbol}</td>
                  <td className="text-muted text-[13px] max-w-[260px] truncate" title={g.name}>{g.name}</td>
                  <td className="num text-right">{fix(g.b_AB, 2)}</td>
                  <td className="num text-right">{sci(g.p, 2)}</td>
                  <td className="num text-right text-alert" title="Far above the 0.05 needed">{sci(g.q, 2)}</td>
                  <td className="num text-right text-xs">{g.same_sign_in_replication === null ? '—' : g.same_sign_in_replication ? '● yes' : '○ no'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-faint mt-2">Showing 20 of {int(d.total)} tested genes, ranked by p. Every q is far above 0.05, so none is a finding. "Same sign in skin" is a consistency check on the same animals, not replication.</p>
        </div>
      )}
    </Async>
  );
}

function Body({ o }: { o: SpaceOverview }) {
  const c = o.consistency;
  const n = o.interaction_counts;
  return (
    <>
      <div className="px-6 md:px-10 pt-2 pb-2">
        <div className="relative border border-line-strong px-5 md:px-8 py-6 bg-void/50 overflow-hidden">
          <SpaceHelix className="absolute right-4 top-3 w-48 opacity-60 hidden md:block" />
          <div className="label !text-solar mb-2">What the data say</div>
          <p className="display text-lg md:text-2xl leading-snug m-0 max-w-4xl">{o.statement}</p>
          <div className="flex flex-wrap items-center gap-4 mt-4">
            <EvidenceTag level={o.evidence_level} />
            <span className="num text-xs text-muted">{int(o.genes_tested)} genes tested · best q <span className="text-alert">{sci(o.best_q, 2)}</span> (a gene needs q below {o.fdr_alpha})</span>
          </div>
        </div>
      </div>

      <Section n="A" title="The experiment" lead={<>Mice were exposed to chronic low-dose radiation, to <Term k="hlu">hindlimb unloading</Term> (the standard ground model of microgravity), to both, or to neither. Two tissues were sequenced from the same animals. The question: do radiation and unloading <Term k="interaction">interact</Term> in a gene, doing something neither does alone?</>}>
        <Design o={o} />
      </Section>

      <Section n="B" title="Three kinds of interaction, counted" lead="After correcting for testing thousands of genes at once, the number of genes in each class is:">
        <div className="grid sm:grid-cols-3 gap-8 max-w-4xl">
          <Readout label="Synergistic" value={n.SYNERGISTIC} tone="biosphere" hint="Together they do more than the sum of the parts." />
          <Readout label="Antagonistic" value={n.ANTAGONISTIC} tone="signal" hint="Together they do less than the sum of the parts." />
          <Readout label="Non-linear" value={n.NONLINEAR} tone="solar" hint="The response bends or switches on." />
        </div>
        <p className="text-sm text-muted mt-5 max-w-2xl">Zero here is a real result of this experiment, shown as zero. It does not say radiation and unloading never interact; the next card shows why this experiment could not tell.</p>
      </Section>

      <div className="px-4 md:px-8 py-2">
        <Panel variant="bracketed" title="Statistical power" index="C" provenance={o.power.provenance === 'SIMULATED' ? 'SIMULATED' : 'REAL'} right={<span className="num text-[10px] text-faint hidden sm:inline">SPIKE-IN SIMULATION</span>}>
          <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] gap-8 px-1 md:px-3 pb-3">
            <SpacePower power={o.power} />
            <div className="grid gap-4 content-start">
              <Explainer tone="solar">With this few mice, only <strong>very large</strong> interactions can be detected: {o.power.minimum_detectable_log2_80pct_power === null ? 'none of the sizes tested reaches 80% power' : <>a change of <span className="num">{fix(o.power.minimum_detectable_log2_80pct_power, 1)}</span> on the log2 scale</>} is the smallest that reaches the usual 80% bar. <strong>Absence of a finding is not absence of an effect.</strong></Explainer>
              <Caveat kind="POWER" />
              <p className="text-xs text-muted m-0">How it was measured: artificial interactions of known size were spiked into the real data and the analysis was run again. This is a simulation ({o.power.provenance}) of the experiment's sensitivity, not a measurement of biology.{o.power.note ? ` ${o.power.note}` : ''}</p>
            </div>
          </div>
        </Panel>
      </div>

      <Section n="D" title="Exploratory ranking: below the FDR threshold, not findings"
        lead={<>Every one of the {int(o.genes_tested)} genes tested in the discovery tissue is a dot. The dashed red line is the bar for a discovery under <Term k="fdr">FDR control</Term>: {o.fdr_line_note}.</>}>
        <div className="mb-5"><Explainer>Right and left show how large the interaction is; higher means more surprising. A real finding would sit <em>above the red line</em>. The cloud stays below it: the most surprising genes are about what you expect from chance among {int(o.genes_tested)} tries. The eight most surprising are labelled.</Explainer></div>
        <SpaceVolcano overview={o} />
      </Section>

      <div className="px-4 md:px-8 py-2">
        <Panel variant="inset" title="Top 20, exploratory" index="E" provenance="REAL">
          <div className="px-1 md:px-3 pb-3"><div className="mb-4"><Caveat kind="HYPOTHESIS_ONLY">Ranked for curiosity and follow-up experiments only. None of these genes passes FDR control.</Caveat></div><TopTable /></div>
        </Panel>
      </div>

      <Section n="F" title="Do the two tissues agree?" lead="The second tissue is a consistency check on the first.">
        <div className="grid lg:grid-cols-[1fr_minmax(0,420px)] gap-10">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-8 gap-y-6">
            <Readout label="Animals shared" value={c.animals_shared} unit={`of ${int(c.animals_discovery)}`} tone="signal" hint={`${int(c.animals_replication)} animals in the second tissue.`} />
            <Readout label="Genes shared" value={c.genes_shared_after_filter} tone="text" hint="Pass the expression filter in both tissues." />
            <Readout label="Top-100 sign agreement" value={c.exploratory_top100_sign_concordance * 100} decimals={0} unit="%" tone="solar" hint={`Coin-flip is 50%. Binomial p ${sci(c.exploratory_top100_binomial_p_vs_half, 2)}.`} />
            <Readout label="Spearman rho, all shared genes" value={c.interaction_effect_spearman_rho_all_shared_genes} decimals={3} tone="text" hint="Correlation of interaction sizes between tissues. 0 = unrelated." />
            <Readout label="FDR hits, discovery" value={c.fdr_hits_discovery} tone="alert" />
            <Readout label="FDR hits, second tissue" value={c.fdr_hits_replication} tone="alert" />
          </div>
          <div className="grid gap-4 content-start">
            <Caveat kind="CROSS_TISSUE_SAME_COHORT">{c.caveat}</Caveat>
            <Explainer tone="solar" title="How to read this">{c.interpretation}</Explainer>
            <div><EvidenceTag level={o.evidence_level} /></div>
          </div>
        </div>
      </Section>

      <Section n="G" title="Quality control" lead="Is the analysis itself trustworthy? Three checks.">
        <div className="grid lg:grid-cols-3 gap-10">
          <div>
            <div className="label !text-signal mb-2">1 · Permutation null</div>
            <SpaceNullHistogram bins={o.null_calibration.pooled_p_histogram_10bins} />
            <p className="text-xs text-muted mt-2">Treatment labels were shuffled {int(o.null_calibration.n_permutations)} times, which should find nothing. Flat bars mean honest p-values. Inflation <Term k="lambda">lambda</Term> median <span className="num">{fix(o.null_calibration.lambda_median, 2)}</span> (range <span className="num">{fix(o.null_calibration.lambda_range[0], 2)} to {fix(o.null_calibration.lambda_range[1], 2)}</span>; 1 is ideal). A hit at q below 0.05 appeared in {pct(o.null_calibration.frac_permutations_with_a_hit, 0)} of shuffles (mean {fix(o.null_calibration.mean_hits_q05_per_permutation, 2)} per shuffle).</p>
          </div>
          <div>
            <div className="label !text-signal mb-2">2 · Positive controls</div>
            <Controls pc={o.positive_controls} />
            <p className="text-xs text-muted mt-3">Genes responding to radiation or unloading alone (q below 0.05), under each <Term k="moderation">variance prior</Term>. The count changes with the prior, which is why the choice is reported rather than hidden. Moderation prior df: discovery <span className="num">{fix(o.moderation.prior_df_discovery, 2)}</span>, second tissue <span className="num">{fix(o.moderation.prior_df_replication, 2)}</span>.</p>
          </div>
          <div>
            <div className="label !text-signal mb-2">3 · Filter and PC1</div>
            <p className="text-xs text-muted mt-0 mb-3">Genes kept: mean log2 expression at least <span className="num">{o.expression_filter.min_mean_log2}</span>, and at least <span className="num">{o.expression_filter.min_log2}</span> log2 in <span className="num">{o.expression_filter.min_samples}</span> samples. Expression variant <span className="num">{o.expression_variant}</span>.</p>
            <Pc1 pc={o.pc1} />
          </div>
        </div>
      </Section>
    </>
  );
}

export default function SpaceBiology() {
  const q = useQuery({ queryKey: ['space-overview'], queryFn: api.spaceOverview });
  return (
    <div className="overflow-x-clip">
      <PageHeader kicker="THE TESTBED" title={<>Space biology: <span className="serif normal-case font-normal text-sun" style={{ fontSize: '1.08em' }}>radiation × microgravity</span></>}
        standfirst={<>NASA mouse data from the Open Science Data Repository: chronic low-dose radiation combined with hindlimb unloading, a ground model of microgravity. Two tissues come from the same animals. This is the real-data testbed, so the page reports honestly what it can and cannot show.</>}
        right={<ProvenanceTag provenance="REAL" className="hidden md:inline-flex pb-2" />} />
      <Async q={q} h={420}>{(o) => <Body o={o} />}</Async>
    </div>
  );
}
