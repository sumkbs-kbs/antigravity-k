---
title: CR-08 설정·명령 팔레트 키보드/접근성 계약
status: REVIEW (독립 검토 미배정, 코드 미커밋)
date: 2026-09-12
baseline_sha: 08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f
evidence: .omo/evidence/commercial-reliability/CR-08/attempt-001/
related: [16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md, 17_COMMERCIAL_RELIABILITY_CHECKLIST.md]
tags: [ga, accessibility, keyboard, dialog, runbook]
---

# CR-08 설정·명령 팔레트 키보드/접근성 계약

이 문서는 **구현자가 정한 계약과 잔여 위험**을 운영·검증 담당자에게 넘기기 위한 것이다.
수용 기준의 정의는 [계획서 16](../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md)의 CR-08 카드가 갖는다.

## 1. 닫은 결함 (BASELINE F04)

| 코드 | 결함 | 이전 동작 | 새 동작 |
|---|---|---|---|
| `F04-a` | provider 비밀 입력에 label 연결 없음 | 여섯 입력의 접근성 이름이 placeholder(`API 키 입력`)로 동일 | 각 입력이 `🌐 OpenRouter` … `🟣 Anthropic Claude`로 **고유한 이름** |
| `F04-b` | 팔레트에 modal 계약 없음 | 초기 focus만. Tab이 배경으로 샘, 닫아도 focus 복귀 없음, 배경 inert 없음 | `aria-modal="true"` + Tab 순환 + focus 복귀 + 배경 inert |
| `F04-c` | 한글 IME 조합 확정 Enter가 실행됨 | 조합 중 Enter → 명령 실행 | 조합 중 Enter는 무시(실행은 그대로) |

추가로 팔레트 **선택 항목 부제목**의 색 대비 3.87:1(axe serious)을 새 게이트가 적발해 5.12:1로 올렸다.

## 2. 팔레트 dialog 계약 (구현 사실)

- 요소: `div.command-palette-overlay` > `div.command-palette[role="dialog"][aria-modal="true"]`
- **초기 focus**: 검색 입력(`role="combobox"`). 열린 다음 tick에 이동한다.
- **Tab 순환**: `Tab`/`Shift+Tab`이 dialog 안에서만 순환한다. 구현은 `document` capture 단계의
  keydown이며, 컨테이너 밖에서 Tab이 눌리면 첫 요소로 되돌린다. focusable 요소가 하나도 없으면
  컨테이너 자체에 focus를 둔다.
- **배경 inert**: 팔레트가 열려 있는 동안 overlay가 아닌 배경 요소가 `inert`가 된다. 대상은
  **조상 체인의 모든 형제**다 — 오버레이가 실제로 `.app-layout` 안쪽에 마운트되므로, 같은 레벨
  (사이드바·본문)뿐 아니라 `.app-shell` 레벨의 상단 바·토스트·폴더 브라우저도 포함된다.
  `document.body`의 자식은 건드리지 않는다.
- **focus 복귀**: Escape/명령 실행으로 닫힐 때 열기 직전 요소로 돌아간다(연결이 살아 있을 때만).
  **순서 제약이 있다**: 배경 inert를 먼저 해제한 뒤 focus를 옮긴다. 순서를 뒤집으면 브라우저가
  inert 하위 `focus()`를 무시해 focus가 body로 남는다(실브라우저 실측, D-07).
- **Escape 닫기**: 팔레트 자체 리스너와 App의 전역 단축키가 함께 처리한다(기존 동작 유지).
- **IME**: `nativeEvent.isComposing` 또는 legacy `keyCode === 229`인 Enter는 실행하지 않는다.

## 3. 재사용 훅

`dashboard/src/hooks/useModalDialog.ts` (신규)

- `useModalDialog({ active, containerRef, initialFocusRef })` — 초기 focus, Tab 순환, focus 복귀,
  배경 inert. **Escape 닫기는 호출자 책임**이다.
- `getFocusableElements(container)` — 가능한 요소를 DOM 순서로. `inert`/`aria-hidden="true"` 하위 제외.
- `inertBackgroundSiblings(overlay)` — 조상 체인의 형제를 inert로 만들고 복구 함수를 반환.
- 적용 범위: **현재 CommandPalette만**. `PinModal`·`KeyboardShortcutsModal`·`GitCommitDialog`·wiki
  모달은 아직 이 계약을 쓰지 않는다(후속 후보).

## 4. 접근성 게이트

| 게이트 | 파일 | 정책 |
|---|---|---|
| UI-01 | `dashboard/e2e/tests/accessibility.spec.ts` | route별 marker + axe **critical/serious 0** |
| UI-02 | `dashboard/e2e/tests/accessibility-hard-gate.spec.ts` | axe **전 impact 0** |
| UI-02 keyboard | `dashboard/e2e/tests/keyboard-workflows.spec.ts` | 키보드만으로 workflow + visible focus |
| CR-08 | `dashboard/e2e/tests/cr08-keyboard-accessibility.spec.ts` | provider 이름, 팔레트 계약, IME, axe(desktop/narrow) |

CR-08에서 UI-01·UI-02 매트릭스를 **16 → 17 route**로 확장했다(404 화면 `/cr08-unknown-route`,
marker `[data-testid="cr07-not-found"]`). 두 스펙의 매트릭스 고정 단언도 함께 17로 갱신되어 있다.

## 5. 배포·검증 절차

```bash
pnpm --dir dashboard exec vitest run
pnpm --dir dashboard run typecheck && pnpm --dir dashboard run lint
pnpm --dir dashboard build          # ← 추적 번들 갱신. 배포 전 필수
pnpm --dir dashboard exec playwright test e2e/tests/cr08-keyboard-accessibility.spec.ts
pnpm --dir dashboard exec playwright test \
  e2e/tests/accessibility.spec.ts \
  e2e/tests/accessibility-hard-gate.spec.ts \
  e2e/tests/keyboard-workflows.spec.ts
uv run --no-sync pytest tests/test_dashboard_wheel_assets.py tests/test_rel02_container_contract.py -q
```

**주의**: `src/antigravity_k/dashboard_dist/`는 추적되는 커밋 대상 번들이다. CR-08 attempt는
검증 후 이를 HEAD로 복원했다. 재빌드 없이 배포하면 **CR-08 이전 UI가 서빙**된다.

## 6. 잔여 위험 / 미검증

- 실제 스크린리더(VoiceOver/NVDA) 낭독 품질 — 미검증. 접근성 이름에 아이콘 이모지가 포함된다.
- Firefox/Safari의 `inert` 지원과 IME 동작 — 미검증(chromium만).
- 검색 결과가 0건일 때 Tab 순환 경로 — 실브라우저 미확인.
- axe 통과는 **전체 WCAG 인증이 아니다**: 자동 검사 범위(UI-01 critical/serious, UI-02 전 impact)만 보장한다.
- 다른 모달에는 같은 계약이 없다 — 사용자가 그 모달을 키보드로 쓸 때의 격리는 보장되지 않는다.

## 7. 롤백

1. `dashboard/src/components/UI/CommandPalette.tsx`에서 `useModalDialog` 호출을 제거하고 이전
   focus 효과로 되돌린다.
2. `dashboard/src/styles/index.css`의 `.cmd-item.selected .cmd-item-subtitle` 규칙을 제거한다
   (색 대비 serious 위반이 되살아난다).
3. 두 접근성 매트릭스에서 404 route를 빼고 고정 단언을 16으로 되돌린다.
4. `pnpm --dir dashboard build` 후 재배포.
훅 파일은 남겨도 무해하다(다른 곳에서 import하지 않으면 번들에 포함되지 않는다).
