// End-to-end smoke test against a running stack (API :8000 + web :5173). `npm run e2e`.
// Observatory counts -> engine run (recorded, quick) -> finding -> re-verify (SIMULATED cap) -> tamper -> real ledger still valid.
const { chromium } = require('playwright');
const base = process.env.E2E_BASE || 'http://localhost:5173';
const fail = (m) => { console.error('FAIL:', m); process.exitCode = 1; };
const ok = (m) => console.log('ok  ', m);

(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => m.type() === 'error' && !/502|Failed to load resource/.test(m.text()) && errors.push(m.text()));

  await page.goto(base + '/', { waitUntil: 'networkidle' });
  await page.getByText('API LIVE').waitFor({ timeout: 15000 }).then(() => ok('top bar reports API LIVE'), () => fail('API LIVE not shown'));
  await page.getByText(/^verified$/i).first().waitFor({ timeout: 15000 }).then(() => ok('pipeline strip shows the VERIFIED count'), () => fail('no verified readout'));

  await page.goto(base + '/discovery', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /run the engine/i }).click();
  await page.getByText(/FINALIZE|Assign statuses/i).first().waitFor({ timeout: 240000 }).then(() => ok('engine run reached FINALIZE'), () => fail('engine run did not finish'));

  await page.goto(base + '/findings', { waitUntil: 'networkidle' });
  const row = page.locator('a[href^="/findings/"]').first();
  await row.waitFor({ timeout: 15000 }).then(() => ok('registry lists findings'), () => fail('no findings listed'));
  await row.click();
  await page.getByRole('button', { name: /re-verify/i }).click();
  await page.getByText(/SIMULATED provenance cap/i).first().waitFor({ timeout: 20000 }).then(() => ok('re-verify explains the SIMULATED cap'), () => fail('SIMULATED cap not shown'));

  await page.goto(base + '/trust', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /launch attack/i }).click();
  await page.getByText(/RESULT BLOCKED FROM VERIFIED STATUS/i).first().waitFor({ timeout: 60000 }).then(() => ok('tamper simulation ends BLOCKED'), () => fail('no BLOCKED verdict'));
  await page.getByText(/REAL LEDGER STILL VALID/i).first().waitFor({ timeout: 30000 }).then(() => ok('real ledger still VALID after the attack'), () => fail('ledger validity not shown'));

  if (errors.length) fail('console errors: ' + [...new Set(errors)].slice(0, 5).join(' | '));
  await browser.close();
  console.log(process.exitCode ? 'E2E FAILED' : 'E2E PASSED');
})();
