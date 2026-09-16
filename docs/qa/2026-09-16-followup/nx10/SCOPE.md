# NX-10 attempt-001 — 측정 전 동결(범위·게이트·skip 사유·전제조건)

카드: `docs/18` §NX-10 / `docs/19` §NX-10. 작성 시각: 2026-09-16.
규칙(카드 §절차 1): **지원 범위·필수 게이트·skip 사유는 측정 전에 고정한다** — 결과를 보고
범위를 넓히거나 좁히지 않는다. 이 문서는 실행 **전**에 작성됐다.

## 1. 지원 범위 (측정 전 고정)

`docs/ga/GA_SUPPORT_MATRIX.md` 의 분류 어휘(Supported/Experimental/Unsupported/Not evaluated)를
그대로 쓴다. 현재 **Supported 행은 0개**이며, 이 후보가 주장하는 표면도 없다:

| 표면 | 분류(고정) | 이 후보의 판정 대상인가 |
|---|---|---|
| macOS Apple Silicon + 로컬 Ollama | Experimental | 아니오 — VAL-01 staging + 담당자 필요(`BLOCKED_EXTERNAL`) |
| macOS Apple Silicon + direct MLX | Experimental | 아니오 — 실기기 + 모델 약관 |
| Linux x86_64 컨테이너 CPU/로컬 런타임 | Experimental | 아니오 — 깨끗한 호스트 설치 리허설 필요 |
| Linux x86_64 + NVIDIA CUDA · Windows | Unsupported | 아니오 |
| **데스크톱 네이티브 배포**(ADR-0003) | **Unsupported** | 아니오 → **NX-11 은 이 후보의 선행조건이 아니다** |
| macOS DMG **산출물**(로컬 빌드) | Not evaluated | 아니오 — codesign/공증·실기기·업데이트 피드 미완, desktop lane PAUSED |
| provider 경계(Ollama·LM Studio·MLX·OpenRouter·NIM·OpenAI·Gemini·ZAI) | Experimental | 아니오 — 자격증명 staging + 약관/법무 승인 필요 |

**따라서 이 attempt 의 의미는 "출시 GO 판정"이 아니라 "후보 고정 기계장치와 필수 게이트 실행"이다.**
desktop 을 지원 범위로 넓히지 않으므로 NX-11 은 조건부 카드로 남는다.

## 2. 필수 게이트 (하드코딩 금지 — 실제 manifest 에서 읽었다)

- manifest: `scripts/commercial_ga_gates.json` · sha256 `a40867c743a9df5ba5854548476fcc53913e5364968a01e30e00c3e03b2eadb7`
- 게이트 **23개 = 전부 `required: true`** (`optional` 0개). 카테고리: python_backend 6 · runtime 5 ·
  dashboard 5 · supply_chain 3 · package/docker/security/accessibility 각 1.
- 의존성 lock: `uv.lock` · `dashboard/pnpm-lock.yaml` · `dashboard/package-lock.json` (manifest 가 지정).
- 과거 문서의 "23개" 는 이번에 **manifest 를 읽어 확인**했다(그 숫자를 하드코딩하지 않는다).

### execution ledger (측정 전 선언)

| 게이트 | 이 창(로컬 개발 기기) 실행 | 사유(결과와 무관하게 고정) |
|---|---|---|
| python-ruff · python-format · python-mypy · python-basedpyright | 실행 | 정적검사 — 로컬에서 가능 |
| dashboard-lint · dashboard-typecheck · dashboard-test · dashboard-build | 실행 | `pnpm` 사용 가능 |
| package-build · sbom-generate · security-bandit | 실행 | 로컬 가능 |
| api-e2e | 실행 | `tests/test_e2e_smoke.py` |
| dashboard-e2e-witnesses | 실행(번들 빌드 후) | `cr\d+-` 스펙, chromium |
| docker-build | 조건부 | docker CLI 는 있으나 **daemon 가용성 미확인** — 불가하면 not_run |
| dependency-audit-python · dependency-audit-dashboard | 조건부 | 네트워크 advisory DB 접근 필요 |
| python-tests (전량, 7200s) | **미실행** | 별도 전용 창 필요(단일 호출 예산 초과) |
| python-benchmark (1800s) | **미실행** | 별도 창 |
| master-e2e | **미실행** | 긴 전 구간 흐름 — 별도 창 |
| dashboard-e2e-ambient | **미실행** | 상시 서버(ambient) 구성 필요 |
| accessibility-e2e | **미실행** | 별도 창 |
| clean-machine-runtime (7200s) | **미실행** | 깨끗한 지원 호스트 필요(`BLOCKED_EXTERNAL`) |
| SC-1~6 soak 28,800s | **미실행** | 전용 창 + 관측(카드 §추가 soak 계약) |

**not_run 은 not_run 으로 남긴다** — 통과로 세지 않는다(카드 §수용: required 실패0/not_run0).

## 3. 전제조건 대장 (비차단 "허용"이 필요한 항목)

카드 §선행: "NX-00~09 완료 또는 **명시적으로 허용된** 비차단 조건". 현재 상태:

| 항목 | 상태 | 허용 기록 |
|---|---|---|
| NX-00 | 종료·귀속 INCONCLUSIVE | **없음** |
| NX-01~06·NX-08 | REVIEW(독립 검토자 미배정) | **없음** |
| NX-06 | 런타임 BLOCKED(cluster 없음) | **없음** |
| NX-09 | REVIEW — F03 수정, **F04(서빙 번들 신선도) 열림** | **없음** (F04 는 이 attempt 의 `dashboard-build` 게이트를 UI 증인의 전제로 만든다) |

→ **owner 허용이 기록되기 전에는 이 후보로 GO 를 선언할 수 없다**(카드 §판정). attempt 는
기술 증거만 쌓고 판정은 REVIEW/NO-GO 로 남긴다.

## 4. 후보 식별자 (측정 시점)

- HEAD: `ffb0ebb312b76d86742d3e4065628a9704f8268e`
- **dirty: true** — 작업 트리에 미커밋 변경이 있다(NX 카드 작업분 포함). 따라서 **공식 후보 SHA 는
  아직 없다**: 지문(`tree_fingerprint`, docs/.omo 제외 코드 기준)은 잠정값으로 기록한다.
- 커밋 없이 "후보 고정"이라 부르지 않는다. 커밋은 사용자 승인 사항이다.

## 5. 창(candidate window) 규칙

- 창·후보가 다르면 green 을 **합산하지 않는다**(카드 §절차 6). `ga_gate.py --merge-into` 는 같은
  SHA·같은 manifest sha·같은 지문일 때만 이월한다.
- 실패한 attempt 는 지우지 않고 남긴다(카드 §판정).
