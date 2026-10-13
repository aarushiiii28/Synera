import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchDatasets, postRun, fetchInteractionMatrix, fetchInteractionNetwork } from '../../lib/api';
import { Panel } from '../../components/Panel';
import { OrbitProgress } from '../../components/OrbitProgress';
import * as d3 from 'd3';

function ConstellationNetwork({ network, onSelect }: { network: any, onSelect: any }) {
  const svgRef = useRef<SVGSVGElement>(null);
  
  useEffect(() => {
    if (!network || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    
    const width = 400;
    const height = 400;
    const cx = width / 2;
    const cy = height / 2;
    
    const simulation = d3.forceSimulation<any>(network.nodes)
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(cx, cy))
      .force('link', d3.forceLink<any, any>(network.edges).id((d: any) => d.id).distance(100));
      
    const gEdges = svg.append('g').attr('stroke-width', 2);
    const gNodes = svg.append('g');
    
    const edges = gEdges.selectAll('line').data<any>(network.edges).enter().append('line')
      .attr('stroke', (d: any) => d.type === 'SYNERGISTIC' ? 'var(--biosphere)' : 'var(--signal)')
      .attr('stroke-dasharray', (d: any) => d.status === 'CANDIDATE' ? '4,4' : 'none');
      
    const nodes = gNodes.selectAll('circle').data<any>(network.nodes).enter().append('circle')
      .attr('r', 6)
      .attr('fill', 'var(--text)')
      .call(d3.drag<SVGCircleElement, any>()
        .on('start', (e: any, d: any) => { if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (e: any, d: any) => { d.fx = e.x; d.fy = e.y; })
        .on('end', (e: any, d: any) => { if(!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));
        
    const labels = gNodes.selectAll('text').data<any>(network.nodes).enter().append('text')
      .text((d: any) => d.id)
      .attr('font-size', '10px')
      .attr('fill', 'var(--muted)')
      .attr('dx', 10)
      .attr('dy', 4)
      .attr('font-family', 'var(--font-mono)');
      
    simulation.on('tick', () => {
      edges.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
           .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y);
      nodes.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y);
      labels.attr('x', (d: any) => d.x).attr('y', (d: any) => d.y);
    });
    
    return () => { simulation.stop(); };
  }, [network, onSelect]);

  return <svg ref={svgRef} width="100%" height="400" viewBox="0 0 400 400" className="bg-hull/50 rounded-[2px]" />;
}

function InteractionMatrix({ matrix }: { matrix: any }) {
  if (!matrix) return null;
  const labels = matrix.matrix[0].slice(1);
  const data = matrix.matrix.slice(1).map((r: any) => r.slice(1));
  const types = matrix.types.slice(1).map((r: any) => r.slice(1));
  
  return (
    <div className="flex flex-col gap-1">
      <div className="flex">
        <div className="w-24"></div>
        {labels.map((l: string) => <div key={l} className="w-12 text-[10px] text-faint font-mono -rotate-45 origin-bottom-left">{l}</div>)}
      </div>
      {labels.map((l: string, i: number) => (
        <div key={l} className="flex items-center gap-1">
          <div className="w-24 text-[10px] text-muted font-mono text-right pr-2">{l}</div>
          {labels.map((_: any, j: number) => {
            const val = data[i][j];
            const type = types[i][j];
            const size = val > 0 ? 8 + val * 10 : 0;
            return (
              <div key={j} className="w-12 h-12 flex items-center justify-center border border-line/20">
                {size > 0 && j > i && (
                  <div 
                    className="rotate-45"
                    style={{
                      width: size, height: size,
                      backgroundColor: type === 'SYNERGISTIC' ? 'var(--biosphere)' : 'var(--signal)'
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function ResponseSurface({ surface }: { surface: any }) {
  const svgRef = useRef<SVGSVGElement>(null);
  
  useEffect(() => {
    if (!surface || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    
    const width = 400, height = 300;
    const margin = { top: 20, right: 20, bottom: 40, left: 40 };
    
    // Convert 2D array to 1D for contours
    const nx = surface.v1_grid.length;
    const ny = surface.v2_grid.length;
    
    const additive1D = [].concat(...surface.additive);
    const observed1D = [].concat(...surface.observed);
    
    if (nx < 2 || ny < 2) return;
    
    const maxVal = Math.max(...additive1D, ...observed1D);
    const minVal = Math.min(...additive1D, ...observed1D);
    
    const x = d3.scaleLinear().domain([0, nx - 1]).range([margin.left, width - margin.right]);
    const y = d3.scaleLinear().domain([0, ny - 1]).range([height - margin.bottom, margin.top]);
    
    const path = d3.geoPath();
    const contours = d3.contours().size([nx, ny]).thresholds(d3.range(minVal, maxVal, (maxVal - minVal) / 8));
    
    // Additive (dashed)
    const gAdd = svg.append('g');
    gAdd.selectAll('path').data(contours(additive1D)).enter().append('path')
      .attr('d', d => {
         const p = path(d);
         // manual scale because contours are in grid coordinates [0, nx]
         return p;
      })
      .attr('transform', `scale(${(width - margin.left - margin.right)/nx}, ${(height - margin.top - margin.bottom)/ny}) translate(${margin.left}, ${margin.top})`)
      .attr('fill', 'none')
      .attr('stroke', 'var(--muted)')
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '4,4');
      
    // Observed (solid)
    const gObs = svg.append('g');
    gObs.selectAll('path').data(contours(observed1D)).enter().append('path')
      .attr('d', path)
      .attr('transform', `scale(${(width - margin.left - margin.right)/nx}, ${(height - margin.top - margin.bottom)/ny}) translate(${margin.left}, ${margin.top})`)
      .attr('fill', 'none')
      .attr('stroke', 'var(--signal)')
      .attr('stroke-width', 1.5);
      
    // Axes
    svg.append('g').attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).ticks(5)).attr('color', 'var(--line-strong)');
    svg.append('g').attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(5)).attr('color', 'var(--line-strong)');
      
  }, [surface]);

  return <svg ref={svgRef} width="100%" height="300" viewBox="0 0 400 300" className="bg-hull/30" />;
}

export function Discovery() {
  const [selectedDataset, setSelectedDataset] = useState<string>('env_panel');
  const [runId, setRunId] = useState<string | null>(null);
  const [sseStatus, setSseStatus] = useState<any>(null);
  
  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: fetchDatasets });
  const { data: matrix } = useQuery({ queryKey: ['matrix', selectedDataset], queryFn: () => fetchInteractionMatrix(selectedDataset) });
  const { data: network } = useQuery({ queryKey: ['network', selectedDataset], queryFn: () => fetchInteractionNetwork(selectedDataset) });

  const runMutation = useMutation({
    mutationFn: () => postRun({ dataset_id: selectedDataset, stressor_pairs: ['all'], methods: ['gbm'], alpha: 0.05, force: false }),
    onSuccess: (data) => {
      setRunId(data.run_id);
    }
  });

  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(`http://localhost:8000/api/v1/runs/${runId}/events`);
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setSseStatus(data);
      if (data.progress >= 1) es.close();
    };
    return () => es.close();
  }, [runId]);

  const surface: any = null;

  return (
    <div className="flex flex-col gap-12 p-8 lg:p-12 pb-32 overflow-auto h-full">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-4xl uppercase tracking-tight text-text">Discovery Engine</h1>
        <p className="text-muted font-sans max-w-2xl">
          Hypothesis generation through combinatorial search over high-dimensional datasets.
        </p>
      </div>

      <div className="flex gap-8 items-start">
        <Panel className="w-1/3 flex flex-col gap-6" indexLabel="01 / ENGINE CONFIG">
          <div className="flex flex-col gap-2">
            <label className="text-[10px] text-faint font-mono uppercase tracking-widest">Dataset</label>
            <select 
              className="bg-void border border-line text-text p-2 font-mono text-sm outline-none focus:border-signal"
              value={selectedDataset}
              onChange={e => setSelectedDataset(e.target.value)}
            >
              {datasets?.map(d => (
                <option key={d.id} value={d.id}>{d.name} {d.provenance === 'SIMULATED' ? '(SIM)' : ''}</option>
              ))}
              {!datasets && <option value="env_panel">env_panel (SIM)</option>}
            </select>
          </div>
          
          <button 
            className="bg-signal text-void font-mono text-xs tracking-widest uppercase py-3 hover:bg-signal/80 transition-colors"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending}
          >
            {runMutation.isPending ? 'STARTING...' : 'RUN ENGINE'}
          </button>
          
          {runId && (
            <div className="mt-8 flex flex-col items-center gap-4 border-t border-line pt-8">
              <OrbitProgress size={120} progress={sseStatus?.progress || 0} />
              <div className="font-mono text-xs text-muted text-center h-8">
                {sseStatus?.message || 'Awaiting telemetry...'}
              </div>
            </div>
          )}
        </Panel>
        
        <Panel className="flex-1" indexLabel="02 / INTERACTION MATRIX">
          <InteractionMatrix matrix={matrix} />
        </Panel>
      </div>

      <div className="flex gap-8 items-start">
        <Panel className="flex-1" indexLabel="03 / CONSTELLATION NETWORK">
          <ConstellationNetwork network={network} onSelect={() => {}} />
        </Panel>
        
        <Panel className="w-1/3" indexLabel="04 / RESPONSE SURFACE">
          <div className="text-[10px] text-faint font-mono uppercase tracking-widest mb-4">SELECTED PAIR: heat_index x pm25</div>
          {surface ? (
            <ResponseSurface surface={surface} />
          ) : (
            <div className="h-[300px] flex items-center justify-center font-mono text-xs text-muted border border-line/30 bg-hull/20">
              NO RESPONSE SURFACE LOADED
            </div>
          )}
          <div className="mt-4 flex gap-4 text-[10px] font-mono tracking-widest uppercase">
            <div className="flex items-center gap-2"><div className="w-3 h-[2px] bg-muted border-dashed border-t border-void" /> ADDITIVE</div>
            <div className="flex items-center gap-2"><div className="w-3 h-[2px] bg-signal" /> OBSERVED</div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
