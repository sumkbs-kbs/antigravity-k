/**
 * CR-09 · mermaid 런타임 로더 계약
 * ================================
 * 발견 F05: mermaid를 `index.html`의 CDN 동기 script로 불러왔고, 라이브러리가
 * 없으면 다이어그램이 오류로 떨어졌다. 지금은 정식 의존성으로 두고 다이어그램을
 * 실제로 그릴 때만 동적 import한다.
 *
 * 이 테스트는 계약을 고정한다.
 *   C09-01 런타임 import는 필요할 때 한 번만 일어나고 초기 설정은 보안 기본값을 유지한다.
 *   C09-05 로드 실패는 조용히 대체되지 않고 그대로 전파된다(호출자가 오류를 표시).
 *   CR-14 F-04 렌더 출력은 라이브러리 sanitizer 를 믿지 않고 우리 정책으로 다시 정화된다.
 *     (mermaid 10.9.8 은 라벨의 `<img>` 를 남겨 외부 요청을 만들 수 있었다 — 실 브라우저
 *      프로브로 확인. `securityLevel: 'strict'` 만으로는 막히지 않았다.)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mermaidMock = vi.hoisted(() => ({
  initialize: vi.fn(),
  // 호출 인자를 검증할 수 있도록 `render` 의 시그니처를 그대로 입힌다.
  render: vi.fn<MermaidRuntime['render']>(async () => ({ svg: '<svg data-testid="mock-svg" />' })),
}));

vi.mock('mermaid', () => ({ default: mermaidMock }));

import {
  MERMAID_CONFIG,
  loadMermaid,
  neutralizeMermaidDefinition,
  peekMermaid,
  resetMermaidRuntimeForTests,
  sanitizeMermaidSvg,
  type MermaidRuntime,
} from './mermaidRuntime';

describe('CR-09 mermaidRuntime', () => {
  beforeEach(() => {
    mermaidMock.initialize.mockClear();
    mermaidMock.render.mockClear();
    resetMermaidRuntimeForTests();
  });

  afterEach(() => {
    resetMermaidRuntimeForTests();
  });

  it('C09-01: 보안 기본값(securityLevel strict, startOnLoad false)을 명시적으로 고정한다', () => {
    expect(MERMAID_CONFIG.securityLevel).toBe('strict');
    expect(MERMAID_CONFIG.startOnLoad).toBe(false);
    expect(Object.isFrozen(MERMAID_CONFIG)).toBe(true);
  });

  it('C09-01: 런타임을 한 번만 초기화하고 이후 호출은 같은 인스턴스를 재사용한다', async () => {
    const first = await loadMermaid();
    const second = await loadMermaid();

    expect(first).toBe(second);
    expect(mermaidMock.initialize).toHaveBeenCalledTimes(1);
    expect(mermaidMock.initialize).toHaveBeenCalledWith({ ...MERMAID_CONFIG });
  });

  it('C09-01: 필요할 때까지 import하지 않는다(초기 로드 비용 없음)', () => {
    expect(peekMermaid()).toBeNull();
    expect(mermaidMock.initialize).not.toHaveBeenCalled();
  });

  it('C09-05: 로드/초기화 실패를 감추지 않고 그대로 전파한다', async () => {
    // 실패는 그대로 전파되고(호출자가 사용자 오류를 표시), 실패한 promise는
    // 캐시되어 재렌더마다 import를 반복하지 않는다.
    mermaidMock.initialize.mockImplementationOnce(() => {
      throw new Error('Failed to fetch dynamically imported module: mermaid');
    });

    await expect(loadMermaid()).rejects.toThrow(/dynamically imported/);
    await expect(loadMermaid()).rejects.toThrow(/dynamically imported/);

    expect(mermaidMock.initialize).toHaveBeenCalledTimes(1);
  });

  it('CR-14 F-04: 라벨에서 유도된 img/script 를 제거하고 이벤트 핸들러도 남기지 않는다', () => {
    const hostile = [
      '<svg xmlns="http://www.w3.org/2000/svg">',
      '<rect width="10" height="10" />',
      '<text>label</text>',
      '<img src=x onerror="window.__agkXss=1">',
      '<img src="https://beacon.invalid/leak.png">',
      '<image xlink:href="https://beacon.invalid/svg.png" />',
      '<script>window.__agkXss=2</script>',
      '<a href="https://evil.invalid/"><text>link</text></a>',
      '</svg>',
    ].join('');

    const cleaned = sanitizeMermaidSvg(hostile);

    expect(cleaned).not.toMatch(/<img/i);
    expect(cleaned).not.toMatch(/<image/i);
    expect(cleaned).not.toMatch(/<script/i);
    expect(cleaned).not.toMatch(/onerror/i);
    expect(cleaned).not.toMatch(/beacon\.invalid/);
    expect(cleaned).not.toMatch(/evil\.invalid/);
    // 렌더에 필요한 도형/라벨은 보존된다.
    expect(cleaned).toMatch(/<rect/);
    expect(cleaned).toMatch(/<text>label<\/text>/);
  });

  it('CR-14 F-04: 같은 문서 앵커는 남기고 외부 URI 속성만 중화한다', () => {
    const withAnchor = '<svg xmlns="http://www.w3.org/2000/svg"><use href="#marker-1" /><use href="https://beacon.invalid/x.svg#m" /></svg>';

    const cleaned = sanitizeMermaidSvg(withAnchor);

    expect(cleaned).toMatch(/href="#marker-1"/);
    expect(cleaned).not.toMatch(/beacon\.invalid/);
  });

  it('CR-14 F-04: 정의 단계에서 자원을 당기는 태그를 텍스트로 무력화한다', () => {
    const hostile = 'graph TD; A["<img src=https://beacon.invalid/leak.png>"] --> B;';

    const neutralized = neutralizeMermaidDefinition(hostile);

    // 꺾쇠가 이스케이프되어 mermaid 가 요소를 만들지 못한다(출력 정화 전에 요청이 나가는 것을 막는다).
    expect(neutralized).not.toMatch(/<img/i);
    expect(neutralized).toContain('&lt;img');
    // 다이어그램 문법 자체는 건드리지 않는다.
    expect(neutralized).toContain('graph TD;');
    expect(neutralized).toContain('--> B;');
  });

  it('CR-14 F-04: 정상 텍스트(스테레오타입·제네릭)는 정의 단계에서 깨지지 않는다', () => {
    const legit = [
      'classDiagram',
      'class List&lt;T&gt;',
      '<<interface>>',
      'A<br/>B',
      'graph TD; A-->B;',
    ].join('\n');

    expect(neutralizeMermaidDefinition(legit)).toBe(legit);
  });

  it('CR-14 F-04: render() 출력이 정화를 거쳐 돌아온다', async () => {
    mermaidMock.render.mockResolvedValueOnce({
      svg: '<svg><foreignObject><span>label</span><img src="https://beacon.invalid/x.png"></foreignObject></svg>',
    });

    const runtime = await loadMermaid();
    const { svg } = await runtime.render('diagram-1', 'graph TD; A-->B;');

    expect(svg).toMatch(/<foreignObject/);
    expect(svg).toMatch(/label/);
    expect(svg).not.toMatch(/<img/i);
    expect(svg).not.toMatch(/beacon\.invalid/);
  });

  it('CR-14 F-04: render() 는 정의를 중화한 뒤 라이브러리에 넘긴다', async () => {
    const runtime = await loadMermaid();
    const { svg } = await runtime.render('diagram-2', 'graph TD; A["<img src=https://beacon.invalid/x.png>"] --> B;');

    const passed = mermaidMock.render.mock.calls.at(-1);
    expect(passed?.[0]).toBe('diagram-2');
    expect(passed?.[1]).not.toMatch(/<img/i);
    expect(svg).toMatch(/<svg/);
  });
});
