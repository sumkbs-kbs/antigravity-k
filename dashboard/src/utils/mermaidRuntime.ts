/**
 * mermaid 런타임 로더 (CR-09 → CR-14)
 * =================================
 * BASELINE F05: `dashboard/index.html`이 mermaid를 CDN에서 **head의 큰 동기 script**로
 * 불러왔고, 라이브러리가 없으면 다이어그램이 오류로 떨어졌다(`ChatMessage.tsx`).
 *
 * 지금은 mermaid를 정식 의존성으로 두고 **다이어그램을 실제로 그릴 때만** 동적 import한다
 * (Vite가 별도 chunk로 분리한다). 초기 로드에 2MB 스크립트가 붙지 않고, 오프라인에서도
 * 번들된 코드로 렌더된다.
 *
 * 보안 (CR-14 F-04 실측)
 * ---------------------
 * `securityLevel: 'strict'` 만으로는 부족하다는 사실이 버전 승격 과정에서 드러났다.
 * mermaid 10.6.1 은 라벨의 raw HTML(`A["<img src=x onerror=…>"]`)을 제거했지만,
 * **10.9.8 은 그 `<img>` 를 DOM 에 남긴다**. 핸들러는 사라지지만 요소가 남으므로
 * ① 절대 URL 을 쓰면 브라우저가 **외부로 요청을 보낸다**(실측: `https://beacon.invalid/leak.png`),
 * ② 같은 라벨의 `blocked` 요청 수가 늘어 CR-09 의 “외부 요청 0” 계약을 깨뜨릴 수 있다.
 *
 * 그래서 라이브러리 내부 sanitizer 에 의존하지 않고 **렌더 출력을 우리가 직접 정화해서**
 * 돌려준다(`sanitizeMermaidSvg`). 모든 호출자가 이 한 지점을 지나므로, `svg` 를 그대로
 * `innerHTML` 에 넣는 소비자도 안전하다.
 */
export interface MermaidRenderResult {
  readonly svg: string;
}

export interface MermaidRuntime {
  initialize: (config: Readonly<Record<string, unknown>>) => void;
  render: (id: string, definition: string) => Promise<MermaidRenderResult>;
}

/** mermaid 초기 설정 — 보안/동작 계약을 한 곳에서 고정한다. */
export const MERMAID_CONFIG = Object.freeze({
  /** 시작 시 DOM 스캔 금지: 우리가 명시적으로 render()를 호출한다. */
  startOnLoad: false,
  theme: 'dark',
  /** F05 이전 기본값(strict)을 유지한다 — 라벨의 HTML/스크립트 비실행. */
  securityLevel: 'strict',
} as const);

/**
 * 실행/요청을 만들 수 있는 요소 — `<img>` 는 실측으로 `src` 가 살아남아 외부 요청을
 * 만들었고, SVG 대응물(`<image>`, `<iframe>` 등)도 같은 통로다.
 *
 * DOMPurify 프로파일 대신 **구조적 제거**를 쓴다: `USE_PROFILES` 는 `foreignObject` 안의
 * 라벨 HTML(`span`/`br`)까지 지워서 다이어그램이 빈 채로 남는다(실측). 우리가 막아야 할
 * 것은 화이트리스트가 아니라 **측정된 통로**이므로 그 요소만 없앤다.
 */
export const FORBIDDEN_SVG_TAGS: readonly string[] = Object.freeze([
  'script',
  'img',
  'image',
  'iframe',
  'object',
  'embed',
  'audio',
  'video',
  'source',
  'track',
  'form',
  'input',
  'textarea',
  'select',
  'button',
  'link',
  'meta',
  'base',
]);

/**
 * 정의(입력) 단계에서 무력화하는 태그 — `FORBIDDEN_SVG_TAGS` 와 같은 집합이다.
 *
 * 출력만 정화하면 늦다: mermaid 는 렌더 중 측정용 임시 DOM 을 만들어 라벨 HTML 을
 * 삽입하므로, `<img src=…>` 를 보게 되면 **우리 정화가 돌기 전에 이미 요청이 나간다**
 * (실측: 출력 정화 후에도 `https://beacon.invalid/leak.png` 요청 1건이 남았다).
 * 그래서 정의에서 먼저 꺾쇠를 이스케이프해 mermaid 가 그 요소를 만들지 못하게 한다.
 *
 * **deny-list** 인 이유: 허용 목록으로 넓게 잡으면 `<<interface>>`(클래스 다이어그램
 * 스테레오타입)나 `List<T>` 같은 정상 텍스트가 깨진다. 측정된 통로만 막는다.
 */
export const FORBIDDEN_LABEL_TAGS: readonly string[] = FORBIDDEN_SVG_TAGS;

