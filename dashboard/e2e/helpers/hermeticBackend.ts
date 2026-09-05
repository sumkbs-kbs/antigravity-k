/**
 * Hermetic backend helpers for Playwright E2E.
 *
 * Spawns an isolated uvicorn backend owned by the calling scenario so tests
 * never depend on the machine's `.env`, `data/auth_hash`, or a shared backend.
 *
 * Every auth-related knob is pinned explicitly in the child environment:
 * - `AGK_SEC_ACCESS_PIN` / `AGK_ACCESS_PIN` are set to an empty string
 *   (empty-string values cannot be overwritten by `load_dotenv(override=False)`).
 * - `AGK_ENV` is forced to `development`.
 * - `AGK_ENV_FILE` points at an empty temp file so the project `.env` cannot
 *   re-inject PIN/provider configuration.
 * - `AGK_SEC_PIN_HASH_FILE` points at a fresh temp path that does not exist,
 *   so the shared `data/auth_hash` is never read. With no hash file and an
 *   empty `access_pin`, `/api/auth/login` returns 503 (auth disabled).
 * - `AGK_SEC_TOKEN_SECRET_FILE` is a fresh random secret.
 *
 * `overrides` (e.g. a PIN + TTL) are applied last so auth scenarios can opt
 * in to a configured PIN.
 */

import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomBytes } from 'node:crypto';

import childProcess from 'node:child_process';

export const authPin = 'e2e-auth-pin-20260903';

export interface HermeticServer {
  baseUrl: string;
  cleanup: () => Promise<void>;
}

export async function waitForHealth(baseUrl: string): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) return;
    } catch {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  throw new Error(`Backend did not become healthy: ${baseUrl}`);
}

export async function startBackendServer(overrides: Record<string, string>): Promise<HermeticServer> {
  const stateDirectory = await mkdtemp(path.join(tmpdir(), 'agk-e2e-auth-'));
  const secretPath = path.join(stateDirectory, 'token_secret');
  await writeFile(secretPath, randomBytes(32).toString('hex'), {
    mode: 0o600,
    encoding: 'utf8',
  });
  const isolatedEnvFile = path.join(stateDirectory, 'isolated.env');
  await writeFile(isolatedEnvFile, '# isolated scenario env — intentionally empty\n', {
    encoding: 'utf8',
  });
  const listener = childProcess.spawn(
    'uv',
    [
      'run',
      '--no-sync',
      'python',
      '-m',
      'uvicorn',
      'antigravity_k.api.server:app',
      '--host',
      '127.0.0.1',
      '--port',
      '0',
    ],
    {
      cwd: path.resolve(process.cwd(), '..'),
      env: {
        ...process.env,
        PYTHONPATH: 'src',
        AGK_ENV: 'development',
        AGK_ENV_FILE: isolatedEnvFile,
        AGK_SEC_ACCESS_PIN: '',
        AGK_ACCESS_PIN: '',
        AGK_SEC_PIN_HASH_FILE: path.join(stateDirectory, 'pin_hash'),
        AGK_SEC_TOKEN_SECRET_FILE: secretPath,
        ...overrides,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
  let output = '';
  listener.stdout?.on('data', chunk => { output += chunk; });
  listener.stderr?.on('data', chunk => { output += chunk; });
  const baseUrl = await new Promise<string>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Server startup output:\n${output}`)), 15_000);
    const handleChunk = (chunk: Buffer): void => {
      const address = chunk.toString('utf8').match(/Uvicorn running on http:\/\/([^\s]+)/);
      if (address?.[1]) {
        clearTimeout(timer);
        resolve(`http://${address[1]}`);
      }
    };
    listener.stdout?.on('data', handleChunk);
    listener.stderr?.on('data', handleChunk);
  });
  await waitForHealth(baseUrl);
  return {
    baseUrl,
    cleanup: async () => {
      listener.kill('SIGTERM');
      await new Promise(resolve => {
        if (listener.exitCode !== null || listener.signalCode !== null) {
          resolve(null);
          return;
        }
        listener.once('exit', resolve);
      });
      await rm(stateDirectory, { recursive: true, force: true });
    },
  };
}

/** Backend with authentication disabled (no PIN, no hash file). */
export function startNoAuthServer(): Promise<HermeticServer> {
  return startBackendServer({});
}

/** Backend with a configured plaintext PIN (bootstrap-hashed on first boot). */
export function startAuthServer(tokenTtlHours: number): Promise<HermeticServer> {
  return startBackendServer({
    AGK_SEC_ACCESS_PIN: authPin,
    AGK_SEC_TOKEN_TTL_HOURS: String(tokenTtlHours),
  });
}
