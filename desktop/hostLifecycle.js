'use strict';

/**
 * Host soft-probe + owned-child spawn/stop for the Phase 2 desktop shell.
 * Pure Node helpers (no Electron) so smoke scripts can reuse the same paths.
 *
 * Safety:
 * - Only ever signals the ChildProcess we spawned (ownedHost).
 * - Never kills unrelated PIDs; hard-refuses soak pids 29961/29969.
 */

const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const net = require('net');
const { URL } = require('url');

/** Soak / CR-14 val02_staging — never signal these PIDs. */
const FORBIDDEN_PIDS = new Set([29961, 29969]);

const DEFAULT_HOST_URL = 'http://127.0.0.1:8000';
/** Product default: spawn when Host unreachable. Set SSAK_SPAWN_HOST=0 to never spawn. */
const DEFAULT_SPAWN_HOST = true;
const DEFAULT_START_TIMEOUT_MS = 45_000;
const DEFAULT_STOP_GRACE_MS = 5_000;
const PROBE_INTERVAL_MS = 500;

/**
 * @param {string | undefined} raw
 * @returns {boolean}
 */
function spawnHostEnabled(raw = process.env.SSAK_SPAWN_HOST) {
  if (raw === undefined || raw === '') return DEFAULT_SPAWN_HOST;
  const v = String(raw).trim().toLowerCase();
  if (v === '0' || v === 'false' || v === 'no' || v === 'off') return false;
  return true;
}

/**
 * @param {string | undefined} raw
 * @returns {string}
 */
function resolveHostUrl(raw = process.env.SSAK_HOST_URL) {
  return String(raw || DEFAULT_HOST_URL).replace(/\/$/, '');
}

/**
 * @param {string} urlStr
 * @returns {{ hostname: string, port: number }}
 */
function parseHostBind(urlStr) {
  const u = new URL(urlStr);
  const port = u.port
    ? Number(u.port)
    : u.protocol === 'https:'
      ? 443
      : 80;
  return { hostname: u.hostname || '127.0.0.1', port };
}

/**
 * @param {string} [desktopDir] absolute path to desktop/ (defaults to __dirname)
 * @returns {string} repo root
 */
function resolveRepoRoot(desktopDir = __dirname) {
  return path.resolve(desktopDir, '..');
}

/**
 * @param {string} cmd
 * @returns {boolean}
 */
function commandExists(cmd) {
  try {
    execFileSync(process.platform === 'win32' ? 'where' : 'which', [cmd], {
      stdio: 'ignore',
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * Prefer `uv run agk serve …` from repo root; else DMG-launcher-style
 * `python -m antigravity_k.cli serve …` / `.venv/bin/agk`.
 *
 * @param {{ hostname: string, port: number, repoRoot?: string }} opts
 * @returns {{ command: string, args: string[], cwd: string, label: string }}
 */
function resolveSpawnSpec(opts) {
  const { hostname, port } = opts;
  const repoRoot = opts.repoRoot || resolveRepoRoot();
  const serveArgs = ['serve', '--host', hostname, '--port', String(port)];

  if (commandExists('uv')) {
    return {
      command: 'uv',
      args: ['run', 'agk', ...serveArgs],
      cwd: repoRoot,
      label: `uv run agk serve --host ${hostname} --port ${port}`,
    };
  }

  const venvAgk = path.join(repoRoot, '.venv', 'bin', 'agk');
  if (fs.existsSync(venvAgk)) {
    return {
      command: venvAgk,
      args: serveArgs,
      cwd: repoRoot,
      label: `.venv/bin/agk serve --host ${hostname} --port ${port}`,
    };
  }

  const venvPy = path.join(repoRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPy)) {
    return {
      command: venvPy,
      args: ['-m', 'antigravity_k.cli', ...serveArgs],
      cwd: repoRoot,
      label: `.venv/bin/python -m antigravity_k.cli serve --host ${hostname} --port ${port}`,
    };
  }

  if (commandExists('agk')) {
    return {
      command: 'agk',
      args: serveArgs,
      cwd: repoRoot,
      label: `agk serve --host ${hostname} --port ${port}`,
    };
  }

  throw new Error(
    'No Host launcher found. Install uv (preferred) or ensure .venv/bin/agk ' +
      '(or python -m antigravity_k.cli) is available — same paths as build_mac_dmg launcher.',
  );
}

/**
 * Soft HTTP probe — 2xx–4xx counts as reachable (Host up even if auth/route error).
 * @param {string} url
 * @param {number} [timeoutMs]
 * @returns {Promise<boolean>}
 */
function hostProbe(url, timeoutMs = 2000) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (ok) => {
      if (settled) return;
      settled = true;
      resolve(ok);
    };
    try {
      const req = http.get(url, { timeout: timeoutMs }, (res) => {
        res.resume();
        done((res.statusCode || 0) >= 200 && (res.statusCode || 0) < 500);
      });
      req.on('error', () => done(false));
      req.on('timeout', () => {
        req.destroy();
        done(false);
      });
    } catch {
      done(false);
    }
  });
}

