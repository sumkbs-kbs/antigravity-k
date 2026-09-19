/**
 * 단위 테스트용 Monaco 스텁 (CR-09)
 * =================================
 * vitest.config.ts가 `monaco-editor`(및 그 하위 워커 specifier)를 이 모듈로
 * alias한다. 이유:
 *   · jsdom에는 monaco가 모듈 로드 시 요구하는 브라우저 API가 없다
 *     (`document.queryCommandSupported` 등) → 실제 모듈을 로드하면 suite가 깨진다.
 *   · monaco ESM은 수 MB라 단위 테스트에서 로드할 이유가 없다 — 편집기를 쓰는
 *     컴포넌트 테스트는 어차피 MonacoEditorWrapper/DiffViewer를 mock한다.
 *
 * 실제 로컬 Monaco 로딩 계약은 `src/utils/monacoRuntime.test.ts`(설정 주입)와
 * 브라우저 e2e(`e2e/tests/cr09-offline-assets.spec.ts`, 승인 큐 diff가 외부 요청 0)가
 * 검증한다.
 */
export default class MonacoStubWorker {}

export const editor = {};
export const languages = {};
export const Uri = {};
