import type { ReactNode } from 'react';
import { ApiError } from '../lib/api';

/** Scanning-bar skeleton (not a spinner). */
export function Skeleton({ h = 120, label = 'ACQUIRING SIGNAL' }: { h?: number; label?: string }) {
  return (
    <div className="relative overflow-hidden border border-line bg-void/40" style={{ height: h }} role="status" aria-label={label}>
      <div className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-signal/15 to-transparent" style={{ animation: 'sweep 1.6s linear infinite' }} />
      <div className="absolute left-3 top-2 label">{label}</div>
    </div>
  );
}

export function EmptyState({ title, children, action, tone = 'signal' }: { title: string; children: ReactNode; action?: ReactNode; tone?: 'signal' | 'solar' | 'biosphere' }) {
  return (
    <div className="border border-dashed border-line-strong px-6 py-8 text-center bg-void/30">
      <div className="mx-auto mb-3 w-8 h-8 rounded-full border" style={{ borderColor: `var(--${tone})`, boxShadow: `0 0 18px -4px var(--${tone})` }} aria-hidden />
      <div className="display text-lg mb-1">{title}</div>
      <div className="text-muted text-sm max-w-md mx-auto leading-relaxed">{children}</div>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const offline = error instanceof ApiError && error.status === 0;
  return (
    <div className="hatch-alert border border-alert/60 px-6 py-6" role="alert">
      <div className="num text-alert text-xs tracking-[0.16em] mb-1">{offline ? 'SIGNAL LOST' : 'REQUEST FAILED'}</div>
      <div className="text-sm text-text mb-3">
        {offline ? 'The SYNERA API is not reachable. Start it with  make api  and this page will recover.' : (error as Error)?.message ?? 'Unknown error'}
      </div>
      {retry && <button onClick={retry} className="num text-xs border border-alert px-3 py-1.5 text-alert hover:bg-alert/10">RETRY</button>}
    </div>
  );
}

/** Wrap a react-query result: skeleton while loading, designed error, otherwise render children. */
export function Async<T>({ q, h = 160, children }: { q: { isLoading: boolean; isError: boolean; error: unknown; data: T | undefined; refetch: () => unknown }; h?: number; children: (d: T) => ReactNode }) {
  if (q.isLoading) return <Skeleton h={h} />;
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (q.data === undefined) return null;
  return <>{children(q.data)}</>;
}