/**
 * Soft TCP connect — true if something accepts on hostname:port.
 * @param {string} hostname
 * @param {number} port
 * @param {number} [timeoutMs]
 * @returns {Promise<boolean>}
 */
function tcpPortOpen(hostname, port, timeoutMs = 400) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (ok) => {
      if (settled) return;
      settled = true;
      resolve(ok);
    };
    try {
      const sock = net.connect({ host: hostname, port }, () => {
        sock.destroy();
        done(true);
      });
      sock.on('error', () => done(false));
      sock.setTimeout(timeoutMs, () => {
        sock.destroy();
        done(false);
      });
    } catch {
      done(false);
    }
  });
}

/**
 * True when bind attempt hits EADDRINUSE (port owned by someone).
 * @param {string} hostname
 * @param {number} port
 * @returns {Promise<boolean>}
 */
function bindWouldConflict(hostname, port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', (err) => {
      resolve(Boolean(err && err.code === 'EADDRINUSE'));
    });
    server.once('listening', () => {
      server.close(() => resolve(false));
    });
    try {
      server.listen(port, hostname);
    } catch (err) {
      resolve(Boolean(err && err.code === 'EADDRINUSE'));
    }
  });
}

/**
 * Heuristic for Phase 4 recovery copy (plan Phase 4/6): Host HTTP probe failed
 * but the port looks occupied (TCP accept or EADDRINUSE on bind), or stderr hints
 * at address-already-in-use.
 *
 * @param {string} urlStr
 * @param {{ stderrHint?: string, errorHint?: string }} [opts]
 * @returns {Promise<boolean>}
 */
async function suspectPortConflict(urlStr, opts = {}) {
  const hint = `${opts.stderrHint || ''}\n${opts.errorHint || ''}`;
  if (/EADDRINUSE|address already in use|port.*(?:in use|already)/i.test(hint)) {
    return true;
  }
  const { hostname, port } = parseHostBind(urlStr);
  if (await hostProbe(urlStr, 800)) return false;
  if (await tcpPortOpen(hostname, port)) return true;
  return bindWouldConflict(hostname, port);
}

/**
 * @param {number} ms
 * @returns {Promise<void>}
 */
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * @param {string} url
 * @param {number} timeoutMs
 * @param {{ intervalMs?: number, shouldAbort?: () => boolean }} [opts]
 * @returns {Promise<boolean>}
 */
async function waitForHostReady(url, timeoutMs, opts = {}) {
  const intervalMs = opts.intervalMs ?? PROBE_INTERVAL_MS;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (opts.shouldAbort && opts.shouldAbort()) return false;
    if (await hostProbe(url)) return true;
    await sleep(intervalMs);
  }
  return hostProbe(url);
}

/**
 * @param {import('child_process').ChildProcess | null | undefined} child
 * @returns {boolean}
 */
function isChildAlive(child) {
  return Boolean(child && child.pid && child.exitCode === null && !child.killed);
}

/**
 * Spawn Host as a direct child. Caller owns lifetime (Quit → stopOwnedHost).
 *
 * @param {{ hostname: string, port: number, repoRoot?: string, env?: NodeJS.ProcessEnv }} opts
 * @returns {{ child: import('child_process').ChildProcess, spec: ReturnType<typeof resolveSpawnSpec> }}
 */
function spawnOwnedHost(opts) {
  const spec = resolveSpawnSpec(opts);
  const child = spawn(spec.command, spec.args, {
    cwd: spec.cwd,
    env: opts.env || process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
    windowsHide: true,
  });
  return { child, spec };
}

/**
 * Graceful SIGTERM then SIGKILL after grace. Only signals `child.pid`.
 * Refuses forbidden soak pids and missing/unowned children.
 *
 * @param {import('child_process').ChildProcess | null | undefined} child
 * @param {{ graceMs?: number, log?: (msg: string) => void }} [opts]
 * @returns {Promise<{ stopped: boolean, pid: number | null, reason: string }>}
 */
