// The 3-minute guided tour, in the order of the project deck: problem -> discovery -> trust -> action.
export interface TourStop { route: string; step: string; title: string; text: string; look: string }

export const TOUR: TourStop[] = [
  { route: '/', step: 'THE PROBLEM', title: 'The environment doesn’t change one variable at a time',
    text: 'Heat, air pollution, drought, weather and radiation act together. Most analysis studies them one by one and misses what happens when they interact.',
    look: 'The strip below shows live counts from the engine, including zero where nothing has earned a higher status.' },
  { route: '/discovery', step: 'STEP 1 · DISCOVER', title: 'The AI engine hunts for hidden interactions',
    text: 'It tests every pair of stressors, then three independent methods look at the results: a statistical model, gradient-boosted trees and a small neural network.',
    look: 'Press “Run engine” to watch the real nine-step pipeline. Then open the response surface: the gap between the dashed and solid contours is the interaction.' },
  { route: '/findings', step: 'STEP 2 · VALIDATE', title: 'Science decides what survives',
    text: 'Each candidate must beat false-discovery control, show a meaningful effect size and a robust confidence interval, and be corroborated by a second method.',
    look: 'Every row shows its status and its provenance. Open a finding to see exactly which gates it passed.' },
  { route: '/trust', step: 'STEP 3 · VERIFY', title: 'Can we trust the evidence? Break it on purpose.',
    text: 'Every dataset, run and finding is fingerprinted and chained in a signed ledger. Tamper with data and the hashes diverge; the result is blocked.',
    look: 'Choose an attack and press “Launch attack”. It runs on a temporary copy. Then verify the real ledger chain: it stays valid.' },
  { route: '/space-biology', step: 'THE TESTBED', title: 'Real NASA space-biology data, honestly reported',
    text: 'Radiation × microgravity in mouse tissue from the NASA Open Science Data Repository. With so few samples per group, only large interactions are detectable.',
    look: 'The volcano plot shows every gene tested. No gene passes false-discovery control, and the page says so plainly.' },
  { route: '/benchmark', step: 'HOW GOOD IS IT?', title: 'The engine’s own report card',
    text: 'On simulated data with a known answer we measure false alarms and misses, including where the engine falls short.',
    look: 'Compare the naive test with the calibrated one: the inflation factor λ is the headline.' },
  { route: '/risk', step: 'STEP 4 · ACT', title: 'From discovery to decision support',
    text: 'Validated interactions turn into a compound-risk brief for a city, with uncertainty, sources and a reproducibility receipt.',
    look: 'The brief is a demonstration: it is built on simulated findings and says so on the page.' },
];
