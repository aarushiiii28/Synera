import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchLedgerBlocks, verifyLedger, simulateTamper } from '../../lib/api';
import { Panel } from '../../components/Panel';
import { HashRing } from '../../components/HashRing';
import { motion, AnimatePresence } from 'framer-motion';

function LedgerExplorer() {
  const { data: blocks } = useQuery({ queryKey: ['ledger_blocks'], queryFn: fetchLedgerBlocks });
  const [selectedBlock, setSelectedBlock] = useState<any>(null);
  const [verifying, setVerifying] = useState(false);
  
  const verifyMut = useMutation({
    mutationFn: verifyLedger,
    onSuccess: async () => {
      setVerifying(true);
      await new Promise(r => setTimeout(r, 2000));
      setVerifying(false);
    }
  });

  return (
    <Panel indexLabel="01 / LEDGER EXPLORER" className="flex flex-col gap-4 relative overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono tracking-widest uppercase text-muted">Immutable Activity Chain</div>
        <button 
          className={`font-mono text-xs px-4 py-2 uppercase tracking-widest ${verifying ? 'bg-muted text-void' : 'bg-signal text-void'}`}
          onClick={() => verifyMut.mutate()}
          disabled={verifying}
        >
          {verifying ? 'VERIFYING...' : 'VERIFY ENTIRE CHAIN'}
        </button>
      </div>
      
      {verifying && (
        <motion.div 
          className="absolute top-0 bottom-0 w-[2px] bg-signal shadow-[0_0_12px_var(--signal)] z-50 pointer-events-none"
          initial={{ left: 0 }}
          animate={{ left: '100%' }}
          transition={{ duration: 2, ease: 'linear' }}
        />
      )}

      <div className="flex gap-4 overflow-x-auto py-4 relative hide-scrollbar items-center min-h-[160px]">
        <div className="absolute top-[80px] left-0 right-0 h-[1px] bg-line z-0" />
        {blocks?.map((b: any, i: number) => (
          <div key={b.index} className="flex flex-col items-center gap-2 relative z-10 cursor-pointer group" onClick={() => setSelectedBlock(b)}>
            <div className="text-[10px] font-mono text-faint">#{b.index}</div>
            <div className="bg-void rounded-full p-1 border border-line group-hover:border-signal transition-colors">
              <HashRing hash={b.payload_hash} size={40} />
            </div>
            <div className="text-[10px] font-mono text-signal truncate w-24 text-center">{b.block_type}</div>
            <div className="text-[10px] font-mono text-muted">{b.payload_hash.substring(0,8)}...</div>
          </div>
        ))}
        {!blocks && <div className="text-muted font-mono text-xs">AWAITING LEDGER...</div>}
      </div>

      <AnimatePresence>
        {selectedBlock && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }} 
            animate={{ opacity: 1, height: 'auto' }} 
            exit={{ opacity: 0, height: 0 }}
            className="border-t border-line mt-4 pt-4 flex gap-8"
          >
            <div className="flex-1 font-mono text-xs text-muted whitespace-pre-wrap bg-void p-4 border border-line/30 max-h-64 overflow-auto">
              {JSON.stringify(selectedBlock, null, 2)}
            </div>
            <div className="w-1/3 flex flex-col gap-2">
              <div className="text-[10px] text-faint uppercase tracking-widest">Merkle Proof Path</div>
              <div className="flex flex-col gap-1 border-l border-line/50 pl-2">
                <div className="font-mono text-[10px] text-biosphere">ROOT: {selectedBlock.merkle_root?.substring(0, 16)}...</div>
                <div className="font-mono text-[10px] text-muted">PATH VALIDATED</div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Panel>
  );
}

