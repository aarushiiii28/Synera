import { PageHeader } from '../../components/PageHeader';
import { StatusChip } from '../../components/StatusChip';
import { ProvenanceTag, EvidenceTag } from '../../components/Provenance';
import { HashRing } from '../../components/HashRing';
import { Readout } from '../../components/Readout';
import { Panel } from '../../components/Panel';
import { Caveat, Explainer } from '../../components/Explainer';
import { Term } from '../../components/Term';
import { Skeleton, EmptyState } from '../../components/States';
import type { Status } from '../../lib/api';

const SPECIMEN_HASH = 'a7f39c0d41be5e82fa09cd13b6e7742a91d05fbc28e3a4d6710b9ce85d2f43a1';
const STATUSES: Status[] = ['CANDIDATE', 'VALIDATED', 'VERIFIED', 'BLOCKED', 'REJECTED'];

/** Dev-only specimen sheet. Every number here is labelled SPECIMEN, NOT DATA. */
export default function DesignSystem() {
  return (
    <div>
      <PageHeader index="DS" title="Design system" standfirst="Every component in every state. All values on this page are specimens, not data." />
      <div className="px-6 md:px-10 pb-16 grid gap-10 max-w-5xl">
        <Panel variant="ruled" title="Readouts · SPECIMEN, NOT DATA">
          <div className="flex flex-wrap gap-10">
            <Readout label="Count" value={1240} tone="signal" />
            <Readout label="Ratio" value={0.523} decimals={3} />
            <Readout label="Verified" value={0} tone="biosphere" hint="Zero is shown as zero." />
          </div>
        </Panel>
        <div className="grid md:grid-cols-2 gap-10">
          <Panel title="Status chips" variant="bracketed">
            <ul className="m-0 p-0 list-none grid gap-3">{STATUSES.map((s) => <li key={s}><StatusChip status={s} large /></li>)}</ul>
          </Panel>
          <Panel title="Provenance and evidence" variant="inset">
            <div className="grid gap-3"><ProvenanceTag provenance="REAL" /><ProvenanceTag provenance="SIMULATED" />
              <EvidenceTag level="CROSS_TISSUE_SAME_COHORT" /><EvidenceTag level="INDEPENDENT_REPLICATION" /><EvidenceTag level="INTERNAL_REPLICATION" /><EvidenceTag level="HYPOTHESIS_ONLY" /></div>
          </Panel>
        </div>
        <Panel title="Hash fingerprint · SPECIMEN HASH" variant="bare"><HashRing hash={SPECIMEN_HASH} size={64} label="sha256" /></Panel>
        <Explainer>A <Term k="fdr">false discovery rate</Term> of 5% means about one in twenty discoveries is expected to be a false alarm.</Explainer>
        <div className="grid gap-2"><Caveat kind="SIMULATED" /><Caveat kind="CROSS_TISSUE_SAME_COHORT" /><Caveat kind="VERIFIED_MEANING" /><Caveat kind="POWER" /></div>
        <Skeleton h={80} />
        <EmptyState title="Nothing here yet">Designed empty state with a one-line explanation.</EmptyState>
      </div>
    </div>
  );
}
