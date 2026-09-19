---
title: F08 Wiki Markdown 안전화 진행 기록
tags: [qa, security, frontend, markdown, sanitization, remediation]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_pending_commit
verification_utc: 2026-09-02T23:00:52Z
---

# F08 진행 기록

Wiki 문서 렌더링에서 regex HTML 생성과 `dangerouslySetInnerHTML`을 제거하고, React Markdown 렌더 트리로 전환했다. Raw HTML은 파싱하지 않으며, 구문 해석 이후 sanitizer allowlist와 별도 URL protocol 검사를 다시 적용한다. 기존 Wiki 문법(제목, 목록, inline/block code, 표, 링크)과 한국어 가독성은 유지했다.

## 수정 계약

1. `MarkdownRenderer.tsx`는 더 이상 HTML 문자열을 만들지 않는다. `WikiMarkdown`은 React Markdown/GFM을 렌더하고 `skipHtml`로 raw HTML 노드를 거부한다.
2. 방어 계층은 두 개다. 먼저 Markdown parser가 raw HTML을 만들지 않고, 이후 `rehype-sanitize` allowlist가 Markdown이 생성한 요소만 남긴다. 하나의 필터에만 의존하지 않는다.
3. 허용 tag는 Wiki 문서에 필요한 최소 집합이다. `script`, `iframe`, `svg`, `img`, `button`, `form`, `input`, `style` 등 활성 요소는 허용하지 않는다.
4. `safeWikiUrl`은 `http`, `https`, `mailto`, `tel`만 허용한다. 상대 URL은 페이지 origin으로 해석한 뒤 안전한 protocol일 때만 통과시킨다. `javascript:`, `data:`는 빈 href가 된다.
5. 외부 링크는 React component가 `rel="noreferrer"`와 `target="_blank"`를 강제한다. Markdown source의 임의 속성 주입을 허용하지 않는다.
6. `ContentPanel`에는 어떤 HTML 주입 경로도 남기지 않았다. 문서 메타데이터와 제목은 React text children으로 렌더한다.
7. CSP 설정은 변경하지 않았다. 대응하는 CSP는 E2E에서 원본 header 그대로 검증했다.

## RED → GREEN 증거

수정 전 `ContentPanel.test.tsx`는 5개 모두 실패하면서 아래 사실을 확인했다.

| 입력 | 수정 전 실제 결과 |
|---|---|
| `<h2 id="qa-injected">` | ID를 가진 실제 heading DOM 생성 |
| `<img onerror=...>` | 실제 `img` DOM과 `onerror` 속성 생성 |
| `<script>`, `<iframe>`, `<svg><script>` | 실제 script/iframe/svg DOM 생성 |
| `javascript:` / `data:` Markdown 링크 | 위험 scheme 그대로 href에 반영 |
| malformed link title | `onmouseover` 속성으로 attribute breakout |

수정 후 같은 테스트 5개와 Chat Markdown regression 33개가 모두 통과했다. 실패를 임시로 숨기거나 assertion을 완화하지 않았다.

## 실제 제품 surface 검증

실행 환경:

- HEAD: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b` 위의 미커밋 수정
- Backend: `PYTHONPATH=src uv run --no-sync python -m uvicorn antigravity_k.api.server:app --host 127.0.0.1 --port 8012`
- Browser: Playwright Chromium, `/wiki` route, production bundle
- Vault API는 테스트에서 합성 응답으로 route fulfill했다. 사용자 Vault 파일을 읽거나 외부로 전송하지 않았다.

E2E 시나리오는 문서를 직접 열고 다음을 검증한다:

- 한국어 heading, 목록, 안전 링크, TypeScript code block 렌더
- `#wiki-body` 내 script/iframe/svg 0개
- `onerror`/`onmouseover` 속성 0개
- `javascript:`/`data:` href 0개
- `window.__agkWikiXss` 미실행
- `/health` 응답의 CSP header 원문 유지

처음 E2E가 production bundle에서 여전히 취약하게 실패했다. 원인은 코드 수정 후 `dashboard_dist`가 아직 stale였기 때문이다. bundle을 재생성한 뒤 같은 E2E가 통과했다. 이 실패는 실제 배포물 검증이 source 테스트를 대체할 수 없다는 증거로 보존한다.

## 검증 결과

| 검사 | 명령 | 결과 |
|---|---|---|
| Wiki RED | `pnpm --dir dashboard exec vitest run src/pages/wiki/ContentPanel.test.tsx` | 수정 전 5 failed; 삽입 DOM/속성 존재 |
| Wiki + Chat focused | 동일 command에 ChatMessage test 추가 | 2 files / 38 tests passed |
| Dashboard 전체 | `pnpm --dir dashboard test` | 45 files / 603 tests passed |
| TypeScript | `pnpm --dir dashboard typecheck` | exit 0 |
| Lint | `pnpm --dir dashboard lint` | exit 0 |
| Production build | Vite 6.4.3 `vite build --mode production` | 876 modules transformed, exit 0 |
| 실제 Browser E2E | `pnpm --dir dashboard exec playwright test e2e/tests/wiki-security.spec.ts --project=chromium` | 2 tests passed |
| CSP | `/health` header | 원문 유지, 변경 없음 |
| Tracked node_modules | `git status --short dashboard/node_modules` | dirty 0 |

