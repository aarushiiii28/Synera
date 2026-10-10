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
  
  const isLoading = !health && !ledger && !isHealthError && !isLedgerError;

  if (isHealthError || isLedgerError) {
    return (
      <div className="h-10 border-b border-alert/30 bg-alert/10 backdrop-blur-md flex items-center px-2 md:px-4 justify-between font-mono text-[10px] uppercase tracking-widest text-alert z-50 overflow-hidden">
        <div className="flex items-center gap-2 md:gap-6 flex-1 min-w-0">
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="w-1.5 h-1.5 flex-shrink-0 rounded-full bg-alert motion-safe:animate-pulse" />
            <span className="hidden sm:inline">API_STATUS: </span>OFFLINE
          </div>
          <div className="hidden md:flex items-center gap-2">
            HEIGHT: <span>---</span>
          </div>
          <div className="hidden sm:flex items-center gap-2">
            CHAIN: <span className="text-alert">UNREACHABLE</span>
          </div>
        </div>
        <div className="flex items-center gap-2 md:gap-6 flex-shrink-0">
          <div className="hidden lg:flex items-center gap-2">
            <span>HEAD: ---</span>
          </div>
          <div className="text-alert/60 text-right whitespace-nowrap">
            {time.replace(' GMT', '')}
          </div>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="h-10 border-b border-line bg-void/80 backdrop-blur-md flex items-center px-2 md:px-4 justify-between font-mono text-[10px] uppercase tracking-widest text-muted z-50 overflow-hidden">
        <div className="flex items-center gap-2 md:gap-6 flex-1 min-w-0">
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="w-1.5 h-1.5 flex-shrink-0 rounded-full bg-muted" />
            <span className="hidden sm:inline">API_STATUS: </span>CHECKING
          </div>
          <div className="hidden md:flex items-center gap-2">
            HEIGHT: <span>---</span>
          </div>
          <div className="hidden sm:flex items-center gap-2">
            CHAIN: <span>---</span>
          </div>
        </div>
        <div className="flex items-center gap-2 md:gap-6 flex-shrink-0">
          <div className="hidden lg:flex items-center gap-2">
            <span>HEAD: ---</span>
          </div>
          <div className="text-faint text-right whitespace-nowrap">
            {time.replace(' GMT', '')}
          </div>
        </div>
      </div>
    );
  }

  const isValid = health?.ledger?.chain_valid ?? false;
  const height = health?.ledger?.height ?? 0;
  const root = ledger?.merkle_root ?? '';

  return (
    <div className="h-10 border-b border-line bg-void/80 backdrop-blur-md flex items-center px-2 md:px-4 justify-between font-mono text-[10px] uppercase tracking-widest text-muted z-50 overflow-hidden">
      <div className="flex items-center gap-2 md:gap-6 flex-1 min-w-0">
        <div className="flex items-center gap-2 text-text whitespace-nowrap">
          <span className="w-1.5 h-1.5 flex-shrink-0 rounded-full bg-signal motion-safe:animate-pulse" />
          <span className="hidden sm:inline">API_STATUS: </span>LIVE
        </div>
        
        <div className="hidden md:flex items-center gap-2 whitespace-nowrap">
          HEIGHT: <span className="text-text">{String(height).padStart(6, '0')}</span>
        </div>
        
        <div className="hidden sm:flex items-center gap-2 whitespace-nowrap">
          CHAIN:
          {isValid ? (
            <span className="text-biosphere">VALID</span>
          ) : (
            <span className="text-alert motion-safe:animate-pulse">BROKEN</span>
          )}
        </div>
      </div>
      
      <div className="flex items-center gap-2 md:gap-6 flex-shrink-0">
        <div className="hidden lg:flex items-center gap-2">
          <span className="text-faint">HEAD:</span>
          {root ? <HashRing hash={root} size={14} /> : <span>---</span>}
        </div>
        
        <div className="text-faint text-right whitespace-nowrap">
          {time.replace(' GMT', '')}
        </div>
      </div>
    </div>
  );
}
