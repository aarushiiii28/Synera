import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../../lib/api';
import type { LiveStatus } from '../../lib/live';

const TONE: Record<LiveStatus['state'], string> = { CONNECTED: 'var(--biosphere)', CONNECTING: 'var(--signal)', RECONNECTING: 'var(--solar)', ERROR: 'var(--alert)', DISCONNECTED: 'var(--faint)', TEST_MODE: 'var(--faint)' };
const LABEL: Record<LiveStatus['state'], string> = { CONNECTED: 'CONNECTED', CONNECTING: 'CONNECTING', RECONNECTING: 'RECONNECTING', ERROR: 'ERROR', DISCONNECTED: 'DISCONNECTED', TEST_MODE: 'DISCONNECTED' };

export const StateDot = ({ state, receiving }: { state: LiveStatus['state']; receiving?: boolean }) => (
  <span className="inline-flex items-center gap-2 num text-[11px] tracking-[0.16em]" style={{ color: TONE[state] }}>
    <span aria-hidden className={`w-2 h-2 rounded-full ${state === 'CONNECTED' && receiving ? 'pulse-soft' : ''}`} style={{ background: TONE[state] }} />{LABEL[state]}
  </span>
);

const errText = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : 'Something went wrong');

export function ConnectionPanel({ status, apiError }: { status: LiveStatus | null; apiError: string | null }) {
  const qc = useQueryClient();
  const ports = useQuery({ queryKey: ['live-ports'], queryFn: api.livePorts, retry: false, enabled: !apiError });
  const [port, setPort] = useState('');
  const [baud, setBaud] = useState(9600);
  const [msg, setMsg] = useState<string | null>(null);
  const list = ports.data?.ports ?? [];
  const chosen = port || list.find((p) => /ch340|arduino|usb serial|usb-serial|uno/i.test(p.description + p.manufacturer))?.device || list[0]?.device || '';
  const done = (s: LiveStatus) => { qc.setQueryData(['live-status'], s); setMsg(s.state === 'ERROR' ? s.last_error : null); };
  const connect = useMutation({ mutationFn: () => api.liveConnect(chosen, baud), onSuccess: done, onError: (e) => setMsg(errText(e)) });
  const disconnect = useMutation({ mutationFn: api.liveDisconnect, onSuccess: done, onError: (e) => setMsg(errText(e)) });
  const seal = useMutation({ mutationFn: api.liveSeal, onSuccess: () => { setMsg(null); qc.invalidateQueries({ queryKey: ['live-status'] }); }, onError: (e) => setMsg(errText(e)) });
  const st = status;
  const live = !!st && ['CONNECTED', 'CONNECTING', 'RECONNECTING', 'ERROR'].includes(st.state);
  const hw = st?.state === 'CONNECTED' || st?.state === 'CONNECTING' || st?.state === 'RECONNECTING';
  const field = 'bg-void border border-line px-3 py-2 text-[14px] text-text w-full';
  return (
    <div className="grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-8">
      <div>
        {apiError && <div role="alert" className="hatch-alert border border-alert/60 px-4 py-3 mb-4 text-sm"><div className="num text-alert text-xs tracking-[0.16em]">API UNREACHABLE</div>{apiError} Start the API (dev.cmd) to talk to the device.</div>}
        <div className="grid sm:grid-cols-[1fr_8rem] gap-3">
          <label className="grid gap-1"><span className="label">Serial port</span>
            <select className={field} value={chosen} onChange={(e) => setPort(e.target.value)} disabled={live} aria-label="Serial port">
              {list.length === 0 && <option value="">No serial ports found</option>}
              {list.map((p) => <option key={p.device} value={p.device}>{p.device} · {p.description || 'serial device'}</option>)}
            </select></label>
          <label className="grid gap-1"><span className="label">Baud rate</span>
            <select className={field} value={baud} onChange={(e) => setBaud(Number(e.target.value))} disabled={live} aria-label="Baud rate">
              {(ports.data?.bauds ?? [9600]).map((b) => <option key={b} value={b}>{b}</option>)}</select></label>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          <button type="button" onClick={() => ports.refetch()} disabled={ports.isFetching || !!apiError || live} className="num text-xs tracking-[0.12em] border border-line px-3 py-2 hover:border-signal disabled:opacity-40">{ports.isFetching ? 'SCANNING' : 'REFRESH PORTS'}</button>
          {!hw && st?.state !== 'ERROR'
            ? <button type="button" onClick={() => { setMsg(null); connect.mutate(); }} disabled={!chosen || connect.isPending || !!apiError} className="num text-xs tracking-[0.16em] border border-signal bg-signal/10 text-signal px-4 py-2 hover:bg-signal/20 disabled:opacity-40">{connect.isPending ? 'OPENING PORT…' : 'CONNECT'}</button>
            : <button type="button" onClick={() => disconnect.mutate()} disabled={disconnect.isPending} className="num text-xs tracking-[0.16em] border border-alert/70 text-alert px-4 py-2 hover:bg-alert/10">DISCONNECT</button>}
        </div>
        {ports.data && !ports.data.available && <p className="text-[13px] text-solar mt-3 mb-0">{ports.data.note}</p>}
        {ports.data?.available && list.length === 0 && <p className="text-[13px] text-muted mt-3 mb-0">No serial port is visible. Plug the Arduino into a USB port, wait a few seconds, then refresh. If it still does not appear, try another cable: some are charge-only.</p>}
        {msg && <p role="alert" className="text-[13px] text-alert mt-3 mb-0 break-words">{msg}</p>}
        <p className="text-[12px] text-faint mt-4 mb-0 leading-relaxed">A COM port can be opened by one program at a time. Close the Arduino IDE Serial Monitor before you connect. A detected port is not proof of a working device: the status below turns to CONNECTED only when valid packets arrive.</p>
      </div>
      <div>
        <div className="flex items-center gap-3 mb-3"><StateDot state={st?.state ?? 'DISCONNECTED'} receiving={st?.receiving} />{st?.state === 'CONNECTED' && <span className="num text-[10px] text-muted">{st.receiving ? 'receiving data' : 'no data in the last seconds'}</span>}</div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 m-0 text-[13px]">
          <div><dt className="label">Device</dt><dd className="m-0 num text-muted break-all">{st?.device_id ?? '—'}</dd></div>
          <div><dt className="label">Port / baud</dt><dd className="m-0 num text-muted">{st?.port ? `${st.port} · ${st.baud}` : '—'}</dd></div>
          <div><dt className="label">Valid packets</dt><dd className="m-0 num text-text">{st?.packets_ok ?? 0}</dd></div>
          <div><dt className="label">Rejected lines</dt><dd className="m-0 num" style={{ color: st && st.packets_rejected ? 'var(--solar)' : 'var(--muted)' }}>{st?.packets_rejected ?? 0}</dd></div>
          <div><dt className="label">Last packet</dt><dd className="m-0 num text-muted">{st?.last_packet_utc ? new Date(st.last_packet_utc).toLocaleTimeString() : '—'}</dd></div>
          <div><dt className="label">Data source</dt><dd className="m-0 num text-muted">{st?.source ? 'Arduino sensors' : '—'}</dd></div>
        </dl>
        <p className="text-[13px] text-muted mt-3 mb-0 break-words" aria-live="polite">{st?.message ?? 'Not connected.'}</p>
        {st?.last_error && st.state !== 'ERROR' && <p className="text-[12px] text-solar mt-1 mb-0 break-words">{st.last_error}</p>}
        <div className="border-t border-line mt-5 pt-4 grid gap-3">
          {(st?.session || st?.last_session) && (
            <div className="text-[12.5px] text-muted">
              <span className="label block mb-1">Session evidence</span>
              {(st.session ?? st.last_session)!.rows} readings in <span className="num text-text">{(st.session ?? st.last_session)!.file}</span>.{' '}
              {st.last_session?.sealed ? <span className="text-biosphere">Sealed in the ledger (block {st.last_session.ledger_block}).</span> : <button type="button" onClick={() => seal.mutate()} disabled={seal.isPending} className="text-signal underline bg-transparent border-0 p-0 cursor-pointer">Seal this session in the ledger</button>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
