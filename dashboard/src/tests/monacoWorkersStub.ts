/**
 * 단위 테스트용 Monaco 워커 팩토리 스텁 (CR-09)
 * ===========================================
 * jsdom은 `?worker` specifier를 해석하지 못하고(브라우저 전용) 실제 워커도 쓸 수
 * 없으므로, vitest 설정이 `src/utils/monacoWorkers.ts`를 이 모듈로 alias한다.
 * 라벨별 선택 계약은 `src/utils/monacoRuntime.test.ts`가 이 스텁으로 검증한다.
 */
class MonacoWorkerStub {
  constructor(readonly label: string) {}
}

function create(label: string): Worker {
  return new MonacoWorkerStub(label) as unknown as Worker;
}

export const MONACO_WORKER_FACTORIES = {
  editor: () => create('editor'),
  json: () => create('json'),
  css: () => create('css'),
  html: () => create('html'),
  typescript: () => create('typescript'),
} as const;
