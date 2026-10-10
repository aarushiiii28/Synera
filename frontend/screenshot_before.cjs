const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const routes = [
  '/', '/_design', '/discovery', '/findings', 
  '/space-biology', '/trust-center', '/benchmark', '/risk-assessment'
];

(async () => {
  const browser = await chromium.launch();
  
  const screensDir = path.join(__dirname, '../docs/screens');
  if (!fs.existsSync(screensDir)) {
    fs.mkdirSync(screensDir, { recursive: true });
  }

  for (const route of routes) {
    const safeName = route === '/' ? 'observatory' : route.replace('/', '');
    
    // Desktop
    let page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark' });
    await page.goto(`http://localhost:5173${route}`);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(screensDir, `${safeName}_before_1440.png`) });
    await page.close();

    // Mobile
    page = await browser.newPage({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' });
    await page.goto(`http://localhost:5173${route}`);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(screensDir, `${safeName}_before_390.png`) });
    await page.close();
  }

  await browser.close();
})();
