#!/usr/bin/env node
/**
 * Runs the whole T-Port stack from one command: the FastAPI backend (port 8000) and the Next.js
 * website (port 2028). Output from both is shown with an [api] / [web] prefix, and stopping this
 * script (Ctrl+C) stops both. If either one exits, the other is stopped too.
 *
 *   node scripts/dev.mjs           # API with auto-reload + Next.js dev server
 *   node scripts/dev.mjs --prod    # API + the already-built site (`npm --prefix frontend run build` first)
 *
 * Development defaults are used only for variables you have not set yourself.
 * Requires backend/.venv (see README) and `npm install` in frontend/.
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const prod = process.argv.includes("--prod");
const win = process.platform === "win32";

const python = join(root, "backend", ".venv", win ? "Scripts/python.exe" : "bin/python");
if (!existsSync(python)) {
  console.error(`Python virtual environment not found at ${python}. See README, "Run locally".`);
  process.exit(1);
}
if (prod && !existsSync(join(root, "frontend", ".next", "BUILD_ID"))) {
  console.error("No production build found. Run `npm --prefix frontend run build` first.");
  process.exit(1);
}

const localDir = join(root, "backend", ".local");
mkdirSync(localDir, { recursive: true });
const devDefaults = {
  TPORT_DATABASE_URL: `sqlite:///${join(localDir, "tport-dev.db").replaceAll("\\", "/")}`,
  TPORT_ENVIRONMENT: "development",
  TPORT_RATE_LIMIT_PER_MINUTE: "1000",
  TPORT_AUTH_RATE_LIMIT_PER_MINUTE: "100",
  TPORT_ENABLE_FAULT_SIMULATION: "true",
  TPORT_ENABLE_SYNTHETIC_BOOKING: "true",
};
const env = { ...devDefaults, ...process.env };

// Bring the database schema up to date first (same as the Docker entrypoint does).
const migrate = spawnSync(python, ["-m", "alembic", "upgrade", "head"], {
  cwd: join(root, "backend"),
  env,
  stdio: "inherit",
});
if (migrate.status !== 0) {
  console.error("Database migration failed; not starting.");
  process.exit(migrate.status ?? 1);
}

const apiArgs = ["-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000"];
if (!prod) apiArgs.push("--reload", "--reload-dir", "backend/app");

const next = join(root, "frontend", "node_modules", "next", "dist", "bin", "next");
if (!existsSync(next)) {
  console.error("Next.js not installed. Run `npm --prefix frontend install` first.");
  process.exit(1);
}

const procs = [
  ["api", python, apiArgs, root],
  // Same as `npm run dev` / `npm start` in frontend/, run through this Node so no shell is needed.
  ["web", process.execPath, [next, prod ? "start" : "dev", "--port", "2028"], join(root, "frontend")],
].map(([name, cmd, args, cwd]) => {
  const child = spawn(cmd, args, { cwd, env });
  const pipe = (stream, out) => {
    let buf = "";
    stream.on("data", (chunk) => {
      buf += chunk;
      const lines = buf.split(/\r?\n/);
      buf = lines.pop();
      for (const line of lines) out.write(`[${name}] ${line}\n`);
    });
  };
  pipe(child.stdout, process.stdout);
  pipe(child.stderr, process.stderr);
  child.on("exit", (code, signal) => {
    console.log(`[${name}] stopped (${signal ?? `exit code ${code}`})`);
    shutdown(code ?? 0);
  });
  return child;
});

let stopping = false;
function shutdown(code) {
  if (stopping) return;
  stopping = true;
  for (const child of procs) {
    if (child.exitCode !== null || child.signalCode !== null) continue;
    // On Windows a child's own children (next, uvicorn's reloader) survive child.kill(); end the tree.
    if (win) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else child.kill("SIGTERM");
  }
  process.exitCode = code;
}
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(sig, () => shutdown(0));

console.log(`T-Port ${prod ? "(production build)" : "(development)"}: website http://localhost:2028 · API http://localhost:8000`);
