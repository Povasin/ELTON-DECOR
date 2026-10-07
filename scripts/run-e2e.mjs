import { spawnSync } from "node:child_process";

if (process.env.ELTON_E2E_ENABLED !== "1") {
  console.log("E2E не запущены: задайте ELTON_E2E_ENABLED=1 и подготовьте локальные API/PostgreSQL.");
  process.exit(0);
}

const executable = process.platform === "win32" ? "playwright.cmd" : "playwright";
const result = spawnSync(executable, ["test", ...process.argv.slice(2)], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: process.env,
});

process.exit(result.status ?? 1);
