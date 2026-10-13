import React, { Suspense } from 'react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchHealth, fetchFindings } from '../../lib/api';
import { motion } from 'framer-motion';

const Globe = React.lazy(() => import('../../components/Globe'));

function DataPacket({ delay = 0, duration = 4 }) {
  return (
    <motion.div
      className="absolute top-[-1px] left-0 w-8 h-[2px] bg-gradient-to-r from-transparent via-signal to-transparent z-10"
      initial={{ left: '-5%' }}
      animate={{ left: '105%' }}
      transition={{
        duration,
        ease: 'linear',
        repeat: Infinity,
        delay,
      }}
    />
  );
}

function WorkflowStrip({ counts, isOffline, height }: { counts: Record<string, number>, isOffline: boolean, height: number }) {
  const steps = [
    { id: 'candidates', label: 'CANDIDATES', val: counts.candidates },
    { id: 'validated', label: 'VALIDATED', val: counts.validated },
    { id: 'verified', label: 'VERIFIED', val: counts.verified },
    { id: 'act', label: 'BLOCKED', val: counts.blocked },
  ];

  return (
    <div className="absolute bottom-16 left-8 right-8 lg:left-16 lg:right-[40%] flex items-end">
      <div className="w-full flex justify-between relative border-t border-line pt-4 overflow-hidden">
        {!isOffline && (
          <>
            <DataPacket delay={0} />
            <DataPacket delay={2.5} duration={3} />
          </>
        )}
        {steps.map((s) => (
          <div key={s.id} className="flex flex-col gap-1 relative z-20">
            <div className="absolute -top-[19px] left-0 w-1.5 h-1.5 bg-line rounded-full" />
            <div className="font-mono text-[10px] tracking-widest text-muted uppercase">{s.label}</div>
            <div className={`font-mono text-xl ${isOffline ? 'text-alert' : 'text-text'}`}>
              {isOffline ? '---' : s.val}
            </div>
          </div>
        ))}
        <div className="flex flex-col gap-1 relative z-20 items-end">
          <div className="font-mono text-[10px] tracking-widest text-muted uppercase">LEDGER HEIGHT</div>
          <div className={`font-mono text-xl ${isOffline ? 'text-alert' : 'text-signal'}`}>
            {isOffline ? '---' : height}
          </div>
        </div>
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

  const queries = useQueries({
    queries: [
      { queryKey: ['findings', 'CANDIDATE'], queryFn: () => fetchFindings({ status: 'CANDIDATE', limit: '1' }), refetchInterval: 10000 },
      { queryKey: ['findings', 'VALIDATED'], queryFn: () => fetchFindings({ status: 'VALIDATED', limit: '1' }), refetchInterval: 10000 },
      { queryKey: ['findings', 'VERIFIED'], queryFn: () => fetchFindings({ status: 'VERIFIED', limit: '1' }), refetchInterval: 10000 },
      { queryKey: ['findings', 'BLOCKED'], queryFn: () => fetchFindings({ status: 'BLOCKED', limit: '1' }), refetchInterval: 10000 },
    ]
  });

  const isOffline = isHealthError || (!health && !isHealthError);
  const height = health?.ledger?.height || 0;
  
  // Track B capped at validated. Verified = 0 if no real findings exist.
  const safeCounts = {
    candidates: queries[0].data?.total || 0,
    validated: queries[1].data?.total || 0,
    verified: queries[2].data?.total || 0,
    blocked: queries[3].data?.total || 0,
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
      
      <WorkflowStrip counts={safeCounts} isOffline={isOffline} height={height} />
    </div>
  );
}
