import type { PlaywrightTestConfig } from "@playwright/test";
const config: PlaywrightTestConfig = {
  testDir: "e2e",
  workers: 1,
  use: {
    baseURL: process.env.GATEWAY_URL || "http://127.0.0.1:8093",
    headless: true,
    launchOptions: process.env.CHROME_PATH
      ? { executablePath: process.env.CHROME_PATH }
      : {},
  },
  reporter: "list",
};
export default config;
