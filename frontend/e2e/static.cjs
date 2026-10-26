// End-to-end check of the RECORDED DEMO (the free, server-less build): run it against `npm run preview` with the API switched OFF.
//   npm run build:vercel && npm run preview -- --port 4174     then     E2E_BASE=http://localhost:4174 node e2e/static.cjs
const { chromium } = require('playwright');
const base = process.env.E2E_BASE || 'http://localhost:4174';
let bad = 0;
const ok = (m) => console.log('ok  ', m);
const fail = (m) => { bad++; console.log('FAIL', m); };

(async () => {
  const browser = await chromium.launch();
  const p = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message));
  p.on('console', (m) => m.type() === 'error' && errs.push('CONSOLE ' + m.text().slice(0, 140)));
  p.on('requestfailed', (r) => errs.push('REQFAIL ' + r.url()));
  const see = (re, t = 20000) => p.getByText(re).first().waitFor({ state: 'visible', timeout: t }).then(() => true, () => false);

  await p.goto(base + '/', { waitUntil: 'networkidle' });
  (await see(/RECORDED DEMO/)) ? ok('top bar says RECORDED DEMO') : fail('top bar');
  (await see(/nothing is computed live/i)) ? ok('the notice says results are recorded, not computed live') : fail('notice');

  await p.goto(base + '/discovery', { waitUntil: 'networkidle' });
  await p.getByRole('button', { name: /run the engine/i }).click();
  (await see(/Assign statuses|FINALIZE/i, 30000)) ? ok('"Run the engine" replays the recorded nine steps') : fail('engine steps');

  await p.goto(base + '/findings', { waitUntil: 'networkidle' });
  (await p.locator('a[href^="/findings/"]').count()) >= 6 ? ok('findings registry lists the 3 recorded findings') : fail('findings');
  await p.locator('a[href^="/findings/"]').first().click();
  await p.getByRole('button', { name: /re-verify/i }).click();
  (await see(/SIMULATED provenance cap/i)) ? ok('re-verify replays the recorded SIMULATED cap') : fail('re-verify');

  await p.goto(base + '/trust', { waitUntil: 'networkidle' });
  await p.getByRole('button', { name: /replay recorded attack/i }).click();
  (await see(/RESULT BLOCKED FROM VERIFIED STATUS/i, 30000)) ? ok('an attack replays and ends BLOCKED') : fail('attack');
  (await see(/REAL LEDGER STILL VALID/i)) ? ok('the recorded ledger check is valid') : fail('ledger valid');
  await p.getByRole('button', { name: /recompute and compare/i }).click();
  (await see(/HASHES MATCH/i)) ? ok('the integrity check answers') : fail('integrity');

  await p.goto(base + '/space-biology', { waitUntil: 'networkidle' });
  await p.getByLabel(/find a gene/i).fill('Gm11520'); await p.getByRole('button', { name: /highlight/i }).click();
  (await p.getByRole('button', { name: /Gm11520/ }).first().waitFor({ timeout: 30000 }).then(() => true, () => false)) ? ok('gene search works from the recorded gene table') : fail('gene search');

  await p.goto(base + '/risk', { waitUntil: 'networkidle' });
  for (const c of ['Ludhiana', 'Delhi', 'Jakarta']) { await p.getByText(c, { exact: true }).first().click(); await p.waitForTimeout(500); (await p.locator('main').innerText()).includes('Reproducibility receipt') ? ok('risk brief: ' + c) : fail('risk ' + c); }

  await p.goto(base + '/scenario', { waitUntil: 'networkidle' });
  (await see(/About .*% (more|fewer) deaths|No clear effect/)) ? ok('Scenario Lab shows an estimate') : fail('scenario');

  await p.goto(base + '/discovery', { waitUntil: 'networkidle' });
  await p.getByRole('radio').filter({ hasText: /electricity demand x weather \(8 large/i }).first().click();
  (await see(/Does it repeat in other states/i)) ? ok('India grid: the cross-state check is shown') : fail('india cross-check');
  (await see(/pairs? kept in both panels/i)) ? ok('India grid: pairs kept in both panels are counted') : fail('india counts');
  (await see(/What a standard screen would have reported/i)) ? ok('the standard-screen audit is shown') : fail('audit');

  errs.length ? fail('errors: ' + [...new Set(errs)].slice(0, 3).join(' | ')) : ok('no console errors and no failed requests');
  await browser.close();
  console.log(bad ? 'STATIC E2E FAILED (' + bad + ')' : 'STATIC E2E PASSED');
  process.exitCode = bad ? 1 : 0;
})().catch((e) => { console.log('ABORT', e.message); process.exitCode = 1; });