/** 태그 한 개를 찾는다 — 인용부호 안의 `>` 를 삼키지 않도록 속성부를 따로 처리한다. */
const LABEL_TAG_PATTERN = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:[^<>"']|"[^"]*"|'[^']*')*)>/g;

const escapeAngleBrackets = (text: string): string =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/**
 * mermaid 정의에서 위험한 태그를 **텍스트로** 바꾼다. 나머지 다이어그램 문법은
 * 건드리지 않는다(`<br/>`, `A-->B`, `<<interface>>`, `List<T>` 모두 그대로 통과).
 */
export function neutralizeMermaidDefinition(definition: string): string {
  return definition.replace(LABEL_TAG_PATTERN, (match, _closing: string, name: string) =>
    FORBIDDEN_LABEL_TAGS.includes(name.toLowerCase()) ? escapeAngleBrackets(match) : match,
  );
}

/** 값이 자원을 당길 수 있는 속성. 같은 문서 앵커(`#…`)와 내장 이미지 데이터만 허용한다. */
export const URI_ATTRIBUTES: readonly string[] = Object.freeze([
  'href',
  'xlink:href',
  'src',
  'srcset',
  'action',
  'formaction',
  'ping',
]);

const SAFE_URI = /^(?:#|data:image\/(?:png|gif|jpeg|webp);)/i;

/**
 * mermaid 가 돌려준 SVG 를 그대로 DOM 에 넣지 않고 이 함수를 반드시 거친다.
 *
 * `DOMParser` 로 만든 문서는 browsing context 가 없어 **구문 분석 단계에서 자원을
 * 가져오지 않는다** — 그래서 이 검사 자체가 비컨이 되지 않는다(`innerHTML` 로 살아 있는
 * 문서에 넣는 방식은 그 순간 요청이 나간다).
 *
 * 남기는 것: 도형·경로·`style`·`marker`·`foreignObject` 안의 라벨 HTML.
 * 없애는 것: 자원을 당기는 요소, `on*` 핸들러, 외부/비앵커 URI.
 * 변경 시 `cr09-offline-assets`(실 브라우저) e2e 를 반드시 함께 돌린다.
 */
export function sanitizeMermaidSvg(svg: string): string {
  const parsed = new DOMParser().parseFromString(svg, 'text/html');
  const root = parsed.querySelector('svg');
  if (!root) return '';

  for (const element of Array.from(root.querySelectorAll(FORBIDDEN_SVG_TAGS.join(',')))) {
    element.remove();
  }
  for (const element of Array.from(root.querySelectorAll('*'))) {
    for (const attribute of Array.from(element.attributes)) {
      const name = attribute.name.toLowerCase();
      if (name.startsWith('on')) {
        element.removeAttribute(attribute.name);
      } else if (URI_ATTRIBUTES.includes(name) && !SAFE_URI.test(attribute.value.trim())) {
        element.removeAttribute(attribute.name);
      }
    }
  }
  return root.outerHTML;
}

let runtimePromise: Promise<MermaidRuntime> | null = null;
let loadedRuntime: MermaidRuntime | null = null;

/**
 * mermaid 런타임을 로드하고 초기 설정을 적용한다. 첫 호출만 실제 import를 수행하고
 * 이후 호출은 같은 promise를 재사용한다(중복 chunk 로딩 방지).
 *
 * import 실패는 그대로 reject된다 — 호출자가 사용자에게 오류를 보여줄 수 있게 한다.
 */
export function loadMermaid(): Promise<MermaidRuntime> {
  runtimePromise ??= (async () => {
    const module = await import('mermaid');
    const runtime = module.default as unknown as MermaidRuntime;
    runtime.initialize({ ...MERMAID_CONFIG });
    // render 출력은 라이브러리 sanitizer 를 신뢰하지 않고 우리 정책으로 다시 정화한다.
    const sanitized: MermaidRuntime = {
      initialize: config => runtime.initialize(config),
      render: async (id, definition) => {
        // ① 입력: 정의에서 위험한 태그를 텍스트로 바꿔 mermaid 가 그 요소를 만들지 못하게 한다.
        const result = await runtime.render(id, neutralizeMermaidDefinition(definition));
        // ② 출력: 남아 있을 수 있는 요소/속성을 구조적으로 제거한다(방어심층).
        return { svg: sanitizeMermaidSvg(result.svg) };
      },
    };
    loadedRuntime = sanitized;
    return sanitized;
  })();
  return runtimePromise;
}

/** 이미 로드된 런타임(없으면 null). import/초기화 부작용 없이 확인만 할 때 쓴다. */
export function peekMermaid(): MermaidRuntime | null {
  return loadedRuntime;
}

/** 테스트 전용: 캐시를 비워 다음 호출이 다시 import하도록 한다. */
export function resetMermaidRuntimeForTests(): void {
  runtimePromise = null;
  loadedRuntime = null;
}
