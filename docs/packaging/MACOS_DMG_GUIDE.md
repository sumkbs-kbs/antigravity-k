---
title: Ssak-Ai (Ssak-Ai) macOS .dmg 설치 및 실행 가이드
tags: [packaging, macos, dmg, desktop, app, ssak-ai]
date: 2026-09-15
---

> 관련: 데스크톱 셸·배포 클로저 후속 계획서는 [`DESKTOP_SHELL_REFERENCE_PLAN.md`](./DESKTOP_SHELL_REFERENCE_PLAN.md)를 본다.

# Ssak-Ai (Ssak-Ai) macOS .dmg 설치 및 실행 가이드

Ssak-Ai를 macOS 데스크톱 환경에서 간편하게 설치하고 실행할 수 있는 공식 `.dmg` 디스크 이미지 배포 가이드입니다.

---

## 1. 개요

- **배포 파일**: `dist/Ssak-Ai-0.1.0.dmg` (기본 빌드 약 **55MB** UDZO; `SSAK_BUNDLE_PYTHON=1` 시 인터프리터 동봉으로 **커짐** — 아래 §5 참고)
- **앱 번들**: `Ssak-Ai.app`
- **지원 환경**: macOS 12.0 (Monterey) 이상 (Apple Silicon / Intel 호환)
- **Python 요구사항 (중요)**:
  - **기본 `make dmg`**: 호스트에 **Python 3.12+** (또는 `uv`가 찾을 수 있는 동등 런타임) 필요. `site-packages`는 번들에 포함되지만 **인터프리터는 호스트 탐색**.
  - **옵트인 `SSAK_BUNDLE_PYTHON=1 make dmg`**: `Resources/python/`에 standalone CPython을 동봉 → 클린 Mac에서도 호스트 Python 없이 기동 가능. 용량 증가(~50–60MB+)를 감수.
- **핵심 특징**:
  - 고해상도 Retina 아이콘 (`AppIcon.icns`) 내장
  - 터미널 없이 더블 클릭 한 번으로 백엔드 데몬 구동 및 기본 브라우저 자동 오픈
  - **자립형 라이브러리(`Resources/app/site-packages`) 번들링** + (옵션) **동봉 인터프리터(`Resources/python`)**
  - **Python 탐색 순서**: (1) 번들 `Resources/python/bin/python3` → (2) 사용자/호스트 Python 3.12+ (uv/miniforge/homebrew). 실패 시 알림 후 종료(fail-closed)
  - 네이티브 macOS 알림(Notification) 및 시스템 로그(`~/Library/Logs/Ssak-Ai/server.log`) 지원
  - **읽기 전용 볼륨 격리**: 가변 데이터는 `~/.antigravity-k` / `~/Library/Logs/Ssak-Ai`로 라우팅

---

## 2. 설치 방법 (사용자용)

1. **DMG 열기**: `dist/Ssak-Ai-0.1.0.dmg` 파일을 더블 클릭하여 마운트합니다.
2. **드래그 앤 드롭 설치**: 마운트된 창에서 `Ssak-Ai.app` 아이콘을 `Applications` 폴더 바로가기로 드래그합니다.
3. **디스크 이미지 추출**: 마운트된 볼륨을 추출(Eject)합니다.
4. **실행**:
   - `Launchpad` 또는 `Finder > 응용 프로그램(Applications)`에서 `Ssak-Ai`를 더블 클릭하여 실행합니다.
   - 첫 실행 시 시스템 백엔드가 백그라운드에서 구동되며, "Ssak-Ai 서버가 준비되었습니다" 시스템 알림과 함께 기본 웹 브라우저(Safari, Chrome 등)에 `http://127.0.0.1:8000` 대시보드가 자동으로 열립니다.

---

## 3. 개발자용 빌드 방법

저장소 루트에서 단 한 줄의 명령어로 `.dmg` 파일을 빌드할 수 있습니다:

```bash
# Makefile 타깃 사용
make dmg

# 또는 빌드 스크립트 직접 실행
bash scripts/build_mac_dmg.sh
```

### 빌드 파이프라인 세부 동작
1. **아이콘 생성**: `dashboard/public/icon-512.png` 소스로부터 `sips` 및 `iconutil`을 사용하여 9가지 해상도의 `AppIcon.icns` 컴파일.
2. **번들 어셈블리**: `build/mac/Ssak-Ai.app` 내에 `Info.plist`, 실행 런처(`Ssak-Ai`), 내장 애플리케이션 코어 리소스(`Resources/app`) 동기화.
3. **클로저 검증**: `dashboard_dist/index.html` 필수; `.env` / `auth_hash*` 혼입 시 즉시 FAIL.
4. **(옵션) Python 동봉**: `SSAK_BUNDLE_PYTHON=1`이면 uv-managed CPython을 `Resources/python/`에 복사. **기본값은 OFF** (용량 유지).
5. **DMG 패키징**: `hdiutil create`를 통해 `/Applications` 심볼릭 링크와 함께 읽기 전용 압축 디스크 이미지 생성.
6. **무결성 검사**: 임시 마운트 → `Info.plist` 검증 → 언마운트 → SHA-256 (`*.sha256`) 발행.

