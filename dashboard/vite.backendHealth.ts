/**
 * Dev-only: probe Vite proxy backend once at server start.
 * Loud warning if VITE_BACKEND_URL / AGK_BACKEND_URL / default target is dead,
 * or if the target still points at legacy :8400 (product Host default is :8000).
 * Never fails Vite startup (5173/5174 keep running).
 */
import type { Plugin } from 'vite';
import http from 'node:http';
import https from 'node:https';
import { URL } from 'node:url';

const DEFAULT_BACKEND = 'http://127.0.0.1:8000';
const LEGACY_PORT_RE = /:(?:8400)(?:\/|$)/;

export function resolveBackendTarget(
  env: NodeJS.ProcessEnv = process.env,
): string {
  return (
    env.VITE_BACKEND_URL ||
    env.AGK_BACKEND_URL ||
    DEFAULT_BACKEND
  ).replace(/\/$/, '');
}

function probeOnce(targetBase: string, timeoutMs = 2500): Promise<{ ok: boolean; detail: string }> {
  let url: URL;
  try {
    url = new URL('/health', targetBase.endsWith('/') ? targetBase : `${targetBase}/`);
  } catch (err) {
    return Promise.resolve({
      ok: false,
      detail: `invalid URL: ${(err as Error).message}`,
    });
  }

  const lib = url.protocol === 'https:' ? https : http;
  return new Promise((resolve) => {
    const req = lib.request(
      url,
      { method: 'GET', timeout: timeoutMs },
      (res) => {
        res.resume();
        const code = res.statusCode ?? 0;
        if (code >= 200 && code < 500) {
          resolve({ ok: true, detail: `HTTP ${code}` });
        } else {
          resolve({ ok: false, detail: `HTTP ${code}` });
        }
      },
    );
    req.on('timeout', () => {
      req.destroy();
      resolve({ ok: false, detail: `timeout after ${timeoutMs}ms` });
    });
    req.on('error', (err) => {
      resolve({ ok: false, detail: err.message });
    });
    req.end();
  });
}

function banner(lines: string[]): void {
  const bar = '!'.repeat(72);
  // eslint-disable-next-line no-console
  console.warn(`\n${bar}`);
  for (const line of lines) {
    // eslint-disable-next-line no-console
    console.warn(`! ${line}`);
  }
  // eslint-disable-next-line no-console
  console.warn(`${bar}\n`);
}

export function backendProxyHealthPlugin(target = resolveBackendTarget()): Plugin {
  let probed = false;

  return {
    name: 'ssak-backend-proxy-health',
    apply: 'serve',
    configureServer(server) {
      const run = async () => {
        if (probed) return;
        probed = true;

        if (LEGACY_PORT_RE.test(target)) {
          banner([
            'VITE PROXY TARGET USES LEGACY PORT :8400',
            `  target = ${target}`,
            '  Product Host / Electron default is http://127.0.0.1:8000.',
            '  Dead :8400 → settings save / API calls via Vite proxy FAIL silently.',
            '  Fix: unset VITE_BACKEND_URL / AGK_BACKEND_URL, or set to http://127.0.0.1:8000',
            '  Product path (no Vite): agk serve serves dashboard_dist on one loopback port.',
          ]);
        }

        const result = await probeOnce(target);
        if (result.ok) {
          server.config.logger.info(
            `[ssak] Vite proxy backend OK → ${target} (${result.detail})`,
          );
          return;
        }

        banner([
          'VITE PROXY BACKEND UNREACHABLE',
          `  target = ${target}`,
          `  probe  = GET ${target}/health → ${result.detail}`,
          '  Default is http://127.0.0.1:8000 (NOT :8400).',
          '  Start Host:  uv run agk serve --host 127.0.0.1 --port 8000',
          '  Or set:      VITE_BACKEND_URL=http://127.0.0.1:<live-port>',
          '  Vite keeps running; /api and /ws via proxy will fail until backend is up.',
          '  Product mode needs no Vite — Host serves SPA from dashboard_dist.',
        ]);
      };

      // After listen so the warning is not buried under Vite's own banners.
      server.httpServer?.once('listening', () => {
        void run();
      });
      // Fallback if httpServer is not yet attached when configureServer runs.
      setTimeout(() => {
        void run();
      }, 1500);
    },
  };
}
