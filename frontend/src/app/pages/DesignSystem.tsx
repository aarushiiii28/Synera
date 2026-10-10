import React from 'react';
import { Panel } from '../../components/Panel';
import { StatusChip } from '../../components/StatusChip';
import { HashRing } from '../../components/HashRing';
import { Readout } from '../../components/Readout';
import { OrbitProgress } from '../../components/OrbitProgress';
import { Caveat } from '../../components/Caveat';

export function DesignSystem() {
  const dummyHash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
  
  return (
    <div className="p-8 pb-32">
      <h1 className="font-display text-4xl text-text uppercase tracking-tight mb-8">Design System Overview</h1>
      
      <div className="grid grid-cols-2 gap-8">
        <Panel indexLabel="01 / PANELS & READOUTS" provenance="REAL">
          <div className="text-[10px] text-muted mb-4 tracking-widest">SPECIMEN, NOT DATA</div>
          <div className="flex gap-12 mt-4">
            <Readout value={12000} caption="FEATURES TESTED" />
            <Readout value={0.523} format="float" caption="MAX EFFECT" delta="+0.12" />
            <Readout value={0.99} format="percent" caption="CONFIDENCE" />
          </div>
        </Panel>

        <Panel indexLabel="02 / STATUS CHIPS">
          <div className="text-[10px] text-muted mb-4 tracking-widest">SPECIMEN, NOT DATA</div>
          <div className="flex flex-col gap-4 mt-4">
            <StatusChip status="CANDIDATE" />
            <StatusChip status="VALIDATED" />
            <StatusChip status="VERIFIED" />
            <StatusChip status="BLOCKED" />
            <StatusChip status="REJECTED" />
          </div>
        </Panel>

        <Panel indexLabel="03 / HASH RING">
          <div className="text-[10px] text-muted mb-4 tracking-widest">SPECIMEN, NOT DATA</div>
          <div className="mt-4 flex gap-8 items-center">
            <HashRing hash={dummyHash} size={64} />
            <HashRing hash="b6589fc6ab0dc82cf12099d1c2d40ab994e8410cceeb868019a86a6358db3e84" size={120} />
          </div>
        </Panel>

        <Panel indexLabel="04 / PROGRESS & CAVEAT" provenance="SIMULATED">
          <div className="text-[10px] text-muted mb-4 tracking-widest">SPECIMEN, NOT DATA</div>
          <div className="mt-4 flex flex-col gap-8">
            <div className="flex items-center gap-8">
              <OrbitProgress size={80} progress={0.45} />
              <OrbitProgress size={80} progress={1.0} />
            </div>
            <Caveat>
              VERIFIED = statistically validated with verified provenance, not biological proof. Track B findings cap at VALIDATED.
            </Caveat>
          </div>
        </Panel>
      </div>
    </div>
  );
}