async function stopOwnedHost(child, opts = {}) {
  const graceMs = opts.graceMs ?? DEFAULT_STOP_GRACE_MS;
  const log = opts.log || ((msg) => console.error(`[ssak-desktop] ${msg}`));

  if (!child || !child.pid) {
    return { stopped: true, pid: null, reason: 'no-child' };
  }

  const pid = child.pid;

  if (FORBIDDEN_PIDS.has(pid)) {
    log(`refusing to signal forbidden soak pid ${pid}`);
    return { stopped: false, pid, reason: 'forbidden-pid' };
  }

  if (!isChildAlive(child)) {
    return { stopped: true, pid, reason: 'already-exited' };
  }

  const waitExit = () =>
    new Promise((resolve) => {
      if (!isChildAlive(child)) {
        resolve();
        return;
      }
      const onExit = () => {
        clearTimeout(timer);
        resolve();
      };
      child.once('exit', onExit);
      const timer = setTimeout(() => {
        child.removeListener('exit', onExit);
        resolve();
      }, graceMs);
    });

  try {
    log(`SIGTERM owned Host pid=${pid}`);
    child.kill('SIGTERM');
  } catch (err) {
    log(`SIGTERM failed: ${err && err.message ? err.message : err}`);
  }

  await waitExit();

  if (!isChildAlive(child)) {
    return { stopped: true, pid, reason: 'sigterm' };
  }

  if (FORBIDDEN_PIDS.has(pid)) {
    log(`refusing SIGKILL on forbidden soak pid ${pid}`);
    return { stopped: false, pid, reason: 'forbidden-pid' };
  }

  try {
    log(`SIGKILL owned Host pid=${pid} after ${graceMs}ms grace`);
    child.kill('SIGKILL');
  } catch (err) {
    log(`SIGKILL failed: ${err && err.message ? err.message : err}`);
  }

  await sleep(200);
  return {
    stopped: !isChildAlive(child),
    pid,
    reason: isChildAlive(child) ? 'still-alive' : 'sigkill',
  };
}


/**
 * Resolve how to invoke `agk <args…>` — same launcher preference as Host serve
 * (`uv run agk` → `.venv/bin/agk` → `.venv/bin/python -m antigravity_k.cli` → `agk`).
 *
 * @param {string[]} agkArgs arguments after `agk` (e.g. ['diagnostics', 'export'])
 * @param {{ repoRoot?: string }} [opts]
 * @returns {{ command: string, args: string[], cwd: string, label: string }}
 */
function resolveAgkCliSpec(agkArgs, opts = {}) {
  const repoRoot = opts.repoRoot || resolveRepoRoot();
  const argsList = Array.isArray(agkArgs) ? agkArgs : [];
  const bareLabel = `agk ${argsList.join(' ')}`.trim();

  if (commandExists('uv')) {
    return {
      command: 'uv',
      args: ['run', 'agk', ...argsList],
      cwd: repoRoot,
      label: `uv run ${bareLabel}`,
    };
  }

  const venvAgk = path.join(repoRoot, '.venv', 'bin', 'agk');
  if (fs.existsSync(venvAgk)) {
    return {
      command: venvAgk,
      args: argsList,
      cwd: repoRoot,
      label: `.venv/bin/${bareLabel}`,
    };
  }

  const venvPy = path.join(repoRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPy)) {
    return {
      command: venvPy,
      args: ['-m', 'antigravity_k.cli', ...argsList],
      cwd: repoRoot,
      label: `.venv/bin/python -m antigravity_k.cli ${argsList.join(' ')}`.trim(),
    };
  }

  if (commandExists('agk')) {
    return {
      command: 'agk',
      args: argsList,
      cwd: repoRoot,
      label: bareLabel,
    };
  }

  throw new Error(
    'No agk launcher found. Install uv (preferred) or ensure .venv/bin/agk ' +
      '(or python -m antigravity_k.cli) is available — same paths as Host spawn.',
  );
}

/**
 * Parse ZIP path from `agk diagnostics export` stdout (fallback when --output omitted).
 * @param {string} stdout
 * @returns {string | null}
 */
