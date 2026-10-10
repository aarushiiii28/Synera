import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchHealth, fetchLedgerHead } from '../lib/api';

export function BootSequence({ onComplete }: { onComplete: () => void }) {
  const [logs, setLogs] = useState<string[]>([]);
  
  const { isSuccess: healthOk, isError: healthErr } = useQuery({ queryKey: ['health'], queryFn: fetchHealth });
  const { isSuccess: ledgerOk, isError: ledgerErr } = useQuery({ queryKey: ['ledgerHead'], queryFn: fetchLedgerHead });

  useEffect(() => {
    const sequence = async () => {
      setLogs(prev => [...prev, 'INITIALIZING SYNERA CORE...']);
      await new Promise(r => setTimeout(r, 500));
      
      setLogs(prev => [...prev, 'ESTABLISHING API UPLINK...']);
      if (healthOk || healthErr) {
        setLogs(prev => [...prev, healthOk ? 'API UPLINK: OK' : 'API UPLINK: FAILED (OFFLINE)']);
      }

      await new Promise(r => setTimeout(r, 500));
      
      setLogs(prev => [...prev, 'VERIFYING LEDGER MANIFEST...']);
      if (ledgerOk || ledgerErr) {
        setLogs(prev => [...prev, ledgerOk ? 'LEDGER VERIFIED' : 'LEDGER: UNREACHABLE']);
      }
      
      await new Promise(r => setTimeout(r, 800));
      onComplete();
    };
    
    if ((healthOk || healthErr) && (ledgerOk || ledgerErr)) {
      sequence();
    }
  }, [healthOk, healthErr, ledgerOk, ledgerErr, onComplete]);

  useEffect(() => {
    const handleKeyDown = () => onComplete();
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onComplete]);

  return (
    <div className="fixed inset-0 z-[100] bg-void flex items-end p-8 font-mono text-[10px] text-signal uppercase tracking-widest leading-relaxed">
      <div className="flex flex-col gap-1">
        {logs.map((log, i) => (
          <div key={i} className="animate-[fade-in_0.2s_ease-out]">{log}</div>
        ))}
        <div className="mt-4 text-faint animate-pulse">PRESS ANY KEY TO SKIP</div>
      </div>
    </div>
  );
}
