// node scripts/overflow_probe.cjs /trust 390  -> lists elements wider than the viewport
const { chromium } = require('playwright');
(async () => {
  const [route = '/trust', w = '390'] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: +w, height: 844 } })).newPage();
  await p.goto('http://localhost:5173' + route, { waitUntil: 'networkidle' });
  await p.waitForTimeout(3000);
  if (route === '/trust') {
    await p.getByRole('radio', { name: /^LEDGER_TAMPER/ }).click();
    await p.getByRole('button', { name: /LAUNCH ATTACK/ }).click();
    await p.waitForTimeout(1500);
    await p.getByRole('button', { name: /SKIP ANIMATION/ }).click().catch(() => {});
    await p.waitForTimeout(800);
  }
  const r = await p.evaluate((w) => [...document.querySelectorAll('main *, #root *')].filter((e) => e.getBoundingClientRect().right > w + 0.5 && !e.closest('[tabindex="0"]') && !e.closest('nav')).slice(0, 8).map((e) => e.tagName + '.' + String(e.className).slice(0, 60) + ' ' + Math.round(e.getBoundingClientRect().right)), +w);
  console.log(r, await p.evaluate(() => document.documentElement.scrollWidth));
  await b.close();
})();
