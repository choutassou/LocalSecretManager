import { defineConfig } from "@playwright/test";
import path from "node:path";

const PORT = 8799;
const dataDir = path.resolve(process.cwd(), ".e2e-data");

// Runs the real Python server (serving the built UI in ../static) against a scratch data dir.
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: "chrome", // use the installed Chrome; no browser download needed
    permissions: ["clipboard-read", "clipboard-write"],
    trace: "retain-on-failure",
  },
  webServer: {
    command: `python ../server.py ${PORT}`,
    url: `http://127.0.0.1:${PORT}/`,
    reuseExistingServer: false,
    env: { LSM_DATA_DIR: dataDir },
    timeout: 30_000,
  },
});
