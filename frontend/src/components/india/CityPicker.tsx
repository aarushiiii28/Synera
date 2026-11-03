import { useEffect, useMemo, useRef, useState } from 'react';

type Option = { id: string; name: string; state: string };

/** Rank: name starts with the text, then name contains it, then state matches. Empty text lists every city, A to Z. */
export function filterCities<T extends Option>(cities: T[], text: string): T[] {
  const s = text.trim().toLowerCase();
  const sorted = [...cities].sort((a, b) => a.name.localeCompare(b.name));
  if (!s) return sorted;
  const rank = (c: T) => (c.name.toLowerCase().startsWith(s) ? 0 : c.name.toLowerCase().includes(s) ? 1 : c.state.toLowerCase().includes(s) ? 2 : 3);
  return sorted.filter((c) => rank(c) < 3).sort((a, b) => rank(a) - rank(b));
}

/** A generic searchable dropdown: click to see every city, type to narrow the list ("amr" shows Amritsar), arrow keys and Enter to choose. */
export function CityPicker({ id, label, cities, selectedId, onPick, className = '', menuClassName = '' }: {
  id: string; label: string; cities: Option[]; selectedId?: string | null; onPick: (id: string) => void; className?: string; menuClassName?: string;
}) {
  const [q, setQ] = useState(''), [open, setOpen] = useState(false), [i, setI] = useState(0);
  const list = useRef<HTMLUListElement>(null);
  const selected = cities.find((c) => c.id === selectedId);
  const hits = useMemo(() => filterCities(cities, q), [q, cities]);
  const choose = (c: Option) => { onPick(c.id); setQ(''); setOpen(false); };
  useEffect(() => { list.current?.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' }); }, [i, open]);
  const last = Math.max(hits.length - 1, 0);
  return (
    <div className={`relative ${className}`}>
      <label className="sr-only" htmlFor={id}>{label}</label>
      <input id={id} role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list" autoComplete="off" value={q}
        placeholder={selected ? `${selected.name}, ${selected.state}` : cities.length ? `Choose a city (${cities.length})` : 'Loading cities…'}
        disabled={!cities.length}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setI(0); }} onFocus={() => setOpen(true)} onClick={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setI((x) => Math.min(x + 1, last)); }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); }
          else if (e.key === 'Enter' && open && hits[i]) { e.preventDefault(); choose(hits[i]); }
          else if (e.key === 'Escape') { setOpen(false); setQ(''); }
        }}
        className={`w-full bg-[var(--in-bg2)] border border-[var(--in-line2)] pl-3 pr-8 py-1.5 text-[13px] placeholder:text-[var(--in-muted)] ${selected ? 'placeholder:text-[var(--in-text)]' : ''}`} />
      <span aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-[var(--in-muted)]">▾</span>
      {open && (
        <ul id={`${id}-list`} ref={list} role="listbox" aria-label="Matching cities" className={`absolute left-0 mt-1 w-full min-w-[15rem] z-40 m-0 p-0 list-none border border-[var(--in-line2)] bg-[#0B1014] shadow-2xl max-h-72 overflow-auto scroll ${menuClassName}`}>
          {hits.length === 0 ? <li className="px-3 py-2 text-[12.5px] text-[var(--in-muted)]">No city matches "{q}". The map covers {cities.length} Indian cities; adding one is one line in the city list (docs/INDIA_LIVE.md).</li>
            : hits.map((c, n) => (
              <li key={c.id} role="option" aria-selected={n === i} onMouseDown={() => choose(c)} onMouseEnter={() => setI(n)}
                className={`px-3 py-2 text-[13px] cursor-pointer flex justify-between gap-3 ${n === i ? 'bg-white/[0.08]' : ''} ${c.id === selectedId ? 'text-[var(--in-accent)]' : ''}`}>
                <span>{c.name}</span><span className="text-[11px] text-[var(--in-faint)]">{c.state}</span>
              </li>))}
        </ul>)}
    </div>
  );
}
