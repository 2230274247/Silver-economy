import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium' },
  projects: [
    { name: '360', use: { viewport: { width: 360, height: 800 } } },
    { name: '390', use: { viewport: { width: 390, height: 844 } } },
    { name: '430', use: { viewport: { width: 430, height: 932 } } },
  ],
  webServer: {
    command: 'npm run dev:h5',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 90_000,
  },
});