function parseDiagnosticsZipPath(stdout) {
  const text = String(stdout || '');
  const m =
    text.match(/Diagnostics ZIP written:\s*(.+)/i) ||
    text.match(/ZIP written:\s*(.+)/i);
  if (!m) return null;
  return m[1].trim().replace(/^['"]|['"]$/g, '');
}

/**
 * Run the same path as `agk diagnostics export` via child_process (Promise; does not
 * block the Electron main thread event loop). Prefer `--output` so the caller knows
 * the ZIP path without parsing.
 *
 * @param {{
 *   repoRoot?: string,
 *   outputPath?: string,
 *   timeoutMs?: number,
 *   env?: NodeJS.ProcessEnv,
 * }} [opts]
 * @returns {Promise<{
 *   ok: boolean,
 *   zipPath: string | null,
 *   code: number | null,
 *   signal: NodeJS.Signals | null,
 *   stdout: string,
 *   stderr: string,
 *   label: string,
 *   error?: string,
 * }>}
 */
function runDiagnosticsExport(opts = {}) {
  const timeoutMs = opts.timeoutMs ?? 120_000;
  const repoRoot = opts.repoRoot || resolveRepoRoot();
  const agkArgs = ['diagnostics', 'export'];
  if (opts.outputPath) {
    agkArgs.push('--output', String(opts.outputPath));
  }

  let spec;
  try {
    spec = resolveAgkCliSpec(agkArgs, { repoRoot });
  } catch (err) {
    return Promise.resolve({
      ok: false,
      zipPath: null,
      code: null,
      signal: null,
      stdout: '',
      stderr: '',
      label: 'agk diagnostics export',
      error: err && err.message ? err.message : String(err),
    });
  }

  return new Promise((resolve) => {
    /** @type {import('child_process').ChildProcess} */
    const child = spawn(spec.command, spec.args, {
      cwd: spec.cwd,
      env: opts.env || process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';
    let settled = false;
    /** @type {ReturnType<typeof setTimeout> | null} */
    let timer = null;

    const finish = (result) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve(result);
    };

    if (child.stdout) {
      child.stdout.setEncoding('utf8');
      child.stdout.on('data', (chunk) => {
        stdout += chunk;
        if (stdout.length > 200_000) stdout = stdout.slice(-100_000);
      });
    }
    if (child.stderr) {
      child.stderr.setEncoding('utf8');
      child.stderr.on('data', (chunk) => {
        stderr += chunk;
        if (stderr.length > 200_000) stderr = stderr.slice(-100_000);
      });
    }

    child.on('error', (err) => {
      finish({
        ok: false,
        zipPath: null,
        code: null,
        signal: null,
        stdout,
        stderr,
        label: spec.label,
        error: err && err.message ? err.message : String(err),
      });
    });

    child.on('close', (code, signal) => {
      const parsed = parseDiagnosticsZipPath(stdout);
      const zipPath =
        (opts.outputPath && code === 0 ? String(opts.outputPath) : null) || parsed;
      const ok = code === 0 && Boolean(zipPath);
      finish({
        ok,
        zipPath: zipPath || null,
        code,
        signal,
        stdout,
        stderr,
        label: spec.label,
        error: ok
          ? undefined
          : stderr.trim() ||
            (code === null && signal
              ? `terminated by signal ${signal}`
              : `exit code ${code}`),
      });
    });

    timer = setTimeout(() => {
      try {
        if (child.pid && !FORBIDDEN_PIDS.has(child.pid)) {
          child.kill('SIGTERM');
        }
      } catch {
        /* ignore */
      }
      setTimeout(() => {
        try {
          if (isChildAlive(child) && child.pid && !FORBIDDEN_PIDS.has(child.pid)) {
            child.kill('SIGKILL');
          }
        } catch {
          /* ignore */
        }
      }, 2_000);
      finish({
        ok: false,
        zipPath: null,
        code: null,
        signal: 'SIGTERM',
        stdout,
        stderr,
        label: spec.label,
        error: `diagnostics export timed out after ${timeoutMs}ms`,
      });
    }, timeoutMs);
    if (typeof timer.unref === 'function') timer.unref();
  });
}

module.exports = {
  DEFAULT_HOST_URL,
  DEFAULT_SPAWN_HOST,
  DEFAULT_START_TIMEOUT_MS,
  DEFAULT_STOP_GRACE_MS,
  FORBIDDEN_PIDS,
  spawnHostEnabled,
  resolveHostUrl,
  parseHostBind,
  resolveRepoRoot,
  resolveSpawnSpec,
  resolveAgkCliSpec,
  parseDiagnosticsZipPath,
  runDiagnosticsExport,
  hostProbe,
  tcpPortOpen,
  suspectPortConflict,
  waitForHostReady,
  isChildAlive,
  spawnOwnedHost,
  stopOwnedHost,
  sleep,
};
