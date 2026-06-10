// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * SWAG QA Debug Hunter — Playwright 設定
 *
 * 測試 URL 設定方式（任選其一）：
 *   1. 環境變數：SWAG_TEST_URL=https://v3-277.app.swag.live npx playwright test
 *   2. 直接修改 baseURL 預設值（不推薦，避免 commit 到 Git）
 *
 * 安裝指令（首次使用）：
 *   npm install
 *   npx playwright install
 */
module.exports = defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: process.env.CI ? 2 : 1,

  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
  ],

  use: {
    baseURL: process.env.SWAG_TEST_URL || 'https://swag.live',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    video: 'on-first-retry',
    locale: 'zh-TW',
    timezoneId: 'Asia/Taipei',
  },

  projects: [
    {
      name: 'Desktop Chrome',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'Desktop Safari',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'iPhone 14 Pro',
      use: { ...devices['iPhone 14 Pro'] },
    },
    {
      name: 'Pixel 7',
      use: { ...devices['Pixel 7'] },
    },
  ],
});
