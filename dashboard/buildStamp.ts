/**
 * 빌드 provenance (CR-10 / CR-14 F-12)
 * ===================================
 * BUILD 지표는 "지금 서빙되는 번들이 어느 빌드인지"를 말해야 한다. 값을 여기서 한 번
 * 계산해 `vite.config.ts`(프로덕션 빌드)와 `vitest.config.ts`(단위 테스트)가 같은
 * `define`을 쓰도록 한다.
 *
 * **F-12 (2026-09-13 실측)**: 예전에는 `AGK_BUILD_ID` 가 없으면 `git rev-parse --short HEAD`
 * 를 썼다. 그 결과 **커밋된 번들은 자기 커밋의 SHA 를 담을 수 없었다** — 번들을 만든 시점의
 * HEAD 는 부모 커밋이고, 커밋이 생기면 HEAD 가 바뀌므로 다음 빌드는 반드시 다른 바이트를
 * 낸다(실측: 커밋 전 재빌드 = no-op, 커밋 후 재빌드 = 자산 22개 교체 + 지문 이동). 즉
 * `dashboard-build` gate 가 후보 트리를 매번 흔들어 **커밋된 후보에서 단일 지문 20/20 을
 * 완주할 수 없었다.**
 *
 * 그래서 해석 순서에 **커밋된 핀 파일**을 넣는다:
 *
 *   1. 환경변수 `AGK_BUILD_ID` / `AGK_BUILT_AT` (릴리스 파이프라인 주입)
 *   2. `dashboard/build-provenance.json` (커밋된 기록 — 번들을 만든 **소스 리비전**)
 *   3. `git rev-parse --short HEAD` (핀도 기록도 없는 개발 트리)
 *   4. 없으면 `null` — 추측값으로 채우지 않는다. 기록되지 않은 값은 화면에서 UNKNOWN 이다.
 *
 * 핀은 "이 번들이 어느 소스에서 만들어졌는가"를 기록한다(그 커밋이 번들을 담고 있는 커밋과
 * 같을 필요는 없다 — 자기 자신을 담을 수 없다는 것이 이 결함의 내용이다). 핀이 있는 한
 * 로컬·CI·Docker 빌드가 **같은 바이트**를 내고, 출하 컨테이너도 커밋된 번들과 동일해진다
 * (`.git` 이 없는 컨테이너에서 buildId 가 UNKNOWN 으로 떨어지던 문제도 함께 닫힌다).
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));

/** 커밋된 provenance 핀 파일(대시보드 루트 기준). */
export const BUILD_PROVENANCE_FILE = 'build-provenance.json';

interface BuildProvenancePin {
  buildId?: unknown;
  builtAt?: unknown;
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** 커밋된 핀을 읽는다. 파일이 없거나 깨졌으면 `null` 을 돌려주고 다음 순위로 내려간다. */
export function readBuildProvenancePin(): { buildId: string | null; builtAt: string | null } {
  try {
    const raw = readFileSync(path.join(dashboardRoot, BUILD_PROVENANCE_FILE), 'utf8');
    const parsed = JSON.parse(raw) as BuildProvenancePin;
    return { buildId: nonEmptyString(parsed.buildId), builtAt: nonEmptyString(parsed.builtAt) };
  } catch {
    return { buildId: null, builtAt: null };
  }
}

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
  return nonEmptyString(process.env[name]);
}

const pin = readBuildProvenancePin();

/** 대시보드 번들이 스스로 보고하는 버전(`dashboard/package.json`). */
export const uiVersion: string = readUiVersion();
/** 이 번들을 만든 리비전/빌드 식별자. 기록이 없으면 null. */
export const buildId: string | null = envOrNull('AGK_BUILD_ID') ?? pin.buildId ?? gitShortSha();
/** 이 번들을 만든 시각. 기록이 없으면 null. */
export const builtAt: string | null = envOrNull('AGK_BUILT_AT') ?? pin.builtAt;

/** Vite/Vitest `define`에 넣을 컴파일 타임 상수. */
export const buildStampDefine: Record<string, string> = {
  __AGK_UI_VERSION__: JSON.stringify(uiVersion),
  __AGK_BUILD_ID__: JSON.stringify(buildId),
  __AGK_BUILT_AT__: JSON.stringify(builtAt),
};
