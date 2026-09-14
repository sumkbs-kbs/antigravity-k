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

import { existsSync } from 'node:fs';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomBytes } from 'node:crypto';

import childProcess from 'node:child_process';
import { createServer } from 'node:net';

export const authPin = 'e2e-auth-pin-20260903';

export interface HermeticServer {
  baseUrl: string;
  /** 이 서버가 살아 있는 동안의 상태 디렉터리(토큰 비밀·PIN 해시·격리 env 파일). */
  stateDirectory: string;
  /**
   * HookEventBus 가 감시하는 vault 루트(`…/hooks/events.jsonl` 의 부모의 부모).
   * 스펙이 파일을 주입할 때 **이 값**을 써야 서버와 합의한다(CR-14 F-45).
   */
  hookVaultDir: string;
  /** 서버 **프로세스 그룹 리더**의 pid — 크래시 슬라이스가 이 그룹째로 신호를 보낸다. */
  pid: number | undefined;
  /**
   * 이 서버를 멈춘다(기본 `SIGKILL` — 크래시를 재현할 때 정상 종료를 쓰면 다른 질문이 된다).
   *
   * 신호는 **프로세스 그룹 전체**로 간다: 이 하네스는 `uv run … uvicorn` 을 띄우므로 실제 서버는
   * 런처의 **자식**이다 — 런처만 죽이면 uvicorn 이 살아남아 포트를 붙들고 있고, 그 상태에서는
   * "크래시"가 크래시가 아니다(그 사실을 attempt-030 의 증인이 처음 만났다).
   */
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


async function allocateLoopbackPort(): Promise<number> {
  return await new Promise<number>((resolve, reject) => {
    const probe = createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address();
      if (address === null || typeof address === 'string') {
        probe.close();
        reject(new Error('loopback port allocation failed'));
        return;
      }
      const { port } = address;
      probe.close(error => {
        if (error) reject(error);
        else resolve(port);
      });
    });
  });
}

