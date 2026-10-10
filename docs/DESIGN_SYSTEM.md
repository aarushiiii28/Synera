# SYNERA Design System

## Theme & Aesthetic Concept
**"Mission control meets planetary observatory"**
The SYNERA frontend must not look like a generic B2B SaaS dashboard. It draws inspiration from deep-space navigation interfaces, planetary observatories, and high-fidelity scientific instruments.

- **Vibe**: Technical, rigorous, luminous, asymmetrical, and editorial.
- **Banned Patterns**: Glassmorphism, 24px border radii, large soft drop shadows, default shadcn aesthetics, emoji icons, stock 3-column feature grids, lorem ipsum placeholders, or fake/seeded numbers.
- **Required Details**: 1px hairline borders, max 2px corner radius, corner "crop-mark" brackets on panels, latitude/longitude graticule backgrounds, strict tabular monospaced numerals for data, purposeful slow motion (orbits, data packet pulses).

## Tokens (`src/design/tokens.css`)

### Colors
- `--void`: `#050D18` (Deepest background)
- `--abyss`: `#081B2E` (App background)
- `--hull`: `#0D2540` (Panels)
- `--hull-2`: `#123152` (Hover states, secondary panels)
- `--line`: `rgba(110, 190, 255, 0.16)` (Borders, graticule)
- `--line-strong`: `rgba(110, 190, 255, 0.34)` (Active borders)
- `--text`: `#E8F1FA` (Primary text)
- `--muted`: `#7F98B2` (Secondary text)
- `--faint`: `#4B6480` (Disabled/faint elements)
- `--signal`: `#16B5FF` (Cyan: primary/interactive, antagonistic, CANDIDATE outline)
- `--biosphere`: `#6FD65B` (Green: synergistic, VERIFIED filled, REAL data)
- `--solar`: `#FFB547` (Amber: nonlinear, caution, SIMULATED data)
- `--alert`: `#FF4D5E` (Red: blocked, tampered)
- `--teal`: `#19E3B1` (VALIDATED state)

### Typography
- **Display**: `Sora` (Wordmark light 300 tracked 0.18em; Headings 600 uppercase tight)
- **Body**: `IBM Plex Sans` (Readable, scientific, contrast >= 4.5:1)
- **Data/Hash**: `IBM Plex Mono` (Always tabular-nums via `font-variant-numeric: tabular-nums`)
- **Scale**: 12, 14, 16, 20, 28, 44, 72.

## Core Components
1. **Panel**: A container with a hairline `--line` border, 4 corner SVG brackets, optional mini index header (e.g. `02 / DISCOVERY`), and optional provenance tag.
2. **StatusChip**: Text + semantic glyph (e.g., outline circle for CANDIDATE, half-filled for VALIDATED, sealed check for VERIFIED, slashed hatch for BLOCKED).
3. **HashRing**: A deterministic circular SVG representation of any SHA256 string. Radiating lines interpolating from signal to biosphere based on byte value.
4. **Readout**: Large tabular mono numeral, tiny caption, optional delta. Number increments on mount.
5. **OrbitProgress**: Circular loader with a tiny orbiting satellite dot.
6. **TelemetryBar**: Top structural bar showing ledger height, chain state, API status, and UTC time.
7. **Caveat**: Banner explicitly stating data limitations (e.g., "SIMULATED provenance cap").
8. **Navigation Rail**: 72px left rail containing 7 custom 1.5px-stroke SVGs for the routes.

## Layout & Routing
- Left Rail: Observatory, Discovery, Findings, Space Biology, Trust Center, Benchmark, Risk Assessment.
- Top: TelemetryBar.
- Canvas: Graticule background pattern, asymmetrical layout.
- The `/_design` route renders all components in all states for visual review.

## New Layout Rules (Part 7B)
- **BANNED**: Identical bordered boxes repeated across a page, mono-uppercase for every label, flat single-colour backgrounds.
- **Graticule**: Use an orthographic projection graticule + seeded starfield for background depth.
- **Typography**: `Instrument Serif italic` is the sole accent face for editorial emphasis. Never use for data or UI labels.
- **Panels**: Use open space, direct annotation, and hairline rules. `<Panel>` variants include `bracketed`, `ruled`, `inset`, and `bare`.
- **Readout**: Features 1px baseline rules, larger tabular numerals, and thin unit labels. Animate (count-up) on mount only.
- **Transitions**: Horizontal scan line sweeps with staggered fade-ups. Respect `prefers-reduced-motion` for all ambient animations (globe, graticule rotate, pulses).
