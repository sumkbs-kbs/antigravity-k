/**
 * Monaco 런타임 로컬화 (CR-09)
 * ============================
 * 발견 F05 계열: `@monaco-editor/react`는 `@monaco-editor/loader`의 기본값을 그대로
 * 쓰면 편집기를 **CDN에서** 가져온다(`https://cdn.jsdelivr.net/npm/monaco-editor@0.55.1/min/vs`).
 * 코드 로그에는 이 URL이 그대로 남아 있었고, 실제로 편집기/변경 diff 화면이 열릴 때
 * 브라우저가 jsDelivr에서 로더 스크립트와 `vs` 트리 전체를 내려받았다 — 오프라인에서는
 * 편집기가 깨지고, 상류 CDN 스크립트가 실행되는 공급망 위험도 있었다.
 * (브라우저 실측: 승인 큐 diff에서 CDN 요청 5건 발생, `.monaco-editor` 노드 0개)
 *
 * 지금은 설치된 `monaco-editor`(정식 런타임 의존성) 인스턴스를 로더에 주입하고,
 * 언어별 워커도 로컬 chunk(`src/utils/monacoWorkers.ts`)에서 만든다. CDN 요청은 0이다.
 *
 * 이 모듈은 편집기를 실제로 여는 지연 chunk에서만 호출된다 — 초기 로드에
 * Monaco(수 MB)를 붙이지 않는다.
 */
import { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import { MONACO_WORKER_FACTORIES } from './monacoWorkers';

type MonacoGlobal = typeof globalThis & {
  MonacoEnvironment?: {
    getWorker: (workerId: string, label: string) => Worker;
  };
};

let configured = false;

/** 언어 라벨 → 로컬 워커. 알 수 없는 라벨은 기본 편집기 워커로 처리한다. */
function createWorker(_workerId: string, label: string): Worker {
  switch (label) {
    case 'json':
      return MONACO_WORKER_FACTORIES.json();
    case 'css':
    case 'scss':
    case 'less':
      return MONACO_WORKER_FACTORIES.css();
    case 'html':
    case 'handlebars':
    case 'razor':
      return MONACO_WORKER_FACTORIES.html();
    case 'typescript':
    case 'javascript':
      return MONACO_WORKER_FACTORIES.typescript();
    default:
      return MONACO_WORKER_FACTORIES.editor();
  }
}

/**
 * 로더가 CDN 대신 로컬 번들을 쓰도록 고정한다. 여러 편집기가 동시에 mount되어도
 * 한 번만 실행된다(로더 index는 단일 로드 promise를 공유한다).
 *
 * 편집기를 렌더하는 모듈들이 import 직후(모듈 스코프에서) 호출한다 —
 * `@monaco-editor/react`의 Editor가 처음 로드되기 전에 설정되어야 한다.
 */
export function configureLocalMonacoRuntime(): void {
  if (configured) return;
  configured = true;
  (globalThis as MonacoGlobal).MonacoEnvironment = { getWorker: createWorker };
  loader.config({ monaco });
}
