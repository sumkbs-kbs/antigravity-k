---
title: CR-05 provider API 키 재입력 런북
status: draft-runbook-validated-by-tests (CR-05 REVIEW)
date: 2026-09-12
plan: ../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md
checklist: ../17_COMMERCIAL_RELIABILITY_CHECKLIST.md
tags: [runbook, settings, secrets, api-keys, cr-05]
---

# provider API 키 재입력 런북

CR-05는 provider API 키를 **브라우저에 영속하지 않는다**로 정했다. 그 결과 이전 버전에서
`localStorage`에만 저장돼 있던 키는 정화 과정에서 제거되며 **자동 업로드되지 않는다**.
이 문서는 그때 운영자가 할 일과, 서버 저장이 실패했을 때의 순서를 설명한다.

계약의 전체 정의는 [설정 비밀 계약](CR05_SETTINGS_SECRET_CONTRACT.md)에 있다.

## 키가 어디에 있는가(단일 진실)

| 종류 | 저장 위치 | 서버 조회 |
|---|---|---|
| provider API 키(6종, allowlist) | 서버의 `.env`(`AGK_ENV_FILE`이 있으면 그 파일, 없으면 프로젝트 루트) — 권한 `0600`, 원자적 교체 | `GET /api/settings`의 `settings.api_keys_configured`(provider별 boolean) |
| 모델·검색엔진·예산·한도(비밀 아님) | 브라우저 `agk_user_settings:v1`(allowlist 4키) | 그대로 GET/POST |

부분값·마스킹 문자열은 어떤 응답에도 나오지 않는다. "키가 설정됐는지"만 서버가 알려준다.

## 증상 → 의미

| 증상 | 의미 |
|---|---|
| 설정 화면에서 키를 넣었는데 새로고침 후 "미설정" | 저장이 실패했거나, 다른 `.env`(`AGK_ENV_FILE`)를 보고 있다 |
| 이전 버전에서 쓰던 키가 사라짐 | 정상 동작이다 — 브라우저 영속을 제거하며 정화했다. 재입력이 필요하다 |
| 저장 시 400 | allowlist 밖 키 이름이다(임의의 `*_API_KEY`, `AGK_SEC_ACCESS_PIN`, `PATH` 등) |
| 저장 시 403 | `critical` 위험도 게이트 거부 — 그 세션은 저장 권한이 없다 |

## 절차

1. **어느 `.env`를 쓰는지 확정한다.**
   ```bash
   echo "AGK_ENV_FILE=${AGK_ENV_FILE:-<미설정 → 프로젝트 루트>/.env}"
   ls -l "${AGK_ENV_FILE:-.env}" 2>/dev/null || echo "아직 .env 없음"
   ```
2. **서버가 아는 상태를 먼저 읽는다**(키 원문이 아니라 구성 여부다).
   ```bash
   curl -s http://127.0.0.1:8000/api/settings | python3 -m json.tool | grep -A 10 api_keys_configured
   ```
3. **설정 화면에서 키를 다시 입력한다.** 입력값은 그 브라우저 세션 메모리에만 있다가
   `POST /api/settings/env`로 서버에 전달되고, 서버가 `.env`를 원자적으로 교체한다.
4. **파일에 실제로 반영됐는지 확인한다**(값 전체를 출력하지 않는다).
   ```bash
   F="${AGK_ENV_FILE:-.env}"
   ls -l "$F"                        # 권한이 0600 인지
   grep -c "_API_KEY=" "$F"          # 키 개수만 센다(값 출력 금지)
   stat -c '%a' "$F" 2>/dev/null || stat -f '%Lp' "$F"
   ```
5. **엔진을 재시작해 반영한다.** `.env`는 프로세스 시작 시 로드된다.
   ```bash
   # 개발 실행이면 프로세스를 재시작하고, 배포면 아래처럼 재기동한다
   pkill -f "uvicorn antigravity_k.api.server:app" || true
   uv run --no-sync agk serve   # 또는 사용 중인 배포 절차
   ```
6. **모델 호출로 스모크 확인한다.** 키가 잘못됐으면 인증 오류가 나야 정상이다(조용히
   로컬 모델로 폴백하지 않는다).
   ```bash
   uv run --no-sync agk model list
   ```

## 저장이 계속 실패할 때

1. `.env`가 있는 디렉터리에 쓰기 권한이 있는지 확인한다(원자적 교체는 같은 디렉터리에
   tempfile을 만든다).
   ```bash
   D="$(dirname "${AGK_ENV_FILE:-.env}")"
   T="$D/.env-write-probe-$$"; printf 'x' > "$T" && rm -f "$T" && echo "write OK"
   ```
2. 관리형 환경에서 `.env`를 읽기 전용으로 마운트했는지 확인한다 — 그 경우 설정 화면 저장은
   설계대로 실패한다. 키는 배포 시크릿(환경변수)으로 주입하고, 설정 화면에는 의존하지 않는다.
3. `0600`이 아닌 `.env`는 저장 시 서버가 권한을 정정한다. 계속 `0644`로 남으면 파일시스템이
   POSIX 권한을 지원하지 않는 환경이다(예: 일부 마운트) — 키를 환경변수로 옮긴다.

## 확인

- 키 비영속·정화 회귀:
  ```bash
  uv run --no-sync python -m pytest tests/test_cr05_settings_secret_contract.py -q
  ```
- 브라우저 확인: 설정 화면에서 키를 저장한 뒤 DevTools → Application → Local Storage에
  `apiKeys`가 **남아 있지 않은지** 본다(값이 남아 있으면 회귀다).
- 서버 확인: `GET /api/settings`에 키 원문·부분값이 **없는지** 본다.

## 롤백

- 브라우저 영속으로 되돌리는 롤백은 제공하지 않는다(그 상태가 F01 결함이다).
- 키를 서버에 두는 것이 정책상 불가한 환경이라면, 키를 배포 시크릿으로 주입하고 설정 화면의
  키 입력 기능을 비활성화한 채로 운영한다.

## 남은 위험 / 지원 범위

- 브라우저 정화는 `localStorage` 기준이다. 같은 값이 `sessionStorage`/확장 저장소/OS 클립보드
  기록에 남아 있을 수 있다 — 정화 범위 밖이며 [지원 매트릭스](GA_SUPPORT_MATRIX.md)에
  명시적 승인 항목이 없다.
- 외부 시크릿 관리자(1Password/Vault) 연동은 지원 범위가 아니다(별도 작업).
