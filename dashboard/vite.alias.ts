/**
 * 공유 resolve alias (CR-09)
 * ==========================
 * `vite.config.ts`(production 빌드)와 `vitest.config.ts`(단위 테스트)가 같은 해석
 * 규칙을 쓰도록 한 곳에서 만든다. 두 가지 이유가 있다.
 *
 *   1. mermaid 10.6.1의 mindmap 정의가 cytoscape의 UMD 빌드를
 *      `cytoscape/dist/cytoscape.umd.js` 깊은 경로로 import하는데, cytoscape의
 *      package exports에는 그 경로에 require 조건만 있어 ESM 번들러가 해석하지
 *      못한다 → 같은 라이브러리의 ESM 빌드로 연결한다.
 *   2. monaco-editor 0.56의 package exports는 `?worker` 쿼리가 붙은 하위 경로를
 *      해석하지 못한다 → 쿼리를 포함해 실제 파일 경로로 alias하고, Vite의 worker
 *      플러그인이 로컬 워커 chunk로 emit하게 한다(CDN 워커 대체).
 */
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));

/** monaco 워커 specifier(`...?worker`)를 실제 파일 경로 + 쿼리로 바꾼다. */
function monacoWorkerAlias(relativePath: string): [string, string] {
  const absolutePath = path.join(dashboardRoot, 'node_modules', 'monaco-editor', relativePath);
  return [`monaco-editor/${relativePath}?worker`, `${absolutePath}?worker`];
}

const MONACO_WORKER_ENTRIES: readonly (readonly [string, string])[] = (
  [
    'esm/vs/editor/editor.worker.js',
    'esm/vs/language/json/json.worker.js',
    'esm/vs/language/css/css.worker.js',
    'esm/vs/language/html/html.worker.js',
    'esm/vs/language/typescript/ts.worker.js',
  ] as const
).map(entry => monacoWorkerAlias(entry));

export function createAliases(): Record<string, string> {
  return {
    '@': path.join(dashboardRoot, 'src'),
    'cytoscape/dist/cytoscape.umd.js': 'cytoscape/dist/cytoscape.esm.mjs',
    ...Object.fromEntries(MONACO_WORKER_ENTRIES),
  };
}
