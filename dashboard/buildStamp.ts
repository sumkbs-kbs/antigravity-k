/**
 * 빌드 provenance (CR-10)
 * =======================
 * BUILD 지표는 "지금 서빙되는 번들이 어느 빌드인지"를 말해야 한다. 값을 여기서 한 번
 * 계산해 `vite.config.ts`(프로덕션 빌드)와 `vitest.config.ts`(단위 테스트)가 같은
 * `define`을 쓰도록 한다.
 *
 * 릴리스 파이프라인이 `AGK_BUILD_ID`/`AGK_BUILT_AT`를 주입하면 그 값을, 없으면 로컬
 * git short SHA를 쓴다. 그것도 없으면 `null`이다 — 추측값으로 채우지 않는다.
 * 기록되지 않은 값은 화면에서 UNKNOWN으로 표시된다.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));

function gitShortSha(): string | null {
  try {
    const sha = execFileSync('git', ['rev-parse', '--short', 'HEAD'], {
      cwd: dashboardRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    return sha || null;
  } catch {
    return null;
  }
}

function readUiVersion(): string {
  const raw = readFileSync(path.join(dashboardRoot, 'package.json'), 'utf8');
  const parsed = JSON.parse(raw) as { version?: string };
  return parsed.version ?? '0.0.0';
}

function envOrNull(name: string): string | null {
  const value = process.env[name]?.trim();
  return value ? value : null;
}

/** 대시보드 번들이 스스로 보고하는 버전(`dashboard/package.json`). */
export const uiVersion: string = readUiVersion();
/** 이 번들을 만든 커밋/빌드 식별자. 기록이 없으면 null. */
export const buildId: string | null = envOrNull('AGK_BUILD_ID') ?? gitShortSha();
/** 이 번들을 만든 시각. 기록이 없으면 null. */
export const builtAt: string | null = envOrNull('AGK_BUILT_AT') ?? null;

/** Vite/Vitest `define`에 넣을 컴파일 타임 상수. */
export const buildStampDefine: Record<string, string> = {
  __AGK_UI_VERSION__: JSON.stringify(uiVersion),
  __AGK_BUILD_ID__: JSON.stringify(buildId),
  __AGK_BUILT_AT__: JSON.stringify(builtAt),
};
