# SYNERA design system: "mission control meets planetary observatory"

The interface has three jobs: look like it belongs in space, be understandable in thirty seconds by someone who has never heard of an FDR, and never overstate what the science shows.

## Look

* **Light source and depth.** The planet is the hero. A real NASA Earth (day side, city lights, clouds) is lit by a fixed sun with a visible terminator, a Fresnel atmosphere, a sunrise glare behind the top limb and eight pulsing city markers (`Earth.tsx`, textures in `public/textures`). Behind every page: a seeded star field, a latitude/longitude graticule limb cropped off the corner, a warm glow at the horizon and a vignette. Never a flat colour and never a square grid.
* **Instrument details.** 1px hairlines, a maximum 2px corner radius, crop-mark corner brackets on grouped data, tabular monospaced numerals for every number, slow ambient motion only (orbit, pulse, packets on the pipeline), count-up on first mount.
* **Typography.** Sora (display; wordmark light 300 with 0.24em tracking, headings 600 uppercase), IBM Plex Sans (reading), IBM Plex Mono (data, hashes, labels), Instrument Serif italic for a few editorial words per page only.

## Colour semantics (never deviate)

| Token | Hex | Meaning |
|---|---|---|
| `--void` / `--abyss` / `--hull` | `#02060d` / `#061424` / `#0b2037` | space, app background, panels |
| `--signal` | `#16b5ff` | interactive, antagonistic, candidate |
| `--biosphere` | `#6fd65b` | synergistic, verified, REAL data |
| `--solar` | `#ffb547` | non-linear, caution, SIMULATED data |
| `--alert` | `#ff4d5e` | blocked, tamper, signal lost |
| `--teal` | `#19e3b1` | validated |
| `--sun` | `#ffd9a0` | sunrise accent and the one serif phrase per page |

Status is always **text + glyph**, never colour alone: CANDIDATE ◯, VALIDATED ◐, VERIFIED ● with check, BLOCKED ⃠ (hatched surface), REJECTED —.
`REAL` = green dot, `SIMULATED` = amber dot with the word, on every relevant panel.

## Understandability rules

1. **Every page opens with a plain-language standfirst** and, where a chart follows, an *In plain words* callout (`Explainer`).
2. **Jargon is explained where it appears.** `<Term k="fdr">` shows a one-sentence definition on hover or keyboard focus. Definitions live in `lib/glossary.ts`.
3. **Navigation is always labelled** (rail with title and a one-line subtitle). Pipeline words DISCOVER / VALIDATE / VERIFY / ACT mark the matching pages.
4. **A guided 3-minute tour** (`lib/tour.ts`, `Tour.tsx`) walks the deck order and navigates for the visitor.
5. **Empty is a designed state.** Zero is shown as zero (“0 verified”). Panels never go blank: skeleton scanning bars while loading, a designed explanation when empty, a SIGNAL LOST state when the API is down.
6. **Caveats are not optional UI.** `Caveat` banners render wherever they apply: SIMULATED, CROSS-TISSUE · SAME COHORT, INTERNAL REPLICATION, HYPOTHESIS ONLY, LOW POWER, and the definition of VERIFIED.

## Banned

Purple or indigo gradients, glassmorphism, soft rounded cards with large shadows, emoji icons, a centred SaaS hero, a stock three-column feature grid, lorem ipsum, any number that is not computed from data, identical bordered boxes repeated down a page (vary `Panel` treatments: `bracketed`, `ruled`, `inset`, `bare`, `alert`).

## Components (`src/components`)

`Earth`, `StressorBeams`, `Backdrop` (stars + graticule), `Rail`/`BottomBar`, `TopBar` (states CHECKING / LIVE / OFFLINE), `Tour`, `Panel`, `PageHeader`, `Readout`, `StatusChip`, `ProvenanceTag`/`EvidenceTag`, `HashRing`/`HashGlyph`, `Term`, `Explainer`/`Caveat`, `Skeleton`/`EmptyState`/`ErrorState`/`Async`. The dev-only route `/_design` renders each of them (values labelled SPECIMEN, NOT DATA).

## Accessibility and motion

Body contrast ≥ 4.5:1, visible focus ring in `--signal`, `jsx-a11y` clean, keyboard-reachable tooltips and tour, `prefers-reduced-motion` removes the globe rotation (static NASA disc), beams, pulses and sweeps. Mobile: the rail becomes a bottom bar and charts reflow; nothing scrolls horizontally.

## Data honesty in the UI

Numbers come from the API only (`lib/api.ts` mirrors `docs/API_CONTRACT.md`). No `?? 6` style fallbacks: while loading or offline the page shows a designed state. Large probabilities are formatted with `sci()`; p and q are scientific notation; units are always shown.
