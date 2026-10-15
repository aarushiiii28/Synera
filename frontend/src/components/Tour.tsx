import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { TOUR } from '../lib/tour';
import { useUI } from '../store';

/** Non-blocking guided tour: a card that walks through the deck order and navigates for you. */
export function Tour() {
  const step = useUI((s) => s.tourStep);
  const go = useUI((s) => s.goTour);
  const nav = useNavigate();
  useEffect(() => { if (step !== null) nav(TOUR[step].route); }, [step, nav]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (step !== null && e.key === 'Escape') go(null); };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [step, go]);
  if (step === null) return null;
  const t = TOUR[step];
  return (
    <aside role="dialog" aria-label="Guided tour" className="fixed z-[60] bottom-4 right-4 left-4 md:left-auto md:w-[26rem] border border-signal/60 bg-void/95 p-5 crop no-print">
      <div className="flex items-center gap-2 mb-2">
        <span className="num text-[10px] tracking-[0.16em] text-signal">STOP {step + 1} OF {TOUR.length}</span>
        <span className="num text-[10px] tracking-[0.16em] text-biosphere">{t.step}</span>
        <div className="flex-1" />
        <button onClick={() => go(null)} className="num text-[11px] text-faint hover:text-text" aria-label="Close tour">ESC ✕</button>
      </div>
      <h2 className="display text-lg font-semibold leading-snug m-0 mb-2">{t.title}</h2>
      <p className="text-sm text-muted leading-relaxed m-0">{t.text}</p>
      <p className="text-sm mt-3 mb-4 border-l-2 border-solar pl-3 text-text/90 leading-relaxed"><span className="label !text-solar block mb-0.5">What to look at</span>{t.look}</p>
      <div className="flex items-center gap-2">
        <div className="flex gap-1 flex-1" aria-hidden>
          {TOUR.map((_, i) => <span key={i} className={`h-0.5 flex-1 ${i <= step ? 'bg-signal' : 'bg-line'}`} />)}
        </div>
        <button disabled={step === 0} onClick={() => go(step - 1)} className="num text-xs border border-line px-3 py-1.5 disabled:opacity-30 hover:border-signal">BACK</button>
        {step < TOUR.length - 1
          ? <button onClick={() => go(step + 1)} className="num text-xs border border-signal bg-signal/10 text-signal px-3 py-1.5 hover:bg-signal/20">NEXT →</button>
          : <button onClick={() => go(null)} className="num text-xs border border-biosphere bg-biosphere/10 text-biosphere px-3 py-1.5">FINISH</button>}
      </div>
    </aside>
  );
}