```bash
# 기본 (호스트 Python 필요, ~55M)
make dmg

# 인터프리터 동봉 (클린 Mac용; 용량↑)
SSAK_BUNDLE_PYTHON=1 make dmg

# 기동 스모크 (이미 빌드된 .app, :18080 — soak/:8000 미사용)
make dmg-smoke
```

---

## 5. 번들 클로저 목록 (Phase 1)

`Ssak-Ai.app/Contents/` 기준 포함/제외 인벤토리.

| 경로 | 포함? | 설명 |
|---|---|---|
| `MacOS/Ssak-Ai` | ✅ | 런처 (bash). Host 기동·헬스·브라우저 open |
| `Info.plist` | ✅ | 번들 메타 |
| `Resources/AppIcon.icns` | ✅ | 아이콘 |
| `Resources/app/src/` | ✅ | 애플리케이션 소스 (`antigravity_k` 포함). **`.env` / `auth_hash*` 제외** |
| `Resources/app/src/antigravity_k/dashboard_dist/` | ✅ | 프로덕션 SPA (Vite 불필요). `index.html` 없으면 빌드 FAIL |
| `Resources/app/site-packages/` | ✅ | `uv export`/`uv pip install --target` 로 동봉한 런타임 deps (~79M uncompressed) |
| `Resources/app/pyproject.toml`, `config.yaml`, `uv.lock`(있으면) | ✅ | 메타/기본 설정 |
| `Resources/python/` | ⚪ 옵션 | `SSAK_BUNDLE_PYTHON=1`일 때만. standalone CPython 3.12+ (~50–60M). 런처가 **최우선** 사용 |
| `.env`, `.env.*`, `auth_hash*` | ❌ | 비밀 — 번들 거부. 사용자 데이터(`~/.antigravity-k`)만 |
| `vault_data/`, 모델 가중치 | ❌ | 번들 금지 |
| Vite / `node_modules` / dashboard 소스 | ❌ | 프로덕션 경로 불필요 |

### Python 탐색 (런처)

1. `$APP/Contents/Resources/python/bin/python3` (동봉)
2. 개발용 `.venv` / `~/.antigravity-k/venv`
3. `uv python find` → miniforge/anaconda → homebrew → `python3.12`/`3.13`
4. 모두 실패 → **알림 후 exit 1** (fail-closed)

### 현재 상태 (2026-09-15)

| 항목 | 상태 |
|---|---|
| 기본 DMG (`make dmg`) | PASS — `dist/Ssak-Ai-0.1.0.dmg` ~55M, sha256 `262b54244a…` (로컬 artifact; gitignore) |
| `make dmg-smoke` | PASS (auth/spa 200 on :18080) |
| 클린 Mac (호스트 Python 없음) | **PARTIAL** — 기본 DMG는 호스트 Python 필요. `SSAK_BUNDLE_PYTHON=1` 검증 후 FULL 가능 |
| Windows 클로저 | 설계 stub만 — `docs/packaging/notes/windows_closure_stub.md` |

---

## 6. 문제 해결 (FAQ)

### Q1. "확인되지 않은 개발자가 배포했기 때문에 열 수 없습니다" 경고가 뜰 때
- Apple 공증(Notarization) 서명이 없는 로컬 빌드 앱의 경우:
  - `Finder`에서 `Ssak-Ai.app`을 **마우스 우클릭(Control + 클릭) > 열기(Open)**를 선택한 뒤 팝업 창에서 **열기**를 클릭합니다.
  - 또는 터미널에서 격리 속성(Quarantine)을 해제합니다:
    ```bash
    xattr -cr /Applications/Ssak-Ai.app
    ```

### Q2. 서버가 뜨지 않거나 응답 지연 경고가 나타날 때
- 시스템 로그를 확인합니다:
  ```bash
  tail -f ~/Library/Logs/Ssak-Ai/server.log
  ```
- 이미 다른 프로세스가 포트 8000을 사용 중인지 확인합니다:
  ```bash
  lsof -i :8000
  ```
- 시스템에 `uv` 또는 `Python 3.12+`가 정상 설치되어 있는지 확인합니다 (기본 DMG):
  ```bash
  which uv || which python3.12 || which python3
  ```
- 동봉 빌드라면 번들 인터프리터 존재 여부를 확인합니다:
  ```bash
  ls "/Applications/Ssak-Ai.app/Contents/Resources/python/bin/python3"
  ```
