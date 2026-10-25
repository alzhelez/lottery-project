import path from 'node:path'
import { defineConfig } from '@playwright/test'

const root = path.resolve(__dirname, '../..')
const dataDir = path.join(__dirname, '.data')
const python = process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3')

// Сквозные тесты на моке API Столото: приложение получает пустую папку данных
// и загружает тиражи с мок-сервера. Перед запуском: npm run build.
export default defineConfig({
  testDir: '.',
  timeout: 300_000,
  expect: { timeout: 30_000 },
  workers: 1,
  globalSetup: './global-setup.ts',
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: path.join(root, 'playwright-report') }],
    ['allure-playwright', { resultsDir: path.join(root, 'allure-results', 'e2e'), suiteTitle: false }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:3100',
    launchOptions: process.env.PW_CHROMIUM_PATH
      ? { executablePath: process.env.PW_CHROMIUM_PATH, args: ['--no-sandbox'] }
      : {},
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `${python} tests/mock_stoloto/server.py --port 3199 --hold 4x20`,
      cwd: root,
      port: 3199,
      reuseExistingServer: false,
    },
    {
      command: 'npx next start -p 3100',
      cwd: root,
      port: 3100,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        LOTTERY_DATA_DIR: dataDir,
        STOLOTO_API_BASE: 'http://127.0.0.1:3199',
        STOLOTO_DELAY: '0',
        // всеобъемлющий режим Бога в тестах — минута на игру
        LOTTERY_GODMODE_ALL_BUDGET: '1',
        ...(process.env.PYTHON_BIN ? { PYTHON_BIN: process.env.PYTHON_BIN } : {}),
      },
    },
  ],
})
