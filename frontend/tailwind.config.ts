import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        void: 'var(--void)', abyss: 'var(--abyss)', hull: 'var(--hull)', 'hull-2': 'var(--hull-2)',
        line: 'var(--line)', 'line-strong': 'var(--line-strong)',
        text: 'var(--text)', muted: 'var(--muted)', faint: 'var(--faint)',
        signal: 'var(--signal)', biosphere: 'var(--biosphere)', solar: 'var(--solar)', alert: 'var(--alert)',
        teal: 'var(--teal)', sun: 'var(--sun)',
      },
      borderRadius: { DEFAULT: '2px', sm: '2px', md: '2px', lg: '2px' },
      fontFamily: {
        display: ['Sora', 'sans-serif'],
        sans: ['IBM Plex Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
        serif: ['Instrument Serif', 'serif'],
      },
      boxShadow: {
        glow: '0 0 28px -6px rgba(22,181,255,.55)',
        bio: '0 0 28px -6px rgba(111,214,91,.5)',
        sun: '0 0 40px -8px rgba(255,181,71,.55)',
      },
      fontSize: { hero: ['clamp(2.6rem, 5.4vw, 5.2rem)', { lineHeight: '1.02', letterSpacing: '-0.01em' }] },
    },
  },
  plugins: [],
} satisfies Config
