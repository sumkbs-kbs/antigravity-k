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
  /** 이 서버가 살아 있는 동안의 상태 디렉터리(토큰 비밀·PIN 해시·격리 env 파일). */
  stateDirectory: string;
  /** uvicorn 프로세스의 pid — 크래시 슬라이스가 신호를 보낸다. */
  pid: number | undefined;
  /** 이 서버에 신호를 보낸다(기본 `SIGKILL` — 크래시를 재현할 때 정상 종료를 쓰면 다른 질문이 된다). */
  kill: (signal?: NodeJS.Signals) => boolean;
  cleanup: () => Promise<void>;
}

export interface HermeticServerOptions {
  /**
   * 서버 프로세스의 **작업 디렉터리**(기본: 저장소 루트).
   *
   * 프로젝트 레지스트리는 **상대 경로**(`data/projects.json`)라 서버의 cwd 를 따라간다 — 그리고
   * 그 값이 이 증인의 질문에 들어 있다: 한 번도 열리지 않은 프로젝트는 `last_accessed_at: null`
   * 로 직렬화된다(개발 기계의 레지스트리는 이미 열려 있어 그 값을 감춘다). 격리된 디렉터리를 넘기면
   * 서버가 **처음 설치한 기계**를 보게 된다 — 저장소는 그대로 import 하되 cwd 만 옴긴다.
   */
  workingDirectory?: string;
  /**
   * 재사용할 상태 디렉터리 — **크래시·재시작 슬라이스**가 쓴다.
   *
   * 같은 디렉터리를 다시 넘기면 두 번째 프로세스가 **같은** PIN 해시·토큰 비밀을 보게 된다.
   * 토큰 비밀이 바뀌면 브라우저가 들고 있던 세션이 무효가 되므로, 재시작 뒤의 질문
   * ("열려 있는 화면이 새 사실을 배우는가")이 **다른 질문**(인증 실패)으로 바뀐다.
   */
  stateDirectory?: string;
  /** 정리할 때 상태 디렉터리까지 지울지(기본 true). 두 번째 서버가 지운다. */
  removeStateOnCleanup?: boolean;
  /**
   * 고정 포트(기본 0 = 임의).**크래시·재시작 슬라이스는 반드시 고정 포트를 쓴다**:
   * 브라우저 탭의 origin 은 포트를 포함하므로, 재기동이 다른 포트로 뜨면 화면은 **다른 서버**를
   * 보게 되고 질문이 "재연결이 새 사실을 가져오는가"에서 "죽은 서버를 보는 화면"으로 바뀐다.
   */
  port?: number;
  /** 서버 프로세스에 추가로 넘길 환경. 첫 서버와 두 번째 서버에 **같은 값**을 넘겨야 한다. */
  overrides?: Record<string, string>;
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

export async function startBackendServer(
  overrides: Record<string, string>,
  options: HermeticServerOptions = {},
): Promise<HermeticServer> {
  const stateDirectory = options.stateDirectory
    ?? await mkdtemp(path.join(tmpdir(), 'agk-e2e-auth-'));
  const secretPath = path.join(stateDirectory, 'token_secret');
  await writeFile(secretPath, randomBytes(32).toString('hex'), {
    mode: 0o600,
    encoding: 'utf8',
  });
  const isolatedEnvFile = path.join(stateDirectory, 'isolated.env');
  await writeFile(isolatedEnvFile, '# isolated scenario env — intentionally empty\n', {
    encoding: 'utf8',
  });
  const projectRoot = path.resolve(process.cwd(), '..');
  const workingDirectory = options.workingDirectory ?? projectRoot;
  const listener = childProcess.spawn(
    'uv',
    [
      'run',
      '--project',
      projectRoot,
      '--no-sync',
      'python',
      '-m',
      'uvicorn',
      'antigravity_k.api.server:app',
      '--host',
      '127.0.0.1',
      '--port',
      String(options.port ?? 0),
    ],
    {
      cwd: workingDirectory,
      env: {
        ...process.env,
        PYTHONPATH: path.join(projectRoot, 'src'),
        AGK_ENV: 'development',
        AGK_ENV_FILE: isolatedEnvFile,
        AGK_SEC_ACCESS_PIN: '',
        AGK_ACCESS_PIN: '',
        AGK_SEC_PIN_HASH_FILE: path.join(stateDirectory, 'pin_hash'),
        AGK_SEC_TOKEN_SECRET_FILE: secretPath,
        ...options.overrides,
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
    stateDirectory,
    pid: listener.pid,
    kill: (signal: NodeJS.Signals = 'SIGKILL') => listener.kill(signal),
    cleanup: async () => {
      listener.kill('SIGTERM');
      await new Promise(resolve => {
        if (listener.exitCode !== null || listener.signalCode !== null) {
          resolve(null);
          return;
        }
        listener.once('exit', resolve);
      });
      if (options.removeStateOnCleanup ?? true) {
        await rm(stateDirectory, { recursive: true, force: true });
      }
    },
  };
}

/** Backend with authentication disabled (no PIN, no hash file). */
export function startNoAuthServer(): Promise<HermeticServer> {
  return startBackendServer({});
}

/** Backend with a configured plaintext PIN (bootstrap-hashed on first boot). */
export function startAuthServer(
  tokenTtlHours: number,
  options: HermeticServerOptions = {},
): Promise<HermeticServer> {
  return startBackendServer(
    {
      AGK_SEC_ACCESS_PIN: authPin,
      AGK_SEC_TOKEN_TTL_HOURS: String(tokenTtlHours),
    },
    options,
  );
}
