import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { fetchFindings } from '../../lib/api';
import { StatusChip } from '../../components/StatusChip';

function MiniForest({ effect, ci_low, ci_high }: { effect?: number, ci_low?: number, ci_high?: number }) {
  if (effect === undefined || ci_low === undefined || ci_high === undefined) return null;
  // simple SVG forest plot
  const scale = (v: number) => 20 + v * 15; // domain roughly -1 to +1 -> 5 to 35
  return (
    <div className="flex items-center gap-2">
      <svg width={40} height={12} className="overflow-visible">
        <line x1={20} y1={0} x2={20} y2={12} stroke="var(--line-strong)" strokeDasharray="1,1" />
        <line x1={scale(ci_low)} y1={6} x2={scale(ci_high)} y2={6} stroke="var(--text)" strokeWidth={1} />
        <circle cx={scale(effect)} cy={6} r={2.5} fill="var(--signal)" />
      </svg>
      <span className="font-mono text-[10px] w-8">{effect.toFixed(2)}</span>
    </div>
  );
}

function ConfidenceGauge({ value = 0.8 }: { value?: number }) {
  return (
    <svg width={24} height={24} viewBox="0 0 24 24" className="transform -rotate-90">
      <circle cx={12} cy={12} r={10} fill="none" stroke="var(--line)" strokeWidth={2} />
      <circle cx={12} cy={12} r={10} fill="none" stroke="var(--biosphere)" strokeWidth={2} strokeDasharray={`${value * 62.8} 62.8`} />
    </svg>
  );
}

export function Findings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const statusFilter = searchParams.get('status') || '';
  const typeFilter = searchParams.get('type') || '';
  const search = searchParams.get('q') || '';
  
  const { data, isLoading } = useQuery({
    queryKey: ['findings', statusFilter, typeFilter, search],
    queryFn: () => fetchFindings({ 
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(typeFilter ? { type: typeFilter } : {}),
      ...(search ? { q: search } : {})
    })
  });

  return (
    <div className="flex flex-col h-full overflow-hidden p-8 lg:p-12 pb-16">
      <div className="flex flex-col gap-2 mb-8">
        <h1 className="font-display text-4xl uppercase tracking-tight text-text">Finding Registry</h1>
        <p className="text-muted font-sans max-w-2xl">
          Complete log of all interaction pairs evaluated by the system.
        </p>
      </div>

      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Instrument Strip */}
        <div className="flex items-center gap-4 mb-4 pb-4 border-b border-line">
          <input 
            type="text" 
            placeholder="Search variables..." 
            value={search}
            onChange={(e) => {
              const p = new URLSearchParams(searchParams);
              if (e.target.value) p.set('q', e.target.value); else p.delete('q');
              setSearchParams(p);
            }}
            className="bg-void border border-line p-2 text-xs font-mono text-text outline-none focus:border-signal w-64"
          />
          <select 
            value={statusFilter}
            onChange={(e) => {
              const p = new URLSearchParams(searchParams);
              if (e.target.value) p.set('status', e.target.value); else p.delete('status');
              setSearchParams(p);
            }}
            className="bg-void border border-line p-2 text-xs font-mono text-text outline-none focus:border-signal"
          >
            <option value="">ALL STATUSES</option>
            <option value="CANDIDATE">CANDIDATE</option>
            <option value="VALIDATED">VALIDATED</option>
            <option value="VERIFIED">VERIFIED</option>
            <option value="BLOCKED">BLOCKED</option>
          </select>
          <select 
            value={typeFilter}
            onChange={(e) => {
              const p = new URLSearchParams(searchParams);
              if (e.target.value) p.set('type', e.target.value); else p.delete('type');
              setSearchParams(p);
            }}
            className="bg-void border border-line p-2 text-xs font-mono text-text outline-none focus:border-signal"
          >
            <option value="">ALL TYPES</option>
            <option value="SYNERGISTIC">SYNERGISTIC</option>
            <option value="ANTAGONISTIC">ANTAGONISTIC</option>
            <option value="NONLINEAR">NONLINEAR</option>
          </select>
          <div className="ml-auto text-xs font-mono text-muted">
            TOTAL: {data?.total || 0}
          </div>
        </div>

        {/* Table Header */}
        <div className="flex px-4 py-2 text-[10px] font-mono tracking-widest text-faint uppercase border-b border-line">
          <div className="w-32">Status</div>
          <div className="w-24">Type</div>
          <div className="flex-1">Pair</div>
          <div className="w-48">Effect (CI)</div>
          <div className="w-24">Q-Value</div>
          <div className="w-24 text-center">Confidence</div>
          <div className="w-32 text-right">Provenance</div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-auto">
          {isLoading && <div className="p-4 font-mono text-xs text-muted">LOADING...</div>}
          {!isLoading && data?.items.length === 0 && (
            <div className="p-8 text-center border border-line border-dashed m-4 text-faint font-mono text-xs">
              NO FINDINGS MATCH YOUR CRITERIA.
            </div>
          )}
          {!isLoading && data?.items.map((f) => (
            <div 
              key={f.id} 
              className="flex items-center px-4 py-3 border-b border-line/30 hover:bg-hull/30 cursor-pointer transition-colors"
              onClick={() => navigate(`/findings/${f.id}`)}
            >
              <div className="w-32">
                <StatusChip status={f.status} />
              </div>
              <div className="w-24 font-mono text-[10px] tracking-widest text-signal">
                {f.interaction_type.substring(0,3)}
              </div>
              <div className="flex-1 font-mono text-sm text-text">
                {f.v1} <span className="text-muted mx-2">×</span> {f.v2}
              </div>
              <div className="w-48">
                <MiniForest effect={(f as any).b_AB || f.effect_size} ci_low={(f as any).ci_low} ci_high={(f as any).ci_high} />
              </div>
              <div className="w-24 font-mono text-xs text-muted">
                {f.q_value.toExponential(2)}
              </div>
              <div className="w-24 flex justify-center">
                <ConfidenceGauge value={0.8} />
              </div>
              <div className="w-32 text-right">
                <span className={`text-[10px] font-mono tracking-widest px-2 py-1 rounded-sm ${f.provenance === 'SIMULATED' ? 'bg-solar/10 text-solar' : 'bg-biosphere/10 text-biosphere'}`}>
                  {f.provenance}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
