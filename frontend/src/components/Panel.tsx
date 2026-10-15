import type { ReactNode } from 'react';
import { ProvenanceTag } from './Provenance';
import type { Provenance } from '../lib/api';

type Variant = 'bracketed' | 'ruled' | 'bare' | 'inset' | 'alert';

interface Props {
  title?: string;
  index?: string;
  provenance?: Provenance;
  right?: ReactNode;
  variant?: Variant;
  className?: string;
  children: ReactNode;
  padded?: boolean;
}

/** Container with several treatments so no two neighbouring areas look the same. Max radius 2px, no shadows. */
export function Panel({ title, index, provenance, right, variant = 'bracketed', className = '', children, padded = true }: Props) {
  const base: Record<Variant, string> = {
    bracketed: 'crop border border-line bg-hull/40',
    ruled: 'border-t border-line-strong',
    bare: '',
    inset: 'border border-line bg-void/60',
    alert: 'crop border border-alert/60 hatch-alert bg-void/60',
  };
  const header = (title || index || provenance || right) && (
    <header className="flex items-center gap-3 px-4 pt-3 pb-2">
      {index && <span className="num text-[11px] text-signal">{index}</span>}
      {title && <h3 className="label !text-muted m-0">{title}</h3>}
      <div className="flex-1" />
      {provenance && <ProvenanceTag provenance={provenance} />}
      {right}
    </header>
  );
  return (
    <section className={`${base[variant]} ${className}`}>
      {header}
      <div className={padded ? (variant === 'ruled' || variant === 'bare' ? 'pt-3' : 'p-4 pt-2') : ''}>{children}</div>
      {variant === 'bracketed' || variant === 'alert' ? <span className="crop-b" aria-hidden /> : null}
    </section>
  );
}
