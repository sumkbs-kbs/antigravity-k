# CR-10 · 운영 지표와 빌드 신뢰성 (운영 문서)

상태: **REVIEW**(코드 미커밋, 독립 검토 미배정)
증거팩: `.omo/evidence/commercial-reliability/CR-10/attempt-001/`
관련 발견: `docs/qa/2026-09-11-commercial-review/BASELINE.md` F06

## 1. 무엇이 문제였나

헤더 텔레메트리 바(`dashboard/src/components/Layout/SystemTelemetricsBar.tsx`)가 운영 지표를
**문자열로 박아 두고** 있었다.

```
BUILD: v0.8.0-RC        ← 실제 버전과 무관
UPTIME: 14D 08H 12M     ← 실제 가동 시간과 무관
NODE: LOCAL-01 · NOMINAL ← 실제 프로세스와 무관, healthy 부재를 true로 처리
CTRL: OPEN INTAKE WAVE 01 ← 상태가 아닌 장식
CPU/MEM/VAULT           ← 값이 없으면 0으로 표시(누락과 0을 구분 못 함)
```

서버도 도와주지 않았다. `/api/system/status`는 벽시계 기반 uptime만 주었고, 프로세스 식별자도
빌드 provenance도 없었다. 그래서 화면이 실제 값을 알 방법이 없었다.

## 2. 지금의 계약

### 2-1. 값의 출처

| 화면 | 출처 | 없을 때 |
| --- | --- | --- |
| `BUILD` | `/health`·`/api/system/status`의 `version` + `build.build_id` | `UNKNOWN` |
| `UPTIME` | `/api/system/status`의 `uptime_seconds`(+ 관측 이후 경과) | `UNKNOWN` |
| `NODE` | `process_id` + health | `UNKNOWN · …` |
| `CPU` / `MEM` | `cpu_percent` / `memory_percent` | `UNKNOWN` |
| `VAULT` | `/health`의 `rag_index_files` | `UNKNOWN` |
| `LINK` | 마지막 **성공** 관측 시각과 현재 시각 | `UNKNOWN` |

### 2-2. UPTIME의 정의 (중요)

**현재 API 서버 프로세스의 가동 시간이다.** 다음이 아니다.

- 호스트(머신)의 업타임
- 대시보드 탭이 열려 있던 시간 (CR-10 이전 `AgentPage`가 이 값을 업타임으로 표시했다)

계산은 `time.monotonic()` 경과를 쓴다. 따라서 NTP 보정이나 수동 시계 조정이 값을 흔들지 않고,
**프로세스가 재시작되면 0에서 다시 시작**한다. 값은 음수로 내려가지 않는다.

여러 worker로 띄우면 응답한 프로세스의 값이며, 어느 프로세스인지는 `process_id`(PID)로 구분한다.

### 2-3. 연결 상태 (`LINK`)

| 표시 | 의미 | 조건 |
| --- | --- | --- |
| `LIVE` | 최근 관측 성공 | 마지막 성공 관측이 30초 이내 |
| `STALE` | 관측이 오래됨 | 마지막 성공 관측이 30초 초과(폴링 주기 10초의 3배) |
| `OFFLINE` | 요청이 명시적으로 실패 | `/api/system/status` 또는 `/health` 호출 실패 |
| `UNKNOWN` | 아직 관측 전 | 첫 응답을 아직 받지 못함 |

`STALE`/`OFFLINE`에서도 **마지막 값은 지우지 않고** `· 35s ago`처럼 기준 시각을 함께 보여준다.
다만 연결이 끊기면 `healthy`는 `null`이 되어 `NOMINAL`을 주장하지 않는다.

### 2-4. UNKNOWN과 0의 구분

`CPU: 0.0%`와 `UNKNOWN`은 다르다. 0.0%는 **측정된 값**이고, UNKNOWN은 **모른다**는 뜻이다.
store의 기본값은 `null`이며 `0`/`false`/`true`로 뭉개지 않는다.

### 2-5. BUILD와 버전 구분

`BUILD`는 **서버가 보고한 버전**이다. 대시보드 번들 버전과 다르면 둘 다 표시해 오해를 막는다.

