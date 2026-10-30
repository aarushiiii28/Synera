// End-to-end check of the Live Stress Lab against the running app (API + web).
//   node e2e/live.cjs                      page and empty states (no device needed)
//   LIVE_HARDWARE=1 node e2e/live.cjs      additionally connects the REAL Arduino (needs it plugged in and the Serial Monitor closed)
const { chromium } = require('playwright');
const base = process.env.E2E_BASE || 'http://localhost:5173';
const hw = process.env.LIVE_HARDWARE === '1';
let bad = 0;
const ok = (m) => console.log('ok  ', m);
const fail = (m) => { bad++; console.log('FAIL', m); };

(async () => {
  const browser = await chromium.launch();
  const p = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message));
  p.on('console', (m) => m.type() === 'error' && !/EventSource|net::ERR/i.test(m.text()) && errs.push('CONSOLE ' + m.text().slice(0, 140)));
  const see = (re, t = 15000) => p.getByText(re).first().waitFor({ state: 'visible', timeout: t }).then(() => true, () => false);

  await p.goto(base + '/live-stress-lab', { waitUntil: 'networkidle' });
  await p.evaluate(() => fetch('/api/v1/live/disconnect', { method: 'POST' })).catch(() => {});
  await p.reload({ waitUntil: 'networkidle' });
  (await see(/Live air/)) ? ok('page loads') : fail('heading');
  (await p.getByRole('link', { name: /Live Stress Lab/ }).count()) ? ok('navigation entry present') : fail('nav');
  (await see(/DISCONNECTED/)) ? ok('disconnected state is shown honestly') : fail('disconnected');
  (await see(/Not connected\. Connect the device above/)) ? ok('charts show an empty state, not invented data') : fail('empty chart');
  (await see(/Waiting for readings/)) ? ok('the prediction area waits for real readings') : fail('insights empty');
  (await p.locator('svg[aria-label$="over time"], svg[aria-label*=" over time,"]').count()) === 0 ? ok('no chart is drawn without data') : fail('chart without data');
  const t0 = await p.locator('main').innerText();
  /simulated|fake/i.test(t0) ? fail('the page mentions simulated or fake data') : ok('no simulated-data controls or tags on the page');

  if (hw) {
    await p.getByRole('button', { name: /refresh ports/i }).click();
    console.log('     ports seen:', (await p.getByLabel('Serial port').locator('option').allInnerTexts()).join(' | '));
    await p.getByRole('button', { name: /^connect$/i }).click();
    (await see(/receiving data/, 25000)) ? ok('HARDWARE: connected and receiving valid packets from the Arduino') : fail('hardware connect');
    (await see(/Heat comfort/, 15000)) ? ok('HARDWARE: the heat comfort result appears') : fail('heat comfort');
    (await see(/Engine estimate/)) ? ok('HARDWARE: the engine estimate panel appears') : fail('engine panel');
    (await see(/weekly deaths, range/, 20000)) ? ok('HARDWARE: the engine predicts an outcome from the live readings') : fail('engine prediction');
    await p.waitForTimeout(7000);
    const txt = await p.locator('main').innerText();
    const m = txt.match(/valid packets\s+(\d+)/i);          // the label is upper-cased by CSS
    m && Number(m[1]) >= 3 ? ok(`HARDWARE: ${m[1]} valid packets counted`) : fail('packet count ' + (m && m[1]));
    (await p.locator('svg[aria-label^="Temperature over time"]').count()) ? ok('HARDWARE: live temperature chart is drawn') : fail('temperature chart');
    /smoke alert/i.test(txt) ? ok('HARDWARE: the smoke alert is shown') : fail('smoke alert');
    /simulated|fake|PM2\.5/i.test(txt.replace(/Not ppm[^.]*\./i, '')) ? fail('the live page mentions simulated, fake or PM2.5') : ok('HARDWARE: no simulated tags, no PM2.5 claim');
    await p.screenshot({ path: process.env.SHOT || 'live_hardware.png' });
    await p.getByRole('button', { name: /^disconnect$/i }).click();
    (await see(/DISCONNECTED/)) ? ok('HARDWARE: disconnect works and releases the port') : fail('hardware disconnect');
  }

  errs.length ? fail('errors: ' + [...new Set(errs)].slice(0, 3).join(' | ')) : ok('no console errors');
  await browser.close();
  console.log(bad ? 'LIVE E2E FAILED (' + bad + ')' : 'LIVE E2E PASSED' + (hw ? ' (with the physical Arduino)' : ' (software only; hardware not exercised)'));
  process.exitCode = bad ? 1 : 0;
})().catch((e) => { console.log('ABORT', e.message); process.exitCode = 1; });
