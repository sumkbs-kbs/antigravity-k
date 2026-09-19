---
title: Windows packaging closure — design stub
date: 2026-09-15
tz: Asia/Seoul
status: STUB-ONLY / DEFERRED
plan: docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md
phase: 1 (stub) → 3 (implementation DEFERRED — D-08; no NSIS this checkpoint)
---

# Windows 클로저 설계 stub (구현 없음)

> Phase 1 말미 산출물. **설치기/NSIS/portable 구현은 Phase 3** — 현재 **STUB-ONLY / DEFERRED** (계획서 D-08 / §10). Linked from [`DESKTOP_SHELL_REFERENCE_PLAN.md`](../DESKTOP_SHELL_REFERENCE_PLAN.md) Phase 3 + §11. 이 문서는 계약·인벤토리·리스크만 고정한다. **NSIS 구현 금지** until Phase 3 explicitly resumed.

## 1. 목표 상태 (Phase 3에서 구현)

클린 Windows x64에서:

1. 설치기(또는 portable zip)로 앱 배치
2. 더블클릭/시작 메뉴로 Host(`agk serve`) 기동
3. 기본 브라우저가 `http://127.0.0.1:<port>` 대시보드를 연다
4. Vite/Node/개발용 Python 설치를 사용자에게 요구하지 않는다 (클로저)

## 2. 권장 기술 후보 (Decision은 Phase 3)

| 옵션 | 장점 | 단점 | 비고 |
|---|---|---|---|
| **W-A. Electron Builder (NSIS + portable)** | D-01(Electron 셸)과 정합, 트레이/업데이트 공용 | 용량↑, 이중 런타임 | **1순위 후보** (셸 도입 후) |
| **W-B. Briefcase / PyInstaller + Inno/NSIS** | Python 단일 바이너리 클로저 | 셸 UX(트레이) 별도 | Electron 전 긴급 Win만 |
| **W-C. 기존 mac `.app` 패턴의 Win 포터블 zip** | 단순 | 설치 UX·업데이트 약함 | 임시 |

mac Phase 1의 **1a (site-packages + 근접/동봉 인터프리터)** 와 대칭: Win도 site-packages(또는 frozen) + 임베디드 Python/런처를 기본으로 하고, 1b(단일 바이너리)는 실패 시에만.

## 3. 번들 인벤토리 (초안 — mac와 대칭)

| 항목 | Win 경로(안) | mac 대응 |
|---|---|---|
| 런처 | `Ssak-Ai.exe` 또는 `scripts/launch.cmd` + 향후 Electron main | `Contents/MacOS/Ssak-Ai` |
| 앱 소스 | `resources/app/src/` | `Resources/app/src/` |
| SPA | `resources/app/src/antigravity_k/dashboard_dist/` | 동일 |
| site-packages | `resources/app/site-packages/` | 동일 |
| 임베디드 Python | `resources/python/` (embeddable 또는 uv standalone) | `Resources/python/` (옵션) |
| 사용자 데이터 | `%LOCALAPPDATA%\Ssak-Ai\` 또는 `%USERPROFILE%\.antigravity-k\` | `~/.antigravity-k` |
| 로그 | `%LOCALAPPDATA%\Ssak-Ai\logs\` | `~/Library/Logs/Ssak-Ai` |

**절대 포함 금지:** `.env`, `auth_hash*`, `vault_data`, 모델 가중치, 비밀.

## 4. 런타임 계약

- Bind 기본: `127.0.0.1` (모바일/LAN은 명시 설정 — `mobile_host_premise.md`)
- 포트: 제품 단일 포트 (개발 Vite 분리)
- Python: >= 3.12
- Fail-closed: 인터프리터/필수 dist 없으면 메시지 박스 후 종료
- 가변 데이터는 설치 디렉터리(Program Files 읽기 전용 가능)가 아닌 user data로

## 5. 검증 게이트 (Phase 3)

| ID | 검증 |
|---|---|
| W-T01 | 클린 VM 설치 → 대시보드 1회 |
| W-T02 | 번들 secret scan 0건 |
| W-T03 | `verify_release_artifacts` 또는 `verify:win-package` 연동 |
| W-T04 | Uninstall이 시작 메뉴/서비스를 남기지 않음 (설치기 경로) |

## 6. 명시적 비범위 (이 stub)

- 코드 서명 / SmartScreen — `BLOCKED_EXTERNAL` 가능
- Electron 스캐폴드 — Phase 2
- 실제 NSIS 스크립트·CI 매트릭스 — Phase 3
- CR-14 GO 주장 — 금지

## 7. 다음 액션 (Phase 3 진입 시)

1. §9 Decision에 Win 기술(W-A/B/C) 확정
2. mac `SSAK_BUNDLE_PYTHON` 교훈을 Win embeddable layout에 반영
3. `docs/packaging/WINDOWS_INSTALLER_GUIDE.md` 본문 작성
4. 설치기 구현 + 클린 VM 증거
