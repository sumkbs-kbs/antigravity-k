# NX-10 — SCOPE 동결 **이후** 바뀐 것 (addendum)

`SCOPE.md` 는 카드 §절차 1 에 따라 **측정 전에** 작성했고 **수정하지 않는다**. 그런데
측정이 진행되면서 (a) 게이트가 결함을 잡아 코드가 바뀌었고 (b) 번들 신선도 문제가
드러나 산출물이 바뀌었다. 그 사실을 동결 문서에 조용히 덮어쓰지 않고 여기에 적는다.

## 1. 실행 ledger 의 변경 (넓힌 것 · 좁힌 것)

| 항목 | `SCOPE.md` 선언 | 실제 | 사유 |
|---|---|---|---|
| dashboard-install·lint·typecheck·test·build | 실행 | **실행** | 선언대로 |
| dashboard-e2e-witnesses | 실행(번들 빌드 후) | **실행 30/30 passed** | 선언대로. 번들 빌드가 선행 조건이었다 |
| api-e2e · package-build · sbom-generate · security-bandit | 실행 | **실행** | 선언대로 |
| accessibility-e2e | **미실행**(별도 창) | **실행 9.8s passed** | 선언보다 **많이** 했다(비용이 작았다) — 판정 기준을 낮추는 방향이 아니므로 문제 없음 |
| dependency-audit-dashboard · dependency-audit-python | 조건부(네트워크 필요) | **실행 passed** | advisory DB 접근이 가능했다. 조건부였으므로 결과와 무관하게 범위 변경 아님 |
| docker-build | 조건부(daemon 미확인) | **실행 passed**(230.6s) | `docker info` 가 UP — 사전 확인 후 실행 |
| python-tests · python-benchmark · master-e2e · dashboard-e2e-ambient | 미실행 | **실행**(benchmark·master-e2e·ambient 는 green, python-tests 는 타 레인 실패 4건) | 선언의 “별도 창” 요구를 전용 창(screen)으로 만족시켰다 |
| clean-machine-runtime | 미실행(`BLOCKED_EXTERNAL` — 깨끗한 지원 호스트) | **실행 → passed** | **선언의 사유가 틀렸다.** 그 게이트는 호스트 청결 검사가 아니라 **클린룸 재현 검사**(`git archive` → 임시 디렉토리 → `uv sync` → CLI/doctor → API E2E → wheel → 신규 venv 설치)이고, `git`+`uv`(+네트워크)만 있으면 어디서든 돈다. 실행해서 확인했고 통과했다 — 상세·경계(HEAD 를 검증하며 dirty 후보는 미포함)는 `GATE_LEDGER.md` §2 |

**지원 범위(Supported/Experimental/Unsupported)는 한 글자도 바꾸지 않았다.** 게이트 green 을
근거로 데스크톱 배포나 provider 경계를 Supported 로 올리지 않는다.

**선언을 고친 경우(방향이 다른 두 가지):** ① `clean-machine-runtime` 의 skip 사유는 **사실오류**였고
실행해서 바로잡았다 — 증거를 **늘리는** 방향이다. ② 나머지 not_run 은 사유(전용 창)가 맞았고
screen 으로 돌려 해소했다. 어느 쪽이든 **결과를 보고 기준을 낮춘 적은 없다**(실패는 그대로 실패로 남겼다).

## 2. 측정 중 코드가 바뀐 사실 (지문 이동)

`SCOPE.md` §4 는 후보 식별자를 `ffb0ebb3`·`dirty=true` 로 적었다. 이후:

1. **다른 레인**이 `78012f4a`·`ef960ae2`·`ffb0ebb3`·`20d529fc` 를 커밋해 HEAD 가 이동했다
   (CR-14 EX-05 문서 커밋 — 이 카드의 변경이 아니다).
2. 게이트가 잡은 결함을 고치면서 **작업 트리 내용**이 바뀌어 worktree fingerprint 가
   `d8f040ef… → cd9d9560… → 7d4ed001… → b7850c76… → da54e07b…` 로 이동했다.
3. 번들 재생성으로 `dashboard_dist` 61개 파일이 바뀌었다(그 전에 지문이 한 번 더 이동).

따라서 **attempt 001~003 의 green/red 는 최종 후보의 것이 아니다.** 대장(`GATE_LEDGER.md`)
에는 지문과 함께 남겼고, 최종 상태는 attempt 004~011(= `da54e07b…`)로만 주장한다.

## 3. 코드를 고친 뒤 다시 돌린 것 (합산 금지 규칙의 적용)

지문이 바뀌면 이전 green 을 합산할 수 없으므로, **같은 attempt 안에서** 정적검사와
관련 시험을 다시 돌렸다:

- attempt 004 = 리팩터·가드·해시 플래그 반영 후 정적검사 4개 + supply chain 3개 + api-e2e.
- 리팩터가 만진 seam 의 시험 192건을 같은 지문에서 재실행(전부 passed).
- attempt 007 이후 지문이 안정(`da54e07b…`)된 상태에서 008~011 을 측정했다.

## 4. SCOPE 를 넓히지 **않은** 결정

- `python-tests` 전량을 부분집합으로 대체해 “통과”로 세지 않았다. 부분집합(192건)은
  **리팩터 회귀 확인**으로만 기록했고, 게이트 상태는 `not_run` 그대로다.
- soak(SC-1~6)은 실행하지 않았고 “통과”로 세지 않는다.
- 기준선 재측정(`/tmp/nx10-base` = `git archive HEAD` 추출본)은 **귀속 확정용**이며,
  기준선의 green 을 후보의 green 으로 옮기지 않았다.