노트: 이 환경에서 `pnpm build`는 tracked `dashboard/node_modules/vite` 실체에 runtime `dist/`가 누락되어 실패했다. pnpm store의 동일 6.4.3 package에서 runtime 파일을 보완한 뒤 Vite build와 E2E를 실행했고, tracked Git 상태는 변하지 않았다. 이는 F08이 아니라 fresh checkout/package layout 문제이며 아래 별도 항목으로 기록한다.

## 구현 및 지문

변경 파일:

- [MarkdownRenderer.tsx](../../../../dashboard/src/pages/wiki/MarkdownRenderer.tsx): React Markdown + 이중 안전 경계
- [ContentPanel.tsx](../../../../dashboard/src/pages/wiki/ContentPanel.tsx): `dangerouslySetInnerHTML` 제거
- [ContentPanel.test.tsx](../../../../dashboard/src/pages/wiki/ContentPanel.test.tsx): adversarial Markdown/HTML 및 정상 문법 회귀
- [wiki-security.spec.ts](../../../../dashboard/e2e/tests/wiki-security.spec.ts): 실제 routed UI와 CSP 검증

SHA-256:

| 파일 | SHA-256 |
|---|---|
| `dashboard/src/pages/wiki/MarkdownRenderer.tsx` | `27b42c1087a263deb666cc299976a11ec64ab88f00a416b74eb1fe1b6c4e6473` |
| `dashboard/src/pages/wiki/ContentPanel.tsx` | `5d42f847ec8deeb10d40f24c9719c48af9d7d7f23cadda0a4e40242c5557d48d` |
| `dashboard/src/pages/wiki/ContentPanel.test.tsx` | `fb84c52451c8dd687a361e075a2eb1465b8d251ee47df17aa038fff128fba024` |
| `dashboard/e2e/tests/wiki-security.spec.ts` | `674ac3b324a3a19b8c9da34a9cf0c78c670455a587753646e41a72cf3eab8ca6` |

Evidence directory: `.omo/evidence/f08-wiki-markdown-sanitization/`

| 자료 | 링크 |
|---|---|
| Playwright JSON | [playwright-security-e2e.json](../../../../.omo/evidence/f08-wiki-markdown-sanitization/playwright-security-e2e.json) |
| 실제 UI screenshot | [wiki-security-safe.png](../../../../.omo/evidence/f08-wiki-markdown-sanitization/wiki-security-safe.png) |
| Production build log | [production-build.txt](../../../../.omo/evidence/f08-wiki-markdown-sanitization/production-build.txt) |
| CSP 원문 header | [health-headers.txt](../../../../.omo/evidence/f08-wiki-markdown-sanitization/health-headers.txt) |
| Dashboard 전체 test log | [dashboard-full-tests.log](../../../../.omo/evidence/f08-wiki-markdown-sanitization/dashboard-full-tests.log) |
| TypeScript log | [typecheck.log](../../../../.omo/evidence/f08-wiki-markdown-sanitization/typecheck.log) |
| Lint log | [lint.log](../../../../.omo/evidence/f08-wiki-markdown-sanitization/lint.log) |

## 발견한 별도 문제: tracked Vite runtime 누락

Repository는 `dashboard/node_modules/vite` 일부를 일반 파일로 추적한다. 현재 index에는 `bin/vite.js`와 type declarations이 있지만 `dist/node/cli.js`를 비롯한 runtime 구현이 없다. pnpm layout의 실제 package는 `.pnpm/vite@6.4.3.../node_modules/vite`에 완전히 존재하지만, `dashboard/node_modules/vite` 실체가 symlink가 아니라 불완전한 directory이므로 `pnpm build`가 `ERR_MODULE_NOT_FOUND`로 실패할 수 있다.

이번 F08 검증 중 재현된 명령과 오류:

```bash
pnpm --dir dashboard build
# Error [ERR_MODULE_NOT_FOUND]: dashboard/node_modules/vite/dist/node/cli.js
```

임시 조치로 pnpm store 쪽 동일 버전 파일을 불완전한 tracked directory에 겹쳤다. `git status --short dashboard/node_modules`는 여전히 dirty 0이므로 tracked index는 변하지 않았다. 근본 수정은 node_modules 추적 중단/제거이며, 이는 package layout을 바꾸는 별도 변경으로 F08에 섞지 않았다. 다음 에이전트는 fresh checkout에서 이 문제가 재현되면 node_modules 추적 정책을 먼저 결정해야 한다.

## 한계 및 다음 에이전트 지시

1. Wiki raw HTML을 “표시”하지 않고 “거부”한다. HTML 조각을 문서에서 시각적으로 보존해야 하는 제품 요구가 있다면, escaped inline code나 전용 preview 경로처럼 활성 DOM 없는 방식을 별도 설계해야 한다.
2. F08은 Wiki Markdown 경계만 다룬다. Chat의 기존 raw HTML sanitizer는 그대로 두었고 regression만 통과시켰다. Chat과 Wiki를 하나의 sanitizer contract로 통합하는 리팩터링은 별도 작업이다.
3. CSP의 `style-src 'unsafe-inline'`과 CDN script 허용은 기존 대로다. CSP 자체 강화는 이번 범위가 아니다.
4. F09/F10이 끝나면 새 security E2E를 포함해 전체 Playwright suite를 hard gate로 실행해야 한다. 현재는 F08의 실제 surface 검증과 dashboard 전체 unit/component suite만 통과했다.
5. 이 수정은 커밋하지 않았다. 위 지문과 HEAD로 대상을 확인한 뒤 소유자가 원하는 커밋 전략에 따라 반영한다.