```
BUILD: v9.9.9 · stubbeef (ui v0.1.0)
        └ 서버 버전·빌드 ID      └ 번들 버전
```

### 2-6. 빌드 provenance

| 값 | 서버 | 대시보드 번들 |
| --- | --- | --- |
| 버전 | `antigravity_k.__version__`(단일 원본, `pyproject.toml`이 참조) | `dashboard/package.json`의 `version` |
| 빌드 ID | env `AGK_BUILD_ID` | env `AGK_BUILD_ID` 또는 빌드 시점 git short SHA |
| 빌드 시각 | env `AGK_BUILT_AT` | env `AGK_BUILT_AT` |
| 채널 | env `AGK_BUILD_CHANNEL` | — |

**기록되지 않은 값은 `null`이고 화면은 그 부분을 생략한다.** 빈 문자열·공백만 있는 값도 미기록으로 본다.
"그럴듯한 기본값"을 만들어 넣지 않는 것이 이 계약의 핵심이다.

## 3. 운영자가 확인할 것

### 3-1. 배포 전

```bash
pnpm --dir dashboard build           # dashboard_dist를 갱신 (추적 대상 번들)
git status --porcelain -- src/antigravity_k/dashboard_dist
rm -rf src/antigravity_k/dashboard_dist/assets/*.map   # 미추적 산출물 정리
uv run --no-sync python -m pytest tests/test_dashboard_wheel_assets.py -q
```

`dashboard_dist`는 **추적되는 커밋 대상 번들**이다. 재빌드하지 않고 배포하면 구버전 UI(하드코딩
지표)가 서빙된다.

### 3-2. 배포 후

- 헤더의 `BUILD`가 방금 배포한 버전과 같은가?
- `LINK`가 `LIVE`인가? `STALE`/`OFFLINE`이면 폴링이 실패하고 있는 것이다(브라우저 콘솔과
  `/api/system/status` 응답을 확인).
- `UPTIME`이 배포 직후 작은 값에서 시작해 증가하는가? 재시작했는데 값이 이어지면 이전 프로세스가
  아직 살아 있는지 확인한다.
- `NOMINAL`/`DEGRADED`가 실제 상태와 맞는가? 연결이 끊긴 동안에는 `UNKNOWN`이어야 한다.

### 3-3. 오해 방지

- `MEM`은 **사용률 percent**다. MB가 아니다. (`/api/system/status`의 `memory_mb`는 legacy 키 이름이며
  값은 percent다. 새 코드는 `memory_percent`를 쓴다.)
- `CPU`/`MEM`은 요청 시점 표본이므로 조회할 때마다 조금씩 다르다. 순간 비교로 이상 판단하지 않는다.
- `UNKNOWN`은 장애가 아니라 "아직/다시 모른다"는 뜻이다. `OFFLINE`이 함께 뜨면 그때가 장애다.

## 4. 구현 위치

| 역할 | 파일 |
| --- | --- |
| 화면 | `dashboard/src/components/Layout/SystemTelemetricsBar.tsx` |
| 상태·연결 판정 | `dashboard/src/stores/uiStore.ts`, `dashboard/src/App.tsx` |
| 번들 provenance | `dashboard/buildStamp.ts`, `dashboard/src/utils/uiBuildInfo.ts`, `dashboard/vite.config.ts` |
| 서버 provenance | `src/antigravity_k/build_info.py`, `src/antigravity_k/api/routes/system_api.py`, `models_api.py` |
| 계약 테스트 | `tests/test_cr10_runtime_metadata.py`, `dashboard/src/components/Layout/__tests__/SystemTelemetricsBar.cr10.test.tsx`, `dashboard/src/utils/uiBuildInfo.test.ts`, `dashboard/e2e/tests/cr10-telemetry.spec.ts` |

## 5. 알려진 한계

- 실제 스크린리더 낭독·장기 stale 전이·다중 worker 배포는 미검증이다.
- `STALE_AFTER_MS`(30초)는 폴링 주기(10초)의 3배로 **상수**다. 폴링 주기를 바꾸면 함께 바꿔야 한다.
- `memory_mb` legacy 키는 호환을 위해 남아 있다. 제거는 파괴적 변경 창구에서 결정한다.