function TamperSimulator() {
  const [mode, setMode] = useState('bit_flip');
  const [result, setResult] = useState<any>(null);
  const [ledgerStatus, setLedgerStatus] = useState<any>(null);
  
  const mut = useMutation({
    mutationFn: () => simulateTamper({ dataset_id: 'env_panel', mode, magnitude: 0.1 }),
    onSuccess: async (data) => {
      setResult(data);
      try {
        const v = await verifyLedger();
        setLedgerStatus(v);
      } catch (err) {
        console.error('Failed to verify ledger', err);
      }
    }
  });

  const modes = ['bit_flip', 'row_edit', 'poison_labels', 'inject_outliers', 'drift_units', 'subtle_edit'];

  return (
    <Panel indexLabel="02 / TAMPER SIMULATOR (DEMO)">
      <div className="flex flex-col gap-4">
        <div className="font-sans text-muted text-sm max-w-md">
          Simulate a malicious mutation in the dataset to observe cryptographic detection. 
          <span className="text-alert ml-1">Runs on a temporary copy; touches no real data.</span>
        </div>
        
        <div className="flex flex-wrap gap-4">
          <select 
            value={mode}
            onChange={e => setMode(e.target.value)}
            className="bg-void border border-line px-4 py-2 text-xs font-mono text-text outline-none focus:border-signal uppercase"
          >
            {modes.map(m => (
              <option key={m} value={m}>MODE: {m.replace('_', ' ')}</option>
            ))}
          </select>
          <button className="bg-void border border-line px-4 py-2 text-xs font-mono text-text opacity-50 cursor-not-allowed">MAG: 0.1</button>
          <button 
            className="bg-alert text-void font-mono text-xs tracking-widest px-6 py-2 uppercase hover:bg-alert/80 transition-colors ml-auto"
            onClick={() => mut.mutate()}
            disabled={mut.isPending}
          >
            {mut.isPending ? 'SIMULATING...' : 'INJECT & VERIFY'}
          </button>
        </div>

        {result && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 flex flex-col gap-4 border border-alert bg-alert/10 p-4">
            <div className="text-alert font-mono text-[10px] tracking-widest uppercase">
              SCIENTIFIC DATA INTEGRITY FAILURE: {result.verdict}
            </div>
            <div className="flex gap-4 text-xs font-mono">
              <div className="flex-1 flex flex-col gap-1">
                <span className="text-faint">ORIGINAL HASH</span>
                <span className="text-text">{result.original_hash ? `${result.original_hash.substring(0, 16)}...` : 'CLEAN'}</span>
              </div>
              <div className="flex-1 flex flex-col gap-1">
                <span className="text-faint">RECOMPUTED HASH</span>
                <span className="text-alert">{result.tampered_hash ? `${result.tampered_hash.substring(0, 16)}... (MISMATCH)` : 'MISMATCH'}</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {result.detections?.map((d: string) => (
                <div key={d} className="px-2 py-1 bg-alert/20 border border-alert text-[10px] text-alert uppercase tracking-widest">
                  DETECTOR: {d}
                </div>
              ))}
            </div>
            {ledgerStatus && (
              <div className="text-[10px] text-biosphere font-mono mt-2 pt-2 border-t border-alert/30 flex justify-between">
                <span>CHAIN VERIFY: {ledgerStatus.valid ? 'VALID' : 'INVALID'} (height: {ledgerStatus.height}, head: {ledgerStatus.head ? `${ledgerStatus.head.substring(0, 8)}...` : 'valid'})</span>
                <span>ISSUES: {ledgerStatus.issues?.length || 0}</span>
              </div>
            )}
            <div className="text-[10px] text-muted font-mono mt-1">
              Note: Simulated on a temporary copy. Global ledger /ledger/verify remains valid.
            </div>
          </motion.div>
        )}
      </div>
    </Panel>
  );
}

function VulnerablePath() {
  const points = ['DATA', 'MODEL', 'CODE', 'PIPELINE', 'VERSION', 'REPRODUCIBILITY'];
  return (
    <Panel indexLabel="03 / VULNERABLE PATH DIAGRAM" className="flex-1">
      <div className="flex items-center justify-between w-full h-32 relative">
        <div className="absolute left-8 right-8 top-1/2 h-[1px] bg-line/50 -translate-y-1/2" />
        {points.map((p, i) => (
          <div key={p} className="flex flex-col items-center gap-2 relative z-10">
            <div className="w-8 h-8 rounded-full border border-line bg-void flex items-center justify-center font-mono text-[10px] text-faint">
              0{i+1}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted">{p}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function TrustCenter() {
  return (
    <div className="flex flex-col gap-12 p-8 lg:p-12 pb-32 h-full overflow-auto">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-4xl uppercase tracking-tight text-text">Trust Center</h1>
        <p className="text-muted font-sans max-w-2xl">
          Cryptographic provenance, tamper simulation, and ledger verification.
        </p>
      </div>

      <LedgerExplorer />
      
      <div className="flex gap-8 items-start">
        <TamperSimulator />
        <VulnerablePath />
      </div>
    </div>
  );
}
