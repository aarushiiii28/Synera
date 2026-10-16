import { useEffect, useState } from 'react';
import { isStatic, snapshotMeta } from '../lib/snapshot';

/** Shown only on the hosted, server-less build: says plainly that results are recorded, not computed live. */
export function StaticBanner() {
  const [when, setWhen] = useState<string | null>(null);
  useEffect(() => {
    if (isStatic) snapshotMeta().then((m) => setWhen(m.generated_at), () => setWhen(null));
  }, []);
  if (!isStatic) return null;
  return (
    <div role="note" className="no-print border-b border-solar/50 bg-solar/10 px-4 md:px-10 py-2 text-[12px] leading-snug text-text/90">
      <span className="num tracking-[0.14em] text-solar mr-2">RECORDED DEMO</span>
      Every number, chart and hash here is a real result recorded from the SYNERA engine{when ? ` on ${when}` : ''}. “Run the engine”, “Launch attack” and “Re-verify” replay those recordings; nothing is computed live in this hosted version. Run it locally to compute for real.
    </div>
  );
}
