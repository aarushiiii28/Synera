import { execSync } from 'child_process';
import fs from 'fs';

const routes = [
  { path: '/', name: 'observatory' },
  { path: '/discovery', name: 'discovery' },
  { path: '/findings', name: 'findings' },
  { path: '/findings/find_123', name: 'dossier' },
  { path: '/space-biology', name: 'space-biology' },
  { path: '/trust', name: 'trust' },
  { path: '/benchmark', name: 'benchmark' },
  { path: '/risk', name: 'risk' }
];

const baseUrl = 'http://localhost:5173';
const outDir = '../docs/screens';

if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

console.log('Taking screenshots...');
for (const route of routes) {
  const url = `${baseUrl}${route.path}`;
  try {
    // Desktop 1440x900
    execSync(`npx playwright screenshot --viewport-size "1440, 900" --wait-for-timeout 2000 ${url} ${outDir}/${route.name}_desktop.png`, { stdio: 'inherit' });
    // Mobile 390x844
    execSync(`npx playwright screenshot --viewport-size "390, 844" --wait-for-timeout 2000 ${url} ${outDir}/${route.name}_mobile.png`, { stdio: 'inherit' });
    console.log(`Saved screenshots for ${route.name}`);
  } catch (err) {
    console.error(`Failed for ${route.name}: ${err.message}`);
  }
}
console.log('Done.');
