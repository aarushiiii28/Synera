// Screenshots the ledger explorer (deep link, mid-scan, result) and the Merkle proof tool.
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errs = []; p.on('console', (m) => m.type() === 'error' && errs.push(m.text())); p.on('pageerror', (e) => errs.push(e.message));
  await p.goto('http://localhost:5173/trust?block=11', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2000);
  const v = p.getByRole('button', { name: /VERIFY ENTIRE CHAIN/ });
  await v.scrollIntoViewIfNeeded();
  await p.evaluate(() => window.scrollBy(0, 250));
  await v.click();
  await p.waitForTimeout(1200);
  await p.screenshot({ path: '../docs/screens/trust_ledger_scan_1440.png' });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: '../docs/screens/trust_ledger_done_1440.png' });
  await p.evaluate(() => window.scrollBy(0, 520));
  await p.waitForTimeout(500);
  await p.screenshot({ path: '../docs/screens/trust_ledger_detail_1440.png' });
  await p.getByRole('group', { name: 'Registered datasets' }).getByRole('button', { name: 'osd-211' }).click();
  await p.waitForTimeout(800);
  await p.getByRole('button', { name: /PROVE INCLUSION/ }).click();
  await p.waitForTimeout(3500);
  await p.screenshot({ path: '../docs/screens/trust_merkle_1440.png' });
  console.log(errs);
  await b.close();
})();
