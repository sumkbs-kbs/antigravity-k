/**
 * Monaco 언어 워커 팩토리 (CR-09)
 * ==============================
 * `?worker` import는 Vite가 **로컬 chunk**로 emit한다 — 이전에는 로더가 CDN의
 * `monaco-editor/min/vs` 트리에서 워커를 가져왔다(오프라인에서는 편집기 없음).
 *
 * 워커 import를 이 모듈에 모아 두는 이유: jsdom 단위 테스트는 `?worker` specifier를
 * 해석할 수 없으므로 vitest 설정이 이 파일만 스텁으로 alias한다.
 */
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker.js?worker';
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker.js?worker';
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker.js?worker';
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker.js?worker';
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker.js?worker';

export interface MonacoWorkerFactories {
  readonly editor: () => Worker;
  readonly json: () => Worker;
  readonly css: () => Worker;
  readonly html: () => Worker;
  readonly typescript: () => Worker;
}

export const MONACO_WORKER_FACTORIES: MonacoWorkerFactories = {
  editor: () => new editorWorker(),
  json: () => new jsonWorker(),
  css: () => new cssWorker(),
  html: () => new htmlWorker(),
  typescript: () => new tsWorker(),
};
