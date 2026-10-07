import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(here, "..");
const repoRoot = resolve(packageRoot, "../..");
const openapiPath = resolve(packageRoot, "openapi.json");
const generatedPath = resolve(packageRoot, "src/generated.ts");
const check = process.argv.includes("--check");
const tempRoot = resolve(repoRoot, ".test-artifacts/api-client-check");

function pythonCommand() {
  const candidates = process.platform === "win32"
    ? [resolve(repoRoot, ".venv/Scripts/python.exe"), "python"]
    : [resolve(repoRoot, ".venv/bin/python"), "python3", "python"];
  return candidates.find((candidate) => candidate === "python" || existsSync(candidate)) ?? candidates.at(-1);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: repoRoot, encoding: "utf8", stdio: "inherit", ...options });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function generate(targetOpenapi, targetTypes) {
  mkdirSync(dirname(targetOpenapi), { recursive: true });
  mkdirSync(dirname(targetTypes), { recursive: true });
  const python = pythonCommand();
  const pythonPath = [resolve(repoRoot, "apps/api/src"), resolve(repoRoot, "packages/database/src")].join(process.platform === "win32" ? ";" : ":");
  run(python, ["scripts/export_openapi.py", "--output", targetOpenapi], { env: { ...process.env, PYTHONPATH: pythonPath } });
  const localCli = resolve(packageRoot, "node_modules/openapi-typescript/bin/cli.js");
  if (existsSync(localCli)) {
    run(process.execPath, [localCli, targetOpenapi, "-o", targetTypes], { cwd: packageRoot });
  } else {
    const pnpm = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
    run(pnpm, ["exec", "openapi-typescript", targetOpenapi, "-o", targetTypes], { cwd: packageRoot });
  }
}

if (check) {
  rmSync(tempRoot, { recursive: true, force: true });
  const tempOpenapi = resolve(tempRoot, "openapi.json");
  const tempTypes = resolve(tempRoot, "generated.ts");
  generate(tempOpenapi, tempTypes);
  const currentOpenapi = readFileSync(openapiPath, "utf8");
  const currentTypes = readFileSync(generatedPath, "utf8");
  const freshOpenapi = readFileSync(tempOpenapi, "utf8");
  const freshTypes = readFileSync(tempTypes, "utf8");
  if (currentOpenapi !== freshOpenapi || currentTypes !== freshTypes) {
    console.error("API artifacts are stale. Run pnpm generate:api and review the generated diff.");
    process.exit(1);
  }
  console.log("API OpenAPI and TypeScript artifacts match the active FastAPI application.");
} else {
  generate(openapiPath, generatedPath);
}
