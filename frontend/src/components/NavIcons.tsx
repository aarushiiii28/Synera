import React from 'react';

// Custom SVG navigation icons
export const IconObservatory = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
    <circle cx="12" cy="12" r="5" />
    <ellipse cx="12" cy="12" rx="10" ry="3" transform="rotate(-30 12 12)" />
  </svg>
);

export const IconDiscovery = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
    <path d="M4 12h16M12 4v16M8 8l8 8M8 16l8-8" />
    <circle cx="12" cy="12" r="2" fill="currentColor" />
  </svg>
);

export const IconFindings = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
    <rect x="3" y="4" width="18" height="16" rx="1" />
    <path d="M7 8h10M7 12h10M7 16h6" />
  </svg>
);

export const IconBiology = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
    <path d="M6 4c0 8 12 8 12 16M18 4c0 8-12 8-12 16" />
    <line x1="8" y1="8" x2="16" y2="8" />
    <line x1="8" y1="16" x2="16" y2="16" />
    <line x1="12" y1="12" x2="12" y2="12" />
  </svg>
);

export const IconTrust = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <circle cx="12" cy="11" r="3" />
  </svg>
);

export const IconBenchmark = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2" />
  </svg>
);

export const IconRisk = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6">
    <path d="M4 18h16M4 14l4-4 4 4 4-4 4 4" />
  </svg>
);
