// Usage: node scripts/shoot.cjs <baseUrl> <outDir> <route[,route...]> [width] [height] [waitMs] [fullPage]
// Saves one PNG per route (e.g. docs/screens/observatory_1440.png). Needs Playwright browsers installed.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const [base, out, routes, w = '1440', h = '900', wait = '2500', full = '0'] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  for (const r of routes.split(',')) {
    await page.goto(base + r, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(+wait);
    const name = (r === '/' ? 'observatory' : r.replace(/^\//, '').replace(/[\/?=&]/g, '_')) + '_' + w;
    await page.screenshot({ path: path.join(out, name + '.png'), fullPage: full === '1' });
    console.log('saved', name, 'console errors so far:', errors.length);
  }
  if (errors.length) console.log('ERRORS:\n' + [...new Set(errors)].slice(0, 12).join('\n'));
  await browser.close();
})();
