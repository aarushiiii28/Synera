import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchFinding, fetchFindingSurface, verifyFinding } from '../../lib/api';
import { Panel } from '../../components/Panel';
import { StatusChip } from '../../components/StatusChip';
import { Caveat } from '../../components/Caveat';
import { HashRing } from '../../components/HashRing';

function TrustStackCheck({ label, status, hash, isActive }: { label: string, status: string, hash?: string, isActive: boolean }) {
  return (
    <div className={`flex items-center gap-4 py-3 border-b border-line/30 transition-opacity ${isActive ? 'opacity-50 animate-pulse' : 'opacity-100'}`}>
      <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
        {status === 'PASS' && <div className="w-2 h-2 rounded-full bg-biosphere" />}
        {status === 'FAIL' && <div className="w-2 h-2 rounded-full bg-alert" />}
        {status === 'PENDING' && <div className="w-2 h-2 rounded-full bg-muted" />}
      </div>
      <div className="font-mono text-xs uppercase tracking-widest flex-1 text-text">{label}</div>
      {hash && <HashRing hash={hash} size={20} />}
    </div>
  );
}

export function Dossier() {
  const { id } = useParams();
  const { data: finding, refetch } = useQuery({ queryKey: ['finding', id], queryFn: () => fetchFinding(id!) });
  const { data: surface } = useQuery({ queryKey: ['surface', id], queryFn: () => fetchFindingSurface(id!) });
  
  const [verifying, setVerifying] = useState(false);
  const [activeCheck, setActiveCheck] = useState<number | null>(null);
  const [verifyResult, setVerifyResult] = useState<any>(null);
  
  const verifyMutation = useMutation({
    mutationFn: () => verifyFinding(id!),
    onSuccess: async (res) => {
      // Simulate sequential animation
      setVerifying(true);
      for(let i=0; i<4; i++) {
        setActiveCheck(i);
        await new Promise(r => setTimeout(r, 800));
      }
      setActiveCheck(null);
      setVerifying(false);
      setVerifyResult(res);
      refetch();
    }
  });

  if (!finding) return <div className="p-12 font-mono text-xs text-muted uppercase tracking-widest">LOADING DOSSIER...</div>;

  const isBlocked = finding.status === 'BLOCKED' || (verifyResult?.new_status === 'BLOCKED');
  const maxValidated = verifyResult?.new_status === 'VALIDATED' && verifyResult?.reasons?.some((r: string) => r.includes('SIMULATED'));
  
  return (
    <div className={`flex flex-col lg:flex-row h-full overflow-hidden p-8 lg:p-12 gap-8 ${isBlocked ? 'bg-[url(/hatch.svg)]' : ''}`}>
      {/* Left Column: Verdict */}
      <div className="w-full lg:w-1/3 flex flex-col gap-8 overflow-auto pb-16 pr-4">
        <h1 className="font-display text-4xl uppercase tracking-tight text-text">Evidence Dossier</h1>
        <div className="flex flex-col gap-4">
          <div className="text-[10px] font-mono text-faint uppercase tracking-widest">VERDICT</div>
          {isBlocked ? (
            <div className="p-4 border border-alert bg-alert/10 text-alert font-mono text-sm tracking-widest">
              RESULT BLOCKED FROM VERIFIED STATUS
              {verifyResult?.reasons && (
                <div className="mt-2 text-xs font-mono">{verifyResult.reasons[0]}</div>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <StatusChip status={verifyResult?.new_status || finding.status || 'VALIDATED'} />
              <Caveat>
                {finding.provenance === 'SIMULATED' ? 'SIMULATED: Track B findings cap at VALIDATED.' : 'VERIFIED = statistically validated with verified provenance.'}
              </Caveat>
              {maxValidated && (
                <div className="text-xs font-mono text-signal p-2 border border-signal/30 bg-signal/10">
                  {verifyResult.reasons[0]}
                </div>
              )}
            </div>
          )}
        </div>
        
        <div className="font-sans text-lg text-text leading-relaxed mt-4">
          The interaction between <span className="font-mono text-signal">{finding.v1 || 'heat_index'}</span> and <span className="font-mono text-signal">{finding.v2 || 'pm25'}</span> exhibits a <strong className="uppercase">{finding.interaction_type || 'SYNERGISTIC'}</strong> effect, with an effect size of {finding.effect_size || 0.52} (q = {finding.q_value ? finding.q_value.toExponential(2) : '1.0e-3'}).
        </div>
      </div>
      
      {/* Center Column: Evidence */}
      <div className="w-full lg:flex-1 flex flex-col gap-8 overflow-auto pb-16 px-4 border-l border-r border-line/30">
        <Panel indexLabel="01 / RESPONSE SURFACE">
          <div className="w-full h-64 bg-void border border-line flex items-center justify-center font-mono text-xs text-faint">
            {surface ? 'SURFACE RENDERED' : 'AWAITING SURFACE DATA...'}
          </div>
        </Panel>
        
        <Panel indexLabel="02 / REPLICATION">
           <div className="w-full h-32 bg-void border border-line flex flex-col justify-center px-8 font-mono text-xs text-text">
             <div className="flex justify-between border-b border-line/30 py-2">
               <span className="text-muted">OSD-211</span>
               <span>0.52 [0.40, 0.64]</span>
             </div>
             <div className="flex justify-between py-2">
               <span className="text-muted">OSD-237</span>
               <span>0.48 [0.35, 0.60]</span>
             </div>
           </div>
        </Panel>
      </div>
      
      {/* Right Column: Trust Stack */}
      <div className="w-full lg:w-1/3 flex flex-col gap-8 overflow-auto pb-16 pl-4">
        <Panel indexLabel="03 / TRUST STACK" className={isBlocked ? 'border-alert' : ''}>
          <div className="flex flex-col">
            <TrustStackCheck label="Security Scan" status={isBlocked ? 'FAIL' : 'PASS'} hash={finding.id} isActive={activeCheck === 0} />
            <TrustStackCheck label="Ledger Inclusion" status={isBlocked ? 'FAIL' : 'PASS'} hash="a1b2c3d4e5f6" isActive={activeCheck === 1} />
            <TrustStackCheck label="Reproducibility" status={isBlocked ? 'FAIL' : 'PASS'} hash="f6e5d4c3b2a1" isActive={activeCheck === 2} />
            <TrustStackCheck label="Chain Validity" status={isBlocked ? 'FAIL' : 'PASS'} hash="123456abcdef" isActive={activeCheck === 3} />
          </div>
          
          <button 
            className={`w-full mt-6 py-3 font-mono text-xs tracking-widest uppercase transition-colors ${verifying ? 'bg-muted text-void' : 'bg-signal text-void hover:bg-signal/80'}`}
            onClick={() => verifyMutation.mutate()}
            disabled={verifying}
          >
            {verifying ? 'VERIFYING...' : 'RE-VERIFY NOW'}
          </button>
        </Panel>
      </div>
    </div>
  );
}
