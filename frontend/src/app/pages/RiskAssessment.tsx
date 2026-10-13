import React, { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchRiskAssessment } from '../../lib/api';
import { Panel } from '../../components/Panel';
import { Caveat } from '../../components/Caveat';
import { Readout } from '../../components/Readout';
import * as d3 from 'd3';

function Sparkline({ data }: { data: number[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  
  useEffect(() => {
    if (!data || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    
    const width = 200, height = 40;
    const margin = { top: 5, right: 5, bottom: 5, left: 5 };
    
    const x = d3.scaleLinear().domain([0, data.length - 1]).range([margin.left, width - margin.right]);
    const y = d3.scaleLinear().domain([Math.min(...data) as any, Math.max(...data) as any]).range([height - margin.bottom, margin.top]);
    
    const line = d3.line<any>().x((d: any, i: number) => x(i)).y((d: any) => y(d)).curve(d3.curveMonotoneX);
    
    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', 'var(--alert)')
      .attr('stroke-width', 1.5)
      .attr('d', line);
      
    // Area
    const area = d3.area<any>().x((d: any, i: number) => x(i)).y0(height - margin.bottom).y1((d: any) => y(d)).curve(d3.curveMonotoneX);
    svg.append('path')
      .datum(data)
      .attr('fill', 'var(--alert)')
      .attr('opacity', 0.2)
      .attr('d', area);
      
  }, [data]);

  return <svg ref={svgRef} width={200} height={40} viewBox="0 0 200 40" />;
}

export function RiskAssessment() {
  const [region, setRegion] = useState('Seattle');
  const { data } = useQuery({ queryKey: ['risk', region], queryFn: () => fetchRiskAssessment(region) });

  return (
    <div className="flex flex-col gap-12 p-8 lg:p-12 pb-32 h-full overflow-auto print:bg-white print:text-black">
      <div className="flex justify-between items-end mb-4 print:mb-8">
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-4xl uppercase tracking-tight text-text print:text-black">Action / Risk Brief</h1>
          <p className="text-muted font-sans max-w-2xl print:text-gray-600">
            Compound environmental risk forecasts driven by verified interactions.
          </p>
        </div>
        <div className="flex gap-4 items-center print:hidden">
          <select 
            value={region} 
            onChange={e => setRegion(e.target.value)}
            className="bg-void border border-line p-2 text-xs font-mono text-text outline-none focus:border-signal"
          >
            <option value="Seattle">Seattle</option>
            <option value="London">London</option>
            <option value="Tokyo">Tokyo</option>
          </select>
          <button 
            onClick={() => window.print()}
            className="bg-signal text-void px-6 py-2 font-mono text-xs tracking-widest uppercase hover:bg-signal/80"
          >
            PRINT BRIEF
          </button>
        </div>
      </div>

      {data?.simulated_only && (
        <Caveat>
          SIMULATED DEMONSTRATION: The data for this region is based on Track B simulated interactions. Action recommendations are not based on verified biological proof.
        </Caveat>
      )}

      {data && (
        <div className="flex flex-col gap-8">
          <Panel indexLabel="01 / COMPOUND RISK CARD" className="print:border-gray-300">
            <div className="flex flex-col lg:flex-row gap-12 py-4">
              <div className="flex flex-col gap-4">
                <div className="text-[10px] font-mono tracking-widest text-faint uppercase">Risk Tier</div>
                <div className={`font-display text-6xl ${data.risk_tier === 'HIGH' ? 'text-alert' : 'text-signal'}`}>
                  {data.risk_tier}
                </div>
                <div className="font-mono text-xs text-muted uppercase tracking-widest">
                  REGION: {data.region}
                </div>
              </div>
              
              <div className="flex-1 flex gap-12 border-l border-line/30 pl-12 print:border-gray-300">
                <Readout value={data.interaction_uplift} format="float" caption="INTERACTION UPLIFT" />
                <div className="flex flex-col gap-2">
                  <div className="text-[10px] font-mono tracking-widest text-muted uppercase">Uncertainty Band</div>
                  <div className="font-mono text-lg text-text print:text-black">
                    [{data.uncertainty_lower.toFixed(2)}, {data.uncertainty_upper.toFixed(2)}]
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <div className="text-[10px] font-mono tracking-widest text-muted uppercase">7-Day Forecast (Uplift)</div>
                  <Sparkline data={[0.1, 0.12, 0.15, 0.14, 0.18, 0.22, 0.25]} />
                </div>
              </div>
            </div>
            
            <div className="mt-8 pt-4 border-t border-line/30 print:border-gray-300 flex flex-col gap-2">
              <div className="text-[10px] font-mono tracking-widest text-faint uppercase">Source Findings</div>
              <div className="flex gap-4">
                {data.source_findings.map(id => (
                  <a key={id} href={`/findings/${id}`} className="font-mono text-xs text-signal hover:underline">
                    {id}
                  </a>
                ))}
              </div>
            </div>
          </Panel>

          <Panel indexLabel="02 / REPRODUCIBILITY RECEIPT" className="print:border-gray-300">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 py-4 font-mono text-xs">
              <div className="flex flex-col gap-1">
                <span className="text-faint">RUN ID</span>
                <span className="text-text print:text-black">run_4f9a2b</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-faint">CONFIG HASH</span>
                <span className="text-text print:text-black">a1b2c3d4e5f67890</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-faint">RESULT HASH</span>
                <span className="text-text print:text-black">0987654321fedcba</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-faint">LEDGER BLOCK</span>
                <span className="text-text print:text-black">#42</span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-line/30 print:border-gray-300">
              <img src="/api/v1/qr-code?data=run_4f9a2b" alt="QR Code" className="w-16 h-16 bg-white p-1" onError={(e) => e.currentTarget.style.display = 'none'} />
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
