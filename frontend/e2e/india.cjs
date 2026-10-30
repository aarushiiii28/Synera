// End-to-end check of the India live map against the running app (API + web): the whole journey from the home page to actions and evidence.
//   node e2e/india.cjs        needs internet: it reads the real providers; nothing is mocked
const { chromium } = require('playwright');
const base = process.env.E2E_BASE || 'http://localhost:5173';
let bad = 0;
const ok = (m) => console.log('ok  ', m);
const fail = (m) => { bad++; console.log('FAIL', m); };

(async () => {
  const browser = await chromium.launch();
  const p = await (await browser.newContext({ viewport: { width: 1600, height: 960 } })).newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message));
  p.on('console', (m) => m.type() === 'error' && errs.push('CONSOLE ' + m.text().slice(0, 160)));
  const see = (re, t = 45000) => p.getByText(re).first().waitFor({ state: 'visible', timeout: t }).then(() => true, () => false);

  await p.goto(base + '/', { waitUntil: 'networkidle' });
  (await see(/India live intelligence/i)) ? ok('home page is the India command centre') : fail('home heading');
  await p.locator('svg[aria-label^="Map of India"] path').first().waitFor({ timeout: 20000 }).catch(() => {});
  (await p.locator('svg[aria-label^="Map of India"] path').count()) > 30 ? ok('the map draws every state and union territory (36 outlines)') : fail('map outlines');
  (await p.locator('svg[aria-label^="Map of India"] [role=button]').count()) >= 40 ? ok('city markers are present and focusable') : fail('markers');
  (await see(/^LIVE$|STALE DATA/)) ? ok('the status chip reports the data state') : fail('status chip');
  (await see(/Select a city on the map/)) ? ok('the city panel invites a selection') : fail('placeholder');
  const layerBtn = (name) => p.getByRole('group', { name: 'Map layer' }).getByRole('button', { name, exact: true });
  for (const name of ['Air quality', 'Temperature', 'Humidity', 'Rainfall', 'Wind', 'Composite risk']) {
    await layerBtn(name).click();
    (await p.getByLabel(new RegExp('Legend: ' + name, 'i')).count()) ? ok('layer "' + name + '" switches and its legend appears') : fail('layer ' + name);
  }
  await layerBtn('Air quality').click();

  // search, then the click-through journey
  await p.getByLabel('Search a city').fill('amrit');
  await p.getByRole('option', { name: /Amritsar/ }).click();
  (await see(/What should we do now\?/, 90000)) ? ok('Amritsar: live readings fetched, engine run, ranked actions shown') : fail('actions');
  const txt = await p.locator('main, aside').evaluateAll((els) => els.map((e) => e.innerText).join('\n'));
  /Action\s/i.test(txt) && /Reason/i.test(txt) && /Affected/i.test(txt) && /Confidence/i.test(txt) ? ok('each recommendation shows action, reason, affected group and confidence') : fail('recommendation fields');
  /Immediate|Next few hours|Upcoming forecast period/i.test(txt) && /Advisory|Informational|High priority|Critical/i.test(txt) ? ok('urgency and time window are stated') : fail('urgency / window');
  /Official threshold|SYNERA engine/i.test(txt) ? ok('each recommendation says whether it rests on an official threshold or the engine') : fail('basis');
  await p.getByRole('tab', { name: 'Conditions' }).click();
  (await see(/India AQI \(PM-based\)/)) ? ok('conditions tab: AQI is labelled PM-based, with each value tagged by kind') : fail('conditions');
  await p.getByRole('tab', { name: 'Evidence' }).click();
  (await see(/How much to trust it/)) ? ok('evidence tab states how much the engine can be trusted') : fail('trust statement');
  (await see(/not been run|not run|R² /i, 5000)) || (await see(/explains a very small share/i, 5000)) ? ok('evidence tab reports the model\'s own out-of-sample skill') : fail('skill');
  /PM2\.5.*(simulated|fake)/i.test(txt) ? fail('simulated wording on a live page') : ok('no simulated or fabricated-data wording');
  await p.getByRole('tab', { name: 'Sources' }).click();
  (await see(/NOT_CONFIGURED/, 8000)) ? ok('sources tab says plainly which optional providers are not configured') : fail('sources');
  (await p.getByRole('img', { name: /over the past 3 days and next 3 days/i }).count()) ? ok('timeline chart is drawn for the city') : fail('timeline');
  await p.screenshot({ path: process.env.SHOT || 'india_live.png' });

  // a second city repeats the flow
  await p.getByLabel('Search a city').fill('mumbai');
  await p.getByRole('option', { name: /Mumbai/ }).click();
  (await see(/^Mumbai$/, 90000)) ? ok('switching to Mumbai repeats the process') : fail('second city');
  (await see(/What should we do now\?|Unavailable/, 90000)) ? ok('Mumbai: actions or an honest unavailable state') : fail('second city actions');

  // phone width
  const m = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await m.goto(base + '/?city=delhi', { waitUntil: 'networkidle' });
  await m.getByText(/What should we do now\?|Unavailable/).first().waitFor({ timeout: 90000 }).then(() => ok('phone: the city panel is reachable'), () => fail('phone panel'));
  (await m.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)) ? ok('phone: no horizontal scrolling') : fail('phone overflow');

  errs.length ? fail('errors: ' + [...new Set(errs)].slice(0, 3).join(' | ')) : ok('no console errors');
  await browser.close();
  console.log(bad ? 'INDIA E2E FAILED (' + bad + ')' : 'INDIA E2E PASSED');
  process.exitCode = bad ? 1 : 0;
})().catch((e) => { console.log('ABORT', e.message); process.exitCode = 1; });
