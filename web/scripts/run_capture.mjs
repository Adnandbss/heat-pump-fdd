import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(webDir, "..");
const py = process.env.CI ? "python" : resolve(root, ".venv/bin/python");
const started = [];

async function waitFor(url, timeoutMs = 90_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      /* still booting */
    }
    await sleep(400);
  }
  throw new Error(`timed out waiting for ${url}`);
}

async function alreadyUp(url) {
  try {
    return (await fetch(url)).ok;
  } catch {
    return false;
  }
}

function start(command, args, cwd) {
  const child = spawn(command, args, { cwd, stdio: "inherit" });
  started.push(child);
  return child;
}

function stopStarted() {
  for (const child of started) {
    child.kill("SIGTERM");
  }
}

process.on("exit", stopStarted);
process.on("SIGINT", () => {
  stopStarted();
  process.exit(1);
});

if (!(await alreadyUp("http://127.0.0.1:8000/api/evidence/summary"))) {
  start(py, ["-m", "uvicorn", "api.app:app", "--host", "127.0.0.1", "--port", "8000"], root);
}
if (!(await alreadyUp("http://127.0.0.1:5173"))) {
  start("npm", ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"], webDir);
}

await waitFor("http://127.0.0.1:8000/api/evidence/summary");
await waitFor("http://127.0.0.1:5173");

const capture = spawn(process.execPath, [resolve(webDir, "scripts/capture_evidence.mjs")], {
  cwd: webDir,
  stdio: "inherit",
});
const code = await new Promise((resolveExit) => {
  capture.on("exit", (exitCode) => resolveExit(exitCode ?? 1));
});
stopStarted();
process.exit(code);
