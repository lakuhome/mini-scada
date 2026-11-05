import { defineConfig } from '@playwright/test';
import path from 'node:path';

const python = process.env.SCADA_TEST_PYTHON || 'python';
export default defineConfig({
  testDir: './tests',
  workers: 1,
  globalTeardown: './tests/teardown.js',
  use: { baseURL: 'http://127.0.0.1:18000', viewport: { width: 1440, height: 1000 } },
  webServer:
    { command: `"${python}" frontend/tests/server.py`, cwd: '..',
      url: 'http://127.0.0.1:18000/api/health', timeout: 30000,
      env: { SCADA_DB_PATH: path.resolve('test-results', `e2e-${Date.now()}.db`) } },
});
