import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 60000,
  expect: { timeout: 10000 },
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  projects: [360, 390, 412].map((width) => ({
    name: `android-${width}`,
    use: { viewport: { width, height: 850 }, isMobile: true, hasTouch: true },
  })),
  webServer: [
    {
      command: '../.venv/bin/python ../scripts/e2e_server.py',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
    },
  ],
});
