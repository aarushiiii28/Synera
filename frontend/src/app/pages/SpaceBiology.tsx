import React, { useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchSpaceBiologyOverview, fetchSpaceBiologyGenes } from '../../lib/api';
import { Panel } from '../../components/Panel';
import { Readout } from '../../components/Readout';
import { Caveat } from '../../components/Caveat';
import * as d3 from 'd3';

function VolcanoPlot({ genes }: { genes: any[] }) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!genes || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    
    const width = 600, height = 400;
    const margin = { top: 20, right: 20, bottom: 40, left: 40 };
    
    const x = d3.scaleLinear().domain([-2, 2]).range([margin.left, width - margin.right]);
    const y = d3.scaleLinear().domain([0, 10]).range([height - margin.bottom, margin.top]);
    
    // Axes
    svg.append('g').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x)).attr('color', 'var(--line-strong)');
    svg.append('g').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y)).attr('color', 'var(--line-strong)');
    
    // Points
    const gPoints = svg.append('g');
    gPoints.selectAll('circle').data(genes).enter().append('circle')
      .attr('cx', (d: any) => x(d.b_AB))
      .attr('cy', (d: any) => y(d.neg_log10_q))
      .attr('r', 4)
      .attr('fill', (d: any) => d.type === 'SYNERGISTIC' ? 'var(--biosphere)' : (d.type === 'ANTAGONISTIC' ? 'var(--signal)' : 'var(--text)'))
      .attr('stroke', (d: any) => d.replicated ? 'var(--text)' : 'none')
      .attr('stroke-width', (d: any) => d.replicated ? 1.5 : 0)
      .append('title')
      .text((d: any) => d.gene_symbol);
      
    // Threshold lines
    svg.append('line').attr('x1', margin.left).attr('x2', width - margin.right).attr('y1', y(1.3)).attr('y2', y(1.3))
      .attr('stroke', 'var(--line)').attr('stroke-dasharray', '4,4');
      
  }, [genes]);

  return <svg ref={svgRef} width="100%" height="400" viewBox="0 0 600 400" />;
}

export function SpaceBiology() {
  const { data: overview } = useQuery({ queryKey: ['sb_overview'], queryFn: fetchSpaceBiologyOverview });
  const { data: genes } = useQuery({ queryKey: ['sb_genes'], queryFn: () => fetchSpaceBiologyGenes() });
  
  return (
    <div className="flex flex-col gap-12 p-8 lg:p-12 pb-32 h-full overflow-auto">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-4xl uppercase tracking-tight text-text">Radiation × Microgravity</h1>
        <p className="text-muted font-sans max-w-2xl">
          Transcriptomic analysis of combined spaceflight stressors in murine models (OSD-211 & OSD-237).
        </p>
      </div>

      <Caveat>
        evidence_level CROSS_TISSUE_SAME_COHORT (same animals, two tissues; not independent), detectable interaction &gt;= ~1.5 log2, volcano = all tested genes, &ldquo;exploratory, below FDR threshold, not findings&rdquo;. Track A is REAL.
      </Caveat>

      <div className="flex gap-8">
        <Panel className="w-1/3" indexLabel="01 / 2x2 DESIGN" provenance="REAL">
          <div className="flex flex-col gap-4 py-4">
            <div className="grid grid-cols-2 gap-4 text-center font-mono text-[10px] tracking-widest text-text">
              <div className="border border-line p-4">SHAM / GROUND<br/><span className="text-faint">n = {overview?.design_2x2?.sham_ground ?? 6}</span></div>
              <div className="border border-line p-4 text-signal">RAD / GROUND<br/><span className="text-faint">n = {overview?.design_2x2?.rad_ground ?? 6}</span></div>
              <div className="border border-line p-4 text-biosphere">SHAM / MICROG<br/><span className="text-faint">n = {overview?.design_2x2?.sham_microg ?? 3}</span></div>
              <div className="border border-signal/50 bg-signal/10 p-4 text-text font-bold">RAD / MICROG<br/><span className="text-faint">n = {overview?.design_2x2?.rad_microg ?? 6}</span></div>
            </div>
            <div className="text-xs font-mono text-muted text-center mt-2">
              This design can detect |interaction| &gt;= ~1.5 log2
            </div>
          </div>
        </Panel>
        
        <Panel className="flex-1" indexLabel="02 / INTERACTION OVERVIEW" provenance="REAL">
          <div className="flex gap-16 py-4">
            <Readout value={overview?.interaction_counts?.SYNERGISTIC || 0} caption="SYNERGISTIC GENES" />
            <Readout value={overview?.interaction_counts?.ANTAGONISTIC || 0} caption="ANTAGONISTIC GENES" />
            <Readout value={overview?.studies || 0} caption="STUDIES" />
          </div>
        </Panel>
      </div>

      <div className="flex gap-8">
        <Panel className="flex-1" indexLabel="03 / VOLCANO PLOT" provenance="REAL">
          <div className="absolute top-2 right-2 text-[10px] text-faint font-mono uppercase tracking-widest max-w-xs text-right">
            Exploratory, below FDR threshold, not findings
          </div>
          <VolcanoPlot genes={genes || []} />
        </Panel>
        
        <Panel className="w-1/3 flex flex-col" indexLabel="04 / TOP GENES" provenance="REAL">
          <div className="flex flex-col gap-2 flex-1 overflow-auto">
            <div className="flex text-[10px] font-mono tracking-widest text-faint uppercase border-b border-line pb-2 mb-2">
              <div className="flex-1">Symbol</div>
              <div className="w-16 text-right">b_AB</div>
              <div className="w-16 text-right">-log Q</div>
            </div>
            {genes?.map((g: any) => (
              <div key={g.ensembl_id} className="flex text-xs font-mono text-text py-2 border-b border-line/30">
                <div className="flex-1 font-bold">{g.gene_symbol}</div>
                <div className="w-16 text-right text-muted">{g.b_AB.toFixed(2)}</div>
                <div className="w-16 text-right text-muted">{g.neg_log10_q.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
