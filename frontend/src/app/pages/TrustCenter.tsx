import { useState, type ReactNode } from 'react';
import { PageHeader } from '../../components/PageHeader';
import { Panel } from '../../components/Panel';
import { Explainer } from '../../components/Explainer';
import { Term } from '../../components/Term';
import { useHealth, useReducedMotion } from '../../lib/hooks';
import { int, shortHash } from '../../lib/format';
import { TrustAttackPath } from '../../components/charts/TrustAttackPath';
import { TrustTamperSimulator } from '../../components/charts/TrustTamperSimulator';
import { TrustReliability } from '../../components/charts/TrustReliability';
import { TrustLedgerExplorer } from '../../components/charts/TrustLedgerExplorer';
import { TrustMerkleProof } from '../../components/charts/TrustMerkleProof';
import { TrustIntegrityCheck } from '../../components/charts/TrustIntegrityCheck';

const LAYER = [
  { n: '1', t: 'Cybersecurity', c: 'var(--signal)', d: 'Detect anomalies, suspicious changes, poisoned records, and model and pipeline integrity issues.' },
  { n: '2', t: 'Cryptographic provenance', c: 'var(--teal)', d: 'A fingerprint (SHA-256) for the dataset, the model, the code, the experiment and the result.' },
  { n: '3', t: 'Blockchain-style evidence ledger', c: 'var(--biosphere)', d: 'Dataset and model versions, experiment metadata, timestamps and hashes, and validation status, chained and signed.' },
] as const;

function Section({ id, n, title, lead, children }: { id: string; n: string; title: ReactNode; lead?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="px-6 md:px-10 py-10 scroll-mt-16">
      <div className="flex items-baseline gap-3 mb-1">
        <span className="num text-signal text-xs">{n}</span>
        <h2 id={`${id}-h`} className="display font-semibold uppercase tracking-tight text-xl md:text-2xl m-0">{title}</h2>
      </div>
      {lead && <p className="text-muted max-w-3xl mt-1 mb-6 leading-relaxed">{lead}</p>}
      {children}
    </section>
  );
}

