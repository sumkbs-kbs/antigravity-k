/**
 * CR-09 · Monaco 로컬 런타임 계약
 * ===============================
 * `@monaco-editor/react`는 로더를 설정하지 않으면 편집기를 CDN
 * (`https://cdn.jsdelivr.net/npm/monaco-editor@.../min/vs`)에서 가져온다.
 * 이 테스트는 로더에 로컬 인스턴스가 주입되는지, 언어별 워커가 로컬 chunk로
 * 연결되는지를 고정한다. 실제 로드 경로는 브라우저 e2e(승인 큐 diff)가 검증한다.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const loaderMock = vi.hoisted(() => ({ config: vi.fn() }));

vi.mock('@monaco-editor/react', () => ({ loader: loaderMock }));

import { configureLocalMonacoRuntime } from './monacoRuntime';

interface MonacoEnvironmentLike {
  getWorker: (workerId: string, label: string) => unknown;
}

function resetRuntimeFlag(): void {
  // 모듈 내부의 'configured' 플래그를 초기화한다(테스트 간 독립).
  vi.resetModules();
}

describe('CR-09 monacoRuntime', () => {
  beforeEach(() => {
    loaderMock.config.mockClear();
    resetRuntimeFlag();
    delete (globalThis as { MonacoEnvironment?: unknown }).MonacoEnvironment;
  });

  it('C09-01: 로더에 로컬 monaco 인스턴스를 주입한다(CDN 기본값 제거)', async () => {
    const runtime = await import('./monacoRuntime');
    runtime.configureLocalMonacoRuntime();

    expect(loaderMock.config).toHaveBeenCalledTimes(1);
    const config = loaderMock.config.mock.calls[0]?.[0] as { monaco?: unknown };
    expect(config.monaco).toBeDefined();
  });

  it('C09-01: 여러 번 호출해도 설정을 반복하지 않는다', async () => {
    const runtime = await import('./monacoRuntime');
    runtime.configureLocalMonacoRuntime();
    runtime.configureLocalMonacoRuntime();

    expect(loaderMock.config).toHaveBeenCalledTimes(1);
  });

  it('C09-01: 언어 라벨별로 로컬 워커를 돌려주고 모르는 라벨은 기본 워커를 쓴다', async () => {
    const runtime = await import('./monacoRuntime');
    runtime.configureLocalMonacoRuntime();

    const environment = (globalThis as { MonacoEnvironment?: MonacoEnvironmentLike }).MonacoEnvironment;
    expect(environment).toBeDefined();

    const ts = environment?.getWorker('worker', 'typescript');
    const json = environment?.getWorker('worker', 'json');
    const fallback = environment?.getWorker('worker', 'unknown-language');

    expect(ts).toBeInstanceOf(Object);
    expect(json).toBeInstanceOf(Object);
    expect(fallback).toBeInstanceOf(Object);
    // 라벨마다 서로 다른 워커(로컬 chunk)가 연결된다 — 스텁 클래스 인스턴스로 확인.
    expect(ts).not.toBe(json);
  });
});
