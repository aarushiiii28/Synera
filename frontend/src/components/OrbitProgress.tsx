import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

export function OrbitProgress({ size = 120, progress = 0 }: { size?: number; progress?: number }) {
  const c = size / 2;
  const r = size * 0.45;
  const strokeWidth = 1.5;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - progress * circumference;
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={c} cy={c} r={r} fill="none" stroke="var(--line)" strokeWidth={strokeWidth} />
        
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke="var(--signal)"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={shouldReduceMotion ? "" : "transition-all duration-1000 ease-out"}
        />
      </svg>
      
      {/* Orbiting Satellite (only spins if progress < 1 and not reduced motion) */}
      <motion.div 
        className="absolute inset-0 origin-center"
        animate={{ rotate: (progress < 1 && !shouldReduceMotion) ? 360 : 0 }}
        transition={{ duration: 4, repeat: (progress < 1 && !shouldReduceMotion) ? Infinity : 0, ease: 'linear' }}
      >
        <div 
          className="absolute rounded-full bg-signal"
          style={{
            width: 4, height: 4,
            left: c - 2, top: c - r - 2,
            boxShadow: '0 0 8px 1px var(--signal)'
          }}
        />
      </motion.div>
      
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-mono text-xs text-signal">{Math.round(progress * 100)}%</span>
      </div>
    </div>
  );
}
