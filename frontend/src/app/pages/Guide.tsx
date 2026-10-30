import { Link } from 'react-router-dom';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { StatusChip } from '../../components/StatusChip';
import { Caveat } from '../../components/Explainer';
import { useHealth } from '../../lib/hooks';
import { GLOSSARY } from '../../lib/glossary';
import { int } from '../../lib/format';
import { useUI } from '../../store';

const LAYERS = [
  { n: '01', t: 'Data', d: 'Climate, air-quality, NASA space-biology and CDC mortality data, hashed and registered the moment they enter.', to: '/space-biology', tone: 'var(--signal)' },
  { n: '02', t: 'AI discovery engine', d: 'A statistical model tests every stressor pair; LightGBM-SHAP and a neural detector give independent second opinions.', to: '/discovery', tone: 'var(--signal)' },
  { n: '03', t: 'Scientific validation', d: 'False-discovery control, effect size, block-bootstrap intervals, conditional selection and replication.', to: '/findings', tone: 'var(--teal)' },
  { n: '04', t: 'Cybersecurity', d: 'Tamper, poisoning and drift detection; model and pipeline integrity; only integrity-critical failures block a result.', to: '/trust', tone: 'var(--alert)' },
  { n: '05', t: 'Provenance', d: 'SHA-256 fingerprints and a signed, hash-chained ledger with Merkle proofs. Tamper-evident, not proof of the science.', to: '/trust', tone: 'var(--biosphere)' },
  { n: '06', t: 'Web intelligence platform', d: 'This interface: findings, evidence dossiers, graphs, validation status, confidence and experiment history.', to: '/findings', tone: 'var(--signal)' },
  { n: '07', t: 'Action', d: 'A compound-risk brief and a what-if Scenario Lab, each with uncertainty, sources and a reproducibility receipt.', to: '/risk', tone: 'var(--solar)' },
];

