import { legendColor, type LayerDef, type LayerId } from '../../lib/india';

/** Explains the active layer's colours; the same stops draw the map. */
export function Legend({ layer }: { layer: LayerDef }) {
  const id = layer.id as LayerId;
  return (
    <div className="border border-[var(--in-line2)] bg-[#0B1014]/90 px-3 py-2.5 w-[250px] max-w-full" aria-label={`Legend: ${layer.label}`}>
      <div className="flex items-baseline justify-between"><span className="lbl">{layer.label}</span><span className="num text-[10px] text-[var(--in-faint)]">{layer.unit}</span></div>
      <div className="mt-2 flex">
        {layer.legend.map(([lo, hi, name]) => <div key={name} className="flex-1 h-2" style={{ background: legendColor(id, lo, hi) }} title={`${name}: ${lo} to ${hi}`} />)}
      </div>
      <div className="mt-1 flex">
        {layer.legend.map(([lo, , name]) => <div key={name} className="flex-1 min-w-0"><div className="num text-[9.5px] text-[var(--in-muted)]">{lo}</div><div className="text-[9px] leading-tight text-[var(--in-faint)] truncate" title={name}>{name}</div></div>)}
      </div>
      <details className="mt-2"><summary className="cursor-pointer text-[10.5px] text-[var(--in-accent)]">About this layer</summary>
        <p className="m-0 mt-1 text-[10.5px] leading-snug text-[var(--in-faint)]">{layer.note} Colour between cities is interpolated for readability and fades where no city is near; it is not a measurement.</p></details>
    </div>
  );
}
