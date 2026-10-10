import React, { Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from '../../lib/api';

const Globe = React.lazy(() => import('../../components/Globe'));



function WorkflowStrip({ counts, isOffline }: { counts: Record<string, number>, isOffline: boolean }) {
  const steps = [
    { id: 'candidates', label: 'CANDIDATES', val: counts.candidates },
    { id: 'validated', label: 'VALIDATED', val: counts.validated },
    { id: 'verified', label: 'VERIFIED', val: counts.verified },
    { id: 'act', label: 'BLOCKED', val: counts.blocked },
  ];

  return (
    <div className="absolute bottom-16 left-8 right-8 lg:left-16 lg:right-[40%] flex items-end">
      <div className="w-full flex justify-between relative border-t border-line pt-4">
        {steps.map((s) => (
          <div key={s.id} className="flex flex-col gap-1 relative">
            <div className="absolute -top-[19px] left-0 w-1.5 h-1.5 bg-line rounded-full" />
            <div className="font-mono text-[10px] tracking-widest text-muted uppercase">{s.label}</div>
            <div className={`font-mono text-xl ${isOffline ? 'text-alert' : 'text-text'}`}>
              {isOffline ? '---' : s.val}
            </div>
          </div>
        ))}
      </div>
      
      {isOffline && (
        <div className="absolute -top-12 left-0 text-alert font-mono text-xs tracking-widest flex items-center gap-2">
          <span className="w-2 h-2 bg-alert rounded-full animate-pulse" />
          SIGNAL LOST
        </div>
      )}
    </div>
  );
}

export function Observatory() {
  const { data: health, isError: isHealthError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 10000
  });

  const isOffline = isHealthError || (!health && !isHealthError);
  
  // Wait, Track B capped at validated. Verified = 0. We'll use real counts when integrated in Part 8.

  const safeCounts = {
    candidates: 0,
    validated: 0,
    verified: 0,
    blocked: 0
  };

  return (
    <div className="w-full h-full relative overflow-hidden">
      <div className="absolute right-[-20%] bottom-[-20%] w-[80%] h-[120%] z-0 pointer-events-none">
        <Suspense fallback={<div className="w-full h-full rounded-full border border-line bg-void/50 backdrop-blur-sm" />}>
          <Globe />
        </Suspense>
      </div>
      
      

      <div className="relative z-10 w-full h-full flex flex-col justify-between p-8 lg:p-16 pointer-events-none">
        <div className="max-w-[45%] pointer-events-auto">
          <h1 className="font-display font-semibold text-[32px] lg:text-[56px] leading-[1.1] uppercase tracking-tight text-text text-balance">
            THE ENVIRONMENT DOESN'T CHANGE <span className="font-accent italic font-normal text-[1.1em] text-white lowercase">one variable</span> AT A TIME.
          </h1>
          <p className="mt-6 text-muted font-sans text-lg max-w-md leading-relaxed">
            See how multiple stressors <span className="text-signal font-mono uppercase tracking-widest text-xs">interact</span> to compound biological risk.
          </p>
        </div>

        <div className="mt-auto pb-24 pointer-events-auto">
          <div className="font-display text-[10px] tracking-[0.2em] text-faint mb-12">
            AI GENERATES HYPOTHESES. SCIENCE VALIDATES THEM.
          </div>
        </div>
      </div>
      
      <WorkflowStrip counts={safeCounts} isOffline={isOffline} />
    </div>
  );
}
