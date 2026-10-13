import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchBenchmarkResults } from '../../lib/api';
import { Panel } from '../../components/Panel';
import { Caveat } from '../../components/Caveat';
import { Readout } from '../../components/Readout';

export function Benchmark() {
  const { data } = useQuery({ queryKey: ['benchmark'], queryFn: fetchBenchmarkResults });
  
  const fdr = data?.fdr_decomposition?.['snr_20.0']?.strict_fdr || 0;
  const nullCal = data?.null_calibration;

  return (
    <div className="flex flex-col gap-12 p-8 lg:p-12 pb-32 h-full overflow-auto">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-4xl uppercase tracking-tight text-text">Engine Report Card</h1>
        <p className="text-muted font-sans max-w-2xl">
          Empirical validation of the SYNERA pipeline on planted-effect synthetic topologies.
        </p>
      </div>

      <Caveat>
        SIMULATED: All benchmark results are derived from semi-synthetic data (Track B) and do not represent biological proof.
      </Caveat>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <Panel indexLabel="01 / PRECISION" provenance="SIMULATED">
          <Readout value={data?.fdr_decomposition?.['snr_20.0']?.precision || 0} format="float" caption="GLOBAL PRECISION" />
        </Panel>
        <Panel indexLabel="02 / RECALL" provenance="SIMULATED">
          <Readout value={data?.fdr_decomposition?.['snr_20.0']?.recall || 0} format="float" caption="GLOBAL RECALL" />
        </Panel>
        <Panel indexLabel="03 / EMPIRICAL FDR" provenance="SIMULATED" className={fdr > 0.5 ? 'border-alert' : ''}>
          <div className="flex flex-col">
            <Readout value={fdr} format="percent" caption="STRICT FALSE DISCOVERY RATE" />
            {fdr > 0.5 && <div className="text-[10px] text-alert mt-2 font-mono uppercase tracking-widest">WARNING: EXCEEDS 80%</div>}
          </div>
        </Panel>
      </div>

      <div className="flex gap-8">
        <Panel className="flex-1" indexLabel="04 / NULL CALIBRATION (LAMBDA)">
          {nullCal ? (
            <div className="flex flex-col gap-4 font-mono text-xs">
              {(() => {
                const renderRange = (r: any) => typeof r === 'string' ? r : (Array.isArray(r) ? `${r[0]} - ${r[1]}` : 'not computed');
                return (
                  <>
                    <div className="flex justify-between border-b border-line/30 pb-2">
                      <span className="text-muted">Naive (No Covariates)</span>
                      <span className="text-alert">{nullCal.naive_no_covariates?.median?.toFixed(3)} <span className="text-faint">[{renderRange(nullCal.naive_no_covariates?.range)}]</span></span>
                    </div>
                    <div className="flex justify-between border-b border-line/30 pb-2">
                      <span className="text-muted">Naive (With Covariates)</span>
                      <span className="text-alert">{nullCal.naive_with_covariates?.median?.toFixed(3)} <span className="text-faint">[{renderRange(nullCal.naive_with_covariates?.range)}]</span></span>
                    </div>
                    <div className="flex justify-between border-b border-line/30 pb-2">
                      <span className="text-muted">HAC (With Covariates)</span>
                      <span className="text-alert">{nullCal.hac_with_covariates?.median?.toFixed(3)} <span className="text-faint">[{renderRange(nullCal.hac_with_covariates?.range)}]</span></span>
                    </div>
                    <div className="flex justify-between pb-2">
                      <span className="text-muted">Bootstrap (With Covariates)</span>
                      <span className="text-signal">{nullCal.bootstrap_with_covariates?.median?.toFixed(3)} <span className="text-faint">[{renderRange(nullCal.bootstrap_with_covariates?.range)}]</span></span>
                    </div>
                  </>
                );
              })()}
            </div>
          ) : (
            <div className="text-muted text-xs font-mono">NO DATA</div>
          )}
        </Panel>
      </div>
      
      {data?.limitations && (
        <Panel indexLabel="05 / KNOWN LIMITATIONS" className="border-alert">
          <ul className="list-disc list-inside font-mono text-xs text-alert leading-relaxed">
            {data.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}
          </ul>
        </Panel>
      )}
    </div>
  );
}
