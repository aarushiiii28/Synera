// Drives the tamper simulator and screenshots the sequence. Usage: node scripts/trust_sim.cjs [mode] [dataset] [width] [height]
const { chromium } = require('playwright');
(async () => {
  const [mode = 'subtle_edit', ds = 'osd-211', w = '1440', h = '900'] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: +w, height: +h } })).newPage();
  const errs = [];
  page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  page.on('pageerror', (e) => errs.push(e.message));
  await page.goto('http://localhost:5173/trust', { waitUntil: 'networkidle' });
  await page.getByRole('radio', { name: new RegExp('^' + ds) }).first().click();
  await page.getByRole('radio', { name: new RegExp('^' + mode.toUpperCase()) }).click();
  const launch = page.getByRole('button', { name: /LAUNCH ATTACK/ });
  await launch.scrollIntoViewIfNeeded();
  await launch.click();
  await page.waitForTimeout(2600);
  const live = page.getByText(/LIVE RESPONSE/);
  await live.scrollIntoViewIfNeeded(); await page.evaluate(() => window.scrollBy(0, 420));
  await page.screenshot({ path: `../docs/screens/trust_sim_${mode}_mid_${w}.png` });
  await page.waitForTimeout(7500);
  await live.scrollIntoViewIfNeeded(); await page.evaluate(() => window.scrollBy(0, 420));
  await page.screenshot({ path: `../docs/screens/trust_sim_${mode}_end_${w}.png`, fullPage: false });
  const box = await page.locator('#root').boundingBox();
  console.log('docWidth', await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]), box && box.width);
  console.log('errors', errs);
  await browser.close();
})();

