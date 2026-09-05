---
title: Ssak-Ai (Ssak-Ai) macOS .dmg 설치 및 실행 가이드
tags: [packaging, macos, dmg, desktop, app, ssak-ai]
date: 2026-09-03
---

# Ssak-Ai (Ssak-Ai) macOS .dmg 설치 및 실행 가이드

Ssak-Ai를 macOS 데스크톱 환경에서 간편하게 설치하고 실행할 수 있는 공식 `.dmg` 디스크 이미지 배포 가이드입니다.

---

## 1. 개요

- **배포 파일**: `dist/Ssak-Ai-0.1.0.dmg` (약 48MB, UDZO 고압축 포맷)
- **앱 번들**: `Ssak-Ai.app`
- **지원 환경**: macOS 12.0 (Monterey) 이상 (Apple Silicon / Intel 호환, Python 3.12+)
- **핵심 특징**:
  - 고해상도 Retina 아이콘 (`AppIcon.icns`) 내장
  - 터미널 없이 더블 클릭 한 번으로 백엔드 데몬 구동 및 기본 브라우저 자동 오픈
  - **자립형 독립 런타임(`site-packages`) 번들링**: 호스트 환경에 별도 라이브러리 설치 없이 Python 3.12+ 인터프리터만 있으면 100% 즉시 구동
  - **스마트 Python 3.12+ 프로브**: macOS 내장 구형 Python 3.9를 자동 배제하고 최신 Python(3.12/3.13, uv, miniforge, homebrew)을 자동 탐색하여 바인딩
  - 네이티브 macOS 알림(Notification) 및 시스템 로그(`~/Library/Logs/Ssak-Ai/server.log`) 지원
  - **읽기 전용 볼륨 격리 및 독립 런타임**: 마운트된 DMG나 `/Applications` 등 쓰기 금지된 경로에서도 오류 없이 구동되도록 모든 가변 데이터(`logs`, `data`, `models`)를 `~/.antigravity-k` 및 `~/Library/Logs/Ssak-Ai`로 안전하게 라우팅

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
3. **DMG 패키징**: `hdiutil create`를 통해 `/Applications` 심볼릭 링크와 함께 읽기 전용 압축 디스크 이미지 생성.
4. **무결성 검사**: 임시 마운트 포인트에 자동 마운트하여 `Info.plist` 검증(`plutil -lint`) 후 언마운트 및 SHA-256 체크섬(`*.sha256`) 발행.

---

## 4. 문제 해결 (FAQ)

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
- 시스템에 `uv` 또는 `Python 3.12+`가 정상 설치되어 있는지 확인합니다:
  ```bash
  which uv || which python3
  ```
