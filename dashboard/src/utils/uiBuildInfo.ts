/**
 * UI 번들 빌드 provenance 접근자 (CR-10)
 * ======================================
 * `vite.config.ts`/`vitest.config.ts`의 `define`이 주입한 컴파일 타임 상수를 읽는다.
 * 컴파일 타임 상수를 직접 참조하면 단위 테스트에서 값을 바꿀 수 없으므로, 얇은 함수로
 * 감싸 테스트가 mock할 수 있게 한다(서버 버전과 번들 버전이 다른 경우의 표시 검증).
 *
 * 미기록 값은 null이다 — 화면은 UNKNOWN을 표시한다.
 */

export interface UiBuildInfo {
  /** `dashboard/package.json`의 버전. */
  version: string;
  /** 이 번들을 만든 빌드/커밋 식별자. 미기록이면 null. */
  buildId: string | null;
  /** 이 번들을 만든 시각. 미기록이면 null. */
  builtAt: string | null;
}

export function getUiBuildInfo(): UiBuildInfo {
  return {
    version: __AGK_UI_VERSION__,
    buildId: __AGK_BUILD_ID__,
    builtAt: __AGK_BUILT_AT__,
  };
}
