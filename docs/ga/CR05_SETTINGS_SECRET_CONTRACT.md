# CR-05 — 설정 비밀 계약 (운영 문서)

API 키는 **입력 중에만 메모리에** 존재하고 **서버 `.env`에만** 저장된다. 브라우저
영속 저장소(localStorage/sessionStorage/IndexedDB)에는 어떤 형태로도 남지 않는다.
이 문서는 배포·운영·보안 검토가 기대해야 하는 계약과 잔여 위험을 고정한다.

## 1. 저장 위치

| 값 | 저장 위치 | 비고 |
| --- | --- | --- |
| provider API 키 (6종) | 서버 `<AGK_ENV_FILE 또는 프로젝트 루트>/.env` | 권한 `0600`, 원자적 교체 |
| 모델·검색엔진·예산·한도 | 브라우저 `agk_user_settings:v1` | allowlist 4키, 비밀 아님 |
| 그 외(테마, 히스토리 등) | 기존 자체 저장소 | 변경 없음 |

* `AGK_ENV_FILE`이 설정되면 **그 파일**을 쓴다(`config._load_dotenv_once`와 같은 규칙).
  이 경로는 테스트/격리 배포가 사용자의 실제 `.env`를 건드리지 않게 하는 공식 수단이다.
* `.env` 쓰기는 같은 디렉터리 tempfile(0600) → flush/fsync → `os.replace` →
  디렉터리 fsync 순서이며, 실패해도 기존 내용이 잘리지 않는다.

## 2. API 계약

### `GET /api/settings`

`settings.api_keys_configured` — provider별 `boolean` 맵. **키 원문·부분값·마스킹
문자열을 보내지 않는다.** (이전 구현은 `.env` 값의 앞 4자를 반환했다.)

`configured`는 **실행 중 프로세스 환경변수 또는 지속 `.env` 중 하나라도 값이 있으면**
`true`다. 그래서 설정 화면에서 방금 저장한 키가 즉시 `설정됨`으로 보이고, 삭제하면
`미설정`으로 돌아온다(단, 프로세스 환경에 남아 있는 키는 재시작 후 사라진다).

config.yaml의 `api_keys` 섹션과 `security.access_pin`은 응답에서 제거된다. 설정 읽기
실패 시 응답은 `{"settings": {"error": "settings_unavailable"}}`이며 예외 원문은
로그에만 남는다.

### `POST /api/settings/env`

본문은 평평한 `{"KEY": "value"}` 맵이다.

| 입력 | 결과 |
| --- | --- |
| 본문에 없음 | **유지** |
| `""`(빈 문자열) | **아무것도 하지 않음** (기존 서버 키를 삭제하지 않는다) |
| 비어 있지 않은 값 | **교체** |

응답: `{"ok": true, "updated": N, "message": ...}`

### `POST /api/settings/env/delete`

본문은 삭제할 키 **이름** 배열 `["GEMINI_API_KEY"]`. 명시적 삭제 전용 경로이며
없는 키는 조용히 0건으로 처리한다(멱등). 응답: `{"ok": true, "deleted": N, ...}`

두 쓰기 경로 모두 `critical` 위험도의 권한 게이트를 통과해야 한다(거부 시 403).
감사 인자에는 **키 이름만** 들어가고 값은 들어가지 않는다.

## 3. 거부되는 입력 (400)

* allowlist 밖 키: 임의의 `*_API_KEY`(예: `EVIL_API_KEY`), `AGK_SEC_ACCESS_PIN`, `PATH` 등
* 값에 개행/CR/NUL 포함 — `.env`에 다른 변수를 주입하려는 시도
* 4096자를 넘는 값, 키 이름 형식 위반(`^[A-Z][A-Z0-9_]{0,63}$`)

허용 키: `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`,
`ZAI_API_KEY`, `ANTHROPIC_API_KEY`, `AGK_DAILY_BUDGET_USD`, `AGK_HOURLY_ACTION_LIMIT`.

## 4. 브라우저 측

* `dashboard/src/utils/browserSettings.ts`가 브라우저 저장의 유일한 진입점이다.
  allowlist 4키만 통과시키고 나머지는 조용히 버린다.
* 앱 시작(`main.tsx`)에서 `sanitizeLegacyBrowserSettings()`가 1회 실행되어
  `agk_user_settings:v1` / `agk_user_settings` 두 키에서 비밀 아닌 키만 남기고
  정리한다(idempotent, 값은 읽지 않고 키 이름만 로그에 남긴다).
* localStorage 접근 거부(쿠키/스토리지 차단)·잘못된 JSON에서도 앱은 중단되지 않는다.
* 성공 저장·페이지 이탈 시 입력값을 메모리에서 지우고, 상태만 서버에서 다시 조회한다.
  마스킹 값이나 원문을 폼으로 재주입하지 않는다.

## 5. 운영 영향 / 주의

* **설정 화면은 더 이상 브라우저에 키를 캐시하지 않는다.** 이전 버전에서 브라우저에만
  저장돼 있던 키는 자동으로 서버에 전송되지 않고 정화 과정에서 제거되므로 **재입력이
  필요할 수 있다**. 화면에 그 안내 문구가 있다.
* 키 반영 시점: 프로세스 환경변수는 재시작 시 갱신된다(설정 화면의 "서버 재시작 후
  적용" 문구). `configured` 상태는 `.env`도 보므로 저장 직후에도 참으로 보인다.
* 예산/한도(`AGK_DAILY_BUDGET_USD`, `AGK_HOURLY_ACTION_LIMIT`)는 서버 allowlist에
  있지만, 현재 설정 화면은 이 값을 브라우저 preference로만 다룬다(서버 전송 안 함).
  화면이 서버 값을 반영하지 않는 문제는 **CR-06** 소관이다.
* 이 키들은 로그·응답·증거에 들어가지 않는다. 검증은 합성 canary로만 한다.

## 6. 배포 시 확인

```bash
# 1) 서버 계약
uv run --no-sync pytest tests/test_cr05_settings_secret_contract.py -q   # 20 passed

# 2) 대시보드 (브라우저 저장 정화 + 폼 상태)
pnpm --dir dashboard run typecheck && pnpm --dir dashboard run lint
pnpm --dir dashboard run test

# 3) 실제 브라우저 (dashboard_dist 빌드가 선행되어야 한다)
pnpm --dir dashboard build
pnpm --dir dashboard exec playwright test e2e/tests/cr05-settings-secrets.spec.ts --project=chromium
```

롤백 시 위험이 되돌아온다(키 원문의 browser 영속 + 부분값 GET 응답) → **되돌리지 않는
것을 권장**한다. 되돌린다면 이미 브라우저에 저장된 키를 각 사용자 브라우저에서
직접 지워야 한다.
