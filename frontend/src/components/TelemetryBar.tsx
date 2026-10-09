import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchHealth, fetchLedgerHead } from '../lib/api';
import { HashRing } from './HashRing';

export function TelemetryBar() {
  const { data: health, isError: isHealthError } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 10000 });
  const { data: ledger, isError: isLedgerError } = useQuery({ queryKey: ['ledger'], queryFn: fetchLedgerHead, refetchInterval: 10000 });
  
  const [time, setTime] = useState(new Date().toUTCString());
  
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toUTCString()), 1000);
    return () => clearInterval(timer);
  }, []);
  
  if (isHealthError || isLedgerError) {
    return (
      <div className="h-10 border-b border-alert/30 bg-alert/10 backdrop-blur-md flex items-center px-4 justify-between font-mono text-[10px] uppercase tracking-widest text-alert z-50">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-alert motion-safe:animate-pulse" />
            API_STATUS: OFFLINE
          </div>
          <div className="flex items-center gap-2">
            HEIGHT: <span>---</span>
          </div>
          <div className="flex items-center gap-2">
            CHAIN: <span className="text-alert">UNREACHABLE</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span>HEAD: ---</span>
          </div>
          <div className="text-alert/60 w-48 text-right">
            {time}
          </div>
        </div>
      </div>
    );
  }

  const isValid = health?.ledger?.chain_valid ?? true;
  const height = health?.ledger?.height ?? 0;
  const root = ledger?.merkle_root ?? '00000000000000000000000000000000';

  return (
    <div className="h-10 border-b border-line bg-void/80 backdrop-blur-md flex items-center px-4 justify-between font-mono text-[10px] uppercase tracking-widest text-muted z-50">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 text-text">
          <span className="w-1.5 h-1.5 rounded-full bg-signal motion-safe:animate-pulse" />
          API_STATUS: {health?.status || 'CONNECTING...'}
        </div>
        
        <div className="flex items-center gap-2">
          HEIGHT: <span className="text-text">{String(height).padStart(6, '0')}</span>
        </div>
        
        <div className="flex items-center gap-2">
          CHAIN:
          {isValid ? (
            <span className="text-biosphere">VALID</span>
          ) : (
            <span className="text-alert motion-safe:animate-pulse">BROKEN</span>
          )}
        </div>
      </div>
      
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-faint">HEAD:</span>
          {ledger ? <HashRing hash={root} size={16} /> : <span>---</span>}
        </div>
        
        <div className="text-faint w-48 text-right">
          {time}
        </div>
      </div>
    </div>
  );
}