export default function TrustCenter() {
  const reduced = useReducedMotion();
  const health = useHealth();
  const [proofHash, setProofHash] = useState('');
  const l = health.data?.ledger;
  const goProve = (h: string) => {
    setProofHash(h);
    document.getElementById('merkle')?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
  };

  return (
    <div className="overflow-x-clip">
      <PageHeader
        index="03" kicker="VERIFY"
        title={<>Discovery is not enough. <span className="serif normal-case font-normal text-sun" style={{ fontSize: '1.08em' }}>Can we trust the evidence?</span></>}
        standfirst={<>A result is only as good as the file, the model and the code behind it. SYNERA fingerprints every one of them, writes the fingerprints into a signed, hash-chained ledger, and then <em>attacks itself on a copy</em> to show that tampering is caught. Try it below.</>}
        right={l ? (
          <div className="hidden md:block text-right pb-1" role="status">
            <div className={`num text-xs tracking-[0.14em] ${l.chain_valid ? 'text-biosphere' : 'text-alert'}`}>{l.chain_valid ? '● LEDGER VALID' : '⊘ LEDGER BROKEN'}</div>
            <div className="num text-[11px] text-muted">{int(l.height)} blocks · head {shortHash(l.head, 6, 4)}</div>
          </div>
        ) : null}
      />

      <Section id="path" n="A" title="A vulnerable path to scientific results"
        lead={<>A result travels through six stages. At each one somebody, or something, can quietly change the outcome. The red points are those attacks.</>}>
        <div className="mb-6"><Explainer>Think of a result as a parcel passed along six hands. If any hand swaps what is inside, the answer at the end is wrong and nobody can tell. Each red point is one way that can happen, and the green text names the real check in SYNERA that catches it.</Explainer></div>
        <TrustAttackPath />
      </Section>

      <Section id="layer" n="B" title="The SYNERA trust layer">
        <ol className="m-0 p-0 list-none grid md:grid-cols-3 gap-8 border-t border-line-strong pt-6">
          {LAYER.map((s) => (
            <li key={s.n} className="relative">
              <div className="display text-6xl font-light leading-none" style={{ color: s.c }} aria-hidden>{s.n}</div>
              <h3 className="display text-sm tracking-[0.12em] uppercase mt-3 mb-2" style={{ color: s.c }}>{s.t}</h3>
              <p className="m-0 text-[15px] text-muted leading-relaxed max-w-xs">{s.d}</p>
            </li>
          ))}
        </ol>
        <p className="mt-8 display text-lg md:text-xl max-w-3xl leading-snug border-l-2 border-sun pl-4">
          The ledger does not prove the science. <span className="text-sun">It makes the computational provenance tamper-evident.</span>
        </p>
      </Section>

      <div className="px-4 md:px-8">
        <Panel variant="bracketed" title="Tamper simulator" index="C" right={<span className="num text-[10px] tracking-[0.14em] text-alert hidden sm:inline">RUNS ON A TEMPORARY COPY</span>}>
          <div className="px-1 md:px-3 pb-3">
            <h2 className="display font-semibold uppercase text-xl md:text-2xl m-0 mt-1">Attack the evidence, live</h2>
            <div className="my-5"><Explainer tone="alert">
              Pick a dataset and a way to damage it. SYNERA copies it, damages the copy, and recomputes the fingerprint (<Term k="hash">SHA-256</Term>). If even one character of the fingerprint changes, the result is <strong>blocked from VERIFIED status</strong>. Nothing real is ever modified.
            </Explainer></div>
            <TrustTamperSimulator />
          </div>
        </Panel>
      </div>

      <Section id="reliability" n="D" title="How reliable are the alarms?"
        lead={<>Anomaly detectors are statistical guesses: they can miss subtle edits and sometimes cry wolf. The fingerprint is not a guess. These are measured rates.</>}>
        <div className="mb-6"><Explainer>On the left, how often each detector raises a false alarm on clean data. In the grids, how often it spots each kind of attack as more of the data is damaged. Note how many attacks only the hash catches: that is why detectors only <em>advise</em> and integrity checks <em>block</em>.</Explainer></div>
        <TrustReliability />
      </Section>

      <div className="px-4 md:px-8 py-4">
        <Panel variant="bracketed" title="Ledger explorer" index="E" right={<span className="num text-[10px] text-faint hidden sm:inline">GET /ledger/blocks</span>}>
          <div className="px-1 md:px-3 pb-3">
            <h2 className="display font-semibold uppercase text-xl md:text-2xl m-0 mt-1"><Term k="ledger">Evidence ledger</Term></h2>
            <p className="text-muted max-w-3xl mt-1 mb-5">Each block stores the fingerprint of the one before it, so changing any block breaks every link after it. Click a block to read it.</p>
            <TrustLedgerExplorer onProve={goProve} />
          </div>
        </Panel>
      </div>

      <section id="merkle" className="px-6 md:px-10 py-10 scroll-mt-16" aria-labelledby="merkle-h">
        <div className="flex items-baseline gap-3 mb-4"><span className="num text-signal text-xs">F</span><h2 id="merkle-h" className="display font-semibold uppercase text-xl md:text-2xl m-0">Prove an artifact is in the ledger</h2></div>
        <TrustMerkleProof value={proofHash} onChange={setProofHash} />
      </section>

      <div className="px-4 md:px-8 pb-16">
        <Panel variant="inset" title="Integrity check" index="G">
          <div className="px-1 md:px-3 pb-3">
            <h2 className="display font-semibold uppercase text-xl md:text-2xl m-0 mt-1">Is the file still the file we registered?</h2>
            <p className="text-muted max-w-3xl mt-1 mb-5">This recomputes a real dataset's fingerprint right now and compares it with the one the ledger holds. Unlike the simulator, this checks the actual file.</p>
            <TrustIntegrityCheck />
          </div>
        </Panel>
      </div>
    </div>
  );
}

