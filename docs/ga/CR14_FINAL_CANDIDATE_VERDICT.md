# CR-14 최종 후보 판정서 — NO-GO

- 판정일: 2026-09-12 (attempt-001) · **attempt-002 갱신: 2026-09-12** · **attempt-003 갱신: 2026-09-12** · **attempt-004 갱신: 2026-09-12** · **attempt-005 갱신: 2026-09-13** · **attempt-006 갱신: 2026-09-13** · **attempt-007 갱신: 2026-09-13** · **attempt-008 갱신: 2026-09-13** · **attempt-009 갱신: 2026-09-13** · **attempt-010 갱신: 2026-09-13** · **attempt-011 갱신: 2026-09-13(최신)**
- 후보: 커밋 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch(CR-01~CR-14)
- 코드 지문(gate 실행 시점, `docs/`·`.omo/` 제외): attempt-001 `11979d6c…` → attempt-002 `ebbbd7f06fab3fb2d10008336ef96ba0d7949ee72007774c6372fc07f1bba0b5`(2544 files) → attempt-003 `eb10aed606ba7e84ecce03a50a19153b92105cacd196b5a167b5e38770f1f448`(2545 files) → attempt-004 `eca54773d5504e40a724a0c86ab9d1724be310986ef3e326f8f4904f52d98dd8`(2546 files) → attempt-005 `1981bfb5143d3f9eac947826bf6ee53655c47194f5be9c4a5bf755ba982a1844` → attempt-006 `3a9a7d66909e2fafaf31b4c429d2338f262d50b0d0d8ef3b5f00b5be0ca41e2d` → attempt-007 `c36327effafcc6dbe4a80970682f5e82eccd98f81951b000c758e888e7b0130a` → attempt-008 `6641446ef41e0562118dd0741637f57eae6412f18fdf18813ea87f777d0b0076` → **attempt-009 `dd34a76bf076ebc09be8c575ad733c52a0a647faa4d5d9758f3b01cf6f667f37`**
- **코드 후보 full SHA: `54e4169a947d4ba0cbe3fabf92b0c8590b8ccef6`**(attempt-009 — 커밋 `5a717c4a` + F-12 수정 `54e4169a`). `git.dirty: true` 의 원인은 ` M vault_data`(별도 저장소의 런타임 이벤트 로그) **한 줄뿐**이다 — F-13.
- 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-001/`, `attempt-002/`, `attempt-003/`, `attempt-004/`, `attempt-005/`, `attempt-006/`, `attempt-007/`, `attempt-008/`, **`attempt-009/`(최신)**
- **판정: NO-GO. GA 승인 없음. CR-14는 DONE이 아니다.**
- 출시 책임자 / 독립 검토자: **미배정 / 미배정**

이 문서는 계획서 §CR-14의 판정 규칙에 따라 작성한 **평가 산출물**이다. "NO-GO를 기록했다"는
사실은 GA 승인도, 구현 전체 완료도 아니다.

---

## attempt-011 갱신 (2026-09-13, 최신) — 계약화 + required gate 가 드러낸 **제품 결함 F-15** 폐쇄

**판정은 NO-GO 로 유지한다.** 이번 attempt 는 기술 축이 닫힌 상태에서 두 가지를 더 했다: ① attempt-010 이 규율로만 남긴 지문 경계 규칙을 **계약**으로 옮겼고, ② 그 계약을 추가한 지문에서 `python-tests` 가 실패한 것을 **flake 로 넘기지 않고 파고들어 제품 결함을 찾아 닫았다**.

- 후보: **`d72b17111ceca8518d3f9f1fb1f3a22a04c176aa`** · 코드 지문 `e428aacc…`(값 전체는 아래 §5 판정 카드가 소유한다 — `C14-F15-2` 계약이 선언 자리를 하나로 강제한다)

**① 규율 → 계약 (D-56)**

- `tests/test_cr14_fingerprint_scope_contract.py`(9건, 그중 **5건은 위반을 심어 확인하는 이빨**): README 는 지문 값을 담지 않고 소유 문서를 가리킨다 · 지문 스코프(README·`tests/**`)는 선언된 현재 지문을 인용하지 않는다 · 제외 목록(`FINGERPRINT_EXCLUDED_PREFIXES = ("docs/", ".omo/")`)이 바뀌면 계약이 먼저 깨진다 · 세 기록 문서가 그 경계를 말한다.
- 이 커밋 자체가 지문을 이동시켰다(`d4a42ab8…` → `cdfbbb96…`) — 즉 **규율을 강제하는 행위도 증거를 낡게 만든다**. 그래서 게이트를 새 지문에서 완전히 다시 돌렸다.

**② required gate 의 일회성 실패는 flake 가 아니었다 (F-15)**

- 증상: `test_cancel_sets_termination_cancelled` 가 `assert 'completed' == 'cancelled'` 로 1건 실패 — **단독 실행은 5/5 통과**했다.
- 원인: API cancel 은 `cancel_event.set()` 과 **동시에** `terminate_process_group` 을 호출하는데, watchdog 은 0.2초 폴링이라 프로세스가 먼저 죽으면 `fired_reason` 을 세우지 못하고 루프를 빠져나간다 → `reason = "completed" if fired is None else fired` 가 취소를 완료로 분류(exit_code=-15)하고, 잡 스레드가 `job.view["termination"]` 으로 **취소 기록을 덮어쓴다**. 사용자는 취소했는데 잡은 `status=failed, termination=completed, exit_code=-15` 로 남는다.
- 재현 100%: 증인 A(폴링 간격 확대 = 경주 확정) 3/3 · B(실제 간격, API 와 같은 순서) **12/12 오분류** · C(정상 완료 뒤 취소) 통과 → 수정 후 A 0/3 · B 0/12 · C 유지(exit 1 → exit 0).
- 수정: 분류를 **관측이 아니라 사실**로 — `fired is None` + `cancel_event.is_set()` + `exit_code != 0` 이면 `cancelled`. 정상 완료(exit 0)는 오분류되지 않고, 그 방향은 회귀가 고정한다.

**검증** — **required gate 20/20 을 동결된 clean HEAD 에서 되돌리기 0회로 단일 지문 `e428aacc…` 에서 완주**(python-tests **6200 passed / 13 skipped** 467.75s · docker 233.3s · clean-machine 41.3s `ref: HEAD` · dashboard-build 24.1s 드리프트 0) · `data/` 드리프트 0 · 실행 후 지문 재측정 동일. 이번에는 코드 변경을 **측정 전에 커밋**했으므로 HEAD 의존 gate 재실행이 **필요 없었다**(attempt-010 은 이 순서를 어겨 재실행이 필요했다 — D-52 의 실증).

**이 attempt 가 닫지 못한 것** — R-1: API 수준 취소 검사는 여전히 경주에 의존한다(수정을 꺼도 통과할 수 있다 — 결정적 보증은 모듈 수준 회귀). R-2: 계약이 검사하는 것은 '지문 인용'과 '경계 서술'이지 문서의 모든 수치가 아니다. R-3: `clean-machine-runtime` 초록은 `d72b1711` 시점 HEAD 에 대한 것이다. R-4: **`job.view` 를 두 스레드가 잠금 없이 쓰는 구조는 그대로다** — 이번엔 그 증상(거짓 분류)만 닫았다.

---

## attempt-010 갱신 (2026-09-13) — 지문 경계 실측 + 동결 트리에서 20/20 재검증: **기록이 증거를 낡게 만들던 경계를 찾았다**

**판정은 NO-GO 로 유지한다.** attempt-009 가 측정한 코드 내용은 그대로이고, 그 내용을 **동결된 커밋 트리**에 묶었다. 대신 그 과정에서 이 저장소가 전제해 온 가정 하나가 **틀렸음**이 드러났다.

- 후보: **clean HEAD `5ccb938e5d31411b16f2a69e3015fc8fb826455d`**(커밋 4개) · 코드 지문 **`d4a42ab87697ba299129719d054c9259a717628a1bc8f80d00cd03ae0e372ce7`**(attempt-009 의 `dd34a76b…` 에서 이동).

**드러난 경계 — "문서를 써도 증거가 낡지 않는다"는 `docs/` 안에서만 참이다**

- 게이트 코드 지문의 제외 목록은 `FINGERPRINT_EXCLUDED_PREFIXES = ("docs/", ".omo/")` 이고 **경로 접두사 비교**다. 그래서 **`README.md`(루트)와 `tests/**` 는 지문 안**이다.
- attempt-009 기록을 쓰면서 커밋 계약 파일(`tests/test_cr12_docs_alignment.py`)을 고치자 지문이 `dd34a76b…` → `003205f2…` → `d4a42ab8…` 로 **이동**했다 — 그대로 두면 attempt-009 의 20/20 초록이 **후보가 아닌 트리**를 가리킨다(F-07 과 같은 병).
- 수정: README 에서 지문 **값**을 제거하고 **출처**(본 문서·보고서)를 가리키게 했다(D-51). 최신 값을 손으로 계속 갱신하는 대안은 **갱신하는 행위가 값을 낡게 만들어** 자기모순이라 기각했다.

**동결 트리에서 20/20**

- **커밋은 지문을 옮기지 않는다**(내용 hash 기반): README 수정본 미커밋 상태 `d4a42ab8…` == 커밋 `5ccb938e` 후 `d4a42ab8…`. 그래서 "트리 동결 → 커밋 → 측정" 순서가 보고서의 SHA 와 지문을 **같은 트리**로 묶는다(D-52).
- **required gate 20개가 되돌리기 0회로 단일 지문 `d4a42ab8…` 에서 20/20 PASS**(python-tests **6189 passed / 13 skipped** 463.3s · dashboard-test **81 files/849** · docker 233.7s · clean-machine 41.0s · dashboard-build 24.6s)이고 **실행 후 지문 재측정도 동일**하다. `data/` 드리프트 0, 실행 후 트리는 ` M vault_data` 한 줄.
- **HEAD 의존 gate 분리 재실행**(D-53): `git HEAD` 에 의존하는 것은 `dashboard-build`(핀을 읽어야 드리프트 0)와 `clean-machine-runtime`(`git archive HEAD`)뿐이라 이 둘만 clean HEAD 에서 다시 돌려 `gate-report-clean-head.json`(2/2 PASS)에 남겼다 — `ref: HEAD` 로 **3001 파일**을 아카이브했고 `git ls-tree -r HEAD` 도 3001 이며 아카이브의 README 가 커밋본임을 확인했다. **전체 인벤토리는 `gate-report.json`(20/20)** 이고 단독 보고서를 '18개 미실행'으로 읽으면 안 된다.

**F-14(신규/폐쇄)** — attempt-009 기록이 `frontend 846 passed(80 files)` 를 인용했으나 **같은 attempt 의 보고서는 `Test Files 81 passed (81)` · `Tests 849 passed (849)`** 였다(F-12 가 추가한 테스트 3건 이전 값이 넘어왔다). 이 저장소가 반복해 잡아 온 **'주장 ≠ 측정'** 병과 같은 모양이므로 수치를 정정하고, **수치는 그 attempt 의 `gate-report.json` 에서 직접 인용**하기로 했다(D-54).

**이 attempt 가 닫지 못한 것** — R-4: 규율을 강제하는 회귀(문서가 지문·수치를 인용하지 않는다)는 **아직 없다**(추가하면 그 자체가 지문을 옮겨 이 증거를 무효화한다 — 게이트 실행 직전에 만들어야 한다, D-55). R-2: 목표 지문에서 20/20 을 **한 보고서로** 본 것은 아니다(20/20 + 2/2 분리). R-3: `clean-machine-runtime` 초록은 `5ccb938e` 시점 HEAD 에 대한 것이다.

---

## attempt-009 갱신 (2026-09-13) — 후보 커밋 + F-12·F-07 폐쇄: **기술 축을 모두 닫았다**

**판정은 NO-GO 로 유지한다.** 달라진 것은 **커밋된 후보에서 20/20 을 완주**했고 **`clean-machine-runtime` 이 후보를 검증**했다는 점이다. 이제 남은 차단 사유는 **사람의 영역**(외부 승인·독립 검토·장기 검증)뿐이다.

**커밋 — 그리고 훅이 막은 것이 옳았다**

- 사용자 결정에 따라 **단일 커밋**으로 고정했다: `5a717c4a`(CR-01~CR-14 후보 268 파일) + `54e4169a`(F-12 수정 27 파일). `.omo/evidence/**` 는 `.gitignore`(.omo/)의 Phase 0 규칙대로 커밋하지 않았다(D-47).
- 첫 시도가 중단됐다 — `trailing-whitespace` 가 **생성 번들 11개를 다시 썼고** `check-added-large-files`(maxkb=1024)가 모나코·TS 워커(MB 단위)를 거부했다. 훅이 생성물을 소스처럼 다루면 커밋된 바이트와 `pnpm run build` 결과가 갈라진다.
- **`--no-verify` 로 우회하지 않고** 생성 경로를 훅 대상에서 제외했다(D-46). 훅이 고친 번들 11개는 **빌드 산출물로 되돌려** 커밋했다.

**F-12 — "빌드는 멱등"은 고정 HEAD 에서만 참이었다**

- 커밋 직후 `dashboard-build` 가 **자산 22개를 교체**하고 `index.html` 을 고쳐 지문이 이동했다(`07118329…` → `a4be7868…`). 같은 HEAD 에서 두 번째 빌드는 **no-op** 이었다.
- 원인: `dashboard/buildStamp.ts` 가 `AGK_BUILD_ID` 기본값으로 `git rev-parse --short HEAD` 를 쓴다. 번들에 커밋 SHA 를 박으면 **커밋된 번들은 자기 커밋의 SHA 를 담을 수 없다**(치킨-에그). `dashboard-build` 가 required gate 인 한 **커밋된 후보에서 단일 지문 20/20 을 완주할 수 없었고**, C14-01/C14-02 가 구조적으로 미충족이었다.
- attempt-003 의 F-01 서술("빌드는 바이트 단위로 멱등")을 **조건부로 정정**한다 — 그 실측 시점에는 HEAD 가 바뀌지 않아 참이었다.
- 수정: 해석 순서를 `AGK_BUILD_ID`(릴리스 주입) → **커밋된 핀 `dashboard/build-provenance.json`** → `git short SHA` → null 로 바꾸고, 번들을 핀 값(`5a717c4a`)으로 재생성했다. **핀 ≠ HEAD 는 정상이다** — 핀은 '번들을 만든 소스 리비전'을 기록하며, 그 커밋이 번들을 담고 있는 커밋과 같을 수 없다(그것이 이 결함의 내용이다). **핀을 맞추려고 amend 하지 말 것** — 같은 루프로 돌아간다.
- **부수 개선**: `.git` 이 없는 Docker 빌드도 핀을 읽어 출하 컨테이너가 **커밋된 번들과 같은 바이트**를 서빙한다(그전에는 buildId 가 UNKNOWN). 다만 이 효과는 이번에 컨테이너 안에서 두 번 빌드해 비교한 것이 아니라 해석 순서에서 따라오는 결론이다(R-5).

**F-07 폐쇄 — 게이트가 후보를 검증했다**

- `clean-machine-runtime` 은 `git archive HEAD` 를 쓴다. 커밋 전 초록은 후보가 아닌 낡은 HEAD(2877 파일)를 검증했다.
- 후보 커밋 `54e4169a` 에서 전 게이트를 재실행해 `ref: HEAD` 로 **후보 전체(3001 파일)** 를 아카이브·검증했다 → **이 초록은 후보의 근거다**.
- 순서 규율은 남는다: **릴리스는 태그 SHA 에서 이 gate 를 마지막으로 다시 실행해야 한다**(이후 커밋·rebase 가 있으면 초록이 다시 낡는다 — R-3).

**검증**

- **required gate 20개가 커밋된 후보에서 되돌리기 0회로 단일 지문 `dd34a76b…` 에서 20/20 PASS**(python-tests 6189 passed / 13 skipped · docker 227.3s · clean-machine 42.5s · dashboard-build 24.0s · api-e2e 18.4s)이고 **실행 후 지문이 불변**임을 재측정했다.
- 증인 `cr14_f12_build_drift_witness.py` exit 0 — A) 핀 유효·해석 순서, B) 출하 번들이 핀 값을 보유, C) 재빌드 digest 불변(수정 전에는 22개 교체).
- 회귀 9건(`tests/test_cr14_bundle_provenance.py` 6 · `dashboard/src/utils/buildStamp.provenance.test.ts` 3). 핀 값을 `deadbeef` 로 바꾸면 pytest 2건 실패(이빨 확인).
- `data/` 드리프트 0. release 문서 해시 불변(의존성 변경 없음).

**F-13(신규, advisory)** — `git status` 의 유일한 줄은 ` M vault_data` 이고 그 안은 ` M hooks/events.jsonl`(+3537줄 훅 이벤트)이다. gitlink SHA 는 불변(`464708c…`)이라 커밋에는 영향이 없지만 `ga_gate.py` 의 `dirty = bool(git status --porcelain)` 때문에 보고서에 `git.dirty: true` 가 남아 **'clean 후보' 판정을 흐린다**. 선택지(untrack / vault 안에서 로그 ignore / dirty 판정 정교화)를 D-50 에 남겼다.

**이 attempt 가 닫지 못한 것** — C14-01 은 **부분 충족**이다('worktree 완전 clean' 을 기준으로 삼을지는 출시 책임자 결정 — R-1). 핀 == 실제 소스 리비전은 자동 검증되지 않는다(R-2). C14-03/04/05 와 C14-08 은 여전히 미실행이며, 이제 남은 차단 사유는 **전부 사람의 영역**이다.

---

## attempt-008 갱신 (2026-09-13) — F-10·F-11: **측정 도구**를 살리고 그 도구가 검증하던 경로를 끝까지 확인

**판정은 NO-GO 로 유지한다.** 이번 attempt 는 **F-10 과 F-11 을 닫고 F-09 의 `qs` 편차를 실행 검증**했으며,
그 과정에서 **지문이 이동**했다(`c36327ef…` → **`6641446ef41e0562…`**). attempt-007 의 20-gate 증거는
**그 시점 실측**으로 보존한다.

**F-10 — 오류 메시지를 그대로 믿으면 진단이 뒤집힌다**

- `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 죽는다. 이 메시지는 "러너를
  설치하라" 로 읽히지만, 실측은 **탐색 경로** 문제다 — Stryker 의 자동 플러그인 탐색은 **자기 자신의
  설치 디렉터리**를 스캔하고(`--logLevel debug` 의 `Loading @stryker-mutator/* from …` 가 증거), pnpm 의
  격리 레이아웃에서 그 안에는 core 의 의존(api·instrumenter·util)만 있으며 devDependency 인 러너는
  루트에만 있다.
- 수정은 `stryker.config.mjs` 의 **한 줄**이다(`plugins: ['@stryker-mutator/vitest-runner']`). 설치된 조합
  (9.6.1 ↔ vitest 4.x)은 이미 peer 계약(`vitest: >=2.0.0`)을 만족하고 dry-run 843 테스트가 실제로 돌므로,
  **버전을 올리는 것은 결함을 고치지 않으면서 도구 체인 전체를 움직여 두 lock 갈라짐(F-06/F-09) 위험을
  만든다**(D-40).

**F-09 의 '미검증' 이 닫혔다 — 근거가 추론에서 재현으로 올라갔다**

- 그 도구가 `qs` override 의 **유일한 소비자 경로**였다(attempt-007 R-1 이 남긴 반증 조건). 소스로 지목한
  경로는 `@stryker-mutator/core → typed-rest-client RestClient → Util.getUrl → qs.stringify` 이고, 여기서
  `encodeValuesOnly` 가 **기본값**이라 advisory(GHSA-q8mj-m7cp-5q26) 발동 조건과 일치한다.
- 실측: `qs 6.15.1`(벤더가 정확히 고정한 값)에서 `Util.getUrl`·`RestClient.get` **두 축 모두 크래시**
  (`TypeError: Cannot read properties of null (reading 'length')`, exit 1) → `6.16.0` 에서 두 축 OK(exit 0).
  즉 **advisory 가 우리 경로에서 실재**했고, 이 override 를 revert 하는 것이 **더 위험한 선택**이 됐다(D-41).

**F-11 — 도구가 돌아가자 '선언한 범위를 덮지 않는다' 가 보였다**

- `--mutate A --mutate B` 는 **마지막 하나만** 적용한다. 스크립트는 2개 파일을 선언했는데 보고서에는
  `outputStore.ts` 만 들어갔고(82.35%) **exit 0** 이었다. 통제 실험(단일 플래그로 `terminalStore.ts` 만 →
  정상 96.92%)으로 원인을 **파일 선택이 아니라 반복 플래그**로 분리하고 **쉼표 단일 플래그**로 고쳤다 —
  수정 후 보고서에 두 파일 모두(All files **91.92%** = 91 kill / 8 survive, exit 0).
- 이는 **F-07 과 같은 병**이다: exit 0 이 검증한 대상과 확인하려는 대상이 다르다. 그래서 알면서 남기지
  않았고, 그 대가로 그때까지의 20-gate 증거(지문 `faa55e0d…`)를 버리고 **최종 지문에서 20/20 을 다시
  완주**했다(D-42).
- quick 범위 생존 변이 **8건**(outputStore 6 · terminalStore 2)은 임계값(`high 80`·`break 55`)을 통과하므로
  **GA 차단이 아니다**(D-43). 도구가 이제 이 신호를 **측정 가능**하게 만들었다는 사실이 진전이다.

**검증**

- 증인 `cr14_f09_qs_consumer_probe.cjs`: `6.15.1` 에서 A·B 두 축 모두 CRASH(exit 1) → `6.16.0` 에서 A·B OK(exit 0).
- `pnpm exec stryker run --dryRunOnly` → exit 0(`Instrumented 9 source file(s) with 2344 mutant(s)`, `Ran 843 tests`).
- 회귀 **9건**(`tests/test_cr14_stryker_toolchain_contract.py`) — `plugins` 한 줄 제거 시 1건 실패, 스크립트를
  반복 플래그로 되돌리면 2건 실패(이빨 확인).
- 전체 suite **6183 passed / 13 skipped**(457.9초)에서 `data/` 드리프트 0 · 정적 검사 4종 exit 0.
- **required gate 20개가 되돌리기 없이 단일 지문 `6641446ef41e0562…` 에서 20/20 PASS**(python-tests 459.9s ·
  docker 46.0s · clean-machine 41.8s · dashboard-build 25.3s · api-e2e 18.3s)이고 **실행 후 지문이 불변**임을
  재측정했다. 의존성은 바뀌지 않았고 release 문서 해시도 불변이다(`666a2ea3…` / `14c24238…`).
- 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-008/`(한계는 `review.md` R-1~R-5).

**정직한 한계(이 attempt 가 닫지 못한 것)**

- ① `qs` 검증은 **우리가 소스로 지목한 소비자 경로**에 대한 것이고 `stryker init` 을 실행한 것은 아니다
  (R-1) ② **91.92% 는 quick 범위(2 파일)의 점수**이고 전체 `stryker`(10 파일)는 비용 때문에 돌리지 않았다
  (R-3) ③ `reports/mutation/mutation.json` 은 JsonReporter 미설정으로 **7월 21일 파일이 남아 있다**(그 안의
  break 는 50) — 현재 결과로 인용하면 틀린다(D-44) ④ **F-07 은 여전히 열려 있다** — 이번 attempt 도 커밋을
  하지 않았으므로 `clean-machine-runtime` 의 초록은 후보가 아닌 HEAD 를 가리킨다.

**출하 문서 수치 정정(D-45)** — `dashboard.cdx.json` 은 **241 항목 / 207 고유 패키지**다(attempt-007 이
"구성요소 207" 로 적은 것은 고유 이름 수였다). 해시는 불변이라 결함은 문서 표현에만 있다.

---

## attempt-007 갱신 (2026-09-13) — F-09: dev 도구 체인 취약과 **출하 경계**

**판정은 NO-GO 로 유지한다.** 이번 attempt 는 **F-09 하나만** 닫았고, 그 과정에서 **지문이 이동**했다
(`3a9a7d66…` → **`c36327ef…`**). attempt-006 의 20-gate 증거는 **그 시점 실측**으로 보존한다.

**F-09 — 게이트 초록과 공존하던 dev 취약, 그리고 세 번째 '두 진실원 갈라짐'**

- `dependency-audit-dashboard` 는 `pnpm audit --prod --audit-level high` 다. 그래서 dev 도구 체인의
  취약점은 **초록과 공존**한다. 실측(수정 전): high 1건
  (`eslint → @eslint/eslintrc → js-yaml`, `<4.3.2`) · moderate 3건
  (`@stryker-mutator/core → typed-rest-client → qs`, `<6.16.0`).
- **절반은 F-03·F-06 과 같은 병이었다** — `js-yaml` 이 **pnpm 4.3.1(취약) / npm 4.3.2(패치)** 로
  갈라져 있었다. 설치 진실원과 고지 진실원이 같은 패키지에 다른 답을 하는 상황이 **세 번째**다.
- **출하 경계를 측정으로 남겼다** — 두 패키지 모두 출하 SBOM(`dashboard.cdx.json`, 241 항목 / 207 고유
  패키지 — 수치는 attempt-008 에서 정정, D-45)과 `THIRD_PARTY_NOTICES.txt` 에 **없다**. "dev 니까 출하물에 영향 없다"를 주장이 아니라 검사(회귀
  C14-F09-6)로 바꿔, override 결정의 안전 근거로 삼았다.
- **수정** — 두 override 를 **양쪽 설정**(`pnpm-workspace.yaml` + `package.json`)에 선언하고 두 lock 을
  재생성했다. `js-yaml: 4.3.2` 는 상류(`@eslint/eslintrc`)가 `^4.3.0` 을 선언하므로 **편차가 아니라
  최소 패치**다. `qs: 6.16.0` 은 **의도된 편차**다 — `typed-rest-client@2.3.1` 이 `qs: 6.15.1` 로
  **정확히 고정**했고 수정판은 `typed-rest-client` 3.x(`^6.16.0`)에만 있는데 stryker(core 9·10)는
  `~2.3.0` 만 허용한다 — **선언 범위 안에 수정판이 없다.**
- 검증: **전체 트리 audit 0/0/0/0/0**(advisories 0 — 수정 전 1 high + 3 moderate),
  `pnpm run lint` **0 errors**(js-yaml 4.3.2 정상 로드) · vitest **846 passed** · build exit 0 ·
  출하 문서는 dev override 로 **바뀌지 않는다**(241 항목 / 207 고유 패키지에 dev 패키지 부재). 증인은 하한·두 lock
  일치·출하 closure 부재를 분리 측정해 수정 전 exit 1(위반 4건) → 수정 후 exit 0.
  전체 suite **6174 passed / 13 skipped** 에서 `data/` 드리프트 0, **required gate 20/20 을 되돌리기
  없이 단일 지문 `c36327ef…` 에서 완주**(docker 240.9s · clean-machine 41.9s). 회귀 7건.
- **닫는 중에 나온 새 결함 — F-10**: `pnpm run stryker:quick` 이
  `Cannot find TestRunner plugin "vitest"` 로 exit 1. 내 override 탓인지 의심할 수밖에 없는 위치라
  **통제 실험**을 했다 — F-09 override 를 제거하고(qs 6.15.1) 같은 명령을 실행해도 **동일하게 실패**했다.
  즉 **기존 결함**이다(stryker 9.6.1 ↔ vitest 4.1.11; 플러그인은 설치돼 있고 직접 import 도 성공).
  required gate 는 아니지만 두 가지를 막는다: ① 변이 점수(테스트 품질) 측정 수단 부재,
  ② **`qs` 편차의 유일한 소비자 경로가 실행되지 않아 그 편차가 end-to-end 로 검증되지 않았다.**
  이 미검증을 결정 대장(D-36)과 자기 검토(R-1)에 남겼다.
- **정직한 한계**: pnpm 은 override 를 지워도 해석을 즉시 되돌리지 않으므로(lock 보존) **선언 자체를
  검사하는 회귀**가 해석 검사와 짝으로 필요하다. `qs` 편차는 "수용 vs 감사 예외 등록"의 갈림길이라
  출시 책임자 결정으로 남긴다.
- 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-007/`
  (`reproduction.md`·`decision.md`(D-34~D-40)·`review.md`·`handoff.md`·`gate-report.json`·
  `logs/f09-witness-{before,after}.txt`·`logs/dev-audit-{before,after}.txt`·
  `logs/stryker-preexisting-failure.txt`·`repro/cr14_f09_dev_audit_witness.py`).

---

## attempt-006 갱신 (2026-09-13) — F-06: mermaid 경유 `uuid` 하한과 **출하 바이트**

**판정은 NO-GO 로 유지한다.** 이번 attempt 는 **F-06 하나만** 닫았고, 그 과정에서 **지문이 이동**했다
(`1981bfb5…` → **`3a9a7d66…`**). attempt-005 의 20-gate 증거는 **그 시점 실측**으로 보존한다.

**F-06 — "게이트 초록"과 "위험 0"이 갈라져 있었고, 실제 결함은 악용 경로가 아니라 하한이었다**

- 등록 서술은 "mermaid 경유 `uuid@9.0.1` moderate(GHSA-w5hq-g745-h8pq, `<11.1.1`)인데 감사
  임계값이 `high` 라 차단되지 않는다"였다. 실측하니 두 축으로 나뉘었고, 그것을 분리해 기록한다.
- ① **의존 하한 위반** — pnpm(설치·빌드 진실원)과 npm(SBOM·고지 진실원) **두 lock 모두**
  `uuid@9.0.1` 로 해석했다(위반 3건: pnpm 패키지 항목·pnpm 의존 항목·npm packages 항목).
- ② **취약 서명 미도달** — mermaid 의 erDiagram 청크는 `import { v5 } from "uuid"` 후
  `v5(str, MERMAID_ERDIAGRAM_UUID)` 로 **인자 2개**만 넘긴다. 취약 서명은 `buf` 인자를 넘길 때므로
  **악용 경로는 없었다.** 그래서 이 결함은 "취약한 의존을 쓰는 렌더러"가 아니라 **하한 문제**였다 —
  그러나 잠금 하한은 미래의 호출 경로에도 그대로 적용되고, 상류 `mermaid@10.9.8` 은 이미
  `uuid: ^9.0.0 || ^10 || ^11.1.0 || ^12 || ^13 || ^14.0.0` 로 **패치 버전을 허용**하고 있었다.
- **수정**: `dashboard/pnpm-workspace.yaml` 과 `dashboard/package.json`(npm `overrides`) **양쪽에**
  `uuid: 11.1.1`. 한쪽만 선언하면 npm 은 mermaid 범위의 **최고 가지(14.x)** 를 골라 **설치된 코드와
  고지된 코드가 갈라진다** — F-03 과 같은 병이다(같은 질문에 답하는 산출물이 둘인데 하나만 검사됨).
  11.1.1 은 취약 범위를 벗어나는 **최소 패치**이고 `exports` 가 ESM·CJS 를 모두 제공하는 것을
  확인했다(12+ 는 이번에 검증한 범위가 아니다). 두 lock 재생성 + **출하 번들 재빌드**(추적 산출물 —
  uuid 를 담은 청크가 `…Ca1Z6rrW.js` → `…DK8mMXpA.js` 로 교체) + release 문서 재생성.
- **증인이 세 축을 분리해 측정한다**: A) 잠금 하한(판정 기준), B) 취약 서명 도달성(참고),
  **C) 출하 바이트**(커밋되는 `dashboard_dist` 에서 uuid v35 구현을 담은 청크는 패치 마커
  `out of buffer bounds` 도 담아야 한다 — 판정 기준). C 축이 없으면 **잠금만 올리고 재빌드하지 않은
  상태를 놓친다**(그때 출하물에는 옛 코드가 남는다). 마커는 두 사본(uuid@9.0.1·11.1.1)에서 유무를
  직접 확인해 판별자 자체를 검증한 뒤 쓴다.
- 검증: 증인 `cr14_f06_uuid_reachability.py` 수정 전 exit 1(하한 위반 3건) → 수정 후 exit 0.
  `pnpm audit --prod` **취약 0건**(moderate 포함 0 — 수정 전에도 게이트 명령은 exit 0 이었다),
  CR-09 실브라우저 **4/4 PASS + 전 시나리오 `blockedExternal: []`**(mermaid 가 uuid 11.1.1 로 렌더),
  전체 suite **6167 passed / 13 skipped** 에서 `data/` 드리프트 0, **required gate 20/20 을 되돌리기
  없이 단일 지문 `3a9a7d66…` 에서 완주**(실행 후 지문 불변 재측정). 회귀 8건.
- **남은 위험을 새로 등록했다**: **F-09** — dev 도구 체인에 high 1건(`eslint → @eslint/eslintrc →
  js-yaml <4.3.2`)과 moderate 3건(`@stryker-mutator → typed-rest-client → qs`). 게이트가 `--prod`
  이므로 **차단되지 않는다.** F-06 이 보여준 교훈("감사 통과 ≠ 위험 0")이 한 번 더 실증된 셈이다 —
  임계값 확대/의존 상향/잔여 위험 등록 중 무엇을 고를지는 출시 책임자 결정으로 남긴다.
- **정직한 한계**(상세는 `attempt-006/review.md` R-1~R-8): B 절은 `uuid` 리터럴이 있는 파일만
  스캔하므로 minify 번들(동봉된 `mermaid.min.js` 는 패치 이전 uuid 를 인라인한다)은 놓친다 —
  우리는 그 파일을 import 하지 않으며(`exports['.'].import = ./dist/mermaid.core.mjs`), 그 사실은
  C 절이 잡는다. 12+ 의 `exports` 는 직접 확인하지 않았다(D-29 에 명시).
- **skip 기록**: `python-tests` skip 이 6 → 13 이 됐는데, 증가분 7건은 전부
  `TestAgainstInstalled`(unsloth/trl)이고 두 패키지는 `uv.lock` 에 **0건**이다(pyproject §87-90:
  extra 가 아니라 주간 drift CI 담당). **후보의 성질이 아니라 환경의 성질**이다(D-32).
- 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-006/`
  (`reproduction.md`·`decision.md`(D-27~D-33)·`review.md`·`handoff.md`·`gate-report.json`·
  `logs/f06-witness-{before,after}.txt`·`logs/vendor-prebuilt-bundle-note.txt`·
  `logs/dependency-audit-dashboard-after.txt`·`logs/dashboard-dist-refresh.txt`·
  `repro/cr14_f06_uuid_reachability.py`).

---

## attempt-005 갱신 (2026-09-13) — F-03: release 라이선스 판독이 **고지문과 SBOM 으로 갈라져 있었다**

**판정은 NO-GO 로 유지한다.** 이번 attempt 는 **F-03 하나만** 닫았고, 그 과정에서 **지문이 이동**했다
(`eca54773…` → **`1981bfb5…`**). attempt-004 의 20-gate 증거는 **그 시점 실측**으로 보존한다.

**F-03 — 같은 질문에 리졸버가 둘이었다(그리고 하나만 gate 가 읽는다)**

- 등록 서술은 "release 문서의 파이썬 라이선스가 `importlib.metadata` 로 **실행 환경**에서 읽혀 같은
  후보·같은 lock 인데도 값이 달라진다"였다. 실측하니 결함은 **두 갈래**로 나뉘었고, 무게추는 환경이
  아니라 **판독 실패** 쪽이었다.
- ① **판독 실패(환경과 무관하게 틀린다)** — `THIRD_PARTY_NOTICES.txt` 의 파이썬 절만
  `metadata.metadata(name)["License"]` 를 직접 읽었고, `python.cdx.json` 은 PEP 639
  `License-Expression` → `License` → `License ::` 분류기 → 별명표 순으로 읽었다. PEP 639 이후
  대부분의 배포물은 `License-Expression` 에 SPDX id 를 쓰고 `License` 를 **비워 두므로**, 같은
  실행의 두 산출물이 같은 패키지에 다른 답을 했다 — 실측 **42건 불일치**(파이썬 구성요소 61개),
  그중 **35건은 이 환경의 메타데이터를 직접 읽어 반증한 판독 실패**다(`fastapi`=MIT,
  `anyio`=MIT, `click`=BSD-3-Clause, `cryptography`=Apache-2.0, `networkx`=BSD-3-Clause …).
- 이 고지문은 **wheel/sdist 에 동봉되는 법적 문서**이고 `release_sbom verify` 가 저장소 사본과의
  **바이트 일치**를 요구한다 — 즉 41줄의 `license metadata unavailable` 은 저장소에만 있는 것이
  아니라 **출하물에 그대로 실려 나가는 고지**였다.
- ② **환경 의존(남는 부분)** — 현재 플랫폼에 설치되지 않는 마커 패키지(`colorama`·`pywin32`)만
  양쪽 모두 미상이었고, **그 집합이 어디에도 선언돼 있지 않았다**. 즉 문서가 무엇을 모르는지를
  저장소가 알지 못했다.
- 수정: 고지문이 SBOM 과 **같은 판독 체인**을 쓰도록 통일했다(SPDX id → 정규화 불가 시 원문
  `License` 필드를 **공백만 정규화**해 한 줄 유지 → 미상 표기 — **값을 합성하지 않는다**). 저장소
  사본을 재생성해 미상이 **41건 → 2건**이 됐고, `python.cdx.json` 은 **수정 전후 바이트 동일**,
  `dashboard.cdx.json` 도 재생성 전후 동일이었다(결함은 고지문 쪽이었다). 남은 2건은
  **추정 SPDX 를 `declared_licenses` 에 적어 덮지 않고**(검증되지 않은 라이선스 주장 금지),
  `미해결 ⊆ marker_platform_packages` 를 회귀 17건으로 고정했다. 그중 하나는 **재생성 계약**이라
  잠금 환경보다 부실한 곳에서 생성하면(= 커밋된 값이 미상으로 되돌아가면) 테스트가 실패한다.
- 검증: 증인 `cr14_f03_notices_sbom_divergence.py` 가 수정 전 exit 1(불일치 42 · 판독 실패 35 ·
  미해결 41) → 수정 후 exit 0(불일치 0 · 판독 실패 0 · 미해결 = 정책 선언). 전체 suite
  **6166 passed / 6 skipped** 에서 `data/` 드리프트 0, **required gate 20/20 실행·20/20 PASS 를
  되돌리기 없이 단일 지문 `1981bfb5…` 에서 완주**. ruff/format/mypy/basedpyright 전부 exit 0.
- 구조적 교훈: **gate 는 SBOM 만 읽는다.** 그래서 고지문의 41줄이 틀린 동안에도 REL-03 license
  gate 는 초록이었다 — 같은 질문에 답하는 산출물이 둘인데 하나만 검사되면 검사되지 않는 쪽이 썩는다.
- 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-005/`
  (`reproduction.md`·`decision.md`(D-23~D-26)·`review.md`·`handoff.md`·`gate-report.json`·
  `logs/f03-witness-{before,after}.txt`·`repro/cr14_f03_notices_sbom_divergence.py`).

---

## attempt-004 갱신 (2026-09-12) — F-08: 검증을 더럽히는 **두 번째 경로**

**판정은 NO-GO 로 유지한다.** 이번 attempt 는 **F-08 하나만** 닫았고, 그 과정에서 **지문이 이동**했다
(`eb10aed6…` → **`eca54773…`**, 2546 files). attempt-003 의 20-gate 증거는 **그 시점 실측**으로 보존한다.

**F-08 — 사용량 추적 기본 경로가 추적 파일을 다시 썼다**

- 원인: `api/dependencies.py` 가 ModelManager 를 만들 때
  `UsageTracker(db_path="data/token_usage.json")` 처럼 **CWD 상대·추적 파일 경로를 하드코딩**했다.
  `UsageTracker.record()` 는 `auto_save_interval`(**기본 50**)건마다 `_save()` 를 호출하므로,
  **사용량을 50건 이상 기록하는 테스트 조합 하나면 pytest 실행이 후보 트리를 더럽혔다.**
- 이는 **F-02 와 같은 구조의 두 번째 경로**다. F-02(attempt-003)는 `benchmark_harness` 의 기본 DB 경로
  하나만 리졸버 + conftest 격리로 고쳤고, **경로 결정이 여러 곳에 흩어져 있다**는 구조적 원인은
  남아 있었다. 게다가 F-08 은 임계값(50건) 아래에서만 돌던 **지금까지의 suite 때문에 조용히 잠복**해
  있었다 — "안전했다"가 아니라 **발현 조건이 아니었다.**
- 실측(수정 전): 프로덕션과 같은 방식으로 임계값만큼 기록 → `data/token_usage.json` digest
  `7ee5e106…` → `b9f8c356…`, `git status` **`M data/token_usage.json`**.
- 수정: `usage_tracker` 에 **단일 패치 지점** `default_usage_db_path()`(+순수
  `resolve_usage_db_path(environ)`, `AGK_USAGE_DB` override)를 신설하고 — **프로덕션 기본값은
  그대로**(누적 사용량 DB 계약) — `dependencies.py` 가 리터럴 대신 리졸버를 호출한다.
  `tests/conftest.py` 세션 autouse 픽스처 `_isolate_default_usage_db` 가 테스트에서만 저장소 밖으로
  돌리고(`_isolate_default_benchmark_db` **바로 옆** — 다음 사람에게 패턴이 보이게), 회귀 13건이
  C14-F08-1~6 을 고정한다.
- 회귀 13건 중 하나는 `dependencies.get_model_manager` 의 **소스**를 검사한다(리터럴 부재 +
  `default_usage_db_path()` 호출). 동작 테스트만으로는 **리터럴이 돌아와도** 통과하기 때문이다 —
  리터럴이 돌아오면 conftest 의 패치가 **효과가 없어지는데** 그 사실이 드러나지 않는다.
- 증인 `cr14_f08_usage_db_witness.py` 는 세 구간을 **구분해** 측정한다: A(결함 원형 재현 — 리터럴
  경로가 추적 파일을 쓴다) · B(수정 후 — 패치된 리졸버 경로에 저장되고 저장소 파일은 불변) ·
  C(`AGK_USAGE_DB` override + 미설정 시 프로덕션 기본값 유지). A 만 보면 수정 후에도 실패처럼
  보이므로 종료 코드는 **B/C 가 모두 성립할 때만 0** 이다.
- 검증: 전체 suite **6149 passed / 6 skipped** 에서 `data/` **드리프트 0**(suite 전후 지문 동일),
  **required gate 20/20 실행·20/20 PASS 를 되돌리기(`git checkout`) 없이 단일 지문 `eca54773…`
  에서 완주**(3단계 모두 `--merge-into` 성공). ruff/format/mypy/basedpyright 전부 exit 0.
- 부수 확인: `data/` 에서 지문을 흔드는 파일은 **`token_usage.json`(추적) 뿐**이다 —
  `data/projects.json`·`data/benchmarks/*` 는 gitignore 라 써도 지문이 안 움직인다.
- 스스로 밟은 함정: 증인의 첫 작성이 `from ... import default_usage_db_path` 로 이름을 **직접
  바인딩**해 패치가 보이지 않았고, 그 상태로 B 구간이 저장소 파일을 썼다. F-02 회귀가 이미
  문서화한 함정이며, 이번에 **계약 두 개(소스 검사 + 동작 검사)를 짝으로 두는 이유**가 실측으로
  확인됐다.
- 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-004/`
  (`reproduction.md`·`decision.md`(D-19~D-22)·`review.md`·`handoff.md`·`gate-report.json`·
  `logs/f08-witness-{before,after}.*`·`repro/cr14_f08_usage_db_witness.py`).

**남은 것(attempt-004 시점 기록)**: F-03(라이선스 환경 의존 — **attempt-005 에서 닫힘**) ·
F-06(uuid moderate — **attempt-006 에서 닫힘**) · F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증 —
커밋 뒤 재실행 필요) · **커밋(clean full SHA)** · 외부 승인.
(attempt-007 시점의 남은 것은 **F-07 · F-10(도구 체인) · 커밋 · 외부 승인**이었다 — **F-10 은
attempt-008 에서 닫혔고, 이제 남은 기술 축은 F-07 하나다.**)

---

## 0-A. attempt-003 갱신 (2026-09-12) — 검증이 트리를 바꾸는 뿌리 하나를 제거

**판정은 NO-GO 로 유지한다.** 이번 attempt 는 **F-02 하나만** 닫았다.

**F-02 — 검증 실행이 저장소 추적 파일을 다시 썼다**

- 원인: API 런타임이 `AgentRuntime(task_outcome_recorder=benchmark_harness.record_task_outcome)` 로
  **모든 작업 완료를 기록**하는데, `BenchmarkHarness` 의 기본 DB 경로가 CWD 상대
  `data/benchmark_results.json`(**추적 파일**) 한 곳으로 고정되어 있었다. \"작업을 실행하는 테스트\"
  가 하나라도 있으면 `pytest` 전체 실행이 후보 트리를 더럽혔다.
- 실측: 전체 suite 실행 후 `M data/benchmark_results.json`, **+423줄**, `total_task_results` **656→684**.
  게이트 코드 지문이 실행마다 이동해 단계별 `--merge-into` 가 거부됐다(attempt-001
  `different working tree (81939d1a… != 71a65f32…)`). CR-13 R03 드리프트의 뿌리다.
- 수정: 기본 경로를 **단일 패치 지점**(`default_benchmark_db_path()` + 순수
  `resolve_benchmark_db_path(environ)` + `AGK_BENCHMARK_DB` override)으로 분리하고,
  `tests/conftest.py` autouse 픽스처가 테스트에서만 저장소 밖으로 돌린다(CR-02 D-07 선례).
  **프로덕션 기본값은 그대로다** — 추적 파일은 누적 결과 DB 라는 제품 계약이 있고, 결함의
  원인은 '경로가 저장소 안'이 아니라 **'테스트가 그 경로를 쓴다'** 이다.
- 회귀: 전체 suite **6136 passed / 6 skipped** 에서 `data/` **드리프트 0**(digest 불변 +
  `git status` clean). **20 required gate 가 `git checkout` 되돌리기 없이 단일 지문
  `eb10aed6…` 에서 20/20 PASS** 했고, 실행 **후에도** 지문이 동일하다.
- 새 함정 고정: conftest 는 **모듈 속성**을 패치하므로 테스트가 `from ... import
  default_benchmark_db_path` 로 이름을 직접 바인딩하면 패치를 못 본다(이 attempt 의 첫 회귀
  작성에서 2건이 거짓 실패). 회귀와 파일 상단 주석이 그 함정을 기록한다.

**남은 뿌리**: **F-01**(`src/antigravity_k/dashboard_dist/` 추적) — `clean-machine` gate 가
`git archive HEAD` 를 쓰므로 추적 번들이 낡으면 그 gate 가 낡은 UI 를 포장한다. 검증이 트리를
바꾸는 두 뿌리 중 **하나만** 제거됐다. → **§0-B 에서 이 서술을 실측으로 정정한다.**

---

## 0-B. attempt-003 추가 실측 (2026-09-12) — F-01 의 성질 정정 + F-07 신규 등록

**판정은 NO-GO 로 유지한다.** F-02 를 닫은 뒤 남은 뿌리 F-01 을 실측했더니 **기존 서술이 틀렸다.**

**F-01 정정 — `dashboard-build` 는 비결정적이지 않다**

- 종전 서술: "자산 파일명이 내용 해시라 항상 stale" → 실측: **아니다.**
- 현재 후보 위에서 `pnpm run build` 를 다시 돌려 `src/antigravity_k/dashboard_dist/` 103개 파일을
  전후 비교했다 — **added 0 / removed 0 / changed 0, 바이트 단위 동일**(`logs/f01-build-idempotency.txt`).
  코드 지문도 `eb10aed6…` 로 **불변**이다.
- 게다가 attempt-003 의 **20-gate 전체 실행 후에도** 지문이 같다 — 이 후보 상태에서 **어떤 required
  gate 도 트리를 바꾸지 않는다.** attempt-002 까지 필요했던 `git checkout` 되돌리기가 사라진 것은
  F-02 폐쇄의 직접 효과이고, 그 위에 빌드·SBOM 도 멱등임이 확인됐다.
- 그러면 트리가 dirty 한 이유는? **HEAD(`08b8bb2e…`) 의 추적 번들이 현재 소스보다 낡았기 때문**이다
  (39 삭제 / 93 신규 / 1 수정). 즉 F-01 은 "검증이 트리를 흔든다"가 아니라 **"후보가 아직 커밋되지
  않았고, 커밋된 산출물이 낡았다"** 이다. 갱신된 산출물을 후보와 함께 커밋하면 트리는 clean 이 되고
  이후 빌드는 no-op 이다.
- 남는 것은 **정책 선택**이다(빌드 산출물을 계속 추적할지, 패키징 시점 생성 + 해시 검증으로 전환할지).
  이는 GA blocker 가 아니라 post-GA 엔지니어링 결정이다.

**F-07 신규 — `clean-machine-runtime` 의 PASS 는 후보가 아니라 HEAD 를 검증한다**

- `scripts/verify_clean_machine.sh` 는 `REF="HEAD"` 로 `git archive` 한다(2877 파일). `gate-report.json`
  은 `git.sha: 08b8bb2e…` · `git.dirty: true` 를 기록한다. 즉 이 게이트의 PASS 는 **후보 작업 트리가
  아니라 커밋된 HEAD** 에 대한 판정이다.
- 그래서 지금 HEAD 번들이 낡은 UI(mermaid `10.6.1`)를 담고 있는데도 이 게이트는 **초록**이다.
  CR-10/CR-11 의 "stale bundle" blocker 가 여기서 설명된다 — **초록이 검증한 대상과 우리가 승인하려는
  대상이 다르다.**
- 이것은 코드 결함이 아니라 **검증 범위(sequencing) 문제**다 — 커밋 뒤 그 SHA 에서 다시 돌리면 정확해진다.
  다만 그 전까지 이 게이트의 PASS 를 후보의 근거로 인용하면 안 된다. 후보 커밋 시 **이 게이트를 새
  HEAD 에서 재실행하는 것이 필수**다(§6-3).

**검증** — 신규 로그 `logs/f01-build-idempotency.txt` · `logs/f01-dashboard-build-rerun.log`.
**코드 변경은 없다**(지문 `eb10aed6…` 유지) — attempt-003 의 20-gate 증거가 그대로 유효하다.

---

## 0. attempt-002 갱신 (2026-09-12) — 차단 사유의 성격이 바뀌었다

**판정은 NO-GO로 유지한다. 달라진 것은 "왜 NO-GO인가"다.**

| 규칙 | attempt-001 | attempt-002 |
|---|---|---|
| P1 미해결 | 해당(mermaid high) | **해소** — `mermaid 10.9.8` 승격 |
| required gate 실패 | 해당(1건) | **해소** |
| required gate 미실행 | 해당(4건) | **해소** — 20/20 실행 |
| 필수 외부 승인 부재 | 해당 | **해당(유지)** |
| source mismatch | 해당 | **해당(유지)** — 여전히 미커밋 (F-02 는 닫혔으나 F-01 로 clean tree 는 여전히 불가) — **※ 이 행은 attempt-002 시점 기록이다. attempt-003 에서 F-01 은 실측으로 기각됐다(§0-B).** |

**attempt-002에서 닫은 결함**

- **F-04(P1)** — `mermaid` `10.6.1 → 10.9.8`(lock 3종 동기화)로 `dependency-audit-dashboard`가
  **PASS**(high 0). 그리고 **승격이 새 보안 회귀를 드러냈다**: mermaid 10.9.8은 라벨의 raw
  `<img>`를 DOM에 **남긴다**. 핸들러는 사라져도 요소가 남으므로 **절대 URL이면 외부 요청이
  실제로 나간다**(실브라우저 캡처 `https://beacon.invalid/leak.png`). 컴파일된 계약 `C09-03`이
  승격 직후 실패하며 드러났다. **출력 정화만으로는 늦다** — mermaid가 렌더 중 측정용 임시 DOM에
  라벨 HTML을 넣어 우리 정화가 돌기 전에 요청이 나간다. `dashboard/src/utils/mermaidRuntime.ts`에서
  **입력 중화(deny-list) + 출력 구조 정화** 두 단계로 막았고, `C09-03`이 이제
  `blockedExternal: []`로 상시 감시한다. `DOMPurify` 프로파일은 `foreignObject` 라벨까지 지워
  다이어그램이 빈다(실측) — 화이트리스트가 아니라 **측정된 통로**를 없앤다.
- **F-05(신규, required gate가 처음 돌며 드러남)** — `docker-build`가 14.5초에 heap OOM
  (**3/3 재현**). 원인은 콜드 `tsc -b`이고, `node:22.13-alpine`의 기본 V8 힙 상한이
  **2096MB로 고정**(`--memory=4g`/`12g` 모두 동일 → 호스트 메모리로 회피 불가)이라 2044MB
  지점에서 회수가 안 된다. 같은 입력이 로컬에서는 기본 힙으로도 통과하므로 musl/node 조합이
  더 많은 여유를 필요로 한다. dashboard-builder 스테이지에 빌드 한정
  `ENV NODE_OPTIONS=--max-old-space-size=4096`를 추가해 **PASS(246.8s)**.
  이미지 빌드에서 `tsc -b`를 빼지 않은 이유는, 빼면 "게이트를 통과한 커밋"과 "이미지에 든 코드"의
  검증 수준이 갈라지기 때문이다.

**새로 남긴 결함**

- **F-06** — mermaid 경유 `uuid@9.0.1` moderate(`<11.1.1`, `buf` 인자 경로). 감사 gate의 임계값이
  `--audit-level high`라 **차단되지 않는다**. 상류가 uuid를 올려야 하며, 우리가 override로 11.x를
  강제하면 mermaid 10.x의 사용 경로가 검증되지 않으므로 하지 않았다. **"게이트 초록"과
  "위험 0"은 다르다.**

**검증** — `python-tests` **6124 passed / 6 skipped**(428초) · 대시보드 Vitest **80 files/846 passed**
· 실브라우저 CR-09 4/4(`blockedExternal: []`) · `accessibility-e2e` 35 · `docker-build` PASS ·
`clean-machine-runtime` PASS · ruff/format/mypy/basedpyright 0 errors. **required gate 20/20 실행·
20/20 PASS 를 단일 코드 지문 `ebbbd7f0…` 위에서 완주**했다 — `python-tests`가 재작성한
`data/benchmark_results.json`(F-02)을 되돌려 지문을 유지했고, `dashboard-build`·`sbom-generate`는
자산명이 내용 해시라 멱등이라 지문이 깨지지 않았다(실측).
상세: `.omo/evidence/commercial-reliability/CR-14/attempt-002/`.

---

## 1. 판정 근거 — attempt-001 시점 (기록)

계획서 §CR-14 판정 규칙: 하나라도 해당하면 NO-GO.

| # | 규칙 | attempt-001 실측 | attempt-002 현재 |
|---|---|---|---|
| 1 | P1 미해결 | **해당** — `dependency-audit-dashboard` FAIL. `mermaid@10.6.1` ∈ 취약 범위 `<=10.9.2`, GHSA-m4gq-x24j-jpmf (high, patched `>=10.9.3`) | 해소(F-04 폐쇄) |
| 2 | required gate 실패 | **해당** — 위 1건 | 해소 |
| 3 | required gate 미실행 | **해당** — `docker-build`, `master-e2e`, `accessibility-e2e`, `clean-machine-runtime` (4개) | 해소(20/20 실행) |
| 4 | 필수 외부 승인 부재 | **해당** — EX-01~EX-06 전부 미확보(CR-12 `BLOCKED_EXTERNAL` 유지) | **해당(유지)** |
| 5 | source mismatch | **해당** — clean 코드 후보 full SHA가 없고, 검증 실행이 추적 파일을 다시 써서 작업 트리를 고정할 수 없다 | **해당(유지)** — F-01/F-02 로 여전히 clean tree 를 만들 수 없다 |

> **과거 기록은 재라벨링하지 않는다.** 위 표의 attempt-001 열은 그 시점 실측 그대로고,
> attempt-002 는 **다른 코드 상태에서 다시 측정**한 값이다. 두 값이 다르게 보이는 것이 정상이다.

## 2. required gate 인벤토리 (20개, `scripts/commercial_ga_gates.json`)

`uv run scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json --list` 로 확정했다
(전부 `required: true`). 숫자를 맞추려고 검사를 빼지 않았다 — 인벤토리가 manifest와 같은지를
`tests/test_cr14_candidate_evidence.py::TestCandidateGateInventory` 가 강제한다.

| gate | 상태 | 결과 |
|---|---|---|
| python-ruff, python-format, python-mypy, python-basedpyright, security-bandit, package-build, dashboard-install, dashboard-lint, dashboard-typecheck, dashboard-test | PASS | 10/10, 37초 (`gate-report-part1.json`) |
| python-tests | PASS | **6123 passed / 7 skipped** (447초) |
| sbom-generate, dashboard-build, dependency-audit-python, api-e2e | PASS | `gate-report-part2.json` |
| **dependency-audit-dashboard** | **FAIL** | `pnpm audit --prod --audit-level high` exit 1 — 9건(1 low / 7 moderate / **1 high**) |
| docker-build | NOT_RUN | — |
| master-e2e | NOT_RUN | — |
| accessibility-e2e | NOT_RUN | `dashboard-build` 는 통과했으나 e2e 미실행 |
| clean-machine-runtime | NOT_RUN | timeout 7200초, 실행 창 부족 |

**attempt-001: 15 / 20 실측, 14 PASS / 1 FAIL / 4 NOT_RUN.**
**attempt-002: 20 / 20 실행, 20 / 20 PASS** — 단일 코드 지문 `ebbbd7f06fab3fb2d10008336ef96ba0d7949ee72007774c6372fc07f1bba0b5` 위에서
완주(`attempt-002/gate-report.json`). 위 표의 NOT_RUN·FAIL 은 attempt-001 시점 기록이며,
attempt-002 에서 `dependency-audit-dashboard` 는 PASS, `docker-build`·`master-e2e`·
`accessibility-e2e`·`clean-machine-runtime` 은 모두 실행·PASS 다.

검증 환경: macOS (arm64), Python 3.13 (`uv run --isolated --frozen`), Node 22.13 + pnpm 11.3.0.

## 3. 이번 작업에서 닫은 결함

### 3-1. CR-13이 남긴 승인 우회로 (C14-01) — 닫음

`required_gates`를 비우면 번들 검증기가 gate 검사를 **통째로 건너뛰고 PASS**를 냈다.
빈 gate 목록이 곧 승인이었다. 이제:

- `evidence_kind`(`release`|`reference`)가 필수다(기본값 없음).
- `release`는 `required_gates`가 비면 build·verify 양쪽에서 거부한다.
- `reference`는 `required_gates`가 비어 있어야 하고, CLI `verify`가 `PASS`(exit 0) 대신
  **`REFERENCE_ONLY`(exit 3)** 를 낸다. 참고 번들은 어떤 경로로도 승인이 되지 않는다.
- historical이 아닌 gate report artifact를 참고 번들에 실어 나르는 경로도 막았다.

CR-13 시연 번들과 CR-14 평가 번들 모두 `reference`로 재선언했다(verify exit 3).
회귀: `tests/test_cr14_candidate_evidence.py` 13건.

### 3-2. 검증이 추적 산출물을 다시 쓰던 결함 (C14-06) — 닫음

- REL-01 테스트가 `_REPO_ROOT`로 생성기를 호출해 추적 중인
  `src/antigravity_k/release/*`를 덮어썼다. 이제 임시 프로젝트에서만 생성하고,
  저장소 사본과의 일치는 새 검사 2건이 판정한다.
  이 분리로 **저장소 사본이 CR-09 이후 낡아 있었다**는 사실(대시보드 절 수백 줄)이
  처음 드러났고, release workflow와 같은 명령으로 재생성했다.
- 회귀: `tests/test_rel01_clean_build_sbom.py` (테스트 전후 release 트리 해시 동일 = "TREE STABLE").

### 3-3. 단계별 gate 실행기 (C14-01) — 도입

20개 gate는 한 프로세스 창에 들어가지 않는다(`python-tests` 447초, `clean-machine-runtime`
timeout 7200초). `ga_gate.py --merge-into`가 **같은 후보 SHA + 같은 manifest + 같은 코드 지문**
일 때만 결과를 이어받고, 같은 gate id는 새 결과로 교체한다. 다른 후보·다른 코드 상태면 exit 2.
부수적으로 후보 지문에서 `docs/`·`.omo/`를 제외해, 결과 문서 작성이 gate 증거를 낡게 만들지
않는다(계획서 §CR-14 8의 "결과 문서는 코드 후보와 별도").

## 4. 남긴 결함 (다음 후보에서 처리)

> attempt-002 갱신: **F-04 는 닫혔다**(§0). 새로 **F-06**(mermaid 경유 `uuid@9.0.1` moderate,
> 감사 임계값 `high` 라 미차단)이 등록됐고, **F-01·F-02·F-03 은 그대로 열려 있다**.
> (기록 정정: 이후 F-02 는 attempt-003, F-08 은 attempt-004, **F-03 은 attempt-005** 에서 닫혔고
> F-01 은 attempt-003 실측으로 GA blocker 에서 내려갔다 — §0-A·§0-B·attempt-005 갱신절 참조.)
>
> **attempt-003 갱신(§0-B): F-02 는 닫혔고 F-01 은 실측으로 성질이 정정됐다** — 빌드는 바이트 단위
> 멱등이므로 dirty 의 원인은 "비결정성"이 아니라 **"HEAD 추적 번들이 낡은 것"** 이다. 새로
> **F-07**(`clean-machine-runtime` 이 후보가 아니라 커밋된 HEAD 를 검증)이 등록됐다.

| ID | 결함 | 성질 | 파급 |
|---|---|---|---|
| F-01 | `src/antigravity_k/dashboard_dist/` 가 **추적 중인 빌드 산출물**이다. **§0-B 정정: 빌드는 비결정적이지 않다**(재빌드 전후 103 파일 바이트 동일, 지문 불변). dirty 의 원인은 HEAD 추적 번들이 현재 소스보다 **낡은 것**이고, 갱신 산출물을 후보와 함께 커밋하면 해소된다 | 릴리스 공학 → **정책 선택** | **GA blocker 아님**(§0-B). 남은 것은 "빌드 산출물을 계속 추적할지" 정책 결정(post-GA). 단 커밋 전까지 `clean-machine` gate 는 낡은 UI 를 포장한다(F-07) |
| ~~F-02~~ | 상용 pytest suite가 `data/benchmark_results.json`을 다시 쓴다(= CR-13 R03 드리프트의 뿌리). 단독 실행으로는 재현되지 않고 전체 suite 조합에서만 발생 | 테스트 격리 | **CLOSED (attempt-003)** — 기본 경로를 단일 패치 지점으로 분리 + conftest autouse 격리 |
| ~~F-08~~ | `dependencies.py` 가 `UsageTracker(db_path="data/token_usage.json")` 로 **추적 파일 경로를 하드코딩**. `record()` 가 50건마다 자동 저장 → 임계값을 넘는 테스트 조합에서 F-02 와 같은 실패 모드(실측 `M data/token_usage.json`) | 테스트 격리 | **CLOSED (attempt-004)** — 리졸버(`default_usage_db_path`) + `AGK_USAGE_DB` + conftest autouse 격리, 회귀 13건(그중 1건은 호출부 소스에서 리터럴 부재를 검사) |
| ~~F-03~~ | release 문서의 파이썬 라이선스가 `importlib.metadata`로 **실행 환경**에서 읽힌다 — **attempt-005 실측으로 정정: 실질 원인은 환경이 아니라 고지문과 SBOM 이 각자 다른 함수로 판독한 것이다(42건 불일치, 35건은 판독 실패)** | 설계 계약 | **CLOSED (attempt-005)** — 판독 체인 통일 + 고지문 재생성 + 미해결 집합 고정. 남는 환경 의존은 선언된 마커 2건뿐 |
| ~~F-04~~ | `mermaid@10.6.1` high 취약점 — **CLOSED(attempt-002)** | P1 | 해소: `10.9.8` 승격 + 승격이 드러낸 라벨 주입 비컨까지 폐쇄 |
| ~~F-05~~ | `docker-build`가 콜드 `tsc -b` heap OOM으로 실패(attempt-002 신규 발견) — **CLOSED(attempt-002)** | **P1급** | 해소: dashboard-builder 한정 `NODE_OPTIONS=--max-old-space-size=4096`, PASS 246.8s |
| F-06 | mermaid 경유 `uuid@9.0.1` moderate(`<11.1.1`, `buf` 인자 경로) | 잔여 위험 | 감사 임계값 `high` 라 **차단되지 않는다** — 상류가 uuid를 올려야 함(attempt-002 신규) |
| ~~F-07~~ | `clean-machine-runtime` 이 `git archive HEAD` 로 **커밋된 HEAD** 를 검증한다(그 시점 2877 파일, `git.dirty: true`). 후보가 미커밋이면 **초록이 후보가 아닌 다른 코드를 가리킨다** — **attempt-009 에서 닫혔다**(후보 커밋 후 재실행, 3001 파일) | 검증 범위(sequencing) | 코드 결함 아님 — 후보 커밋 뒤 새 HEAD 에서 재실행하면 정확해진다. 그 전까지 이 PASS 를 후보 근거로 인용 금지(attempt-003 신규) |

## 5. 판정 카드 (attempt-011 기준)

- code candidate full SHA: **`d72b17111ceca8518d3f9f1fb1f3a22a04c176aa`**(attempt-011 — `5a717c4a` 후보 → `54e4169a` F-12 → `7347c5ee` attempt-009 기록 → `5ccb938e` README 지문 제거 → `552d59be`·`024b0661` attempt-010 기록 → `5521ac5f` 지문 스코프 계약 → `d72b1711` F-15 수정). `git.dirty: true` 의 원인은 ` M vault_data` 한 줄(F-13)이며 **코드·산출물은 clean** 이다. 보조 식별자 **코드 지문 `e428aacc29ec5516b311c831880376a0e128c805429486ddf32a83c68cd9877a`**(`docs/`·`.omo/` 제외, attempt-011)
  - **SHA 는 커밋마다 움직이지만 지문이 같으면 같은 코드다** — 증거는 지문으로 읽는다. 지문 제외는 `docs/`·`.omo/` **접두사뿐**이라 `README.md`·`tests/**` 는 지문 안이다(attempt-009 의 `dd34a76b…` 는 기록 커밋이 이 둘을 고쳐서 이동했다 — F-14/D-51)
- evidence bundle 위치 / manifest SHA256: **attempt-002 는 번들을 만들지 않았다** — 근거는 `attempt-002/gate-report.json` + `reproduction.md`·`decision.md`·`manual-qa.md`·`logs/**`. attempt-001 번들(`attempt-001/bundle/`, `manifest.sha256` sidecar)은 **`evidence_kind: reference`, verify verdict `REFERENCE_ONLY`(exit 3). 승인 artifact가 아니다**로 유지
- required gate inventory / PASS / FAIL / NOT_RUN: **20 / 20 / 0 / 0**(attempt-011, **동결된 clean HEAD** 에서 되돌리기 없이 단일 지문 `e428aacc…` · 실행 후 지문 재확인 · 코드를 측정 전에 커밋해 HEAD 의존 재실행 불필요 / attempt-010 은 20 / 20 / 0 / 0(`d4a42ab8…`, HEAD 의존 2개는 별도 보고서 2/2) / attempt-009 는 20 / 20 / 0 / 0 이었으나 그 뒤 지문이 이동했다 / attempt-001 은 20 / 14 / 1 / 4 — 과거 기록 보존)
- backend·frontend·실행 보안·설치/복구·실 provider·8h 결과: backend **6200 passed / 13 skipped**(attempt-011 — skip 13건 중 7건은 unsloth/trl 환경 오버레이 부재이며 uv.lock 에 0건, D-32. attempt-010 은 6189) · frontend **849 passed(81 files)**(F-14 — 종전 기록의 `846/80` 은 F-12 이전 값이었다) · dev 도구 체인 감사 **전체 트리 0건**(attempt-007, F-09 폐쇄) · 실행 보안 PASS · 설치/복구 `clean-machine-runtime` **PASS + 후보를 검증(3001 파일, `ref: HEAD`) · clean HEAD 재실행 PASS(39.2s)** · 컨테이너 `docker-build` **PASS(233.7s)** · 실 provider **미확보** · 8h soak **미실행** · 측정 도구 `stryker:quick` **exit 0 · All files 91.92%(quick 범위 2 파일, attempt-008)**
- 후보 트리 안정성(attempt-003 실측): **20-gate 전체 실행 후 코드 지문 불변** + `dashboard-build` 재빌드 **바이트 단위 동일** → 이 후보에서 검증은 트리를 바꾸지 않는다
- 지원 scope / 실제 외부 승인: 미확정 / 없음
- 독립 리뷰 보고서와 대상 SHA: **미생성 / 미정**
- 후보 트리 안정성(attempt-005 실측): suite 전후 + **20-gate 전체 실행 전후**에 코드 지문 `1981bfb5…` 가 **동일** — 이 후보에서 검증은 트리를 바꾸지 않는다(되돌리기 0회)
- 최종 판정: **NO-GO** (기술 gate 는 초록, 승인·커밋 위생이 차단)
- 출시 책임자 / 판정 날짜: 미배정 / 2026-09-13

## 6. 재개 순서 (권장, attempt-011 갱신)

0. ~~**CR-01~CR-14 커밋 → clean full SHA 고정 → 그 SHA 에서 20-gate 재실행**~~ — **attempt-009·010 에서 완료했다.**
   SHA `54e4169a`(attempt-009) → **clean HEAD `5ccb938e`**(attempt-010) · 커밋된 후보에서 20/20 PASS ·
   `clean-machine-runtime` 이 후보를 검증(F-07 폐쇄) · HEAD 의존 2개는 clean HEAD 재실행(2/2).

0-b. ~~**규율을 계약으로**~~ — **attempt-011 에서 완료했다**(`tests/test_cr14_fingerprint_scope_contract.py` 9건, 5건이 이빨).
   ⚠️ 만드는 행위 자체가 지문을 이동시켰다(`d4a42ab8…` → `cdfbbb96…`) — 만들고 나서 새 지문에서 20 gate 를 완주해야 한다(D-56 의 실증).

0-c. **다음 첫 항목 — F-15 의 구조적 잔여**: `job.view` 를 취소 핸들러와 잡 스레드가 **잠금 없이** 쓴다. 상태 전이를
   한 지점으로 모으는 정리를 별도 attempt 로 하고, 그때도 순서는 재현 → 수정 → 회귀(이빨) → 새 지문에서 20 gate 완주다(attempt-011 R-4).

0-d. **그 다음 — C14-03** 을 취소·중단 경로까지 포함해 실행한다(F-15 같은 결함은 전 구간 시나리오에서 드러난다).
   ※ 단 **`git.dirty: true` 는 ` M vault_data` 한 줄 때문**이다(F-13) — "미커밋 코드가 있다"로 읽지 말 것.
   ※ 릴리스 직전 **태그 SHA 에서 `clean-machine-runtime` 을 마지막으로 다시 돌려라**(R-3).

   ※ **두 lock 을 한쪽만 커밋하면** 설치 코드와 고지 코드가 갈라진다(F-03/F-06 이 같은 병이었다).
   특히 **`clean-machine-runtime`** — 그 gate 는 `git archive HEAD` 를 쓰므로 커밋 전 실행은 후보
   검증이 아니다(**F-07**). **release 문서를 커밋에 빠뜨리면 출하물의 고지가 다시 낡은 상태로 나간다**(F-03).
   ~~**F-03**~~ — **attempt-005 에서 닫혔다**(판독 체인 통일 + 미해결 집합 고정).
   ~~**F-08** `data/token_usage.json` 격리~~ — **attempt-004 에서 닫혔다**(같은 구조의 두 번째 경로).
   ~~**F-01**~~ — attempt-003 실측으로 GA blocker 에서 내려갔다(빌드는 멱등, §0-B).

1. ~~**F-02** `data/benchmark_results.json` 격리~~ — **attempt-003 에서 닫혔다.** 이제 gate 는
   트리를 되돌리지 않고 단일 코드 지문에서 완주한다(`pytest` 뒤 `git checkout` 불필요).
2. ~~**F-01**~~ 은 §0-B 에서 **GA blocker 에서 내려왔다** — 빌드는 멱등이고, 낡은 것은 HEAD 추적 번들이다.
   커밋에 갱신된 `dashboard_dist` 를 포함시키면 clean 해진다. 계속 추적할지 여부는 post-GA 정책 결정.
   **mermaid 승격 이후 HEAD 번들은 소스와 다른(취약한) 코드를 담으므로 HEAD 로 되돌리면 안 된다.**
3. ~~**CR-01~CR-14 커밋 → clean full SHA 확정 → 그 SHA 에서 20-gate 재실행**~~ — **attempt-010 에서 완료했다**(clean HEAD `5ccb938e` · 지문 `d4a42ab8…` · 20/20).
   ⚠️ **기록을 `README.md`·`tests/**` 에 쓰면 지문이 이동해 증거가 낡는다**(지문 예외는 `docs/`·`.omo/` **접두사뿐**) — 릴리스 기록은 `docs/**` 에 쓰고 **결과 수치는 그 attempt 의 `gate-report.json` 에서 직접 인용**한다(F-14 · D-51/D-54).
4. **독립 코드/보안/QA 검토 배정 + 출시 책임자 지정**(C14-08).
5. **외부 조건(EX-01~06) 요청서 발송** — 이게 남은 두 번째 NO-GO 조건이다.
6. ~~**F-06**(mermaid 경유 `uuid@9.0.1` moderate)~~ — **attempt-006 에서 닫혔다**(상류 선언 범위 안의
   override `11.1.1` + 두 lock 동기화 + 출하 번들 재빌드 + 회귀 8건). **게이트 범위의 기술 결함은 0건**이다.
7. ~~**F-09**(dev 도구 체인 취약)~~ — **attempt-007 에서 닫혔다**(양쪽 설정 override + 두 lock 일치 + 출하 경계
   계약 + 회귀 7건; 전체 트리 audit 0건). 단 **`qs` 편차는 상류 정확 고정을 넘긴 유일한 곳**이고, 그 편차의
   실행 검증은 아래 F-10 뒤로 미뤄졌다.
7-1. ~~**F-10**(변이 테스트 도구 미동작)~~ — **attempt-008 에서 닫혔다.** 원인은 러너 미설치가 아니라
   **탐색 경로**였다(pnpm 격리 레이아웃에서 자동 탐색이 core 의 설치 디렉터리만 본다) —
   `stryker.config.mjs` 의 `plugins` 명시 선언으로 해결했다. 오류 메시지에 끌려 **버전을 올리는 선택은
   결함을 고치지 않으면서 도구 체인을 움직여 두 lock 갈라짐 위험을 만든다**(D-40).
   ~~**F-09 의 `qs` 편차 실행 검증**~~ — 같은 attempt 에서 마쳤다(`6.15.1` 에서 실제 크래시 →
   `6.16.0` 정상). a) revert + `config/audit-exceptions.json` 등록을 고른다면 **그 크래시를 감수해야 한다**는
   점을 근거에 넣어라(D-41).
7-2. ~~**F-11a**(quick 스크립트가 선언 범위를 덮지 않음)~~ — **attempt-008 에서 닫혔다**(쉼표 단일 플래그).
   **F-11b 판단**(quick 범위 생존 변이 8건 — GA 차단 아님): `thresholds.break` 를 `high` 로 올려 CI 신호로
   삼을지, `reporters` 에 `json` 을 추가해 기계 판독 산출물을 만들지 결정한다(D-43·D-44).
8. 그 뒤 **CR-14 attempt-009**: 릴리스 번들을 `evidence_kind: release` + 채워진 `required_gates` 로
   만들고, C14-03(같은 bundle 실사용)·C14-04(실제 이전 artifact)·C14-05(8h soak·실 provider)를
   채워 GO/NO-GO 를 다시 판정한다.

F-04(mermaid)·F-05(docker OOM)는 attempt-002 에서, F-02(벤치마크 DB 격리)는 attempt-003 에서,
F-08(사용량 DB 격리)은 attempt-004 에서, F-03(release 라이선스 판독)은 attempt-005 에서,
F-06(uuid 하한·출하 바이트)은 attempt-006 에서, F-09(dev 도구 체인)는 attempt-007 에서,
F-10(도구 미동작)·F-11a(선언 범위 미커버리지)와 F-09 의 `qs` 실행 검증은 attempt-008 에서 폐쇄됐다.
위 순서에서 빠진 항목이 그것이다. **남은 기술 축은 F-07 하나다.**

## 7. 남은 결함 요약 (attempt-007 기준)

| ID | 내용 | 성질 | 상태 |
|---|---|---|---|
| ~~F-01~~ | `dashboard_dist` 가 추적 중인 빌드 산출물 | 릴리스 공학 → 정책 | **내려감(§0-B)** — 빌드는 멱등(실측). 남은 것은 post-GA 추적 정책 선택 |
| ~~F-07~~ | `clean-machine-runtime` 이 후보가 아니라 HEAD 를 검증 | 검증 범위 | **CLOSED (attempt-009)** — 후보 커밋 `54e4169a` 에서 재실행해 `ref: HEAD` 로 **후보 전체(3001 파일, 이전 2877 = 낡은 HEAD)** 를 아카이브·검증했다. **순서 규율은 남는다**: 태그 SHA 에서 마지막으로 다시 돌려야 한다(R-3) |
| ~~F-12~~ | **빌드 provenance 치킨-에그** — `buildStamp.ts` 가 `AGK_BUILD_ID` 기본값으로 `git short SHA` 를 써서 **커밋된 번들은 자기 커밋의 SHA 를 담을 수 없고**, 커밋 직후 `dashboard-build` 가 자산 22개를 교체해 커밋된 후보에서 단일 지문 20/20 을 완주할 수 없었다 | 릴리스 공학(구조) | **CLOSED (attempt-009)** — 해석 순서 `env → 커밋된 핀 → git → null` + 번들 재생성. **핀 ≠ HEAD 는 정상**(핀=번들을 만든 소스 리비전). F-01 의 "빌드 멱등"을 조건부로 정정 |
| ~~F-15~~ | **취소가 `completed` 로 기록된다** — API cancel 은 event set 과 **동시에** 프로세스를 종료하는데 watchdog 은 0.2초 폴링이라 사유를 세우기 전에 루프를 빠져나간다. 감독이 취소를 완료로 분류하고 잡 스레드가 `termination` 을 덮어써 취소 기록이 사라진다 | 제품 결함(TRN-02 분류) | **CLOSED (attempt-011)** — required gate 가 전체 suite 에서 1건 실패(`assert 'completed' == 'cancelled'`)했고 **단독은 5/5 통과**했다. flake 로 넘기지 않고 증인을 썼더니 A 3/3 · B **12/12** 로 재현됐다. 분류를 **관측이 아니라 사실**(`cancel_event` + 비정상 종료 코드)로 바꿔 닫았고, 정상 완료는 오분류하지 않는다. **잔여(R-4)**: `job.view` 무잠금 쓰기 구조는 그대로다(D-57/D-58/D-59) |
| ~~F-14~~ | **기록이 같은 attempt 의 증거와 다른 수치를 인용했다** — attempt-009 기록의 `frontend 846 passed(80 files)` vs 그 보고서 `849 passed(81 files)` | 기록 정합(advisory) | **CLOSED (attempt-010)** — F-12 가 추가한 테스트 3건 이전 값이 넘어왔다. 이 저장소가 반복해 잡아 온 **'주장 ≠ 측정'** 병과 같은 모양이므로 수치를 정정하고 **그 attempt 의 `gate-report.json` 에서 직접 인용**하도록 못박았다(D-54). **부수 교훈**: 지문 예외는 `docs/`·`.omo/` **접두사뿐**이라 README·테스트를 고치는 행위 자체가 증거를 낡게 만든다(D-51) |
| F-13 | 중첩 저장소 `vault_data` 의 런타임 이벤트 로그가 계속 자라 부모 `git status` 가 **영구히 dirty** 다(gitlink SHA 자체는 불변) | repo 위생(advisory) | **OPEN** — 커밋에는 영향 없고 required gate 도 아니지만 `git.dirty: true` 가 보고서에 남아 'clean 후보' 판정을 흐린다. 선택지: untrack / vault 안에서 로그 ignore / dirty 판정 정교화(신호 약화라 비선호) — D-50 |
| ~~F-03~~ | release 문서 파이썬 라이선스 판독이 고지문/SBOM 으로 갈라짐(+마커 환경 의존) | 계약(REL-01) | **CLOSED (attempt-005)** — 판독 체인 통일, 회귀 17건. 고지문 미상 41 → 2건 |
| ~~F-06~~ | mermaid 경유 `uuid@9.0.1` moderate — 실측상 원인은 **의존 하한**(두 lock 모두 9.x)이었고 취약 서명(`buf`)에는 도달하지 않았다 | 잔여 위험 → 하한 | **CLOSED (attempt-006)** — 상류 선언 범위 안의 override `11.1.1` + 두 lock 동기화 + 출하 번들 재빌드 + 증인 C 축 + 회귀 8건. prod 취약 0건 |
| ~~F-10~~ | **mutation testing 도구가 동작하지 않았다** — `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 exit 1. 실측상 러너 미설치가 아니라 **탐색 경로** 문제(pnpm 격리 레이아웃에서 자동 탐색이 core 의 설치 디렉터리만 본다) | 도구 체인(게이트 아님) | **CLOSED (attempt-008)** — `stryker.config.mjs` 의 `plugins` 명시 선언 한 줄. dry-run 843 테스트 · quick exit 0. 미검증으로 남았던 **F-09 의 `qs` 편차 검증 창을 열었다** |
| ~~F-11a~~ | **`stryker:quick` 이 선언한 2개 파일 중 1개만 측정한다** — `--mutate` 반복이 마지막 값만 남겨 보고서에 `outputStore.ts` 만 들어가고도 **exit 0** 이었다(82.35% 는 절반 범위의 점수) | 측정 커버리지(게이트 아님) | **CLOSED (attempt-008)** — 쉼표 단일 플래그로 수정(두 파일 · 91.92%). F-07 과 같은 병(초록이 검증한 대상 ≠ 확인하려는 대상)이라 남기지 않고 고쳤다 |
| F-11b | quick 범위 **생존 변이 8건**(outputStore 6 · terminalStore 2) — 테스트가 잠지 못한 동작 차이 | 테스트 품질(advisory) | 임계값(`high 80`·`break 55`)을 통과하므로 **GA 차단 아님**(D-43). 91.92% 는 **quick 범위(2 파일)** 의 점수다 — 전체 `stryker`(10 파일)는 미실행이므로 프로젝트 전체 품질로 인용 금지 |
| ~~F-09~~ | dev 도구 체인 취약 — `eslint→js-yaml` high 1건 · `@stryker-mutator→qs` moderate 3건. 실측상 절반은 **또 두 lock 갈라짐**(pnpm 4.3.1 / npm 4.3.2)이었다 | 잔여 위험(게이트 범위 밖) → 하한 | **CLOSED (attempt-007)** — 양쪽 설정 override(`js-yaml 4.3.2`=상류 허용 범위, `qs 6.16.0`=기록된 편차) + 두 lock 일치 + dev 전용 경계 계약 + 회귀 7건. 전체 트리 audit 0건 |
| ~~F-02~~ | pytest 가 추적 파일 재작성 | 테스트 격리 | **CLOSED (attempt-003)** |
| ~~F-08~~ | 사용량 추적 기본 경로가 추적 파일 재작성(F-02 와 같은 구조의 두 번째 경로) | 테스트 격리 | **CLOSED (attempt-004)** |
| ~~F-04~~ | mermaid high | P1 | CLOSED (attempt-002) |
| ~~F-05~~ | docker-build tsc OOM | P1급 | CLOSED (attempt-002) |
