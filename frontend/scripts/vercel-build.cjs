// Vercel build: live site when an API address is configured, otherwise the recorded (server-less) demo.
//   VITE_API_URL set   -> normal build, the browser talks to that API (e.g. on Render)
//   VITE_API_URL empty -> `vite build --mode static`, every answer comes from frontend/public/snapshot/
const { spawnSync } = require('node:child_process');

const api = (process.env.VITE_API_URL || '').trim();
const live = api !== '';
console.log(live ? `[build] LIVE site, API at ${api}` : '[build] RECORDED DEMO (no VITE_API_URL set)');

const run = (cmd, args) => {
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: true });
  if (r.status !== 0) process.exit(r.status ?? 1);
};
run('npx', ['tsc', '-b']);
run('npx', ['vite', 'build', ...(live ? [] : ['--mode', 'static'])]);