export async function startBackendServer(
  overrides: Record<string, string>,
  options: HermeticServerOptions = {},
): Promise<HermeticServer> {
  const stateDirectory = options.stateDirectory
    ?? await mkdtemp(path.join(tmpdir(), 'agk-e2e-auth-'));
  const secretPath = path.join(stateDirectory, 'token_secret');
  // 상태 디렉터리를 **재사용**하는 두 번째 서버는 비밀을 **새로 만들지 않는다**: 새로 만들면
  // 브라우저가 들고 있던 세션이 무효가 되어 질문이 "화면이 새 사실을 배우는가"에서 "사용자가
  // 로그아웃됐는가"로 바뀐다(이 파일의 docstring 이 처음부터 약속한 성질이다 — 약속과 구현이
  // 갈라져 있던 것을 attempt-030 의 증인이 만났다).
  if (!existsSync(secretPath)) {
    await writeFile(secretPath, randomBytes(32).toString('hex'), {
      mode: 0o600,
      encoding: 'utf8',
    });
  }
  const isolatedEnvFile = path.join(stateDirectory, 'isolated.env');
  await writeFile(isolatedEnvFile, '# isolated scenario env — intentionally empty\n', {
    encoding: 'utf8',
  });

  const projectRoot = path.resolve(process.cwd(), '..');
  const workingDirectory = options.workingDirectory ?? projectRoot;
  // CR-14 F-45: 훅 IPC 를 상태 디렉터리로 격리한다 — 공유 `vault_data/hooks` 는
  // ambient 서버·다른 테스트와 줄을 섞어 증인이 침묵한다(실측 15MB·13만 줄).
  const hookVaultDir = path.join(stateDirectory, 'vault_data');
  const isolatedDataDir = path.join(stateDirectory, 'data');
  const isolatedLogsDir = path.join(stateDirectory, 'logs');
  // 부모(스펙) 프로세스도 같은 경로를 보게 — hookEventsPath() 가 env 를 읽는다.
  const previousHookVault = process.env.AGK_HOOK_VAULT_DIR;
  process.env.AGK_HOOK_VAULT_DIR = hookVaultDir;
  // SEC-03 Origin allowlist 는 정확 일치다. hermetic 이 임의 포트(0)로 뜨면
  // 브라우저 Origin(`http://127.0.0.1:<port>`)이 기본 allowlist 에 없어
  // `/v1/ws/events` 가 4403 으로 즉시 끊긴다(실측: frames=0 · LINK 는 다른 채널).
  // 포트를 **미리** 잡고 그 Origin 을 `AGK_CORS_ORIGINS` 에 넣는다.
  const listenPort = options.port ?? await allocateLoopbackPort();
  const pageOrigin = `http://127.0.0.1:${listenPort}`;
  const corsOrigins = [
    pageOrigin,
    `http://localhost:${listenPort}`,
    'http://127.0.0.1:8012',
    'http://localhost:8012',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1:5173',
    'http://localhost:5173',
    'http://127.0.0.1:5174',
    'http://localhost:5174',
  ].join(',');
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
      String(listenPort),
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
        AGK_HOOK_VAULT_DIR: hookVaultDir,
        AGK_PATH_DATA_DIR: isolatedDataDir,
        AGK_PATH_LOGS_DIR: isolatedLogsDir,
        AGK_CORS_ORIGINS: corsOrigins,
        ...options.overrides,
        ...overrides,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      // 새 프로세스 그룹의 리더로 띄운다 — 실제 서버(`uvicorn`)는 런처(`uv`)의 자식이므로
      // 런처만 죽이는 신호는 **크래시가 아니다**(포트를 붙들고 살아남는다).
      detached: true,
    },
  );
  /**
   * 그룹째로 신호를 보낸다 — `detached: true` 로 띄우므로 `-pid` 가 그 그룹이다.
   *
   * 실패하면(이미 죽었거나 그룹이 없으면) 직접 신호로 물러선다: 죽은 프로세스에 신호를 보내는
   * 것은 오류가 아니고, 두 번째 서버를 정리하는 경로가 그 사실 때문에 실패하면 안 된다.
   */
  const signalProcessGroup = (target: number | undefined, signal: NodeJS.Signals): boolean => {
    if (target === undefined) return false;
    try {
      process.kill(-target, signal);
      return true;
    } catch {
      return listener.kill(signal);
    }
  };
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
    hookVaultDir,
    pid: listener.pid,
    kill: (signal: NodeJS.Signals = 'SIGKILL') => signalProcessGroup(listener.pid, signal),
    cleanup: async () => {
      if (previousHookVault === undefined) {
        delete process.env.AGK_HOOK_VAULT_DIR;
      } else {
        process.env.AGK_HOOK_VAULT_DIR = previousHookVault;
      }
      signalProcessGroup(listener.pid, 'SIGTERM');
      const exited = new Promise(resolve => {
        if (listener.exitCode !== null || listener.signalCode !== null) {
          resolve(null);
          return;
        }
        listener.once('exit', resolve);
      });
      // 정상 종료를 거부하는 서버(또는 이미 크래시한 서버의 남은 그룹)가 정리 단계를 붙들면
      // 다음 시나리오가 포트를 못 잡는다 — 유예를 넘기면 그룹째 강제로 끝낸다.
      const forced = new Promise(resolve => setTimeout(resolve, 5_000));
      await Promise.race([exited, forced]);
      signalProcessGroup(listener.pid, 'SIGKILL');
      await exited;
      if (options.removeStateOnCleanup ?? true) {
        await rm(stateDirectory, { recursive: true, force: true });
      }
    },
  };
}

/**
 * Backend with authentication disabled (no PIN, no hash file).
 *
 * `AGK_SEC_DEV_NO_PIN_ALLOW=1` 이 없으면 이 서버는 **열려 있지 않다** — 제품의 인증 정책은
 * fail-closed 다(무자격 + dev 허용 env 없음 → deny: `auth_policy.resolve_auth_decision` 규칙 3).
 * 이 env 없이는 브라우저가 PIN 잠금 화면을 보고, "no-auth 서버"라는 이 함수의 약속과 실제가
 * 갈라진다(ws-contract-e2e 가 그 갈라짐을 만났다 — CR-14 F-45). 이 env 는 **loopback + 개발
 * 환경에서만** 열린다(production 은 정책이 이중으로 거부한다).
 */
export function startNoAuthServer(): Promise<HermeticServer> {
  return startBackendServer({ AGK_SEC_DEV_NO_PIN_ALLOW: '1' });
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
