// End-to-end check of the Live Stress Lab against the running app (API + web).
//   node e2e/live.cjs                      page, empty states, the LABELLED simulated feed, scenario builder, interaction explorer
//   LIVE_HARDWARE=1 node e2e/live.cjs      additionally connects the REAL Arduino (needs it plugged in and the Serial Monitor closed)
// The simulated feed never counts as hardware verification: that part only runs with LIVE_HARDWARE=1.
const { chromium } = require('playwright');
const base = process.env.E2E_BASE || 'http://localhost:5173';
const hw = process.env.LIVE_HARDWARE === '1';
let bad = 0;
const ok = (m) => console.log('ok  ', m);
const fail = (m) => { bad++; console.log('FAIL', m); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message));
  p.on('console', (m) => m.type() === 'error' && !/EventSource|net::ERR/i.test(m.text()) && errs.push('CONSOLE ' + m.text().slice(0, 140)));
  const see = (re, t = 15000) => p.getByText(re).first().waitFor({ state: 'visible', timeout: t }).then(() => true, () => false);

  await p.goto(base + '/live-stress-lab', { waitUntil: 'networkidle' });
  await p.evaluate(() => fetch('/api/v1/live/disconnect', { method: 'POST' })).catch(() => {});
  await p.reload({ waitUntil: 'networkidle' });
  (await see(/Real sensors/)) ? ok('page loads and is in the navigation') : fail('heading');
  (await p.getByRole('link', { name: /Live Stress Lab/ }).count()) ? ok('navigation entry present') : fail('nav');
  (await see(/DISCONNECTED/)) ? ok('disconnected state is shown honestly') : fail('disconnected');
  (await see(/Not connected\. Connect the device above/)) ? ok('charts show an empty state, not invented data') : fail('empty chart');
  (await p.getByText('NO DATA').first().count()) ? ok('header says NO DATA') : fail('no data label');

  // scenario builder and interaction explorer work without hardware
  await p.getByRole('button', { name: /run comparison/i }).click();
  (await see(/Comparison with the baseline/)) ? ok('scenario comparison runs') : fail('comparison');
  const table = await p.getByRole('region', { name: /scenario comparison/i }).innerText();
  /Heat index/.test(table) && /DERIVED/.test(table) && /\+\d/.test(table) ? ok('derived heat index is labelled DERIVED and compared with the baseline') : fail('derived rows');
  (await see(/SUPER-ADDITIVE|SUB-ADDITIVE|APPROXIMATELY ADDITIVE/)) ? ok('interaction explorer classifies the 2 x 2 contrast') : fail('interaction class');
  (await see(/NOT A VALIDATED DISCOVERY/)) ? ok('interaction analysis is labelled exploratory') : fail('exploratory label');
  (await see(/Not ppm, not AQI|not ppm, not AQI/i)) ? ok('gas reading is not presented as a concentration') : fail('gas caveat');

  // the labelled simulated feed
  await p.getByRole('button', { name: /start simulated test feed/i }).click();
  (await see(/SIMULATED TEST DATA/)) ? ok('test mode shows an unmistakable banner') : fail('test banner');
  (await p.locator('main').innerText()).includes('SIMULATED') && !(await p.locator('main').innerText()).includes('REAL SENSOR DATA') ? ok('test mode never claims REAL SENSOR DATA') : fail('test claims real');
  (await p.getByRole('button', { name: /^connect$/i }).isDisabled()) ? ok('hardware connect is blocked during the test feed') : fail('connect not blocked');
  await p.getByRole('button', { name: /stop simulated test feed/i }).click();
  (await see(/DISCONNECTED/)) ? ok('test feed stops') : fail('stop');

  if (hw) {
    await p.getByRole('button', { name: /refresh ports/i }).click();
    const sel = p.getByLabel('Serial port');
    const opts = await sel.locator('option').allInnerTexts();
    console.log('     ports seen:', opts.join(' | '));
    await p.getByRole('button', { name: /^connect$/i }).click();
    (await see(/receiving data/, 25000)) ? ok('HARDWARE: connected and receiving valid packets from the Arduino') : fail('hardware connect');
    await p.waitForTimeout(7000);
    const txt = await p.locator('main').innerText();
    /REAL SENSOR DATA/.test(txt) ? ok('HARDWARE: data labelled REAL SENSOR DATA') : fail('hardware label');
    const m = txt.match(/valid packets\s+(\d+)/i);          // the label is upper-cased by CSS
    m && Number(m[1]) >= 3 ? ok(`HARDWARE: ${m[1]} valid packets counted`) : fail('packet count ' + (m && m[1]));
    (await p.locator('svg[aria-label^="Temperature over time"]').count()) ? ok('HARDWARE: live temperature chart is drawn') : fail('temperature chart');
    await p.screenshot({ path: process.env.SHOT || 'live_hardware.png' });
    await p.getByRole('button', { name: /^disconnect$/i }).click();
    (await see(/DISCONNECTED/)) ? ok('HARDWARE: disconnect works and releases the port') : fail('hardware disconnect');
  }

  errs.length ? fail('errors: ' + [...new Set(errs)].slice(0, 3).join(' | ')) : ok('no console errors');
  await browser.close();
  console.log(bad ? 'LIVE E2E FAILED (' + bad + ')' : 'LIVE E2E PASSED' + (hw ? ' (with the physical Arduino)' : ' (software only; hardware not exercised)'));
  process.exitCode = bad ? 1 : 0;
})().catch((e) => { console.log('ABORT', e.message); process.exitCode = 1; });
