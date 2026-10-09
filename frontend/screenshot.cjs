const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'dark',
  });
  
  const screensDir = path.join(__dirname, '../docs/screens');
  if (!fs.existsSync(screensDir)) {
    fs.mkdirSync(screensDir, { recursive: true });
  }

  // Shell screenshot
  await page.goto('http://localhost:5173/');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(screensDir, 'shell.png') });

  // Design System screenshot
  await page.goto('http://localhost:5173/_design');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(screensDir, 'design.png') });

  await browser.close();
})();
