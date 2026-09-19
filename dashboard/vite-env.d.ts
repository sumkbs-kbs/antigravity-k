/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly DEV: boolean;
  readonly VITE_ENABLE_REACT_DEVTOOLS?: string;
  readonly VITE_DISABLE_REACT_DEVTOOLS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/*
 * CR-10 빌드 provenance.
 * `dashboard/buildStamp.ts`의 값이 vite.config.ts / vitest.config.ts의 `define`으로
 * 주입된다. 미기록 값은 null이며 화면은 UNKNOWN을 표시한다.
 */
declare const __AGK_UI_VERSION__: string;
declare const __AGK_BUILD_ID__: string | null;
declare const __AGK_BUILT_AT__: string | null;
