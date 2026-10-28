import { defineConfig } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const localPython = path.resolve('../../.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = fs.existsSync(localPython) ? `"${localPython}"` : 'python';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5174', browserName: 'chromium' },
  projects: [
    { name: '360', use: { viewport: { width: 360, height: 800 } } },
    { name: '390', use: { viewport: { width: 390, height: 844 } } },
    { name: '430', use: { viewport: { width: 430, height: 932 } } },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port 18000 --no-access-log`,
      cwd: '../../services/api', url: 'http://127.0.0.1:18000/api/v1/healthz',
      env: { LLM_PROVIDER: 'mock', MAPS_PROVIDER: 'mock', UI_TEST_MODE: 'true' }, reuseExistingServer: false,
    },
    {
      command: 'npx uni --host 127.0.0.1 --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174', env: { API_PROXY_TARGET: 'http://127.0.0.1:18000' },
      reuseExistingServer: false, timeout: 90_000,
    },
  ],
});
