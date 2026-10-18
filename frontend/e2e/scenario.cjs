// End-to-end check of the Scenario Lab against a running stack (web :5173 + API :8000, or a static build with E2E_BASE).
//   node e2e/scenario.cjs          (E2E_BASE=http://localhost:4174 for the recorded demo)
const { chromium } = require('playwright');
const base = process.env.E2E_BASE || 'http://localhost:5173';
let bad = 0;
const ok = (m) => console.log('ok  ', m);
const fail = (m) => { bad++; console.log('FAIL', m); };

(async () => {
  const browser = await chromium.launch();
  const p = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message));
  p.on('console', (m) => m.type() === 'error' && !/Failed to load resource/.test(m.text()) && errs.push('CONSOLE ' + m.text().slice(0, 160)));
  p.on('response', (r) => r.status() >= 500 && errs.push('HTTP ' + r.status() + ' ' + r.url()));
  const panel = () => p.locator('[aria-live=polite]').first().innerText();
  const effect = async () => { const m = (await panel()).match(/[+−-]\d+\.\d+%/); return m ? Number(m[0].replace('−', '-').replace('%', '')) : NaN; };
  const slide = (id, atMax) => p.locator('#' + id).evaluate((el, max) => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    set.call(el, max ? el.max : el.min); el.dispatchEvent(new Event('input', { bubbles: true }));
  }, atMax);

  await p.goto(base + '/scenario', { waitUntil: 'networkidle' });
  await p.locator('[aria-live=polite]').first().waitFor({ timeout: 20000 });
  (await effect()) > 0 ? ok('default scenario shows a positive effect') : fail('default effect');
  await p.getByRole('button', { name: 'Typical week' }).click();
  (await effect()) === 0 ? ok('typical week is exactly zero') : fail('typical not zero');
  await p.getByRole('button', { name: 'Clean-air week' }).click();
  (await effect()) < 0 ? ok('clean-air week lowers deaths') : fail('clean-air');
  await p.getByRole('button', { name: 'Typical week' }).click();
  await slide('sl-pm25', true); await p.waitForTimeout(300);
  const hi = await effect(); hi > 0 ? ok('PM2.5 slider at its maximum raises deaths (' + hi + '%)') : fail('slider');
  (await p.getByText('EXTRAPOLATION').count()) ? ok('an extreme setting is flagged as extrapolation') : fail('no extrapolation flag');
  await slide('sl-pm25', false); await p.waitForTimeout(300);
  (await effect()) < hi ? ok('slider at minimum is lower than at maximum') : fail('slider order');
  await p.getByRole('button', { name: 'Heatwave' }).click(); await p.waitForTimeout(300);
  const heat = await effect();
  await p.selectOption('select >> nth=1', '1'); await p.waitForTimeout(400);       // January
  const winter = await effect(); winter < heat ? ok('the same heatwave is less harmful in January than in July (' + heat + '% vs ' + winter + '%)') : fail('season effect ' + heat + ' vs ' + winter);
  await p.getByRole('button', { name: 'HEART DISEASE' }).click(); await p.waitForTimeout(1500);
  (await p.url()).includes('outcome=heart') ? ok('switching to heart disease loads its own model') : fail('outcome');
  await p.selectOption('select >> nth=0', 'Ohio'); await p.waitForTimeout(500);
  (await p.url()).includes('state=Ohio') ? ok('choosing a state updates the shareable link') : fail('state link');
  for (const t of ['Where the consequence comes from', 'Every weight of every stressor', 'Two stressors at once', 'Does the model work on states it never saw?', 'Read this before using a number'])
    (await p.getByText(t).count()) ? ok('section: ' + t) : fail('missing: ' + t);
  errs.length ? fail('errors: ' + [...new Set(errs)].slice(0, 3).join(' | ')) : ok('no console or server errors');
  const phone = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await phone.goto(base + '/scenario', { waitUntil: 'networkidle' }); await phone.locator('[aria-live=polite]').first().waitFor(); await phone.waitForTimeout(1500);
  (await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 0 ? ok('phone layout has no sideways scroll') : fail('phone overflow');
  await browser.close();
  console.log(bad ? 'SCENARIO E2E FAILED (' + bad + ')' : 'SCENARIO E2E PASSED');
  process.exitCode = bad ? 1 : 0;
})().catch((e) => { console.log('ABORT', e.message); process.exitCode = 1; });