export default function Guide() {
  const h = useHealth();
  const startTour = useUI((s) => s.startTour);
  return (
    <div>
      <PageHeader kicker="Start here" title="How SYNERA works"
        standfirst="Seven layers turn raw data into a decision-ready, verifiable result. This page is the map; every layer links to where you can see it working."
        right={<button onClick={startTour} className="hidden md:block num text-xs tracking-[0.1em] px-4 py-2.5 border border-signal text-signal hover:bg-signal/10 whitespace-nowrap">▶ 3-MINUTE TOUR</button>} />
      <div className="px-6 md:px-10 pb-16 grid gap-12 max-w-5xl">
        <section aria-labelledby="layers">
          <h2 id="layers" className="display text-lg tracking-[0.12em] uppercase mb-5">The seven layers</h2>
          <ol className="m-0 p-0 list-none grid gap-px">
            {LAYERS.map((l) => (
              <li key={l.n}>
                <Link to={l.to} className="group grid grid-cols-[3rem_1fr_auto] items-baseline gap-4 py-3.5 border-t border-line hover:bg-white/[0.02]">
                  <span className="num text-2xl" style={{ color: l.tone }}>{l.n}</span>
                  <span>
                    <span className="display font-semibold block">{l.t}</span>
                    <span className="text-sm text-muted leading-snug">{l.d}</span>
                  </span>
                  <span className="num text-xs text-faint group-hover:text-text">OPEN →</span>
                </Link>
              </li>
            ))}
          </ol>
          <p className="num text-xs text-faint mt-3">Ledger right now: {h.data ? `${int(h.data.ledger.height)} signed blocks, chain ${h.data.ledger.chain_valid ? 'valid' : 'BROKEN'}` : 'checking…'}</p>
        </section>

        <section aria-labelledby="life">
          <h2 id="life" className="display text-lg tracking-[0.12em] uppercase mb-5">The life of a finding</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <Panel variant="inset" title="Candidate"><StatusChip status="CANDIDATE" large /><p className="text-sm text-muted mt-3 mb-0">Survived false-discovery control <em>and</em> conditional selection (it is not just a look-alike of another pair).</p></Panel>
            <Panel variant="inset" title="Validated"><StatusChip status="VALIDATED" large /><p className="text-sm text-muted mt-3 mb-0">Effect above the pre-specified minimum, a confidence interval that clears it, and at least one independent method agrees.</p></Panel>
            <Panel variant="inset" title="Verified"><StatusChip status="VERIFIED" large /><p className="text-sm text-muted mt-3 mb-0">Validated, replicated in independent data or kept again on later data that was not used to find it, built from REAL data, dataset hash and ledger chain intact, and the run replays to the same result.</p></Panel>
          </div>
          <div className="grid gap-4 md:grid-cols-2 mt-4">
            <Panel variant="alert" title="Blocked"><StatusChip status="BLOCKED" large /><p className="text-sm text-muted mt-3 mb-0">An integrity check failed: data hash, ledger chain, replay or a physical-range violation. “Result blocked from verified status.”</p></Panel>
            <Panel variant="inset" title="Rejected"><StatusChip status="REJECTED" large /><p className="text-sm text-muted mt-3 mb-0">Statistically detectable but smaller than the pre-specified minimal effect, so not worth acting on.</p></Panel>
          </div>
          <div className="mt-4"><Caveat kind="VERIFIED_MEANING" /></div>
        </section>

        <section aria-labelledby="tracks">
          <h2 id="tracks" className="display text-lg tracking-[0.12em] uppercase mb-5">Where the data comes from</h2>
          <div className="grid gap-6 md:grid-cols-2">
            <div className="border-t border-biosphere pt-3"><div className="num text-xs text-biosphere tracking-[0.14em] mb-1">TRACK A · REAL</div>
              <p className="text-sm text-muted m-0">NASA Open Science Data Repository studies OSD-211 (spleen) and OSD-237 (skin): mice exposed to chronic low-dose radiation, hindlimb unloading, both or neither. Same animals, two tissues.</p></div>
            <div className="border-t border-solar pt-3"><div className="num text-xs text-solar tracking-[0.14em] mb-1">TRACK B · SIMULATED</div>
              <p className="text-sm text-muted m-0">Real weather and air quality (Open-Meteo, 8 cities, Aug 2022 – Dec 2023) with an outcome we generated, containing known interactions. It tells us how good the engine is. It can never reach VERIFIED.</p></div>
            <div className="border-t border-biosphere pt-3"><div className="num text-xs text-biosphere tracking-[0.14em] mb-1">TRACK C · REAL OUTCOMES</div>
              <p className="text-sm text-muted m-0">CDC weekly deaths in US states joined to EPA air-pollution monitors and ERA5 weather, 2014–2019. The engine finds no interaction here; the separate effects are real and power the Scenario Lab.</p></div>
            <div className="border-t border-biosphere pt-3"><div className="num text-xs text-biosphere tracking-[0.14em] mb-1">TRACK D · REAL, NOT HEALTH</div>
              <p className="text-sm text-muted m-0">Daily electricity supplied to 16 Indian states (Grid-India), 2019 – 2024, joined to state-level ERA5 weather, in two panels of eight states each. The outcome is stress on the power grid, so it tests whether the engine finds real combined weather effects on a real system.</p></div>
          </div>
        </section>

        <section aria-labelledby="gloss">
          <h2 id="gloss" className="display text-lg tracking-[0.12em] uppercase mb-5">Glossary</h2>
          <dl className="grid gap-x-10 gap-y-4 md:grid-cols-2 m-0">
            {Object.entries(GLOSSARY).map(([k, g]) => (
              <div key={k}><dt className="num text-xs text-signal tracking-[0.1em] mb-0.5">{g.title}</dt><dd className="m-0 text-sm text-muted leading-snug">{g.text}</dd></div>
            ))}
          </dl>
        </section>

        <section aria-labelledby="src" className="text-xs text-faint leading-relaxed border-t border-line pt-5">
          <h2 id="src" className="label mb-2">Sources and attribution</h2>
          NASA Open Science Data Repository / GeneLab (OSD-211, OSD-237) · Open-Meteo weather and air-quality archives · Natural Earth (public domain) ·
          Earth imagery: NASA Visible Earth (public domain) via the three.js example textures · gene symbols: MyGene.info · Team PeakyGliders, Guru Nanak Dev University.
        </section>
      </div>
    </div>
  );
}
