---
title: Ssak-Ai 데스크톱 셸·배포 클로저 반영 계획서 (DSH Desktop 참고)
tags: [packaging, desktop, handoff, dsh-desktop, checklist]
date: 2026-09-15
owner: 강병석
status: IN_PROGRESS
reference_repo: https://github.com/anywhere-labs/dsh-desktop
ssak_branch_context: codex/m1-task-events
cr14_frozen_candidate: b6003205365606407cadfd6cbb1c813110beef0f
cr14_fingerprint: 02349a8d06945e438bdc60799ed770a87d6bb67d33d27f09b52008d242536ed6
---

# Ssak-Ai 데스크톱 셸·배포 클로저 반영 계획서

## 0. 이 문서의 목적 (다른 에이전트용)

이 문서는 [anywhere-labs/dsh-desktop](https://github.com/anywhere-labs/dsh-desktop) 공개 아키텍처·유저가이드를 **참고**하여, Ssak-Ai의 **부족한 배포·데스크톱 셸·운영 UX**를 완성하기 위한 **실행 계획 + 체크리스트**다.

- **하는 일:** Ssak-Ai를 “개발자 `uv`/`vite` 없이도 더블클릭으로 쓰는 데스크톱 제품”에 가깝게 만든다.
- **하지 않는 일:** DeepSeek Harness / Cordis / DSH 플러그인 스택을 Ssak 엔진에 이식하지 않는다. 에이전트 코어·CR-14 기술 게이트는 Ssak 소유로 유지한다.
- **성공 정의:** 아래 Phase 체크리스트가 순서대로 DONE이고, 각 Phase의 **완료 증거**가 문서/스크립트/실측으로 남아 후속 에이전트가 이어서 검증할 수 있다.

### 0.05 제품 목적 (사용자 확정 2026-09-15)

- **주 목적:** 개인 사용.
- **필수 확장:** 모바일에서도 같은 프로그램에 **편리하게 연동·작동**.
- **함의:** UI·API의 정본은 **Host(`agk serve` HTTP+WS+SPA)**. 데스크톱 셸은 얇게. 모바일은 LAN/Tailscale 등으로 Host에 접속 (기본은 loopback, 비-loopback 시 PIN/토큰 필수).
- **비목표:** 다중 테넌트 SaaS·불특정 인터넷 공개 서비스화.
- 상세: `docs/packaging/notes/mobile_host_premise.md`

### 0.0 진행 기록 의무 (사용자 지시 2026-09-15)

**매 진행 단계마다** 다음을 갱신하지 않으면 작업을 끝낸 것으로 보지 않는다.

1. 본 문서 §9 Decision Log / §10 Phase 상태표 / §12 변경 이력
2. `docs/packaging/notes/phaseN_*.md` (또는 동등 증거 메모)
3. 가능하면 **docs 커밋**으로 git history에 남겨 다음 에이전트가 `git log`만으로 상태를 복원

체크리스트 `[x]`와 상태표가 **단일 진실 소스**다. 채팅만으로 상태를 남기지 말 것.

### 0.1 필수 제약 (위반 시 작업 중단)

| ID | 제약 |
|---|---|
| C-01 | **CR-14 동결 후보 `b6003205` / 지문 `02349a8d…`의 GO 주장을 이 작업으로 승격하지 말 것.** 본 계획은 제품화 후속 레인이다. |
| C-02 | 비밀(`.env` 키, PIN, 토큰)을 문서·커밋·증거에 넣지 말 것. |
| C-03 | 실행 중 EX-05 soak(`val02_staging.py` 8h, pid 주변 `29961`/`29969` 계열)을 **죽이지 말 것.** |
| C-04 | `vault_data` 커밋 금지. |
| C-05 | DSH Desktop 코드를 **대량 복붙하지 말 것.** MIT라도 아키텍처·상표·관계 고지가 민감. **아이디어·계약·체크리스트만** 참고. |
| C-06 | 기본 작업면: 사용자 Mac 로컬 `~/program/coding/ssak_comp/Ssak-Ai`. Cursor Cloud SCM 미연결 시 클라우드 에이전트에 맡기지 말고 로컬 이어가기. |
| C-07 | 푸시는 사용자 명시 요청 있을 때만. |
| C-08 | 한국어 커뮤니케이션 선호. 코드/커밋 메시지는 기존 레포 관례 따름. |

### 0.2 현재 Ssak 기준선 (2026-09-15)

| 항목 | 상태 |
|---|---|
| 런타임 | Python FastAPI (`agk serve`) + React dashboard (`dashboard/`, 빌드 산출 `src/antigravity_k/dashboard_dist`) |
| 로컬 개발 | 자주 `8000` 백엔드 + `5173` Vite. Vite/`VITE_BACKEND_URL` 오설정으로 설정 저장 실패 재현됨 |
| macOS 패키징 | `make dmg` → `scripts/build_mac_dmg.sh` → `MACOS_DMG_GUIDE.md`. 기본=**호스트 Python 3.12+**; 옵트인 `SSAK_BUNDLE_PYTHON=1`로 동봉. DMG+`dmg-smoke` PASS (로컬 dist) |
| Windows 설치기 | 제품급 NSIS/portable **미비** (검증 스크립트에 Windows 경로 언급 수준) |
| 트레이/단일 인스턴스/자동 업데이트 | **미비 또는 약함** |
| CR-14 | NO-GO. EX-05 soak IN_PROGRESS. 본 계획과 **판정 축 분리** |

### 0.3 DSH에서 가져올 “패턴” (복붙 대상 아님)

1. 얇은 네이티브 셸이 Host를 기동하고, UI는 loopback Web.
2. 런타임 동봉 → 사용자에게 Node/도구 설치 요구 최소화.
3. 트레이 + 창 닫기≠종료 + 단일 인스턴스.
4. Stable/Beta 채널 헤더 기반 업데이트(확인 후 다운로드).
5. 복구 창 + 진단 ZIP(`--export-diagnostics`류).
6. 포트 랜덤 기본 + LAN 노출은 명시 확인 후에만.
7. generation 수명: 모드/프로파일 전환 시 핸들 dispose.
8. packaging smoke / architecture gate.

---

## 1. 목표 아키텍처 (Ssak용 목표 상태)

```text
[Ssak Desktop Shell]          ← NEW (Electron 또는 동등 네이티브 런처; 기술 선택은 Phase 0)
   │  single-instance, tray, hide-vs-quit
   │  starts/stops bundled runtime
   │  update check (channel)
   │  diagnostics export
   ▼
[Bundled Runtime Closure]     ← STRENGTHEN
   - embedded/nearby Python (or frozen binary) + site-packages
   - dashboard_dist (no Vite in prod)
   - agk serve --host 127.0.0.1 --port <bound>
   ▼
[Ssak Engine + Dashboard]     ← EXISTING (변경 최소화)
   FastAPI + built SPA on same origin or loopback
```

**비목표:** DSH Cordis 플러그인 로더, DeepSeek Harness submodule, Electron API를 페이지에 노출.

### 1.1 기술 선택 (Phase 0에서 결정)

후속 에이전트는 **하나를 고르고 문서에 기록**한 뒤 진행한다. 기본 권장:

| 옵션 | 장점 | 단점 | 권장 |
|---|---|---|---|
| **A. Electron 셸 + 기존 Python 번들** | DSH와 유사한 UX(트레이/업데이트), 크로스플랫폼 | 패키지 용량↑, 이중 런타임 | **1순위** (Windows+mac 동시) |
| **B. 기존 `.app` 런처 강화 (mac only)** | 이미 `build_mac_dmg.sh` 있음 | Windows 공백 남음 | mac 긴급 GA만 |
| **C. Tauri + sidecar Python** | 용량↓ | 러닝커브, sidecar 서명 복잡도 | 여력 있을 때 |

**결정 기록 위치:** 이 문서 §9 Decision Log + (선택) `docs/packaging/DESKTOP_SHELL_DECISION.md`.

---

## 2. 작업 레인 / 브랜치 규칙

| 규칙 | 내용 |
|---|---|
| 브랜치 | `feat/desktop-shell-closure` (또는 동등). **CR-14 후보 SHA를 rewrite하지 말 것.** |
| 커밋 | 기능 단위. docs-only와 code를 섞을 때 메시지에 구분. |
| 증거 | `.omo/evidence/desktop-shell/<YYYY-MM-DD>/` (gitignore 관례 유지 시 요약만 `docs/packaging/`에) |
| CR-14 문서 | 본 계획 진행을 CR-14 GO/DONE으로 적지 말 것. 필요 시 “후속 제품화 레인”으로만 교차 링크. |

---

## 3. Phase 계획 (상세)

### Phase 0 — 범위·결정·베이스라인 측정 (0.5–1일)

**목적:** 후속 에이전트가 같은 전제로 일하게 한다.

**작업**
- [x] 옵션 A/B/C 중 셸 기술 확정 → §9에 기록 (**D-01 = A**, interim D-01-interim)
- [x] 현재 `make dmg` / `scripts/build_mac_dmg.sh` 동작 실측 (성공/실패, 산출물 경로, Python 의존) — **DMG 산출물 없음·스크립트 분석 완료** (전체 `make dmg` 빌드는 Phase 1)
- [x] 프로덕션 경로에서 Vite 없이 `dashboard_dist`만으로 UI가 뜨는지 확인 (`agk serve`가 dist를 서빙하는지) — **`:8000/` HTML 200 + StaticFiles mount 확인**
- [x] 포트 기본값 정리 초안: 개발(5173+8000) vs 제품(단일 포트) 표 — `notes/phase0_baseline.md`
- [x] 이 계획서 `status`를 `IN_PROGRESS`로 갱신

**완료 증거**
- [x] Decision Log 항목 D-01 (기술 선택)
- [x] 베이스라인 메모: `docs/packaging/notes/phase0_baseline.md` (+ `.omo/evidence/desktop-shell/2026-09-15/` 사본)
- [x] `dashboard_dist` 존재·빌드 명령 (`pnpm --dir dashboard build`) 기록

**통과 기준**
- [x] 기술 선택과 “제품은 Vite를 요구하지 않음”이 문서에 명시됨.

---

### Phase 1 — 배포 클로저 (런타임 동봉) ★최우선

**목적:** “호스트에 Python/uv/vite가 없어도” 또는 “최소 의존만으로” 앱이 기동.

**참고 DSH 패턴:** packaged runtime closure, asar.unpacked 물리 의존성, 첫 실행 다운로드 최소화.

**Ssak 구현 방향**
1. **프로덕션 UI:** 항상 `dashboard_dist` 서빙. Vite는 dev-only.
2. **Python 클로저 (택1, Decision에 기록):**
   - 1a. `.app`/`resources`에 venv 또는 `uv`-exported site-packages 동봉
   - 1b. PyInstaller/briefcase로 `agk` 단일 바이너리 + dist 동봉
3. **런처:** 동봉 인터프리터로 `agk serve --host 127.0.0.1 --port $PORT` (또는 동등)
4. **가변 데이터:** 쓰기 금지 경로에서 `~/.antigravity-k` / `~/Library/Logs/Ssak-Ai` 라우팅 (가이드에 이미 언급 — 런처가 강제하는지 검증·보강)
5. **빌드 파이프라인:** `make dmg`가 dist 빌드 → 번들 → DMG → sha256까지 **한 명령**으로 재현

**체크리스트**
- [x] `dashboard` production build가 CI/로컬 한 명령으로 `src/antigravity_k/dashboard_dist` 갱신 — 명령: `pnpm --dir dashboard build` / Makefile `dashboard-build-provenance` (Phase0 확인). DMG 스크립트가 없을 때 자동 호출
- [~] 런처가 **Vite/5173을 호출하지 않음** — `build_mac_dmg.sh` 런처는 포트 8000/`agk serve` 경로(기존). 자동 회귀 테스트는 미착수
- [x] 번들 포함 목록 문서화 — `MACOS_DMG_GUIDE.md` §5 (site-packages~79M + dashboard_dist + src + 옵션 Resources/python)
- [~] 읽기 전용 볼륨/Applications 기동 — DMG 마운트 무결성 PASS + `dmg-smoke` PASS(:18080). Applications 드래그 실기 스모크는 잔여
- [x] `scripts/build_mac_dmg.sh`에 “클로저 검증” 단계 추가 (필수 파일 누락 시 fail) + `.env`/`auth_hash` 혼입 거부
- [x] `make dmg-smoke`: Host on :18080 → auth/spa 200 → 종료 (PASS; soak/:8000 미사용)
- [x] Windows: 동등 클로저 설계 stub — `docs/packaging/notes/windows_closure_stub.md` (구현은 Phase 3)
- [x] Python 1a incremental: 런처가 `Resources/python` 우선; `SSAK_BUNDLE_PYTHON=1` 옵트인 동봉 (기본 OFF, ~55M 유지)
- [~] 클린 Mac(호스트 Python 없음) — **PARTIAL** until `SSAK_BUNDLE_PYTHON=1` rebuild+smoke verified

**완료 증거**
- [x] `dist/Ssak-Ai-0.1.0.dmg` + `.sha256` — sha256 `262b54244a60419567f3dd14e8be4d28a8409c0649bcfbd263ebff36cbd1c362` (로컬 gitignored; `phase1_progress.md`에 기록)
- [x] smoke: `make dmg-smoke` PASS (auth=200 spa=200; 로그는 로컬 `/tmp/ssak-dmg-logs/`, 비밀 없음)
- [x] `MACOS_DMG_GUIDE.md`: 기본=호스트 Python 3.12+ 필요 / 옵트인 동봉(`SSAK_BUNDLE_PYTHON=1`) 명시 + 클로저 인벤토리

**통과 기준**
- 클린 macOS 사용자 시뮬레이션(또는 문서화된 최소 의존)에서 DMG 설치 후 대시보드 도달.

**회귀 주의**
- PIN/`data/auth_hash` 경로가 번들 안이 아니라 user data로 가는지
- `.env`가 번들에 실리지 않는지 (실리면 즉시 FAIL)

---

### Phase 2 — 데스크톱 셸 UX (트레이·단일 인스턴스·숨김≠종료)

**목적:** 브라우저 탭이 아니라 “앱”처럼 동작.

**참고 DSH:** single-instance lock, tray after web ready, close window hides, Quit exits Host.

**체크리스트**
- [x] 단일 인스턴스: 두 번째 실행 시 기존 창 focus / URL open — **DONE** (`desktop/main.js`)
- [x] 트레이 아이콘: 열기 / 설정(`/settings`) / 로그 폴더 / 종료 **DONE**; 상태 라벨 Host starting…|ready|unreachable
- [x] 창 닫기 = hide (프로세스 유지) — **DONE**; owned Host는 유지 (Quit에서만 종료); Dock 아이콘은 Quit까지 유지
- [x] Quit = Host graceful shutdown + 자식 프로세스 회수 — **DONE for owned child only** (SIGTERM→SIGKILL; soak/비소유 PID 미접촉). `SSAK_SPAWN_HOST=0`이면 spawn 안 함
- [x] 기동 실패 시: probe 실패+spawn off → dialog; spawn on → starting… 후 timeout dialog — **DONE**; Phase 4 recovery dialog supersedes one-shot alerts
- [x] 서버 ready 전에 트레이 “시작 중…” 상태 — **DONE** (owned spawn 중)
- [x] macOS Dock 아이콘 정책 — **DONE** (`notes/phase2_progress.md` · `desktop/README.md`): hide-on-close keeps process; Dock stays until Quit

**완료 증거**
- [x] 스캐폴드 + 진행 메모: `desktop/` · `docs/packaging/notes/phase2_progress.md`
- [x] 수동 QA 체크리스트 표 작성 (`notes/phase2_shell_qa.md`) — checklist ready, **not executed** (Pass/Fail blank)
- [ ] (가능하면) 자동 테스트 또는 smoke 스크립트 — deferred

**통과 기준**
- 창을 닫아도 `agk`가 살아 있고, Quit 시에만 포트가 닫힘.

---

### Phase 3 — Windows 설치기 + 크로스플랫폼 패리티

**목적:** GA 지원 행렬에서 Windows를 “문서만”이 아니게.

**참고 DSH:** NSIS + portable, 채널별 아티팩트.

**체크리스트**
- [ ] Windows x64 설치기 설계 문서 (기술: Electron Builder / Inno / NSIS / briefcase 중 Decision)
- [ ] 설치 경로·시작 메뉴·언인스톨
- [ ] portable zip (선택)
- [ ] `scripts/verify_release_artifacts.sh`와 연동 또는 신규 `verify:win-package`
- [ ] `GA_SUPPORT_MATRIX.md`에 **실측 전제**로만 행 추가 (과장 금지; EX/지원 승격 규칙 준수)
- [ ] 코드 서명/공증은 별도 BLOCKED_EXTERNAL로 명시 가능

**통과 기준**
- 클린 Windows VM 또는 실기에서 설치 → 기동 → 대시보드 1회.

---

### Phase 4 — 복구·진단 UX

**목적:** “서버가 안 떠요”를 사용자가 스스로 증거로 남기게.

**참고 DSH:** Recovery window, diagnostics zip, `--export-diagnostics` headless, 로그 스크럽.

**체크리스트**
- [x] `agk diagnostics export` 또는 동등 CLI (Host 기동 없이 가능하면 더 좋음) — **DONE** (`agk diagnostics export`; module `diagnostics_export`)
- [x] ZIP 내용 allowlist: 앱/파이썬 버전, OS, 최근 로그(스크럽), 설정 **키 이름만**, 포트, 최근 에러 코드 — **DONE** (minimal slice)
- [x] **절대 포함 금지:** `.env` 값, PIN, bearer, `vault_data`, raw crash에 비밀 가능 시 경고 — **DONE** (blocklist + `secret_scanner.redact_full`; test asserts)
- [x] UI: 트레이 “진단 내보내기…” — **DONE** (`desktop/main.js` → `runDiagnosticsExport` / `uv run agk diagnostics export`); Settings 버튼은 optional deferred
- [x] 기동 실패 복구 창: 로그 열기 / 포트 충돌 안내 / 진단 내보내기 / 재시도 — **DONE** (Electron `dialog` buttons in `desktop/main.js`; port hint via `suspectPortConflict`; optional `recovery.html` deferred)
- [x] 문서: `docs/packaging/DIAGNOSTICS.md` + `notes/phase4_progress.md`

**통과 기준**
- 내보내기 ZIP에 비밀 스캐너(기존 `secret_scanner` 활용 가능) 0건.

---

### Phase 5 — 업데이트 채널 (stable/beta)

**목적:** EX-03 “이전 artifact 없음” 이후의 **배포 수명주기**.

**참고 DSH:** `X-DSH-Desktop-Channel`, 백그라운드 체크 무음 실패, 수동 Check for Updates, 확인 후 다운로드, 교차 채널 금지.

**체크리스트**
- [ ] 채널 모델 문서: `stable` / `beta` (Git 브랜치 ≠ 채널)
- [ ] 버전 체크 API 계약(자체 또는 GitHub Releases): 요청 채널·현재 버전, 응답 채널 echo
- [ ] 클라이언트: 백그라운드 체크(실패 무음) + 트레이 수동 체크(결과 표시)
- [ ] 자동 설치 금지(기본): 사용자 확인 → 저장 위치 → 다운로드 → mac DMG open / Win installer
- [ ] Beta→Stable 병치 설치는 **명시 메뉴**로만 (원치 않으면 스코프아웃 기록)
- [ ] 실패 시 현재 설치 유지

**통과 기준**
- 가짜 업데이트 서버 또는 fixture로 채널 혼선이 거부됨을 테스트.

**비고:** 서명/공증/CDN은 외부 의존 — `BLOCKED_EXTERNAL`로 남길 수 있음.

---

### Phase 6 — 포트·오리진·설정 저장 안정화

**목적:** 오늘 재현된 Vite `8400`/`5173` 장애류를 제품 경로에서 제거.

**체크리스트**
- [ ] 제품 모드: **단일 loopback 포트** (API+SPA same origin)
- [ ] 개발 모드만 Vite proxy. `VITE_BACKEND_URL` 기본 `http://127.0.0.1:8000`, 죽은 포트로 뜨면 경고
- [~] 포트 점유 시: 명확한 에러 + 진단 힌트 (Phase 4 연결) — recovery dialog port-conflict hint **DONE**; product single-port / bind errors still Phase 6
- [ ] (선택) `port: 0` 랜덤 + 마지막 성공 포트 기억
- [ ] LAN bind는 설정에서 위험 확인 후에만 (`0.0.0.0`)
- [ ] 설정 저장(`/api/settings/env`) 스모크: 인증 토큰 있는 상태에서 200

**모바일·개인사용 추가 체크리스트 (D-04/D-05)**
- [x] 설정에 “모바일/LAN 접속 안내” (기본 OFF · localStorage) + 위험 고지 — **실제 bind는 재시작 명령**
- [x] Tailscale/사설 IP 바인드 안내 (`/api/network/access-info` notes)
- [x] 비-loopback PIN 강제 = 기존 `startup_security`/`AuthPolicy` (문서화). 실기기 스모크는 잔여
- [ ] 폰 브라우저에서 같은 SPA 로그인·채팅 1회 스모크 (개인 Wi‑Fi 또는 Tailscale)
- [x] `notes/mobile_host_premise.md`와 Settings 카피 정렬

**통과 기준**
- 제품 경로에서 5173 없이도 설정 저장·로그인 가능.
- 루프백만으로 개인 데스크톱 사용 가능 + 옵션 켜면 모바일 Host 접속 가능.

---

### Phase 7 — 프로파일/generation 수명 (선택·중기)

**목적:** 모드·워크스페이스 전환 시 좀비 프로세스/핸들 누수 방지.

**참고 DSH:** generation `release()` idempotent, profile select → restart → commit last-known-good.

**체크리스트**
- [ ] “Desktop generation” 개념을 Ssak에 매핑할지 Decision (Ssak는 project binding이 이미 있음 — **중복 만들지 말 것**)
- [ ] 서버 재시작이 필요한 설정 변경 목록 정의
- [ ] 재시작 실패 시 이전 설정으로 롤백 정책
- [ ] soak/장시간 실행과 충돌 없는지 확인 (EX-05와 별개 레인)

**통과 기준**
- 재시작 루프 10회에서 orphan `agk`/포트 리스너 0.

---

### Phase 8 — 문서·게이트·핸드오프 마감

**체크리스트**
- [ ] `docs/packaging/MACOS_DMG_GUIDE.md` / Windows 가이드 / DIAGNOSTICS / UPDATE_CHANNELS 최신화
- [ ] README 설치 섹션이 “개발자용”과 “사용자용”을 분리
- [ ] `make check-desktop` 또는 동등: type/packaging smoke
- [ ] 이 계획서 모든 Phase 상태를 DONE/DEFERRED로 갱신
- [ ] 후속 에이전트용 “남은 일” 표 (§8) 갱신
- [ ] (선택) CR/GA 문서에 **교차 링크만** (GO 주장 금지)

---

## 4. 우선순위 요약 (에이전트가 막히면 이 순서)

| 순위 | Phase | 이유 |
|---|---|---|
| 1 | Phase 0 | 전제 합의 |
| 2 | Phase 1 | 오늘 Vite 장애·배포 미완의 근본 |
| 3 | Phase 6 | 설정/포트 안정 (1과 병행 가능) |
| 4 | Phase 2 | 제품 체감 |
| 5 | Phase 4 | 지원 비용 감소 |
| 6 | Phase 3 | Windows 패리티 |
| 7 | Phase 5 | 배포 수명주기 |
| 8 | Phase 7–8 | 중기·마감 |

---

## 5. 파일·터치포인트 가이드 (예상)

> 실제 경로는 구현 중 달라질 수 있음. 변경 시 이 표를 갱신할 것.

| 영역 | 후보 경로 |
|---|---|
| mac DMG | `scripts/build_mac_dmg.sh`, `Makefile` `dmg`, `docs/packaging/MACOS_DMG_GUIDE.md` |
| Dashboard 빌드 | `dashboard/package.json`, `dashboard/vite.config.ts`, `src/antigravity_k/dashboard_dist/` |
| 서버 정적 서빙 | `src/antigravity_k/api/` (SPA mount), `agk serve` |
| 설정/시크릿 | `src/antigravity_k/api/routes/system_api.py` (`/api/settings/env`), `dashboard/src/pages/SettingsPage.tsx` |
| 새 셸 프로젝트 | **`desktop/`** (D-06; Electron thin shell) |
| 진단 | `src/antigravity_k/cli/` 또는 `scripts/export_diagnostics.py` |
| 증거 | `.omo/evidence/desktop-shell/` |
| 본 계획 | `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` |

---

## 6. 테스트·검증 매트릭스

| ID | 검증 | Phase |
|---|---|---|
| T-01 | Vite 없이 SPA+API same-origin 로드 | 1, 6 |
| T-02 | DMG 마운트→실행→헬스 | 1 |
| T-03 | 창 닫기 후 포트 listen 유지 / Quit 후 해제 | 2 |
| T-04 | 두 번째 실행이 새 서버를 안 띄움 | 2 |
| T-05 | 진단 ZIP secret scan clean | 4 |
| T-06 | 잘못된 업데이트 채널 응답 거부 | 5 |
| T-07 | `VITE_BACKEND_URL` 오설정은 **dev만** 영향, prod 무관 | 6 |
| T-08 | 번들에 `.env` / 실비밀 미포함 | 1 |
| T-09 | Windows 설치 1회 기동 | 3 |

---

## 7. 리스크·오해 방지

| 리스크 | 완화 |
|---|---|
| CR-14와 섞여 GO로 오해 | C-01, 문서에 후속 레인 명시 |
| Electron 도입으로 보안 표면 확대 | 웹뷰에 Node 미통합, loopback only 기본, 기존 PIN/승인 게이트 유지 |
| 용량 폭증 | 클로저 목록 최소화, 모델 가중치 번들 금지 |
| DSH 코드 복붙 | C-05, 리뷰에서 upstream 파일 경로 흔적 거부 |
| soak 방해 | C-03 |
| 설정 저장이 또 깨짐 | Phase 6을 Phase 1과 병행 |

---

## 8. 후속 에이전트 핸드오프 템플릿

새 에이전트는 아래를 복사해 첫 메시지로 쓰면 된다.

```text
작업: docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md 의 다음 미완 Phase부터 진행.
제약: C-01..C-08 준수. CR-14 후보 동결 유지. soak 죽이지 말 것. 비밀 커밋 금지. 푸시 금지(요청 전).
먼저: Phase 상태표(§10)에서 첫 [ ] 항목을 in_progress로 바꾸고 Decision Log 확인.
완료 시: 체크리스트 갱신 + 증거 경로 + 짧은 한국어 브리핑.
참고만: https://github.com/anywhere-labs/dsh-desktop (복붙 금지).
```

---

## 9. Decision Log

| ID | 날짜 | 결정 | 결정자 | 메모 |
|---|---|---|---|---|
| D-00 | 2026-09-15 | DSH는 **배포·셸 UX 참고**만. Harness 이식 안 함 | 강병석 / 마뱀 초안 | 공개 docs 기반 검토 |
| D-01 | 2026-09-15 | 셸 기술 **A (Electron + Python 클로저)** 채택 (목표 UX: 트레이/업데이트/Win+Mac) | 강병석 지시 순차진행 · 마뱀 기록 | Phase 0 |
| D-01-interim | 2026-09-15 | Phase 1은 기존 `build_mac_dmg.sh` 클로저 강화부터 (Electron 스캐폴드에 블로킹되지 않음) | 마뱀 | Phase 1 진입 규칙 |
| D-02 | 2026-09-15 | Python 클로저 **1a 채택** (site-packages + 런처가 `Resources/python` 우선; 없으면 호스트 탐색 fail-closed). `SSAK_BUNDLE_PYTHON=1` 옵트인 동봉(기본 OFF, DMG~55M 유지). **1b(PyInstaller 등)는 1a 실패·용량 불가피 시에만** | 강병석 지시 잔여 클로저 · 마뱀 구현 | Phase 1 residual |
| D-03 | TBD | 업데이트 서버 위치 (GitHub Releases vs 자체) | TBD | Phase 5 |
| D-04 | 2026-09-15 | 제품 목적 = **개인 사용 + 모바일 Host 연동**. UI 정본은 Host. Electron은 얇은 셸만 | 강병석 | `notes/mobile_host_premise.md` |
| D-05 | 2026-09-15 | 기본 bind `127.0.0.1`; 모바일은 **명시적** LAN/Tailscale bind + 비-loopback 시 PIN/토큰 필수 | 강병석 | Phase 6 강화 |
| D-06 | 2026-09-15 | 셸 패키지 경로 **`desktop/`** (비어 있음 확인 후 채택). Host spawn/stop은 Phase 2 후속; 스캐폴드는 Host 기동 가정 | 마뱀 | Phase 2 scaffold |

---

## 10. Phase 상태표 (진행 상황 단일 소스)

| Phase | 이름 | 상태 | 담당 | 증거 경로 |
|---|---|---|---|---|
| 0 | 범위·결정·베이스라인 | **DONE** | 마뱀 | `docs/packaging/notes/phase0_baseline.md` |
| 1 | 배포 클로저 | **DONE-with-caveat** (IN_PROGRESS 잔여=클린 Mac FULL은 `SSAK_BUNDLE_PYTHON` 스모크 후) | 마뱀 | `phase1_progress.md` · `MACOS_DMG_GUIDE.md` §5 · `windows_closure_stub.md` |
| 2 | 셸 UX | **DONE-with-caveat** (manual QA Pass/Fail 미기입; shell DMG/Builder 미완; Host spawn은 dev에서 `uv`/venv PATH 필요) | 마뱀 | `desktop/` · `notes/phase2_progress.md` · `notes/phase2_shell_qa.md` |
| 3 | Windows 패리티 | NOT_STARTED | | |
| 4 | 복구·진단 | **IN_PROGRESS** (CLI + tray export + Host-fail recovery dialog; Settings button / HTML window deferred) | 마뱀 | `agk diagnostics export` · tray 진단 내보내기 · recovery dialog · `DIAGNOSTICS.md` · `notes/phase4_progress.md` · `tests/test_diagnostics_export.py` · `desktop/hostLifecycle.js` · `desktop/main.js` |
| 5 | 업데이트 채널 | NOT_STARTED | | |
| 6 | 포트·오리진·모바일 bind | **IN_PROGRESS** | 마뱀 | `notes/phase6_progress.md` · access-info+Settings 안내 |
| 7 | generation 수명 | NOT_STARTED / OPTIONAL | | |
| 8 | 문서·게이트 마감 | NOT_STARTED | | |

상태 값: `NOT_STARTED` | `IN_PROGRESS` | `BLOCKED` | `DONE` | `DEFERRED`

---

## 11. 관련 문서

- `docs/packaging/MACOS_DMG_GUIDE.md`
- `scripts/build_mac_dmg.sh`
- `docs/ga/GA_SUPPORT_MATRIX.md` (지원 주장 과장 금지)
- `docs/ga/CR14_EX_EXECUTION_LEDGER.md` (본 레인과 분리)
- DSH: `docs/architecture.en.md`, `docs/user-guide.md`, `docs/faq.md` (upstream 참고용 URL)

---

## 12. 변경 이력

| 날짜 | 작성 | 내용 |
|---|---|---|
| 2026-09-15 | 마뱀 (핸드오프 초안) | DSH 공개 검토 기반 반영 계획서·체크리스트 최초 작성 |
| 2026-09-15 | 마뱀 | 커밋 `1314d016`로 계획서 착수. 사용자 지시: **진행 결과는 반드시 문서에 남겨 다음 에이전트가 이어갈 것**. Phase 0 DONE — 베이스라인·D-01/D-01-interim/D-02 기록. Phase 1 다음. |
| 2026-09-15 | 마뱀 | Phase 0 증거 `notes/phase0_baseline.md` 기록. Phase 1 시작: `build_mac_dmg.sh` fail-closed dist + 비밀 파일 거부. 진행 로그 `notes/phase1_progress.md`. 전체 `make dmg` 실측은 다음 스텝. |
| 2026-09-15 | 마뱀 | 사용자 목적 확정 반영(D-04/D-05): 개인사용+모바일 Host. DMG가 `src/.env` 복사로 실패 → rsync exclude로 수정 후 `make dmg` 재시도. |
| 2026-09-15 | 마뱀 | `make dmg` PASS → `dist/Ssak-Ai-0.1.0.dmg` (55M) sha256 `262b54244a…`; 번들 비밀 0건. Phase1 잔여=기동 스모크·Python 동봉 강화·Phase6 모바일 bind. |
| 2026-09-15 | 마뱀 | `dmg-smoke` PASS(:18080). Phase6: `/api/network/access-info` + Settings 모바일 안내(기본 OFF). 실기기 폰 스모크·무재시작 rebind는 잔여. |
| 2026-09-15 | 마뱀 | Phase1 residual: D-02=1a 확정; 런처 bundled-python 우선; `SSAK_BUNDLE_PYTHON` 옵트인; 가이드 클로저 인벤토리; Windows stub. 클린 Mac FULL은 동봉 빌드 스모크 후. |
| 2026-09-15 | 마뱀 | Phase 2 착수(D-06=`desktop/`): Electron thin shell 스캐폴드 — single-instance·tray Open/Quit·hide-on-close·Host URL load. Host spawn/stop 미구현(기동 가정; soak/:8000 미간섭). `notes/phase2_progress.md`. CR-14 GO 주장 없음. |
| 2026-09-15 | 마뱀 | Phase 2 다음 슬라이스: tray Settings(`/settings`)·Open logs folder(`~/Library/Logs/Ssak-Ai`)·Host ready/unreachable 상태 라벨(120s soft probe). QA 표 `notes/phase2_shell_qa.md`. Host spawn/Quit→Host 종료는 계속 deferred. CR-14 GO 없음. |
| 2026-09-15 | 마뱀 | Phase 2 Host lifecycle: soft-probe `SSAK_HOST_URL`; 기존 Host면 spawn 안 함; `SSAK_SPAWN_HOST` 기본 1(0=미spawn); owned child=`uv run agk serve` (DMG 런처 계열 fallback); tray starting…; Quit만 SIGTERM→SIGKILL(owned). Soak 29961/29969 미접촉. `hostLifecycle.js`·`phase2_progress`. CR-14 GO 없음. |
| 2026-09-15 | 마뱀 | Phase 2 **DONE-with-caveat**: Dock 정책 문서화(hide-on-close→프로세스/Dock 유지, Quit까지); 체크리스트 코드 항목 [x]; caveats=수동 QA Pass/Fail 미기입·shell DMG/Builder 미완·spawn은 uv/venv PATH. Phase 4 **IN_PROGRESS**: `agk diagnostics export` allowlist ZIP + `DIAGNOSTICS.md` + `phase4_progress` + 테스트. CR-14 GO 없음. |
| 2026-09-15 | 마뱀 | Phase 4 tray slice: **진단 내보내기…** → `child_process` `uv run agk diagnostics export --output` (동일 CLI); success dialog + `shell.showItemInFolder`; `runDiagnosticsExport` in `hostLifecycle.js`. Recovery window still open (next). Soak 29961/29969 미접촉. CR-14 GO 없음. |
| 2026-09-15 | 마뱀 | Phase 4 recovery: Host-fail → Electron recovery **dialog** (Open logs / Export diagnostics / Retry start / Open in browser / Quit); `suspectPortConflict` 힌트; spawn off는 re-probe only. `DIAGNOSTICS.md`·`phase4_progress`·§10 갱신. Soak 29961/29969 미접촉. CR-14 GO 없음. |
