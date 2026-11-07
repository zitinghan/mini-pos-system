const { spawnSync } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
// On recent Windows Node releases, native TypeScript avoids the legacy
// Playwright 1.52 ESM loader waiting indefinitely during test discovery.
const env = { ...process.env };
if (process.platform === 'win32') env.PW_DISABLE_TS_ESM = '1';
const result = spawnSync(process.execPath, [path.join(root, 'frontend/node_modules/@playwright/test/cli.js'), 'test', ...process.argv.slice(2)], {
  cwd: path.join(root, 'frontend'), env, stdio: 'inherit',
});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
