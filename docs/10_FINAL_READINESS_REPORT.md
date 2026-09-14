# 10 Final Readiness Report

기준일: 2026-08-17

## 결론

> **최신 판정(2026-09-14, attempt-033): GA 출시 판정 NO-GO — attempt-033 은 **F-43 · F-44** 를 닫았다: **화면이 보내는 경로는 서버가 서는 경로여야 한다 + 런타임 상태는 코드 스코프 밖에 있다.** ambient 백엔드 게이트를 만들려고 **서버를 띄우는 증인**을 세우는 첫 걸음에서 F-43 이 먼저 나왔다 — `apiRequest` 가 **래퍼 안에서** '/v1' 을 붙이는데 두 호출부(`askAgent`·`fetchWsTicket`)가 **이미 namespace 를 가진 경로**를 넘겨 실효 경로가 `/v1/api/agent/ask`·`/v1/auth/ws-ticket` 이 됐고 서버에는 그 namespace 가 **없다**(정본 `POST /api/auth/ws-ticket` 은 200 + ticket, 실효 경로는 405). **PIN 이 설정된 배포에서는 이벤트 스트림이 4401 로 거절되고 3초마다 재시도**한다(ticket 없는 WS 는 `open_loopback` 만 통과 — 로컬 dev 익명 모드가 실패를 가렸다). 접두사가 호출부의 **리터럴에 없어서** grep 도 리터럴 대조도 그 자리를 건너뛰었고 `fetchWsTicket` 은 405 를 `catch { return null }` 로 삼켰다 — **URL 을 보는 테스트가 하나도 없었던 것이 살아남은 이유**다. 고침은 전체 경로를 받는 `apiRequestPath` **제품 런타임 2줄** + 소유자 둘(라우트 표와 대조하는 계약 6건 + 정확한 URL 을 고정하는 단위 5건) · 증인 exit 1 → exit 0. 그 측정 **중에** F-44 가 나왔다 — 제품의 상대경로 상태 기본값이 cwd `src/` 프로세스의 `src/data/projects.json` 을 저장소 안에 만들어 **작업 트리 지문을 후보에서 떨어뜨렸고**, 배치가 전부 초록이었는데도 마감 직전에 멈췄다(게이트 지문은 무시되지 않은 미추적 파일도 스코프로 읽는다 — 루트의 같은 파일은 이미 무시돼 있었다). 고침은 무시 규칙 + 계약 5건(**제품 런타임 0줄**)이고 상대경로 설계의 근본 고침은 별도 attempt 로 남긴다(D-71). **세 번 선언**(번들 `tree_moved` → F-44 → 재측정). required gate **22/22 / 0 failed / 0 not_run** 을 커밋된 후보 `c66706ee` 에서 되돌리기 0회·단일 지문 `1873d2c7…`·`tree_moved` 0건·드리프트 0으로 완주했고(python-tests **6376 passed / 13 skipped**(+11 = 두 계약, 스킵 13 → 13) · dashboard-test **876 passed(86 files)**(+5 = `wsTicket.test.ts`)) 마감 검사가 **PASS** 했다. **판정 MOVED 없음** — 남은 차단 사유는 그대로 **사람·조직 축**이다(EX-01~06 · C14-08 · C14-03/04/05 · 지원 scope · 실 provider · 8h soak). ambient 백엔드 슬라이스는 **여전히 게이트 밖**이다(경계 문서 §2-8).→
>
> **이전 판정(2026-09-14, attempt-032): GA 출시 판정 NO-GO — attempt-032 는 **F-42** 를 닫았다: **브라우저 증인에게 게이트 소유자를 줬다**(required **21 → 22**). attempt-030·031 이 경계 문서 §2-6·§2-7 에 자기 한계로 적어 둔 문장(*"실 브라우저 증인은 수동이고 required 게이트 중 어느 것도 이들을 돌리지 않는다 — 게이트 소유를 먼저 정해야 한다"*)을 **측정으로 바꾸니 그 문장은 셋만의 것이 아니었다**: `dashboard/e2e/tests/cr*.spec.ts` **9파일 29건**이 어떤 required 게이트에도 **소유자가 0** 이었고(커버리지 **0/9** — 고침 전 사본으로 재현), 그 패밀리는 **ambient 백엔드 없이** 돈다(**29 passed / 43.5s**) — 즉 한계의 숨은 전제("게이트로 만들면 비싸다")가 **거짓**이었는데 두 attempt 에 걸쳐 **확인되지 않은 채** 한계로 적혀 있었다. 그 증인들은 F-35~F-41 을 찾아낸 바로 그 증인들이고, 돌아간 자리는 **사람이 기억해서 돌린 자리**뿐이었다(`accessibility-e2e` 는 한 파일만 돌리고, CI 의 full suite 는 `main` push/PR 에서만 돌며, 게이트 절차·주간·릴리스는 **어느 것도** 그 슈트를 부르지 않는다). 고침은 required 게이트 `dashboard-e2e-witnesses` 하나 + 그 소유 계약이다 — 선택자는 **목록이 아니라 이름 규칙**(`e2e/tests/cr\d+-`)이라 새 증인이 자동으로 게이트 안에서 태어나고, **경계는 지워지지 않았다**(ambient 백엔드가 필요한 스펙은 게이트가 삼키지 않고, 그들이 어느 required 게이트에도 없다는 사실을 증인이 소리 내어 센다). **이빨 셋**: 게이트를 지우면 계약 **4 failed** · `required: false` 로 강등하면 **1 failed** · 가족 이름으로 만든 **일부로 실패하는 증인**이 게이트를 **exit 1** 로 만든다(그 파일은 고침 전 세계에서 아무도 돌리지 않았다). **제품 런타임 코드 변경 0줄** — 바뀐 것은 게이트 목록과 그 소유 계약이다. required gate **22/22 / 0 failed / 0 not_run** 을 커밋된 후보 `45918a51` 에서 되돌리기 0회·단일 지문 `5a8950a1…`·`tree_moved` 0건·드리프트 0으로 완주했고(python-tests **6365 passed / 13 skipped**(+5 = 새 계약, 스킵 13 → 13) · dashboard-test **871 passed(85 files, 스킵 0건)** · 새 게이트 **29 passed in 9 files (44.1s)**) 마감 검사가 **PASS** 했다. **주의: 이 attempt 가 더한 것은 커버리지이지 제품 능력의 확장이 아니며, ambient 백엔드 슬라이스는 여전히 게이트 밖이다**(경계 문서 §2-8). 남은 차단 사유는 그대로 **사람·조직 축**이다(EX-01~06 · C14-08 · C14-03/04/05 · 지원 scope · 실 provider · 8h soak).
>
> **이전 판정(2026-09-14, attempt-031): GA 출시 판정 NO-GO — attempt-031 은 **F-41 후보를 측정으로 반증**했다: **탈출구는 정말 마지막 수단인가.** attempt-030 은 F-39 를 닫으면서 **자기 한계**를 정직하게 적었다 — *"M3(수동 탈출구) 경로는 이 실행에서 발화하지 않았다"*. 그 문장이 남긴 **재지 않은 질문**을 이 attempt 가 **제품 경로**에서 쟀다. 전제가 증인의 전부다 — M3 를 발화시키려면 자동 재연결(3회)이 소진되어 화면이 `연결 오류` + '다시 연결'을 내놓아야 하므로, 증인은 서버를 **그룹째 SIGKILL** 한 뒤 **재기동하지 않고 기다린다**. 그 다음 ① 서버가 **없는 동안** 탈출구를 눌러 보고 ② **그 뒤에** 같은 포트·같은 상태 디렉터리로 재기동해 ③ 탈출구를 누르고 화면이 **서버의 현재 사실**을 그리는지 재고 ④ **새 태스크를 제출**해 스냅샷을 다시 낡게 만든 뒤 크래시·재기동을 반복한다. **결과는 "예"** 다: 연결 라벨 이력 `["연결됨","재연결 중","연결 오류"]` → 탈출구 → `["연결 오류","연결됨"]`, 행은 **"실행 중단(소유 프로세스 종료) — 재개 가능"**(서버와 일치)이고 2회차도 같다. 세션은 살아 있었고(재기동 뒤 같은 토큰 **200** — 질문이 "로그아웃됐는가"로 바뀌지 않는다) 서버가 없는 동안에도 탈출구는 사라지지 않았다. **대조군이 결론을 정한다**: 같은 증인을 **F-39 고침 이전 트리**에서 돌려도 **exit 0** — 이 축은 attempt-030 **이전에도 참**이었고, 즉 **결함이 아니라 재지 않은 경로**였다(수동 경로는 `retry` 가 올리는 `reloadVersion` 이 **목록 이펙트의 의존성**이기 때문에 처음부터 동작했다. attempt-030 이 닫은 결함은 **자동** 재연결 경로에만 있었다). **이빨**: 스크래치 트리에서 `retry` 를 무력화하고 **그 트리의 번들까지 재빌드**해 돌리면 증인 **exit 1(위반 4건)** · 계약 **1 failed / 3 passed**. required gate **21/21**(후보 `2b4a198b` · 지문 `7461ae3d…` · `tree_moved` 0건 · 드리프트 0 · python-tests **6360 passed / 13 skipped** · dashboard-test **871 passed(85 files)**) + 마감 검사 PASS · **재선언 없음**. **제품 런타임 코드 변경 0줄** — 대신 그 **암묵적 의존**에 계약이 소유자가 됐다(계약 3 → 4). **재지 않은 것**: 다른 주인이 만든 변화(자극이 아니다) · 모델 실행(EX-01) · 다중 호스트 · **실 브라우저 증인 셋은 어느 required 게이트도 돌리지 않는다**(경계 문서 §2-6/§2-7).
>
> **이전 판정(2026-09-14, attempt-030): GA 출시 판정 NO-GO — attempt-030 은 **F-39 · F-40** 을 닫았다: **크래시 뒤 열려 있는 화면도 새 사실을 배워야 한다.** attempt-028(서버가 죽은 주인을 말한다)·attempt-029(화면의 쓰기 경로)는 둘 다 **새로 연 화면**을 덮었고, "**이미 열려 있는** 화면"은 attempt-028 의 기술 잔여 ③이자 attempt-029 의 한계 — **두 번 연속 재지 않고 남긴** 질문이었다. 실 서버 + 실제 PIN 로그인 + 제품의 버튼 + **그룹째 SIGKILL** + 같은 포트·같은 상태 디렉터리로 재기동: 고침 전 화면의 연결 라벨은 `["연결됨"]` 이었다 — **연결을 잃은 적이 없다고 말하면서**(스트림이 조용히 다시 붙었다) 서버가 `execution_owner: dead`·`resumable: true` 라고 답하는데도 크래시 전 스냅샷(`running` · 재개 **없음** · 취소만)을 그렸고, 세션은 살아 있었다(**위반 1건 → 고침 후 OK**: 이력 `["재연결 중","연결됨"]`, 라벨 "실행 중단(소유 프로세스 종료) — 재개 가능"). F-36 이 **서버 표면**에서 없앤 막다른 길이 **열려 있는 화면**에는 그대로 있었다. 고침은 **화면 코드 하나**다 — 재연결 **성공 지점**이 목록을 다시 읽고, 그 재조회는 `reloadVersion` 이 **아니다**(그것은 스트림 이펙트까지 재시작시켜 **재시작 루프**가 된다) · 실패는 삼키지 않는다. **서버는 한 줄도 바뀌지 않았다.** **F-40 은 측정 도구의 결함**이다 — `uv run … uvicorn` 의 실제 서버는 런처의 **자식**이라 런처만 신호하면 **살아남아 포트를 붙들고 있었고**(크래시가 크래시가 아니었다), 재기동이 **토큰 비밀을 새로 만들면** 질문이 "사용자가 로그아웃됐는가"로 바뀐다(두 성질 모두 그 하네스의 docstring 이 처음부터 약속했다) — 이제 **그룹째 신호**·**비밀 재사용**. required gate **21/21**(후보 `e02447fb` · 지문 `87c5091b…` · `tree_moved` 0건 · 드리프트 0 · python-tests **6360 passed / 13 skipped** · dashboard-test **870 passed(85 files)**) + 마감 검사 PASS · **재선언 없음**. **제품 런타임 코드 변경 있음**(화면의 **읽기 시점** — 서버·권한 경계·소유·복구 규칙은 불변). **재지 않은 것**: M3(수동 탈출구) 경로가 발화하지 않았다 · 모델 실행(EX-01) · 다중 호스트 · **게이트는 크래시·재연결 슬라이스를 재지 않는다**(경계 문서 §2-6).
>
> **이전 판정(2026-09-14, attempt-029): GA 출시 판정 NO-GO — attempt-029 는 **F-37·F-38** 을 닫았다: **화면의 쓰기 경로는 서버가 받아들이는 것이어야 한다.** attempt-028 이 기술 잔여로 남긴 "실 브라우저 눈금" 슬라이스를 밟는 **첫 걸음**에서, 제품의 유일한 쓰기 경로("작업 제출")가 **어떤 기계 상태에서도** 성공하지 못한다는 사실이 나왔다: ① 화면은 정체성을 **최상위** `project_id` 로 보내는데(대화·파일 경로가 쓰는 형태이고 공유 리졸버가 **이미** 지원한다) `TaskSubmitRequest`(`extra="forbid"`)가 그 본문을 **422** 로 막았고 ② 서버가 한 번도 열리지 않은 프로젝트를 `last_accessed_at: null` 로 직렬화하는데 화면 스키마가 `null` 을 거부해 **목록 파싱이 실패**하고 화면이 **자기 프로젝트를 얻지 못한 채** 정체성 없이 제출했다(**400**). 뿌리는 같다 — **화면과 서버가 만나는 와이어를 재는 자리가 없었다**. 고침은 각각 **표현할 수 없는 쪽**을 고친다(서버가 두 형태를 **선언**하고 · 화면이 `.nullish()` 로 서버 타입을 그대로 표현한다) — **권한 경계는 그대로다**(모르는 필드 422 · 무정체성 400 · 유령 프로젝트 404). required gate **21/21**(후보 `1890d2b0` · 지문 `57f38a23…` · `tree_moved` 0건 · python-tests **6360 passed / 13 skipped** · dashboard-test **867 passed(84 files)**) + 마감 검사 PASS. **제품 런타임 코드 변경 있음**(쓰기 경로·화면 스키마).
>
> **이전 판정(2026-09-14, attempt-028): GA 출시 판정 NO-GO — attempt-028 은 **F-36** 을 닫았다: **재시작한 서버는 주인에 대해 아는 것을 말한다.** attempt-027 이 문서에 한계로 남긴 절반("실 서버를 띄운 재시작 슬라이스는 재지 않았다")을 그대로 밟았다: `uvicorn` + **실 인증**(PIN→bearer) + **SIGKILL** + **같은 DB** 재기동. 죽은 소유자의 `running` 행은 표면에서 살아 있는 실행과 구별되지 않았고(주인에 대한 필드가 없다), 정작 같은 행에 `POST /resume` 은 **200** 을 돌려주었으며, 화면은 그 침묵을 "실행 중"으로 읽어 복구 가능한 태스크에 **재개가 아니라 취소만** 제안했다(막다른 길). 고침은 **정책이 아니라 표면**이다(재시작이 고아 행을 자동으로 끝내면 **재개 가능성이 사라진다**): `execution_owner`(`live`/`dead`/`none`) · `resumable` 이 두 표면에서 나오고(둘 다 저장하지 않는 파생 값), 값은 `can_*` 와 **같은 liveness 함수**에서 만들어지며, 화면은 그 필드로 버튼을 그린다. required gate **21/21**(후보 `9fb7f068` · 지문 `f838f2ea…` · `tree_moved` 0건 · python-tests **6354 passed / 13 skipped** · dashboard-test **865 passed(84 files)**) + 마감 검사 PASS. **제품 런타임 코드 변경 있음**(읽기 표면의 관측성 — 저장 정책·resume 규칙은 불변).
>
> **직전 판정(2026-09-14, attempt-027): GA 출시 판정 NO-GO — attempt-027 은 **F-35** 를 닫았다: **취소도 소유 규칙을 지킨다.** attempt-026 이 "기술 축은 제품 결함도 검증 장치 결함도 0건"으로 닫힌 뒤, 문서의 §6 이 남긴 `0-d`(**C14-03 을 취소·중단 경로까지 실행**)를 밟다가 나왔다. 첫 질문: **`resume` 은 소유자를 보는데 `cancel` 은 보는가.** 답은 **아니오** — `BackgroundTaskRunner.cancel_task` 는 메모리에 태스크가 없으면 DB 의 `status ∈ {pending, running}` 만 보고 `cancelled` 로 적었다. 실물 프로세스 둘(소유자 자식 + 같은 DB 를 여는 두 번째 러너)로 재니 **세 가지가 동시에 거짓**이 됐다: ① 취소가 성공으로 보고됨(`cancel_task=True`) ② "멈췄다"는 함의 — 취소 신호(`cancel_event`)는 소유자 프로세스 **안**에 있어 다른 프로세스에서 닿지 않는다(효과 5 → 10줄) ③ 그 행이 "일어난 일의 이력"이라는 주장 — 소유자가 **10단계를 끝까지 수행했는데** 최종 행은 `cancelled` + "… or it was lost in memory" 였다(마지막 쓰기가 CAS 에 밀렸다). 고침은 규칙을 **복제하지 않고 공유**한다: `can_cancel(raw_status, owner_pid)` 가 `resume` 과 **같은** `_process_is_alive` 를 쓰고(`pending`/`paused` 는 허용 — 그 취소는 소유자의 시작 CAS 를 실패시켜 **진짜로 실행을 막는다**), `TaskStateStore.cancel_if_permitted` 가 읽은 `status`·`owner_pid`·`version` 을 조건에 넣은 CAS 로만 적으며(거부는 행을 **건드리지 않는다**), 거부 사유가 `owned_elsewhere` 로 **이름 붙어** API **409**(활성 아님은 404 — 두 사건이 다르다)로 나가고 화면이 서버의 `detail` 을 메시지로 올린다. required gate 21/21(커밋된 후보 `64590235` · 단일 지문 `98fd6695…` · 되돌리기 0회 · **`tree_moved` 0건** · python-tests **6342 passed / 13 skipped / 16 deselected** · dashboard-test **859 passed(83 files)** · 드리프트 0) + 마감 검사 PASS · 증인 **고침 전 exit 1(위반 3건) / 고침 후 exit 0**(**같은 증인 파일**을 소스 트리만 바꿔 돌린다 — 취소 거부 · 행은 `running` 유지 · 소유자 pid 보존 · 소유자가 완주한 뒤 최종 이력 `done`). **재선언 한 번**(첫 선언 `e12ec3cb` 의 fast 배치가 17/18 — `security-bandit` B608, 표기 수정이 코드를 옮겨 **측정 전에** 재선언) · **제품 런타임 코드 변경 있음**(취소 경로의 정직성) · 스킵 13 → 13 · **판정을 움직이지 않는다**. ⚠️ **남은 절반**: 실 서버를 띄운 재시작 슬라이스(SIGKILL → 재기동)는 아직이다.
>
> **직전 판정(2026-09-13, attempt-026): GA 출시 판정 NO-GO — attempt-026 은 **F-34** 를 닫았다: **게이트는 자기가 재는 코드를 바꾸지 않는다.** 뿌리는 attempt-025 가 **실제로 멈춘** 자리다 — 그 attempt 는 대시보드 소스를 고치고 번들을 안 만든 채 후보를 커밋했고, 그 사실을 알려 준 것은 게이트가 아니라 **다음 배치의 이어받기 거부**("previous report was produced from a different working tree")였다. 즉 **그 거부가 유일한 탐지기**였다. 두 결함이 겹쳐 있었다: ① **낡은 출하물을 재는 자리가 없다** — `src/antigravity_k/dashboard_dist/` 는 추적되는 빌드 산출물이고(F-01) 서버가 그것을 서빙하는데, 소스만 고치고 번들을 안 만들면 화면에는 **고치기 전의 UI** 가 나가고 번들을 지칭하는 pytest 계약 6파일은 **전부 통과**한다(실측 68 passed). ② **게이트가 코드를 바꿔도 아무도 실패하지 않는다** — `git.tree_fingerprint` 하나로 "21개 초록이 한 코드 상태의 것"이라 주장하는데 지문은 게이트 **앞에서** 한 번 재고 끝났고, 실측으로 게이트 명령이 추적 번들 **45개**를 다시 쓰면서 **exit 0** 이었다. 고침: 지문을 만들던 **한 곳**(`ga_gate.tree_digests`)이 경로별 내용 지도를 돌려주게 하고, 러너가 게이트 **직전·직후**의 지도를 비교해 차이가 있으면 그 게이트를 `tree_moved` 로 적고(경로·이유를 달고 **명령의 `exit_code` 는 그대로 남긴다** — 명령은 성공했고 실패한 것은 계약이다) 실행 전체를 **exit 1** 로 끝낸다 — **required 여부로 거르지 않으므로** non-required 게이트로 같은 결함이 조용해질 수 없다. 소비자 둘도 맞췄다: 승인 검증기는 이 상태를 **구조 오류로 적지 않되** 승인하지 않고, 마감 검사 **항목 9** 는 **어느 게이트가 어느 파일을 바꿨는지 이름으로 대며** 거부한다. required gate 21/21(커밋된 후보 `d62ba10a` · 단일 지문 `994b21fd…` · 되돌리기 0회 · **`tree_moved` 0건** · python-tests **6329 passed / 13 skipped** · dashboard-test **855 passed(82 files)** · 드리프트 0) + 마감 검사 PASS · 증인 **고침 전 exit 1 / 고침 후 exit 0**(같은 증인 파일을 `--tree-at` 만 바꿔 돌린다 — 낡은 번들은 러너가 거부하고, 소스에서 다시 만든 번들에서는 조용하다). **제품 런타임 코드 변경 0줄** · 검증의 강도 불변(게이트 목록·명령·required 여부 동일).
>
> **직전 판정(2026-09-13, attempt-025): GA 출시 판정 NO-GO — attempt-025 는 **F-33** 을 닫았다: attempt-023/024 가 승인 경로로 '항상 허용' 상태를 **만들고도 재지 않고 남긴** 질문("그 부여가 **무엇을 덮고 언제 사라지는가**")에 실물 코드로 답했다 — 부여는 **도구 하나 전체**를 덮고(인자·경로·프로젝트 무관), **만료 시각이 없으며**(365일 뒤에도 살아 있고 사라지는 자동 경로는 프로세스 재시작뿐), 싱글턴이라 **프로세스 폭**이다(다른 세션·다른 프로젝트가 같은 부여를 본다 — 프로세스가 새로 뜨면 0이므로 세션 간 유출은 아니다). **셋 다 설계**이고 결함은 그 사실들이 **감사 불가능**했다는 것이다: 부여 저장소가 `set[str]` 이라 시각·근거가 사라졌고, 부여를 **읽는** 표면이 없었고(해제만 있었다), **동의 없이 실행된 횟수를 아무도 세지 않았고**, 그 읽기 표면을 만들자 `GET /{request_id}` 가 `always-allowed` 를 요청 ID 로 삼켜 **404** 를 냈으며(경로 순서 — 고침을 넣고 **계약을 돌려서 발견**했다), 동의 문구가 **이 요청**을 덮는 것처럼 읽혔다. 다섯 자리를 고치고 **요구는 그대로 둔 채 확인을 의도에 맞췄다** — 해제는 이제 **무엇을 되돌렸는지 이름을 댄다**(`revoked`): 조용한 해제는 검증할 수 없다. **attempt-002 이후 처음으로 제품 런타임 코드가 바뀐 attempt** 이고, 바뀌지 않은 것은 **부여의 범위·수명**이다. required gate 21/21(커밋된 후보 `a2f6f724` · 단일 지문 `57e32c9a…` · 되돌리기 0회 · python-tests **6320 passed / 13 skipped** · dashboard-test **855 passed(82 files)** · **드리프트 0**) + 마감 검사 PASS · 증인 **고침 전 exit 1(깨진 요구 6건) / 고침 후 exit 0(5/5)**. 남은 차단 사유는 **사람·조직 축뿐**이다(EX-01~06 · C14-08 · C14-03/04/05).
>
> **직전 판정(2026-09-13, attempt-024): GA 출시 판정 NO-GO — attempt-024 는 attempt-021 이 스스로 한계로 적어 둔 **R-16** 을 닫아, 등록부가 스킵을 소유하는 단위를 게이트 `python-tests` **하나**에서 **required 게이트 21개 전수**로 넓혔다. 같은 후보가 21개 게이트로 초록을 만드는데 **그중 다섯이 테스트를 돈다**(`python-tests` · `python-benchmark` · `api-e2e` · `dashboard-test` · `accessibility-e2e`) — 나머지 넷의 스킵은 아무도 세지 않았고, 한 게이트가 테스트를 조용히 빼도 초록은 그대로였다. 넓히기 **전에 먼저 셈**했고(러너별 스킵 표기를 스크래치 프로브로 실측), 그 셈이 세 자리를 가리켰다: ① `api-e2e` 는 `-q` 단독이라 스킵이 생겨도 **이름이 없다** → `-rs` ② `dashboard-test` 는 vitest **기본 리포터가 건수만** 낸다 → `--reporter=verbose` ③ `clean-machine-runtime` 의 `--skip-e2e`·`--skip-wheel` 채널이 어디에도 적혀 있지 않았다(켜지면 `SKIP` 행이 생겨도 **게이트는 exit 0**) → 등록부 `skip_channels` + 계약이 **스크립트 표기 ⊆ 선언**을 잰다. `accessibility-e2e` 는 이미 귀속됐다(playwright `list`) — 고치지 않고 계약으로 고정했다. 소유는 **전수성 + 귀속 + 실제 실행** 세 겹이고, 마지막은 **마감 검사 조항 8** 이 편입된 보고서에서 게이트별 스킵 건수를 읽어 소유자 없는 스킵을 거부한다. **스킵 13 → 13 · 제품 런타임 코드 변경 0줄** · required gate 21/21(커밋된 후보 `e2885734` · 단일 지문 `7ae9af28…` · 되돌리기 0회 · python-tests **6302 passed / 13 skipped**) + 마감 검사 PASS · 증인 **고침 전 exit 1 / 고침 후 exit 0(5/5)**. 남은 차단 사유는 **사람·조직 축뿐**이다(EX-01~06 · C14-08 · C14-03/04/05).
>
> **직전 판정(2026-09-13, attempt-023): GA 출시 판정 NO-GO — attempt-023 은 등록부(`scripts/gate_skip_register.json`)의 **마지막 미검증 능력** `orchestrator-refactor-rewrite` 를 닫아 **소유자 없는 스킬 0건 · 미검증 능력 0건**을 만들었고, 그 과정에서 그 항목의 정체가 드러났다 — 두 테스트(`에이전트가 프로그램을 만들고 실행하는가` · `코드 전용 답변에서 품질 재시도가 도는가`)는 **제품 결함이 아니라 계약 드리프트**로 죽어 있었다(F-32). 조건 없는 `@pytest.mark.skip` 은 "고칠 것이 남았다"는 뜻이지만 **"제품에 결함이 있다"는 뜻은 아니다**: 관측해 보니 두 루프는 **돌고 있었고**(실패 스택이 제품 코드 안에서 난다: `tool_loop.run_loop` 의 `manager.router.get_combo(...)` · `self_capability._model_info` 의 무인자 호출), 막은 것은 ① 더블이 리팩토링 **이전** 인터페이스를 흥내낸 것(`manager.router` 부재 · `get_model_info(name)` 의 오류 — 실제는 `status()` 별칭·**무인자**) ② 테스트 **이후에** 생긴 **승인 게이트**(CR-04/CR-05) ③ 같은 경계의 **셀 경로 거부**(`sys.executable` 이 루트 밖) ④ `calls == 2` 가 **환경 의존**(패키지 기본 config 의 재시도 예산). 고침은 다섯 자리를 계약에 맞추되 **게이트를 하나도 약화하지 않았다** — 동의는 **제품의 승인 경로**(`get_approval_manager()` + `ALWAYS_ALLOW` = 대시보드 '항상 허용')로 만들고, 경계는 그대로 두고 명령을 루트 기준 상대 경로로 바꾸고, 재시도 예산을 1로 **고정**했다. 두 테스트는 조건 없이 돌며 **6 passed / 0 skipped**, 등록부는 두 파일을 `closed` 로 옮기며 **`observed_files` 에 남겼다**(돌아오면 대조가 즉시 실패 — F-31a 성질을 **처음 실제로 쓰는** attempt). **python-tests skipped 15 → 13**(passed 6289 → **6291**) · required gate 21/21(커밋된 후보 `ed9e225a` · 단일 지문 `37b76cb8…` · 되돌리기 0회) + 마감 검사 PASS · **제품 런타임 코드 변경 0줄**. **증인** `f32_contract_drift_witness.py` **9/9**(고침 전 **기준 커밋의 실제 코드**가 실패한다 · 고침 후 6 passed · 닫힌 파일에 스킵을 십으면 대조 실패). 남은 차단 사유는 **사람·조직 축뿐**이다(EX-01~06 · C14-08 · C14-03/04/05).
>
> **직전 판정(2026-09-13, attempt-022): GA 출시 판정 NO-GO — attempt-022 는 등록부의 미검증 능력 `config-models-unregistered` 를 **삭제가 아니라 능력 복원으로** 닫았고, 그 과정에서 그 항목의 한 축이 **테스트만의 약속이 아니라 배포 경로**임을 찾아 **F-31** 을 함께 닫았다: `/benchmark run`(인자 없음)의 기본 타겟이 config 가 소유하지 않는 콤보(`collective-council`)를 가리켜 **매 실행마다 오류 행(점수 0)** 을 기록했고, 유일한 회귀 테스트가 `registry._raw` 에 합성 매핑을 주입해 실제 config 를 보지 않았다 — 그 방식이 오래 숨긴 이유다. `collective-council` 을 `strategy: collective` 콤보로, gemma-4-31B 를 reasoning 로스터로 복원하고(둘 다 2026-05 세대 정리가 **의도 기록 없이** 지운 항목이다), 새 계약이 **실제 파일**로 그 일치를 잰다(이빨 2건). 곁들여 **F-31a**(등록부의 관측 목록이 선언에서 파생돼 **닫는 일이 관측을 줄였다**)를 닫았다. **python-tests skipped 17 → 15** · required gate 21/21(커밋된 후보 `d7e66a59` · 단일 지문 `6a51100f…` · 되돌리기 0회) + 마감 검사 PASS · **제품 런타임 코드 변경 0줄**.
>
> **직전 판정(2026-09-13, attempt-021): GA 출시 판정 NO-GO — attempt-021 은 **R-8 감사**(스킵 전수 조사)를 수행하고 그 과정에서 **F-30** 을 닫았다(제품 런타임 변경 0건). attempt-013 이 스스로 "이 감사를 하지 않았다"고 적어 둔 자리다. 게이트 환경을 lock 에 고정한 F-18 은 **도구 출처**를 바로잡았지만 **그 대가를 아무도 세지 않았다**: ambient 실행(attempt-011/012)의 스킵은 **13·6건**이었고 고정 뒤(attempt-013)에는 **40건**이다. 그 40건을 사유별로 전수해 보니 **어떤 파이프라인도 `documents` extra(pypdf)를 설치하지 않았다**(CI 매트릭스는 `base`/`rag`/`mlx`, 주간 job 은 `mlx`/`unsloth`) — 그래서 **출하 능력인 PDF/DOCX 수집을 재는 23건이 게이트·CI·주간 어디서도 돌지 않았다**(게이트는 초록이었다). ① 그 extra 를 `python_backend` 게이트 6종의 환경에 넣어 **복원**했다(그 3파일 실측 **87 passed / 0 skipped** — 실패가 아니라 검증이었고, `pypdf 6.17.0` 은 이미 `uv.lock` 에 있었다). ② 남은 **17건**을 `scripts/gate_skip_register.json` 이 **소유**한다: `ENV_PLATFORM`(mlx 4 · unsloth 7 — 계약이 owner 워크플로 안에서 그 파일 이름을 찾아 **"다른 job 이 돌린다"를 검증**한다) · `ENV_CONFIG`(access-pin 2 — 같은 경계를 `tests/test_cr04_shell_api_boundary.py` 가 게이트 안에서 PIN 을 세우고 401 을 재는 것으로 덮는다) · **`KNOWN_GAP`(4건: 에이전트 실행 루프 2 · 제품 설정 약속 2 — 어디서도 돌지 않는 제품 능력으로 owner·plan·만료일 보유)**. ③ `tests/test_cr14_gate_skip_register.py` 가 등록부와 **실제로 돌린 게이트 환경**을 한 건씩 대조한다 — 등록되지 않은 스킵도(커버리지가 조용히 줄었다) 낡은 등록부도(스킵이 사라졌다) 실패다. ④ `docs/ga/CR14_GATE_COVERAGE_BOUNDARY.md` 가 `21/21` 이 **재지 않는 것**을 적는다. **required gate 21/21 을 커밋된 후보 `1b0a024c` 에서 되돌리기 0회·단일 지문 `15e79e84…` 에서 완주**(python-tests **6280 passed / 17 skipped / 16 deselected** 538.61s · dashboard-test 81 files · docker 237.44s · clean-machine 42.11s · master-e2e 6/6 · api-e2e 9 · accessibility 35 · 드리프트 0 · 실행 후 지문 재측정 동일) + 보고서 편입 뒤 **마감 검사 PASS**(편입 전 FAIL exit 1). **가장 중요한 수치: skipped 40 → 17** — 같은 21/21 이지만 덮는 범위가 넓어졌다. 증인 `attempt-021/repro/f30_skip_register_witness.py` **12/12**(이빨 7 — 그중 ⑦이 `--extra documents` 를 빼고 **실제로 돌려** 23건이 되돌아오는 것을 확인). **증인이 계약을 고친 사례**: 이빨 ⑥ 이 처음 아무것도 물지 못했는데 원인이 **계약이 *측정*이 아니라 *주장*(등록부)을 읽고 있었던 것**이었다(F-29 와 같은 병) — 조항을 자기모순 검사로 좁혔다. **한계**: R-8 닫힘 · **R-16(신규)** 등록부는 `python-tests` 의 환경만 소유한다(`python-benchmark`·`api-e2e`·CI 매트릭스의 스킵은 안 셈) · R-11 닫힘 · R-13 · R-14 · R-15 · R-2/R-3/R-4/R-6/R-7 · **미검증 능력 4건**은 이름을 갖고 남았다(만료 2026-10-15). **직전 판정(2026-09-13, attempt-020): GA 출시 판정 NO-GO — attempt-020 은 **CR-12 소관 재확인(R-5)** 을 수행하고 그 과정에서 **F-29** 를 닫았다(제품 런타임 변경 0건). 판정서 §6 의 `0-h` 는 attempt-014(F-22)가 CR-12 계약을 개정한 뒤 그 개정을 **CR-12 소관으로 다시 재는** 항목이었다 — 재확인은 문장을 다시 읽는 일이 아니라 **요구를 다시 재는** 일이다. 두 자리에서 확인이 의도와 달랐다: ① 값 소유자 포인터를 **토큰**(`README_VALUE_OWNER in text`)으로 보아 "README 가 값을 **가리킨다**"는 요구를 "그 **이름**이 어딘가 있다"로 확인했다 — 산문에 이름만 적거나, 링크를 **다른 문서**로 바꾸거나, 소유자 이름을 링크하면서 **그 파일이 없어도** 통과했다(F-28 과 같은 병: 의도가 아니라 표기). 이제 **실재하는 링크**를 요구한다. ② `"미커밋" in checklist` 는 후보를 커밋한(attempt-009) 뒤로 **과거 attempt 기록 행**이 그 문자열을 계속 공급해 검사가 무의미해졌고 실패 메시지는 거짓을 말했다(테스트는 현재를 묻는데 답은 과거에서 왔다) — 요구를 **현재 상태 줄**로 좁혔다(커밋된 후보·GA 승인 없음 · 그 줄이 미커밋을 주장하면 실패 · 과거 행의 기록은 그대로). **두 요구는 한 글자도 바뀌지 않았고** 바뀐 것은 확인뿐이다 — 계약 26 → **28건**. 증인 `CR-12/attempt-002/repro/cr12_r5_review_witness.py` **12/12** 는 규칙을 **흉내내지 않고** 개정 **전** 규칙의 **실제 코드**(`git show 3fb3fcb9:tests/test_cr12_docs_alignment.py`)를 git 에서 읽어 같은 입력에 물린다: 실물 README·체크리스트는 개정 전·후 **둘 다** 통과(개정이 실물을 깨지 않았고 요구를 조인 것도 아니다) · 품질이 낮은 입력 3종은 **전자만** 통과(구멍의 실증) · 과거 기록의 "미커밋" 은 통과하되 현재 줄이 주장하면 거부한다. **required gate 21/21 을 커밋된 후보 `a5907865` 에서 되돌리기 0회·단일 지문 `aad2601c…` 에서 완주**(python-tests **6251 passed / 40 skipped / 16 deselected** 522.15s · python-benchmark 16 · dashboard-test **849 passed(81 files)** · docker-build 35.45s · clean-machine 42.16s(`git archive HEAD` 로 커밋된 트리 검증) · master-e2e 6/6 · api-e2e 9 · accessibility 34 · `data/`·`dashboard_dist` 드리프트 **0** · 실행 후 지문 재측정 동일) + 보고서 편입 뒤 **마감 검사 PASS(exit 0)**(편입 전에는 같은 검사가 `FAIL exit 1`) — 세 배치가 **별개 프로세스**로 **스스로** 이어받았다(18 → 19 → 21). **한계**: **R-5 는 닫혔다** · R-11(닫힘 — 이번 측정도 파이프라인이 부르는 같은 명령을 돌렸지만 시작은 사람이 했다) · R-13 · **R-14**(러너에서의 실행은 러너만이 답한다) · **R-15**(태그 직전 버전 상향 시 재선언 필요) · R-2·R-3·R-4·R-6·R-7. **일반 교훈: 개정한 계약은 다시 재야 한다** — 요구를 옮긴 사람의 문장은 증거가 아니다. **직전 판정(2026-09-13, attempt-019): GA 출시 판정 NO-GO — attempt-019 는 **R-11** 을 닫았다: 마감을 **사람이 시작하지 않아도 되게** 만들었다(제품 런타임 변경 0건). `.github/workflows/ga-close.yml` 이 마감 절차(`scripts/run_attempt_close.py --stage all`)를 부르고 매주 월요일 **스스로 돌며**, `.github/workflows/release.yml` 의 `publish-pypi`·`github-release` 가 `needs: [build, ga-close]` 로 **막힌다** — 기계가 재측정하지 않은 주장은 출하되지 않는다. 릴리스는 `uses:` 로 **부르기만** 하고, **게이트 목록은 워크플로에 0건**이다(매니페스트·절차 스크립트가 소유). 배선은 새 계약 `tests/test_cr14_close_pipeline_contract.py` 22건이 소유하고, 증인이 실제 워크플로 파일로 **배선을 풀어 보며** 22/22 를 확인한다(`attempt-019/repro/f28_close_pipeline_witness.py`). 도중에 **F-28** 을 만나 함께 닫았다: R-11 배선이 `release.yml` 의 `needs` 를 늘리자 `tests/test_rel01_clean_build_sbom.py` 의 AC-4 가 먼저 깨졌는데, 계약의 **의도**("publish 는 build 가 성숙해야 시작한다")는 지켜졌고 확인이 **문자열** `"needs: build"` 였기 때문이다 — 요구는 그대로 두고 `needs` 목록 **파싱**으로 옮겼다(이빨 유지). 그 수정이 지문을 옮겨 앞선 선언이 낡았고 attempt-019 **안에서 재선언**했으며, 그 순간 F-27 의 거부가 실제 흐름에서 작동했다(낡은 부분 보고서 → exit 2 · 미덮어쓰기 · `rm` 안내). **required gate 21/21 을 커밋된 후보 `43cde98e` 에서 되돌리기 0회·단일 지문 `7f19c3a7…` 에서 완주**(python-tests **6249 passed / 40 skipped / 16 deselected** 535.13s · 되돌리기 0회 · 드리프트 0 · 실행 후 지문 동일) + 보고서 편입 뒤 **마감 검사 PASS**. **한계**: **R-14**(배선은 계약이 소유하지만 **이 저장소는 GitHub Actions 를 로컬에서 실행할 수 없다** — 러너의 21/21 은 러너만이 답한다) · **R-15**(태그 직전 버전 상향 커밋이 생기면 재선언 + 재측정 필요) · R-13 · R-2·R-3·R-4·R-6·R-7. **직전 판정(2026-09-13, attempt-018): GA 출시 판정 NO-GO — attempt-018 은 attempt-017 이 등록한 **F-27** 을 닫았다(R-12 폐쇄, **제품 런타임 변경 0건**). 발견: 이어받기 **판단**(`should_merge`: 후보 sha·manifest **두 축**)이 게이트 **규칙**(`_load_carried_gates`: + **작업 트리 지문**, **세 축**)의 **부분 복제**였고, 두 주체가 같은 질문("같은 코드인가")에 다른 답을 내는 조합이 실재했다(증인 `attempt-017/repro/f27_merge_rule_agreement_witness.py` · `logs/f27-witness.txt`) — 작업 트리만 다르면 실행이 **중단**되고, 후보 sha 만 다르면 앞 배치 초록이 **조용히** 버려졌다. 수정: 규칙을 `ga_gate.merge_refusal_reason` **한 곳**으로 모으고(자기 로더도 그 함수를 쓴다 · 지문은 `worktree_fingerprint` 한 곳에서 온다), 절차는 세 축을 넘겨 **묻기만** 하며, **거부는 조용하지 않다**(이유 + exit 2 + 보고서 미덮어쓰기 + `rm <보고서>` 안내). `close` 는 게이트를 돌리지 않으므로 판단을 **묻지 않는다** — 기록 커밋 뒤의 재확인이 살아 있다. 곁들여 카드 부재가 traceback 이던 것을 exit 2 로 맞췄다. **이빨 8건 신규**(12 → 20) 중 핵심은 **위임 증명**이다 — 규칙 소유자의 함수를 패치하면 **절차의 답이 따라 움직여야** 한다(절차 안에 사본이 있으면 깨진다). 증인 `attempt-018/repro/f27_fix_witness.py` **8/8** · 회귀 `attempt-017/repro/f26_merge_identity_witness.py` **5/5**(게이트를 흉내낸 스텁을 버리고 **실물 게이트**로 재작성 — 스텁은 규칙이 바뀌면 존재하지 않는 규칙을 재게 된다). **커밋된 후보(`ecaeeecc`)에서 required gate 21/21 을 되돌리기 없이 단일 지문(`56971ed6…`)에서 완주**했고(python-tests **6227 passed / 40 skipped / 16 deselected** 526.95s · dashboard-test 849(81 files) · docker 33.74s · clean-machine 41.76s(3010 파일, `ref: HEAD`) · 드리프트 0), 세 배치가 **별개 프로세스로 이어받았다**(18 → 19 → 21) · **마감 검사 PASS(exit 0)**. 남은 한계: **R-13(신규)** 기록 커밋 뒤에 게이트 단계를 재개하면 **끊긴다**(의도된 동작) · **R-11** 절차는 사람이 시작해야 한다(CI 연결이 다음) · R-2/R-3/R-4/R-6/R-7. 이전 판정 요지 보존: attempt-017 은 **마감을 명령 하나로** 만들고(F-25 — attempt-016 한계 R-10 폐쇄, **제품 런타임 변경 0건**), 그 절차를 **직접 돌려서** 절차 자신의 결함까지 닫았다(F-26). `scripts/run_attempt_close.py` 가 게이트를 배치로 돌리고(`fast`=required 에서 무거운 셋을 뺀 나머지 · `tests`=python-tests · `heavy`=docker-build·clean-machine-runtime) 보고서를 증거 트리에 **편입**한 뒤에만 마감 검사를 돌린다 — **게이트 목록을 스크립트가 들고 있지 않고 manifest 에서 런타임에 읽는다**. **dogfooding 이 찾은 F-26**: 각 `--stage` 는 별개 프로세스라 "내가 첫 배치인가"를 알 수 없는데, 첫 구현은 그 기억을 전제로 `--merge-into` 를 결정해 `--stage tests` 단독 실행이 fast 18개를 **덮어썼다**(18 → 1, exit 0 — 조용한 손실). 이어받기 판단을 **보고서의 정체성**(같은 후보 sha·같은 manifest sha256)으로 옮겼고, 다른 후보의 보고서는 여전히 거부된다. F-26 수정이 지문을 옮겨 앞선 선언(`8533319b`/`5e7d5c4c…`)은 낡았다 — 측정 **전**이었으므로 재선언했다. **커밋된 후보(`afa4d26f`)에서 required gate 21/21 을 되돌리기 없이 단일 코드 지문(`29fac8a0…`)에서 완주**했고(python-tests **6219 passed / 40 skipped / 16 deselected** 526.15s · dashboard-test 849(81 files) · docker 231.31s · clean-machine 42.64s(3010 파일, `ref: HEAD`) · 드리프트 0), 세 배치가 **별개 프로세스로 이어받았다**(18 → 19 → 21) · 보고서 편입 뒤 **마감 검사가 PASS(exit 0)**, 편입 전에는 같은 검사가 `FAIL exit 1` 이었다. **그 과정에서 F-27 을 찾았고 등록만 했다(OPEN — 다음 후보)**: 이어받기 **판단**(`should_merge`: 후보 sha·manifest)이 게이트 **규칙**(`ga_gate._load_carried_gates`: + **작업 트리 지문**)의 **부분 복제**라서 두 주체가 갈라진다 — 작업 트리만 다르면 절차는 이어받으라 하고 게이트는 거부해 실행이 exit 2 로 끊기고, 후보 sha 만 다르면 절차는 **조용히** 새로 시작해 앞 배치 초록을 버린다(증인 `attempt-017/repro/f27_merge_rule_agreement_witness.py` · `logs/f27-witness.txt`). attempt-013 F-18·attempt-016 F-24 와 같은 병이며, 수정은 새 후보를 요구하므로 attempt-017 의 초록을 낡게 하지 않기 위해 **한 attempt 안에 섞지 않았다**. 이전 판정 요지 보존: attempt-016 은 **선언한 초록의 출처를 게이트 밖에서 확인하는 마감 검사**를 세웠다(F-24 — attempt-015 한계 R-9 폐쇄, **제품 런타임 변경 0건**). 보고서는 게이트 실행이 끝날 때 쓰이므로 그 실행 **안에서는** 존재할 수 없어 게이트에 넣을 수 없었다 — 그래서 attempt 마감 절차로 넣었고, `scripts/verify_attempt_close.py` 가 ① 선언된 지문을 측정한 보고서가 있는가 ② 그 보고서가 이름 붙인 커밋의 트리를 쟀는가 ③ manifest sha256·required **목록**이 같은가 ④ required 전부 passed·exit 0 인가 ⑤ **카드의 게이트 수치가 보고서 집계와 같은가**(손으로 적은 수치 금지) ⑥ 후보..HEAD 코드 스코프 변경이 없는가를 본다. **커밋된 후보(`0c33aa2e`)에서 required gate 21/21 을 되돌리기 없이 단일 코드 지문(`1b84209e…`)에서 완주**했고 **마감 검사가 PASS(exit 0)** 했다. 이전 판정 요지 보존: attempt-015 는 사람이 눈으로 찾던 **울타리 이동을 계약이 찾게** 했다(F-23 — attempt-014 한계 R-1 폐쇄). 새 계약은 **작업 트리를 쓰지 않고 git 객체만으로** 커밋의 코드 지문을 계산해 ① 선언된 지문 == 선언된 후보 커밋의 **트리** 지문 ② 후보..HEAD 사이 **코드 스코프 변경 0건**(위반 경로를 이름으로 댐) ③ 지문 함수가 git 이 보는 파일을 조용히 무시하지 않는다 ④ 보고서가 이름 붙인 커밋의 트리를 측정했다 — 를 검사한다. **커밋된 후보(`b5729b61`)에서 required gate 21/21 을 되돌리기 없이 단일 코드 지문(`b637d8b9…`)에서 완주**했다. 이전 판정 요지 보존: attempt-014 는 attempt-013 의 **기록 커밋이 gate 지문을 옮긴** 사실을 F-22 로 등록해 닫았다(**제품 런타임 변경 0건**). 원인은 `README.md`(지문 **안**)의 휘발성 값이었고, 그 값을 판정서 §5 판정 카드로 모으고 README 는 그 문서를 가리키게 했다 — `C14-F22-1/2/3` 계약(hex 토큰 금지 · `required gate N` 금지 · **기록 커밋은 `docs/` 전용**)과 CR-12 계약 개정("README 가 SHA 리터럴을 담을 것" → "값을 소유한 문서를 가리킬 것"; 그 옛 요구는 **성립 불가능했다** — 최종 커밋의 SHA 는 커밋 전에 알 수 없고, 그 요구를 만족시키려던 시도가 실제로 지문을 옮겼다). **커밋된 후보(`3fb3fcb9`)에서 required gate 21/21 을 되돌리기 없이 단일 코드 지문(`b6494f40…`)에서 완주**했다.
>
> **직전 판정(2026-09-13, attempt-013): GA 출시 판정 NO-GO — attempt-013 에서 attempt-012 가 한계(R-6)로 남긴 관측을 뿌리까지 파서 검증 장치 결함 3건과 테스트 격리 결함 1건을 닫았고, 그 과정에서 **required gate 를 21개로 늘렸다**(`python-benchmark` — 검사를 빼는 대신 wall-clock 검사를 조용한 프로세스로 옮긴 것). 닫은 것은 **F-18**(게이트 도구가 lock 이 아니라 호출 셀의 PATH 에서 왔다 — 같은 lock 으로 돌린 두 실행이 다른 인터프리터·다른 pytest·다른 skip 집합을 냈다) · **F-19**(lock 이 정의하는 환경에서는 chromadb 부재로 스위트가 실패한다) · **F-20**(로그인 보안 상태가 프로세스 전역이라 순서가 결과를 바꿨다 — 레이트리밋과 lockout 이 서로를 가려 왔다) · **F-21**(wall-clock 임계값이 required 게이트 안에서 머심 부하로 끊겼다: 고립 2250~2265ms vs suite 안 6084ms). **커밋된 후보(`0593dd27`)에서 required gate 21/21 을 되돌리기 없이 단일 코드 지문(`2c5a15c8…`)에서 완주**했다. **기술 결함은 0건**이지만, 이번에 밝혀진 것은 **검증 장치가 거짓말하고 있었다**는 사실이다 — attempt-001~012 의 20/20 은 ambient 도구로 측정됐다.
>
> **해석 주의(important)**: 이전 초록들은 "스위트가 통과했다"로는 유효하고 "lock 이 검증됐다"로는 유효하지 않았다. 이번 초록이 더 강한 주장인 이유는 게이트가 자기 환경을 스스로 재기 때문이고, 그 사실이 계약 3종(`tests/test_cr14_gate_env_pinning.py`·`test_cr14_gate_load_isolation.py`·`test_cr14_login_state_isolation.py`)으로 고정됐다.
>
> **직전 판정 기록(attempt-011)**: GA 출시 판정 NO-GO — attempt-011 에서 지문 경계 규칙을 계약으로 옮기고, 그 계약을 추가한 지문에서 required gate 가 실패한 것을 파고들어 제품 결함 F-15(취소가 `completed` 로 기록된다)를 찾아 닫았으며, 동결된 clean HEAD(`d72b1711`)에서 required gate 20/20 을 되돌리기 없이 완주했다.
>
> **직전 판정 기록(attempt-010)**: GA 출시 판정 NO-GO — attempt-010 에서 코드 트리를 동결(`5ccb938e`)하고 그 트리에서 required gate 20/20 을 되돌리기 없이 완주했다. attempt-009 의 20/20 은 기록 커밋(`README.md`·`tests/`)이 **지문을 옮겨** 후보가 아닌 트리를 가리키게 됐고, 그 과정에서 "결과 문서를 쓰는 것만으로는 증거가 낡지 않는다"는 전제의 **경계**가 실측됐다(예외는 `docs/`·`.omo/` 접두사뿐 — README·테스트는 지문 안이다). **기술 축은 모두 닫혔다.** 남은 것은 사람의 영역이다 — EX-01~06(외부 승인), C14-08(독립 검토·출시 책임자), C14-03/04/05. 참고: attempt-008·009의 20/20은 그 시점 실측으로 보존한다.
>
> **이전 판정 기록(attempt-008)**: GA 출시 판정 NO-GO — required gate 20/20 PASS(되돌리기 없이). 블로커는 **사람의 승인·커밋 위생**만 남았다 — attempt-003 추가 실측으로 **F-01(빌드 비결정성 의심)은 기각**됐고(`dashboard-build` 는 바이트 단위 멱등), 대신 **F-07(`clean-machine-runtime` 이 후보가 아니라 커밋된 HEAD 를 검증한다)** 이 등록됐다. attempt-005는 **F-03**(release 파이썬 라이선스가 고지문↔SBOM 으로 갈라지고 미해결 집합이 선언되지 않음)을, attempt-006은 **F-06**(mermaid 경유 `uuid` 하한 — 게이트 임계값 미만이라 초록과 공존했다)을, attempt-007은 **F-09**(dev 도구 체인 취약 — 게이트가 `--prod` 라 미차단)를 닫아 게이트 범위와 dev 감사 모두 0건이 됐다. **attempt-008은 F-10(stryker 변이 도구가 pnpm 레이아웃에서 죽는다)과 F-11(그 도구가 선언한 2개 파일 중 1개만 측정했다)을 닫고, 같은 수정이 열어 준 소비자 경로로 F-09 의 `qs` override 를 처음으로 실행 검증**했다(`6.15.1` 에서 실제 크래시 → `6.16.0` 정상). 남은 기술 축은 **F-07 하나**다: "감사 통과"와 "위험 0"은 다르고, "도구 초록"과 "범위 전체 측정"도 다르다. 아래 문단은 그 이전(2026-08-17 기준) 결론이다. 최신 근거는 [2026-09-12 CR-14 attempt-003 절](#2026-09-12-cr-14-attempt-003--f-02-폐쇄-검증-실행이-저장소-추적-파일을-다시-쓰지-않는다-판정-no-go-유지)과 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md)을 보라.

현재 Ssak-Ai는 **로컬 중심 에이전트 기능 검증/베타 준비 단계**다. qwen3.6 local-first, tool permission, CoV, QualityGate 수정 재생성, RAG provenance, durable task state, web result quality contract, chat/task/slash/CLI/MAX/multiplexer의 AgentRuntime 연결, memory compliance contract는 실제 코드와 테스트로 확인됐다. 최신 simple 2-case × 2 repeats와 frontier 5-case × 2 repeats 모두 `excellent` 안정성을 확인했고 전체 basedpyright hard gate도 `0 errors`로 통과했지만, live 검색 recall/근거 정확도와 운영 rehearsal이 남아 있어 첨부 요구사항의 “상용서비스 수준” 최종 조건은 아직 충족되지 않았다.

## 요구조건별 판정

| 조건 | 판정 | 근거/부족한 증거 |
|---|---|---|
| 표준 설치·빌드·실행 | [~] | wheel/sdist build와 서버 smoke는 통과했지만 uv/lock과 clean machine 재현 추가 필요 |
| 핵심 검색 자동화 | [~] | adapter/quality contract와 graded 2-case/확장 6-case fixture가 통과했고 precision은 개선됐지만 provider 장애와 live recall/case coverage가 부족 |
| 치명적 보안 취약점 없음 | [~] | permission/URL guard와 41개 guarded egress inventory, robots/crawl-delay, legal terms audit/enforce policy가 존재하지만 배포별 attestation/policy file과 DNS/secret/dep audit rehearsal 필요 |
| 검증 가능한 출처 | [x] | source id/citation/provenance 구조 |
| 답변-근거 연결 | [~] | COV_VERIFY가 검색 context의 untrusted evidence를 복원해 unsupported/unknown/conflict citation과 검증기 예외를 fail-closed로 처리한다. controlled 및 cache-allowed 실제 DuckDuckGo evidence grounding은 통과했지만 forced-refresh provider 안정성·최신성·다국어 sample은 부족 |
| 중복/스팸 제거 | [~] | canonical dedupe/domain diversity, spam classifier 미완료 |
| 최신성 반영 | [~] | category TTL, publish/update freshness 미완료 |
| 외부 API 부분 장애 격리 | [x] | multi-provider fallback과 empty result contract |
| 검색 품질 목표 충족 | [~] | configured self-hosted authority-rescue plus Qwen source-hint run은 `error_count=0`, 6-case P@3 0.389/Recall@3 0.667/MRR 0.917/nDCG@3 0.741로 개선됐지만 provider availability와 load P95 1805.8ms는 여전히 미달 |
| 운영 로그/알림/롤백 | [~] | audit/checkpoint/Vault와 task 실패·취소 snapshot rollback, provider cooldown/load benchmark, stale-cache marker는 구현됐고 alert/restore rehearsal 부족 |
| 최신 문서 | [x] | 01~10 문서와 project diagnostic report 추가 |
| 위험 투명성 | [x] | 본 보고서와 security review에 미해결 항목 기록 |

## 출시 차단 항목

1. 배포별 이용약관/법적 attestation policy file을 채우고 `enforce` 모드로 전환한 증거와 dependency/secret audit 실행 증거
2. live provider 검색 recall 개선과 확장 human-labeled golden set의 healthy-provider 실행. 현재 configured self-hosted baseline은 availability만 통과하고 6-case relevance와 P95 tail은 미달
3. 실제 provider evidence를 넣은 live Qwen claim-level benchmark의 forced-refresh availability, 반복 분산, 최신성, 다국어 conflict presentation
4. shell tool, Git, PageScraper-backed web fetch, external-brain API와 `/api/agent/tools/shell/run`은 canonical permission 경계로 통합됨. shell은 project cwd/timeout/output quota와 fail-closed SandboxRunner를 사용하고 task rollback도 연결됐으며 41개 HTTP egress call site가 공통 runtime policy로 guarded됨
5. memory scope/delete/redaction 계약: provider/durable export-redact-retention과 Vault raw-asset exclusion/redacted opt-in은 완료됐고, 원문 asset 삭제/변경 consent flow가 남음
6. 전체 basedpyright hard gate는 `src` `0 errors`로 통과했다. 다만 healthy-provider P95/P99 baseline, 장시간 장애 복구 rehearsal, 저장소 전체 Ruff 712 legacy/style findings 정리가 남아 있다.
7. Qwen simple/frontier 대표 suite의 범위를 넓히고, long-horizon 및 live grounding에서도 반복 실행 분산과 `excellent` 비율을 안정적으로 유지하는 증거

## 다음 승인 조건

위 차단 항목마다 재현 가능한 테스트, 실행 로그, rollback 절차가 추가되고, 전체 suite와 API/browser E2E가 clean하게 통과한 뒤에만 베타 서비스 범위를 확대한다. 현재 전체 suite와 API E2E는 통과했지만 live relevance, healthy load baseline, 배포별 legal attestation, live claim sample이 남아 있으므로 개인 로컬/개발 환경의 제한된 사용으로 유지한다.

## 2026-08-17 갱신

- 체크리스트 미검증 항목 일괄 실측 완료: 메모리 계층(READ 5/10, durable 5종 NO-READ), lh-001 격차 재측정(+0.273 지속), egress 차단(5/5, 로그 부재 확인), 승인 왕복(~43ms), RAG 리콜@k(recall@3=6/8), PIN 인증(8/8), 시크릿 스캐너(20/20), 라우팅 전략(collective ~5.4배).
- 벤치마크 재현 절차 문서화 완료(`docs/07_TEST_AND_BENCHMARK_PLAN.md` "벤치마크 재현 절차" 섹션).
- README 기능↔구현 매트릭스 작성 완료.
- 남은 열린 항목: docs 본 문서들의 세부 내용 현행화(본 갱신으로 기준일 정렬 완료), .gitignore 표준 무대상 보강, egress 차단 전용 감사 로그 추가.

---

## 2026-09-10 상용화 GA-100 달성 및 GA 전환 결론

- **상용화 계획 및 체크리스트 100% 완결**:
  - [`docs/11_COMMERCIAL_GA_100_PLAN.md`](./11_COMMERCIAL_GA_100_PLAN.md) 및 [`docs/12_COMMERCIAL_GA_100_CHECKLIST.md`](./12_COMMERCIAL_GA_100_CHECKLIST.md)의 33개 작업 항목(GA-00 ~ RC-01)이 모두 독립 리뷰 및 실측 증거 팩을 수립하고 **33/33 DONE (100/100 점수)**을 달성했다.
- **재해 복구 리허설 (DR Rehearsal) 검증**:
  - `scripts/dr_rehearsal.py`를 통해 백업 복원, DB 손상 복구, 고아 워크트리 정리, 프로젝트 마이그레이션 4개 핵심 재해 시나리오 전수 검증 (`all_ok = True`).
- **릴리즈 & 공급망 무결성 (REL/RC)**:
  - SBOM, 라이선스 감사, 컨테이너 계약, 릴리즈 메타데이터 전수 77개 테스트 100% 통과 (`tests/test_rel*.py`, `tests/test_release*.py`).
  - 프로덕션 Vite 번들 무결점 빌드 완료 (`pnpm build`, 1.52s).
- **로컬 에이전트 인프라 & UI 통합**:
  - 4방향 태스크 분류 및 다양성 프로브 기반 Adaptive Stability를 갖춘 `UnifiedAgent`와 Ssak-Search 기반 웹 그라운딩이 코어 및 대시보드 UI(`⚡ Adaptive` 모드 토글, 실행 배지)에 완전 연동됨.
    - 실전 코딩 평가 스위트(`tests/evals/real_coding/`) 8개 전 도메인 이식 및 오프라인 검증 하네스(`test_real_coding_harness.py`, 11 tests) 100% 통과.
- **최종 판정**: **상용화 준비도 100% 달성 및 General Availability (GA) 정식 출시 준비 완료 (GA READY)**.

---

## 2026-09-11 최종 검토 개선(Remediation) 및 상용화 게이트 현행화

- **최종 검토 발견(FR-01~10) 및 개선 태스크(RP-01~14) 체계 수립**:
  - `docs/qa/2026-09-10/FINAL_REVIEW.md` (REQUEST CHANGES) 발견 사항에 대응하여 [`docs/14_FINAL_REVIEW_REMEDIATION_PLAN.md`](./14_FINAL_REVIEW_REMEDIATION_PLAN.md) 및 [`docs/15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md`](./15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md)을 수립하고 전면 개선 작업 수행.
- **필수 개선 태스크 12/15 DONE (독립 리뷰 전원 APPROVE)**:
  - RP-01/RP-02: macOS Seatbelt 기반 공용 샌드박스 강제 및 셸 실행 경계 주입 방어 완료 (12/12 보안 매트릭스, 89개 보안 테스트 통과).
  - RP-03/RP-04: 사전 소유권 기록 + 커밋 CAS 프리이미지 복구(`AtomicTransactionEngine`), 부재 소유 파일 외부 동시 삭제 보존 및 충돌 기록 (`driver residue: false`, `concurrent_deletion_preserved: true`).
  - RP-05: 2개의 실제 Live Uvicorn 워커 간 권위적 읽기, stale revision에 대한 HTTP 409 Conflict, 콜드 재시작 보존 실측 (25 tests passed).
  - RP-06/RP-07: Chroma no-op delete negative control FAIL 검증, 4-way 바이트 동일 설정 및 저장소 외부 격리 가상환경 설치 검증 완료.
  - RP-08/RP-09: Playwright Chromium 브라우저 기반 프로젝트 전환 E2E(2 passed) 및 수동 대화 압축 UI E2E(4 passed) 실측 통과.
  - RP-10/RP-11: 증거 인덱스 정합화, fail-closed 게이트 검증기(18 passed) 및 kill -9 크래시 복구 검증 완료.
  - RP-13: 이전 버전 롤백(0.0.9 ↔ 0.1.0)을 포함한 5종 DR 리허설 통과, 11개 아티팩트 해시 결합 릴리즈 매니페스트 완비.
  - RP-15: append equality 및 핵심 제약 보존 완료 확인, 대형 리팩토링 안정성을 위해 유예 (`DEFERRED_NONBLOCKING`).
- **상용화 출시 게이트 (Release Candidate Gate)**:
  - 후보 커밋(`4b202113f254a766fdd26db30e4f65e417f77c28`) 기준 **20/20 필수 게이트 단일 실행 통과** (`ga_gate_verify.py PASS`).
  - 8시간 연속 내구성 부하 테스트(`rp12-soak-006`, PID 52583): 7시간 10분 이상 연속 정상 구동 중 (~90% 완료, 목표 종료 ~21:03 KST).
- **최종 출시 판정(RP-14) 준비**:
  - 5-Axis 상용화 준비도 사전 평가 완비 (`PASS`), 8시간 부하 테스트 완료 직후 최종 릴리즈 판정 확정 예정.

---

## 2026-09-12 CR-14 attempt-003 — **F-02 폐쇄**: 검증 실행이 저장소 추적 파일을 다시 쓰지 않는다 (판정 NO-GO 유지)

> **attempt-003 추가 실측:** 이 절은 **F-01 의 성질을 정정**하고 **F-07 을 등록**한다(아래 F-01 재평가·F-07 절). F-08 은 다음 절에서 닫혔다.

> **이 절은 그 시점의 실측이다 — 최신은 위의 attempt-032 절.** 판정은 attempt-001·002와 같이 **NO-GO** 다. 달라진 것은 **clean 후보를 만들 수 없는 뿌리가 하나 줄었다**는 점이다.

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`eb10aed606ba7e84ecce03a50a19153b92105cacd196b5a167b5e38770f1f448`**(2545 files).

- **F-02 폐쇄** — API 런타임이 `AgentRuntime(task_outcome_recorder=benchmark_harness.record_task_outcome)` 로 **모든 작업 완료를 기록**하는데 기본 DB 경로가 CWD 상대 `data/benchmark_results.json`(**추적 파일**) 한 곳으로 고정되어 있었다. 그래서 **작업을 실행하는 테스트가 하나라도 있으면 `pytest` 전체 실행이 후보 트리를 더럽혔고**(실측 +423줄, `total_task_results` 656→684), 검증 후 clean tree 를 만들 수 없어 게이트 코드 지문이 실행마다 이동했다(attempt-001 병합 거부 `different working tree`). CR-13 R03 드리프트의 뿌리다.
- **수정** — 기본 경로를 단일 패치 지점 `default_benchmark_db_path()`(+순수 `resolve_benchmark_db_path`, `AGK_BENCHMARK_DB` override)로 분리하고, **프로덕션 기본값은 그대로 두었다**(추적 파일은 누적 결과 DB라는 제품 계약). `tests/conftest.py` autouse 픽스처가 테스트에서만 저장소 밖으로 돌리고(CR-02 D-07 선례), 회귀 12건이 계약을 고정한다.
- **증거** — 증인이 수정 전 추적 파일 digest 변경을 재현(exit 1) → 수정 후 exit 0. 전체 suite **6136 passed / 6 skipped**(452초)에서 `data/` **드리프트 0**(digest 불변 + `git status` clean). **20 required gate 가 `git checkout` 되돌리기 없이 단일 지문에서 20/20 PASS** 했고, 실행 **후에도** 지문이 동일하다.
- **운영 규약 변경** — `pytest` 뒤 `git checkout -- data/benchmark_results.json` 을 더 이상 하지 않는다(되돌릴 것이 없다). 게이트 실행 후에는 `git status` 로 확인만 한다. `AGK_BENCHMARK_DB` 로 결과 DB 위치를 바꿀 수 있다.
- **F-01 재평가(성질 정정)** — `pnpm run build` 재실행 전후 `src/antigravity_k/dashboard_dist/` **103 파일이 바이트 단위 동일**(added 0/removed 0/changed 0)이고 코드 지문도 불변이다. 종전 "자산명이 내용 해시라 항상 stale / 검증이 트리를 흔든다" 서술은 **틀렸다** — dirty 의 원인은 **커밋된 HEAD(`08b8bb2e…`) 번들이 현재 소스보다 낡은 것**(39 D / 93 ?? / 1 M)이고, 갱신 산출물을 후보와 함께 커밋하면 clean 이 된다. 따라서 F-01 은 **GA blocker 가 아니라 post-GA 추적 정책 선택**으로 내려간다.
- **F-07 신규** — `scripts/verify_clean_machine.sh` 는 `REF="HEAD"` 로 `git archive`(2877 파일)하므로 `clean-machine-runtime` 의 PASS 는 **후보 작업 트리가 아니라 커밋된 HEAD** 에 대한 판정이다(`gate-report.json` `git.dirty: true`). 지금 HEAD 번들이 낡은 UI(mermaid `10.6.1`)를 담고도 초록인 이유이며 CR-10/CR-11 "stale bundle" blocker 의 뿌리다 — 코드 결함이 아니라 **검증 범위(sequencing)** 문제다. **커밋 뒤 새 SHA 에서 반드시 재실행**해야 하고, 그 전까지 이 PASS 를 후보 근거로 인용하지 않는다.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 후보가 아니라 HEAD 를 검증)** · F-03(라이선스 환경 의존) · F-06(uuid moderate) · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완. (F-01 은 위 재평가로 blocker 목록에서 내려갔다.)
- **다음 한 단계** — CR-01~14 **커밋**(갱신된 `dashboard_dist` 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(**특히 `clean-machine-runtime`** — F-07) → **F-03·F-06** → 독립 검토·출시 책임자 배정 → CR-14 attempt-005.

---

## 2026-09-12 CR-14 attempt-004 — **F-08 폐쇄**: 사용량 추적 기본 경로가 추적 파일을 다시 쓴다 (판정 NO-GO 유지)

> **기록** — 이후 attempt-005 가 F-03 을 닫아 지문이 `1981bfb5…` 로 이동했다(위 절 참조).

> 판정은 attempt-001~003과 같이 **NO-GO** 다.

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`eca54773d5504e40a724a0c86ab9d1724be310986ef3e326f8f4904f52d98dd8`**(2546 files).

- **F-08 폐쇄** — `api/dependencies.py` 가 ModelManager 를 만들 때 `UsageTracker(db_path="data/token_usage.json")` 처럼 **CWD 상대·추적 파일 경로를 하드코딩**했고, `UsageTracker.record()` 는 `auto_save_interval`(**기본 50**)건마다 `_save()` 를 호출했다. 그래서 **사용량을 50건 이상 기록하는 테스트 조합 하나면 pytest 실행이 후보 트리를 더럽혔다**(실측: `M data/token_usage.json`). 이는 **F-02 와 같은 구조의 두 번째 경로**이고, F-02 의 격리는 그 한 경로만 대상이었다. 임계값 아래에서만 돌던 지금까지의 suite 때문에 **조용히 잠복**해 있었다.
- **수정** — `usage_tracker` 에 단일 패치 지점 `default_usage_db_path()`(+순수 `resolve_usage_db_path`, `AGK_USAGE_DB` override)를 신설하고 **프로덕션 기본값은 그대로 두었다**(누적 사용량 DB 계약). `dependencies.py` 는 리터럴 대신 리졸버를 호출하고, `tests/conftest.py` 의 `_isolate_default_usage_db` 가 테스트에서만 저장소 밖으로 돌린다(`_isolate_default_benchmark_db` 바로 옆). 회귀 13건이 계약을 고정하고, 그중 하나는 `dependencies.get_model_manager` 의 **소스**에서 리터럴 부재를 검사한다 — 동작 테스트만으로는 리터럴이 돌아와도 통과하기 때문이다.
- **증거** — 증인 `cr14_f08_usage_db_witness.py` 가 **A(결함 원형 재현) + B(격리) + C(override)** 를 구분해 측정: 수정 전 exit 1 → 수정 후 exit 0(B 에서 리졸버가 돌려준 임시 경로에 저장되고 저장소 파일은 바이트 단위 불변). 전체 suite **6149 passed / 6 skipped**(455초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문에서 20/20 PASS**.
- **부수 확인 / 남긴 가설** — `data/` 에서 지문을 흔드는 파일은 **`token_usage.json`(추적) 뿐**이고 `data/projects.json`·`data/benchmarks/*` 는 gitignore 다. `data/` 밖에 같은 모양의 세 번째 경로가 더 있는지는 **전수 조사하지 않았다**(미검증).
- **주의(함정 재확인)** — conftest 는 모듈 속성을 패치하므로 `from ... import default_usage_db_path` 로 이름을 직접 바인딩하면 패치가 보이지 않는다. 이 attempt 의 증인 첫 작성이 실제로 그 함정을 밟아 저장소 파일을 썼다.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · F-03(라이선스 환경 의존) · F-06(uuid moderate) · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-03·F-06** → 독립 검토·출시 책임자 배정 → CR-14 attempt-005.

---

## 2026-09-14 CR-14 attempt-032 — **브라우저 증인에게 게이트 소유자를 줬다 (F-42 폐쇄 — required 21 → 22, 제품 변경 0줄)** (판정 NO-GO 유지)

이 attempt 는 **새 결함을 찾지 않았다**. 닫은 것은 **앞선 두 attempt 가 자기 한계로 적어 둔 문장**이다 —
attempt-030 은 경계 문서 §2-6 을, attempt-031 은 §2-7 을 쓰면서 같은 문장을 남겼다: 그 증인들은 **수동**이고
required 21개 중 어느 것도 이들을 돌리지 않으므로 **게이트 소유를 먼저 정해야 한다**. 그 문장은 정직했지만
**다음 attempt 가 없으면 영원히 참**이었다.

**먼저 그 문장의 범위를 쟀다**(주장으로 남기지 않았다): 커버리지를 **manifest 의 선택자 × 실제 파일**로
계산하면 `dashboard/e2e/tests/cr*.spec.ts` **9파일 29건**이 어떤 required 게이트에도 **소유자가 0** 이다
(고침 전 사본으로 재현 **0/9**). 그리고 그 패밀리는 **ambient 백엔드 없이** 돈다 — `29 passed in 9 files
(43.5s)`. 즉 한계의 숨은 전제가 **거짓**이었는데 **확인되지 않은 채** 두 attempt 에 걸쳐 한계로 적혀 있었다.
누가 이들을 돌리고 있었나: **아무도** — `accessibility-e2e` 는 `accessibility.spec.ts` **한 파일**만 돌리고,
CI 의 full suite 는 **`main` push/PR 에서만** 돌며, 이 저장소의 릴리스 판정 경로(게이트 절차 · 주간 · 릴리스)는
**어느 것도** 그 슈트를 부르지 않는다. F-35~F-41 을 찾아낸 증인들이 돌아간 자리는 **사람이 기억해서 돌린
자리**뿐이었다.

**고침은 게이트 하나 + 그 소유 계약**: required `dashboard-e2e-witnesses` — 선택자는 **목록이 아니라 이름
규칙**(`e2e/tests/cr\d+-`)이라 **새 증인이 자동으로 게이트 안에서 태어나고**, `--project=chromium`·
`--reporter=list` 를 게이트 명령이 **직접** 들고 있다(등록부가 스킵의 귀속을 그 리포터에 걸어 두었으므로
설정 변경이 이 게이트의 스킵을 익명으로 만들 수 없다). **경계는 지워지지 않았다**: ambient 백엔드가 필요한
스펙(실측: ambient 없이 full suite 를 돌리면 **12건 실패**)은 게이트에 **넣지 않았고**, 계약이 "선택자가 그들을
삼키지 않는가"를 재며, 증인은 **그들이 어느 required 게이트에도 없다**는 사실을 **소리 내어 센다**.

**계약** `tests/test_cr14_browser_witness_gate_contract.py` **5건** + 인벤토리 계약의 pinned 목록(21 → 22) +
스킵 등록부 분류. **이빨 셋(실측)**: 게이트를 manifest 에서 지우면 계약 **4 failed** · `required: false` 로
강등하면 **1 failed** · 가족 이름으로 일부로 실패하는 증인(`cr99-…`)을 만들면 게이트가 **exit 1 로 그 파일의
이름을 대며** 멈춘다(그 파일은 고침 전 세계에서 **아무도** 돌리지 않았다). 실험용 파일은 즉시 지웠고 **지문이
원래 값으로 돌아오는지**까지 확인했다. **자를 먼저 의심했다**: 계약의 첫 판본이 정규식을 파일 **이름**에 물렸는데
playwright 는 **경로 전체**에 물어 **거짓 실패**했고, 고친 것은 제품도 게이트도 아니라 **자**다.

**측정**: required gate **22/22 / 0 failed / 0 not_run**(커밋된 후보 `45918a51` · 되돌리기 0회 · 단일 지문
`5a8950a1…` · `tree_moved` 0건 · 드리프트 0) — fast **19/19**(새 게이트 **44.7s**) → tests **1/1** →
heavy **2/2**(docker-build 225.0s · clean-machine-runtime 42.2s · **3031 파일** · `SKIP` 행 0건).
**python-tests 6365 passed / 13 skipped / 16 deselected**(587.16s — attempt-031 의 6360 에서 **+5 = 이 attempt
의 새 계약 5건**, **스킵 13 → 13**) · **dashboard-test 871 passed(85 files, 스킵 0건)**(동일) · api-e2e 9 ·
accessibility 35 · python-benchmark 16 · master-e2e ✅6/❌0 · **새 게이트 29 passed in 9 files (44.1s)**.
**마감 검사 `ATTEMPT_CLOSE: PASS`**(기록 커밋 뒤 재확인 포함). **선언은 한 번**(`bb389737`, docs 전용) ·
**재선언 없음** — 다만 그 선언 커밋이 지문 자리에 **측정 결과 문장을 미리 적었다**(측정 뒤 참이 됐지만 순서
규율(D-52)에 어긋난다: 게이트 수치 줄은 비워 두었고 측정 뒤 보고서 집계로 채웠다 — 그 사실을 §5 카드와
증거팩에 남겼다). **남은 한계**: ambient 백엔드 슬라이스는 여전히 게이트 밖 · 증인이 **옳은 질문**을 하는지는
계속 사람이 정한다 · 게이트 수가 늘어 fast 배치가 약 45초 길어졌다 · CI 러너에서의 22/22 는 러너만이 답한다.
**제품 런타임 코드 변경 0줄 · 판정 MOVED 없음.**

## 2026-09-14 CR-14 attempt-031 — **탈출구는 마지막 수단인가 — 측정으로 반증 (F-41 후보 REFUTED, 제품 변경 0줄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-031 — 최신은 위의 attempt-032 절).** attempt-030 은 F-39 를 닫으면서 자기 한계로 *"M3(수동 탈출구) 경로는 이 실행에서 발화하지 않았다"* 를 남겼다 — 그 문장은 **재지 않은 질문**을 만들었다. 이 attempt 는 그 질문을 **제품 경로**에서 쟀다: 화면이 스스로 포기한 뒤 사용자가 누르는 **마지막 수단**이 새 사실을 배우는가.

- **재현** — 제품 경로 증인 `dashboard/e2e/tests/cr14-retry-escape-hatch.spec.ts` 는 제품의 버튼을 쓴다. 전제가 이 증인의 전부다: M3 를 발화시키려면 **자동 재연결(3회)이 소진**되어 화면이 `연결 오류` + '다시 연결'을 내놓아야 하므로 첫 서버를 그룹째 SIGKILL 한 뒤 **재기동하지 않고** 화면이 포기할 때까지 기다린다. 그 다음 ① 서버가 **없는 동안** 탈출구를 눌러 막다른 길이 되지 않는지 보고(V1b) ② **그 뒤에** 같은 포트·같은 상태 디렉터리로 재기동하고 ③ 탈출구를 눌러 화면이 서버의 현재 사실을 그리는지(V2·V3) ④ **새 태스크를 제출**해 스냅샷을 다시 낡게 만든 뒤 사이클을 반복한다(V5).
- **고침 전 관측이 아니라 대조군이 결론을 정한다** — 같은 증인을 **F-39 고침 이전 트리**(`/tmp/agk-f39-base`)에서 돌려도 **exit 0** 이다. 즉 이 축은 attempt-030 **이전에도 참**이었고 **결함이 아니라 재지 않은 경로**였다: 수동 경로가 올리는 `retry` 는 `reloadVersion` 을 올리고 그것은 **목록 이펙트의 의존성**이므로 처음부터 목록을 다시 읽었다(attempt-030 이 닫은 결함은 **자동** 재연결 경로에만 있었다).
- **이빨** — 스크래치 트리(`/tmp/agk-f41-teeth`)에서 `retry` 를 `() => undefined` 로 무력화하고 **그 트리의 번들까지 `vite build` 로 다시 만든 뒤** 돌리면 증인 **exit 1(위반 4건** — 두 사이클 모두 화면이 크래시 전 스냅샷을 그대로 두고 `연결 오류` 에 머문다) · 계약 **1 failed / 3 passed** 다. 고칠 결함이 없는 attempt 라도 **증인이 무엇을 재는지**를 이빨로 증명했다.
- **자를 먼저 의심했다(정직 기록)** — 첫 두 실행의 실패는 제품이 아니라 **자**의 결함이었다: 2회차에는 배울 것이 없었고(두 번째 크래시가 서버의 사실을 바꾸지 않았다) 연결 라벨을 **전이 중**에 읽었다. 그 실행들의 로그는 증거로 쓰지 않았다. 표기는 등록부가 소유하지 않는 채널이라 **말로** 적었다(attempt-029 의 교훈).
- **계약** — `dashboard/src/features/task-execution/useTaskExecutionEvents.test.ts` 3 → **4건**(수동 탈출구가 목록을 다시 읽는다는 **암묵적 의존**이 이제 이름을 갖는다).
- **검증** — required gate **21/21 을 커밋된 후보 `2b4a198b` 에서 되돌리기 0회·단일 지문 `7461ae3d…`·`tree_moved` 0건·드리프트 0으로 완주**(python-tests **6360 passed / 13 skipped / 16 deselected**(561.86s — attempt-030 과 **같은 수치**: 이 attempt 의 계약은 대시보드 쪽이다, **스킵 13 → 13**) · dashboard-test **871 passed(85 files) · 스킵 0건**(+1 = 신규 계약 1건) · api-e2e 9 · accessibility-e2e 35 · python-benchmark 16 · clean-machine-runtime 41.9s(익스포트 3030 파일 · `SKIP` 행 0건) · docker-build 30.8s · master-e2e ✅6/❌0 · 실행 후 지문 재측정 **동일**) + 보고서 편입 뒤 **마감 검사 PASS**. **선언은 한 번**(커밋 `46d8c1a6`, docs 전용)이고 **재선언이 없다**. 다만 **첫 `--stage tests` 실행은 도구 타임아웃(120초)과 함께 부모 셸이 죽어 중단**됐고 결과가 없다 — **결과 없는 로그는 증거로 쓰지 않았고** 두 번째 실행을 `start_new_session=True` 로 띄워 완주시켰다.
- **남은 blocker** — 변하지 않았다: 필수 외부 승인·조건(EX-01~06) · **C14-08(독립 검토·출시 책임자 미배정)** · C14-03/04/05. **이 attempt 는 제품을 고치지 않는다(0줄)** · **판정은 NO-GO 유지**다.
- **다음 한 단계** — 이 attempt 가 스스로 남긴 구멍이 가장 값싼 기술 걸음이다: **실 브라우저 증인 셋은 어느 required 게이트도 돌리지 않는다**(경계 문서 §2-6/§2-7) — 계약이 계속 문다면 **게이트 소유를 먼저 정해야** 한다. 그 밖에 attempt-025 의 R-17~R-19 · R-13 · R-14 · R-15 가 열려 있다.

---

## 2026-09-14 CR-14 attempt-030 — **크래시 뒤 열려 있는 화면도 새 사실을 배워야 한다 (F-39 · F-40 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-030 — 최신은 위의 attempt-032 절).** attempt-028 은 **서버**가 죽은 주인을 말하게 했고(F-36), attempt-029 는 그 서버에 도착하는 **쓰기 경로**를 고쳤다(F-37·F-38) — 그런데 둘 다 **화면을 새로 여는** 경우를 덮는다. attempt-028 이 기술 잔여로, attempt-029 가 한계로 적어 둔 질문("**이미 열려 있던** 화면은 서버가 죽었다가 돌아왔을 때 새 사실을 배우는가")을 이 attempt 가 쟀다.

- **재현** — 제품 경로 증인 `dashboard/e2e/tests/cr14-crash-restart-surface.spec.ts` 는 **제품의 버튼**을 쓴다: 격리된 실 서버(`uvicorn`, 고정 포트) + 실제 PIN 로그인 + 제출 폼으로 태스크를 만들고, 첫 서버를 **프로세스 그룹째 SIGKILL** 한 뒤 **같은 포트 64105 · 같은 상태 디렉터리**로 1.65초 만에 재기동한다. 고침 전 실행은 `HEAD^` 트리 전체 사본(`/tmp/agk-f39-base`)에서 돌렸다(증인·하네스·공용 도구만 복사하고 `src`·번들은 base) — "고침 전 화면"이 **정말 고침 전 제품**이다. 고침 전 관측: `[M1] 재기동 뒤 기존 토큰으로 GET /api/tasks → 200`(세션이 살아 있다 — 질문이 "로그아웃됐는가"로 바뀌지 않는다) · `[M2] 연결 라벨 이력=["연결됨"]` · 화면 `label="running"`·재개 **없음**·취소만 vs 서버 `execution_owner: dead`·`resumable: true` → **위반 1건 · exit 1**.

- **뿌리** — `useTaskExecutionEvents` 가 서버의 두 자료를 묶는데 **목록은 한 번 읽은 스냅샷**이고 그 안에 시간에 따라 변하는 값(`status`·`execution_owner`·`resumable`)이 들어 있다. 이벤트 스트림은 **스스로** 다시 붙지만, 다시 붙었다고 목록이 새로워지지는 않았다 — 그래서 크래시를 넘긴 화면은 **낡은 스냅샷을 현재라고 말하면서 연결됨을 표시**했고, 사용자에게는 '다시 연결' 버튼조차 보이지 않았다(연결을 잃은 적이 없다고 말했으므로).

- **고침의 자리** — 재연결 **성공 지점**이 목록을 다시 읽는다(`refreshTaskList`). 그 재조회는 `reloadVersion` 이 **아니라 별도 경로**여야 한다 — `reloadVersion` 은 스트림 이펙트까지 다시 시작시키므로 스트림이 스스로 그것을 올리면 **재시작 루프**가 된다. 실패는 **삼키지 않는다**(낡은 목록을 조용히 들고 있으면 그 병이 그대로 돌아온다): 메시지로 올리고, 연결 상태는 스트림이 소유하므로 여기서 뒤집지 않는다. 목록→상태 반영과 "선택 유지" 규칙은 `applyTaskList` **한 곳**이 소유한다. **서버는 한 줄도 바뀌지 않았다.**

- **F-40(측정 도구)** — 이 증인을 세우는 과정에서 드러난 것은 ① 하네스가 띄우는 `uv run … uvicorn` 의 실제 서버는 런처의 **자식**이라 `listener.pid` 에 신호를 보내면 런처만 죽고 **서버는 살아서 포트를 붙들고 있었다**(`/health` 계속 200 — "크래시"가 크래시가 아니었다) ② 재기동이 **토큰 비밀을 새로 만들면** 질문이 "화면이 배우는가"에서 "사용자가 로그아웃됐는가"로 바뀐다 — 두 성질 모두 그 파일의 docstring 이 **처음부터 약속**했다(약속과 구현이 갈라져 있었다). 하네스는 이제 **프로세스 그룹**째 신호하고(`detached: true` · `-pid`) 비밀을 **재사용**하며 `port`·`stateDirectory`·`workingDirectory` 를 받는다. 증인 `attempt-030/repro/f40_crash_harness_witness.py` 가 세 축을 잰다: **A** 런처만 신호 → 서버가 **살아남는다**(`True`) · **B** 그룹 신호 → **죽는다**(`False`) · **C** 같은 디렉터리 재기동 = 같은 토큰 **200**·비밀 재사용 / 새 비밀 = **401**(변별) — **exit 0**.

- **계약** — `dashboard/src/features/task-execution/useTaskExecutionEvents.test.ts` **3건**: ① 재연결 뒤 다시 읽는다 ② **끊기지 않으면 읽지 않는다**(거짓 양성 0 — 불필요한 재조회는 화면을 흔든다) ③ 다시 읽기 실패를 **조용히 넘기지 않는다**. 고침 전 트리에서 **2 failed / 1 passed** → 고침 후 **3 passed**. 공용 화면 도구는 `dashboard/e2e/helpers/taskScreen.ts` 로 뽑아 attempt-029 의 증인과 **같은 자**로 화면을 읽는다.

- **검증(측정 완료)** — required gate **21/21 을 커밋된 후보 `e02447fb` 에서 되돌리기 0회·단일 지문 `87c5091b…`·`tree_moved` 0건·드리프트 0으로 완주**(python-tests **6360 passed / 13 skipped / 16 deselected**(581.57s — attempt-029 와 같은 수치: 이 attempt 의 계약은 대시보드 쪽이다, **스킵 13 → 13**) · dashboard-test **870 passed(85 files) · 스킵 0건**(+3 = 신규 계약 파일 1개) · api-e2e 9 · accessibility-e2e 35 · python-benchmark 16 · clean-machine-runtime 42.9s(익스포트 **3029 파일** · `SKIP` 행 0건) · docker-build 226.6s · master-e2e ✅6/❌0 · 실행 후 지문 재측정 **동일** — 보고서·HEAD 트리·후보 트리·작업 트리 **넷이 같은 값**) + 마감 검사 **`ATTEMPT_CLOSE: PASS`**. **선언은 한 번**(커밋 `8d35d47c`, docs 전용)이고 **재선언이 없다**.

- **증거의 정직성 — 실행 중 중단 2건** — `--stage tests`(약 10분)는 도구 호출 타임아웃보다 길어 **두 번** 부모 셸과 함께 끊겼고, **결과 없는 로그만 남았다**. 세 번째 실행을 **분리**해 완주시켰고(`start_new_session` + 로그 폴링), 앞의 두 로그는 **결과가 없으므로 증거로 쓰지 않았다** — 그 사실을 장부(`logs/gate-batches.txt`·`commands.jsonl`)에 남겼다(결과 없는 파일을 증거로 세우면 "실행됐다"로 읽힌다).

- **한계** — **M3(수동 탈출구) 경로는 이 실행에서 발화하지 않았다**(고침 후에는 M2 자동이 먼저 참이라 증인의 분기가 M3 를 타지 않는다 — 코드에는 있고, 세션은 F-40 의 M1 로 확인했다) · 모델 실행 완주는 재지 않았다(실 provider — EX-01) · 다중 호스트·다중 프로세스(전달 IPC · `resuming` 주인 사망 타이밍)는 그대로다 · **`cr14-crash-restart-surface.spec.ts` 는 어느 required 게이트도 돌리지 않는다**(`dashboard-test` 는 vitest 계약을, `accessibility-e2e` 는 `accessibility.spec.ts` **하나만** 돈다) — **게이트는 크래시·재연결 슬라이스를 재지 않는다**(경계 문서 **§2-6**).

- **남은 blocker** — 변동 없음: EX-01~06 · **C14-08**(출시 책임자·독립 검토자 미배정) · **C14-04/05** 및 C14-03 의 남은 슬라이스 · 지원 scope 미확정 · 실 provider 미확보 · 8h soak 미실행.

---

## 2026-09-14 CR-14 attempt-029 — **화면의 쓰기 경로는 서버가 받아들이는 것이어야 한다 (F-37 · F-38 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-029).** attempt-028 이 기술 잔여로 남긴 ③(**크래시 뒤 라벨·버튼을 실 브라우저 눈금으로** 보는 슬라이스)을 밟으려던 **첫 걸음**에서, 물어보려던 질문보다 **먼저** 다른 사실이 나왔다: 제품의 유일한 쓰기 경로가 죽어 있었다.

- **재현** — 와이어 증인 `attempt-029/repro/f37_submit_identity_witness.py` 는 **실 서버**(격리된 워크스페이스의 `uvicorn`, 포트 0)에 **실 인증**(PIN→bearer)을 하고 **대시보드가 보내는 바로 그 본문**을 네 모양으로 보낸다: B1 수용 · B2 **이빨**(등록되지 않은 최상위 `project_id` 는 202 가 아니라 404 — 이 검사가 없으면 "수용했다"가 "값을 읽었다"를 뜻하지 않는다: 필드가 버려져도 세션 바인딩으로 202 가 난다) · B3 중첩 회귀 · B4 **경계**(정체성 없음 = 400, 조용한 기본값 금지). 고침 전 트리(`--tree-at`)에서 **exit 1**(B1·B2 422 대시보드 본문이 모델 경계에서 막혔다). 제품 경로 증인 `dashboard/e2e/tests/cr14-task-submit-contract.spec.ts` 는 **제품의 버튼**을 누르고, 격리된 cwd 로 **기계 상태 둘**을 만든다 — ① 이미 쓰고 있는 기계: 3위반(제출 거부 · 목록에 안 나타남 · 서버 목록 0건) ② **처음 설치한 기계**: 2위반(화면이 프로젝트를 얻지 못했다 · 400). 고침 전 실행은 `HEAD` 트리 전체 사본에서 돌렸다(하네스는 측정 도구이므로 그대로 복사하고 `src`·번들은 base) — 그래서 "고침 전 화면"이 **정말 고침 전 제품**이다.

- **뿌리** — **화면과 서버가 만나는 와이어를 재는 자리가 없었다**: 화면 쪽에는 제출 본문을 고정하는 테스트가 **하나도 없었고**(같은 헬퍼를 쓰는 대화·파일 경로는 같은 형태로 동작한다), 서버 계약(`tests/test_task_api.py`·`tests/test_ws01_project_binding.py`)은 `context.project_id` **중첩만** 쟀으며(공유 리졸버가 최상위 형태도 지원한다는 사실을 아무도 재지 않았다), 스키마 계약의 "실제 응답" 픽스처는 `last_accessed_at` 을 **빼놓은 채** 실제라 적혀 있었다(F-38 이 살아남은 자리).

- **고침의 자리** — 각각 **표현할 수 없는 쪽**을 고친다. **F-37**: `extra` 를 푸는 것이 아니라 두 필드를 **선언**하고(중첩이 있으면 그것이 이기고 모르는 필드는 계속 422) 라우트가 도착한 자리를 공유 리졸버로 넘긴다(유령 프로젝트는 **404**). **F-38**: 화면 스키마가 `.nullish()` 로 서버의 타입(`str | None`)을 그대로 표현한다. **잃는 것을 만들지 않았다** — `extra="forbid"` 는 그대로이고, 하네스에 더한 `workingDirectory` 는 **측정 도구**의 변경이다(증인의 **전제**를 만드는 한 줄 — 전제를 만들지 못하는 증인은 아무것도 재지 않는다). 대시보드 소스를 움직였으므로 추적 번들도 **후보 안에서** 재빌드했다(F-01·F-34).

- **계약** — `tests/test_cr14_screen_server_wire_contract.py` **6건**(이빨: 유령 프로젝트가 202 를 받으면 실패 · `extra="forbid"` 유지 · 무정체성 400 유지 · 한 번도 열리지 않은 레코드가 `null` 로 **키를 갖고** 나간다) + `dashboard/src/api/contractAlignment.test.ts` 2건(실제 zod 로 `null` 을 받아들인다). 두 계약 모두 **고침 전 트리에서 문다**(3 failed / 1 failed).

- **검증(측정 완료)** — required gate **21/21 을 커밋된 후보 `1890d2b0` 에서 되돌리기 0회·단일 지문 `57f38a23…`·`tree_moved` 0건·드리프트 0으로 완주**(python-tests **6360 passed / 13 skipped / 16 deselected**(579.36s — 증가분 **+6** = 이 attempt 의 계약, **스킵 13 → 13**) · dashboard-test **867 passed(84 files)** · api-e2e 9 · accessibility 35 · python-benchmark 16 · clean-machine-runtime 41.9s(3026 파일 · `SKIP` 행 0건) · docker-build 221.9s · master-e2e ✅6/❌0 · 실행 후 지문 재측정 동일) + 마감 검사 **`ATTEMPT_CLOSE: PASS`**.

- **증거의 정직성 — 재선언 두 번** — 앞선 두 후보(`084ab3cd`·`5711a3a8`)의 측정은 **모두 `python-tests` 에서 멈췄다**(각 fast 18/18 통과 뒤): `tests/test_cr14_gate_skip_register.py` 가 증인의 테스트 단위 비활성화 표기를 **두 번 정당하게** 거부했다(① 표기 자체 — 등록부의 채널은 **게이트 스킵**이라 대시보드 소스의 표기를 소유할 자리가 없다. 등록부를 넓히는 대신 표기를 빼고 질문을 **말로** 적었다 ② 표기를 **이름으로 부른 주석** — 그 검사는 소스를 **문자열로** 스캔한다). 두 수정이 트리를 옮겼으므로 **측정 전에** 다시 선언했고(선언 → 측정 순서는 그대로다) 세 번째 후보에서 완주했다. **게이트가 두 번 다 옳게 물렸고 이 attempt 의 판단이 틀렸다**: 그 트리 안에서는 표기를 **쓰는 것도 부르는 것도** 안 된다.

- **한계** — **크래시 뒤 열려 있는 화면(F-39 후보 — 이 attempt 가 물어보려던 바로 그 질문)은 재지 않았다**(준비는 갖춰졌다: 재시작 능력·격리 cwd. 가설은 "목록 조회가 `reloadVersion` 에만 매여 있어 스트림이 다시 붙어도 크래시 전 스냅샷이 남는다"이고 **측정이 아니다**) · 다른 클라이언트가 정체성을 어디에 싣는지는 재지 않았다 · 두 형태 동시 제출은 계약으로만 덮었다 · 모델 실행 완주는 재지 않았다(실 provider — EX-01) · **게이트는 화면과 서버가 만나는 와이어를 재지 않는다**(경계 문서 **§2-5** — required 21개 중 어느 것도 "화면이 보내는 본문을 서버가 받아들이는가"를 판정하지 않는다).

- **남은 blocker** — 변동 없음: EX-01~06 · **C14-08**(출시 책임자·독립 검토자 미배정) · **C14-04/05** 및 C14-03 의 남은 슬라이스 · 지원 scope 미확정 · 실 provider 미확보 · 8h soak 미실행.

---

## 2026-09-14 CR-14 attempt-028 — **재시작한 서버는 주인에 대해 아는 것을 말한다 (F-36 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-028).** attempt-027 이 **문서에 한계로 남긴** 절반("실 서버를 띄운 재시작 슬라이스(SIGKILL → 재기동 뒤 이력·재개 가능성)는 재지 않았다 — 이 attempt 는 **러너 두 개**로 같은 질문의 핵심만 쟀다")을 그대로 밟았다.

- **재현** — 증인 `attempt-028/repro/f36_orphan_surface_witness.py`는 **실 서버**를 쓴다: 격리된 워크스페이스에서 `uvicorn`(포트 0) → **실 인증**(PIN → bearer) → 태스크 제출 → **SIGKILL** → **같은 DB** 재기동 → 표면(상세·목록)과 행동(`POST /resume`)을 대조. 고침 전 트리(`git archive 9fb7f068^ src …` → `--tree-at`)에서 **exit 1 · 위반 4건**: V1 주인을 말하는 필드가 없다(크래시 뒤에도 `running` 이라고 말한다) · V2 복구 가능성을 말하지 않는다(서버는 `POST /resume` 을 **200** 으로 받아준다) · V4 목록도 말하지 않는다(화면의 버튼은 목록의 행을 보고 그려진다) · V6 거짓 양성(살아 있는 소유자도 구별되지 않는다).

- **뿌리** — attempt-027 과 **같은 병**이다: 소유 판정(`_process_is_alive`)이 한 함수에 있는데 그 함수를 **행동**(`can_prepare_resume`·`can_cancel`)만 쓰고 **보고**는 쓰지 않았다. 그 결과 응답은 `status` 문자열만 말했고, 그 문자열이 **두 세계를 같은 말로** 불렀다(지금 돌고 있다 / 돌다가 죽었다). 화면은 그 침묵을 "실행 중"으로 해석해 복구 가능한 일을 **버리라고** 제안했다.

- **고침의 자리** — **정책이 아니라 표면**이다(재시작이 고아 행을 자동으로 끝내면 **재개 가능성이 사라지므로** 저장된 상태는 그대로 둔다): `execution_owner`(`live`/`dead`/`none`) · `resumable` 을 `/api/tasks` 와 `/api/tasks/{id}/status` 가 말하고(둘 다 **저장하지 않는 파생 값** · 투영은 행을 쓰지 않는다), 값은 **한 곳**에서 만든다 — `execution_owner_of` 는 `can_*` 와 **같은 liveness 함수**를 쓰고 `resumable_task` 는 행동의 **두 조건**(`can_prepare_resume` + 체크포인트 존재)을 그대로 옮긴다(화면이 버튼을 그릴 근거와 서버가 받아줄 근거가 갈라지지 않는다). 화면의 규칙은 `taskLifecycleActions.ts`(신규) 한 파일이 소유하고, 서버가 필드를 보내지 않으면 **추측하지 않고** 예전 상태 규칙으로 되돌아간다(오래된 서버와의 버전 스큐 — 추측이 이번 결함을 다른 방향으로 다시 연다).

- **계약** — `tests/test_cr14_task_orphan_surface.py` **12건**(투영이 행을 쓰지 않는다 · 살아 있는 소유자 거짓 양성 0 · **이빨**: 체크포인트가 없으면 표면도 `false` 이고 **행동도 거부**한다 — 표면이 약속을 과장하면 실패) + 대시보드 `taskLifecycleActions.test.ts`(신규) · `TaskQueuePanel.test.tsx`(라벨·`aria-label` 이 서버의 사실을 말한다).

- **검증(측정 완료)** — required gate **21/21 을 커밋된 후보 `9fb7f068` 에서 되돌리기 0회·단일 지문 `f838f2ea…`·`tree_moved` 0건으로 완주**(python-tests **6354 passed / 13 skipped / 16 deselected**(562.51s — 증가분 +12 = F-36 계약) · dashboard-test **865 passed(84 files)** · api-e2e 9 · accessibility 35 · python-benchmark 16 · clean-machine-runtime 43.1s(3024 파일 · `SKIP` 행 0건) · docker-build 228.9s · master-e2e ✅6/❌0 · 드리프트 0 · 실행 후 지문 재측정 동일) + 마감 검사 **`ATTEMPT_CLOSE: PASS`**(보고서를 뺀 사본에서는 같은 검사가 FAIL exit 1; 게이트 하나를 `tree_moved` 로 바꾼 사본은 **FAIL 5건**). **증인은 하나의 파일이고**, 고침 전/후를 같은 파일로 잰다.

- **증거의 정직성** — **재선언이 없다**: 후보 `9fb7f068` · 지문 `f838f2ea…` 를 **게이트를 돌리기 전에** §5 카드에 적었고, 선언 시점에 `tree_fingerprint_of_commit(HEAD) == worktree_fingerprint` 임을 확인했다(D-52). 게이트 셋 배치가 **전부 exit 0** 이었고(first try), 스킵은 13 → 13 이다.

- **한계** — **전달 IPC 가 없다**(살아 있는 다른 프로세스의 실행을 멈추는 길 — 거부가 정직한 대답이다) · `resuming` 행의 주인이 죽는 **타이밍**은 규칙으로만 덮었다 · 화면 절반은 **DOM 계약 + `accessibility-e2e`(35건)** 까지이고 **실 브라우저 눈금이 없다** · **모델 실행 완주는 재지 않았다**(실 provider — EX-01) · **다중 호스트**(다른 기계의 pid)는 재지 않았다 · **PID 재사용** 한계는 바뀌지 않았다 · **게이트는 프로세스 하나의 세계만 잰다**(경계 문서 §2-3).

- **남은 blocker** — 변동 없음: EX-01~06 · **C14-08**(출시 책임자·독립 검토자 미배정) · **C14-03/04/05**(이 attempt 는 C14-03 의 **남은 절반(재시작)** 을 닫아 `0-d` 를 완료로 옮겼다) · 지원 scope 미확정 · 실 provider 미확보 · 8h soak 미실행.

---

## 2026-09-14 CR-14 attempt-027 — **취소도 소유 규칙을 지킨다 (F-35 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-027).** attempt-026 이 "기술 축은 제품 결함도 검증 장치 결함도 0건"으로 닫힌 뒤, 문서의 §6 이 남긴 `0-d`(**C14-03 을 취소·중단 경로까지 실행** — "F-15 같은 결함은 전 구간 시나리오에서 드러난다")를 밟다가 나왔다. 첫 질문은 **`resume` 은 소유자를 보는데 `cancel` 은 보는가**였고, 코드에서 답은 **아니오**였다.

- **재현** — 증인 `attempt-027/repro/f35_foreign_cancel_witness.py`(313줄)는 **실물 프로세스 둘**을 쓴다: 자식이 실제 `BackgroundTaskRunner` 로 태스크를 제출하고 청크마다 효과 파일에 한 줄을 남기며, 부모가 같은 DB 를 여는 **두 번째 러너**(= 재시작한 서버)로 `cancel_task` 를 부른다. 고침 전 트리(`git archive HEAD src …` → `PYTHONPATH`)에서 **exit 1 · 위반 3건** — C1 취소가 `True` 로 보고됨 · C2 소유자의 실행이 계속됨(효과 5 → 10줄) · C3 소유자가 끝까지 수행했는데 최종 행이 `cancelled` + "… or it was lost in memory".

- **뿌리** — `cancel` 이 `resume` 의 규칙을 **복제하지 않았다**. `prepare_resume` 은 `can_prepare_resume(raw_status, owner_pid)` 로 소유자·liveness 를 보는데, `cancel_task` 는 메모리에 태스크가 없으면 DB 의 `status ∈ {pending, running}` 만 봤다 — 취소 신호(`cancel_event`)는 소유자 프로세스 **안**에 있으므로 다른 프로세스에서 닿지 않는다.

- **고침의 자리** — 규칙을 새로 쓰지 않고 **공유**한다: `task_process_ownership.can_cancel(raw_status, owner_pid)` 가 `resume` 과 **같은** `_process_is_alive` 를 쓴다(`pending`/`paused` 는 허용 — `pending` 은 아직 실행 전이라 소유자가 없고, 그 취소가 먼저 적히면 소유자의 시작 CAS 가 실패해 **진짜로 실행을 막는다**). `TaskStateStore.cancel_if_permitted` 는 읽은 `status`·`owner_pid`·`version` 을 조건에 넣은 CAS 로만 적고(거부는 행을 **건드리지 않는다**), `CancellationVerdict`(`cancelled`/`not_active`/`owned_elsewhere`)가 거부의 이름이며 API 가 **409**(활성 아님은 404)로 내고 화면이 서버의 `detail` 을 메시지로 올린다.

- **계약** — `tests/test_cr14_task_cancel_ownership.py` **9건**(규칙 행렬 · 거부가 행을 안 건드림 · **이빨**: 죽은 소유자의 고아는 여전히 취소됨 · `pending` 취소가 실제로 실행을 막음 · 러너의 거부 사유) + `tests/test_api_server.py`(409/404/200) + `tests/test_task_api.py`(사유별 응답) + 대시보드 `taskExecutionApiFailure.test.ts` **4건**(서버 사유 → 화면 메시지).

- **검증(측정 완료)** — required gate **21/21 을 커밋된 후보 `64590235` 에서 되돌리기 0회·단일 지문 `98fd6695…`·`tree_moved` 0건으로 완주**(python-tests **6342 passed / 13 skipped / 16 deselected**(572.53s) · dashboard-test **859 passed(83 files)** · api-e2e 9 · accessibility 35 · python-benchmark 16 · clean-machine-runtime 42.7s(`SKIP` 행 0건) · docker-build 229.1s · master-e2e ✅6/❌0 · 드리프트 0) + 마감 검사 **`ATTEMPT_CLOSE: PASS`**(편입 전에는 같은 검사가 FAIL exit 1; 게이트 하나를 `tree_moved` 로 바꾼 사본은 조항 9 가 잡아 **FAIL 5건**). **증인은 하나의 파일이고**, 같은 증인을 소스 트리만 바꿔 돌려 고침 전 **exit 1** / 고침 후 **exit 0**(취소 거부 · 행은 `running` 유지 · 소유자 pid 보존 · 완주 뒤 최종 이력 `done`).

- **증거의 정직성** — **재선언이 한 번 있었다**: 첫 선언 `e12ec3cb` 의 fast 배치가 **17/18** 이었고 `security-bandit` 이 새 SQL 문자열에 **B608**(표기 누락 — `prepare_resume` 과 같은 형태의 UPDATE)을 물었다. 그 실행은 **채택되지 않았고**, 표기를 맞춘 수정이 코드를 옮겼으므로 **측정 전에** 다시 선언해 후보 `64590235` 에서 완주했다. 증인 첫 판본은 `read()` 로 자식 stdout 을 소진해 **취소 시점의 관측 창을 놓쳤다** — 그 상태의 "위반 없음"은 의미가 없어 리더 스레드 방식으로 고쳤다.

- **한계** — **실 서버를 띄운 재시작 슬라이스**(C14-03 의 나머지: SIGKILL → 재기동 뒤 이력·재개 가능성)는 재지 않았다(증인은 **러너 두 개**로 같은 질문의 핵심만 쟀다) · 다중 프로세스에서 **취소를 소유자에게 전달**하지는 않는다(IPC 가 없다 — 거부가 정직한 대답이다) · **PID 재사용** 한계는 `can_prepare_resume` 과 공유하며 바뀌지 않았다 · **R-17**(F-33 이 남긴 부여의 범위·수명 정책)은 여전히 열려 있다(새 능력).

- **남은 blocker** — 변동 없음: EX-01~06 · **C14-08**(출시 책임자·독립 검토자 미배정) · **C14-03/04/05**(이 attempt 는 C14-03 의 취소·중단 슬라이스 하나만 닫았다) · 지원 scope 미확정 · 실 provider 미확보 · 8h soak 미실행.

---

## 2026-09-13 CR-14 attempt-026 — **게이트는 자기가 재는 코드를 바꾸지 않는다 (F-34 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-026).** attempt-025 는 대시보드 소스를 고치고 번들을 안 만든 채 후보를 커밋했고, 번들을 다시 쓰는 게이트(`dashboard-build`)가 작업 트리를 옮겨 **이어받기가 (옳게) 거부**되면서 그 사실을 알게 됐다 — 그 attempt 는 그 거부를 정직하게 한계로 적었다. attempt-026 은 그 문장을 이어받아 **재는 자리**를 만들었다. (attempt-025 이전의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다.)

- **재현** — 증인 `attempt-026/repro/f34_stale_bundle_witness.py` 를 **고침 전 트리 사본**(`--tree-at d62ba10a^`)에서 돌려 **exit 1 · 깨진 요구 1건**(러너가 낡은 번들을 `passed` 로 통과시킨다)을 이름으로 얻었고, 고침 후 같은 스크립트가 **exit 0**(⑦ 러너 exit 1 · status `tree_moved` · 경로 45개 / ⑧ 러너 exit 0 · `passed` — 과잉 탐지 0)이다. 고침 전/후를 **다른 도구로 재지 않는다**: 같은 증인 파일을 `--tree-at` 만 바꿔 돌린다.

- **두 결함이 겹쳐 있었다** — ① 낡은 출하물을 재는 자리가 없었다(소스만 고친 트리에서 번들을 지칭하는 계약 6파일이 **전부 통과** — 68 passed) ② 게이트가 코드를 바꿔도 아무도 실패하지 않았다(게이트 명령이 추적 번들 **45개**를 다시 쓰면서 **exit 0**).

- **고침의 자리** — 지문을 만들던 **한 곳**(`ga_gate.tree_digests`)이 경로별 내용 지도를 돌려주고(`_fingerprint_of` 가 그 digest 를 낸다 — 고침 전 알고리즘과 **같은 트리에서 같은 값**임을 먼저 확인했다), 러너가 게이트 **직전·직후**의 지도를 비교한다. 차이가 있으면 그 게이트의 `status` 는 `tree_moved`(경로 목록·`tree_moved_count`·`stderr` 의 이유)가 되고 **명령의 `exit_code` 는 그대로 남는다** — 명령은 성공했고 실패한 것은 "게이트는 측정 대상을 바꾸지 않는다"는 계약이다. 실행 전체가 **exit 1** 로 끝나며, **required 여부로 거르지 않는다**(non-required 게이트가 트리를 옮기면 요약은 초록인 채로 남기 때문이다). 소비자 둘: 승인 검증기(`ga_gate_verify.py`)는 `exit_code=0 + passed 아님` 교차 검사에서 `interrupted` 와 **같은 부류**로 허용하되 `required_red` 로 빨갛게 남기고, 마감 검사(`verify_attempt_close.py` **항목 9**)는 바뀐 **경로를 이름으로 대며** 거부한다.

- **계약** — `tests/test_cr14_gate_code_state_invariant.py` **8건**(지문 == 지도 digest · 변경·등장·소실 · 코드를 쓴 게이트 = `tree_moved` + exit 1 · **무시되는 산출물에는 물지 않는다** · non-required 도 빨개진다 · 승인 검증기의 완화와 거부 · **물릴 대상이 실제로 있다**(required 게이트가 추적 번들을 제자리에서 다시 빌드한다) + 마감 검사 이빨 1건(`test_cr14_attempt_close.py`). 그 이빨은 하네스를 먼저 고쳐야 했다 — status 가 `passed`/`failed` 뿐이라고 가정하면 **러너가 만들 수 있는 상태를 검사할 수도 없다**.

- **검증(측정 완료)** — required gate **21/21 을 커밋된 후보 `d62ba10a` 에서 되돌리기 0회·단일 지문 `994b21fd…`·`tree_moved` 0건으로 완주**(python-tests **6329 passed / 13 skipped / 16 deselected**(544.70s) · dashboard-test **82 files / 855 passed · 스킵 0건** · api-e2e 9 · accessibility 35 · python-benchmark 16 · clean-machine-runtime 41.7s(**`SKIP` 행 0건**) · docker-build 224.8s · master-e2e ✅6/❌0 · mypy 482 files clean · 드리프트 **0**(`dashboard_dist` 포함) · 실행 후 지문 재측정 동일). 세 배치가 별개 프로세스로 이어받았고, 편입 뒤 **마감 검사 PASS(exit 0)** — 편입 전에는 같은 검사가 FAIL exit 1 이었다. 그리고 **실제 게이트로 과잉 탐지 0** 을 따로 확인했다(`--only dashboard-build`: `passed` · `tree_moved` 없음 · 드리프트 0).

- **한계** — 제자리에서 추적 산출물을 쓰는 **두 번째** 게이트는 실측하지 않았다(`sbom-generate` 는 현 트리에서 no-op) · **게이트를 돌리지 않으면 이 불변식은 작동하지 않는다**(검사 자신은 게이트가 아니다 — 보고서는 게이트가 끝나야 생긴다. F-24 와 같은 위치. 대신 게이트 목록이 이 성질을 가진 게이트를 포함하는지를 계약이 잰다) · 이 불변식은 **게이트 명령의 실패**와 **계약의 실패**를 보고서에서 구분하므로, `summary.required_failed` 만 보면 후자로 읽힐 수 있다 · R-13 · R-14 · R-15 · R-2/R-3/R-4/R-6/R-7 · attempt-025 의 R-17~R-19 는 그대로 열려 있다. 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-026/`.

## 2026-09-13 CR-14 attempt-025 — **'항상 허용'은 읽고 되돌리고 셀 수 있는 동의다 (F-33 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-025).** attempt-023 은 스킵돼 있던 에이전트 실행 루프를 살리면서 도구 호출이 **승인 게이트**에서 멈추는 것을 발견했고, 게이트를 끄는 대신 **제품의 승인 경로**(`get_approval_manager()` + `ApprovalDecision.ALWAYS_ALLOW`)로 동의를 만들었다. attempt-024 는 그 경로를 다시 쓰지 않았다 — "그 부여가 **무엇을 덮고**, **언제까지 살아 있고**, **사용자가 무엇에 동의했는가**"가 **재지 않은 채** 남았고, attempt-024 의 한계가 그것을 명시하고 있었다. (attempt-024 이전의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다.)

- **재현** — 증인 `attempt-025/repro/f33_always_allow_scope_witness.py` 를 **고침 전 트리 사본**(`git archive 19520cfd`)에서 돌려 **exit 1 · 깨진 요구 6건**(R4 시각 보존 · R1b 동의 문구 · R3 되돌리기 · R2×2 읽기 표면 · R5 자동 승인 관측)을 **이름으로** 얻었고, 고침 후 같은 스크립트가 **exit 0**(5/5) 이다.

- **설계는 그대로였다**(고침 전에도 성립하던 관측) — 부여는 **도구 하나 전체**(인자·경로·프로젝트 무관) · **만료 없음**(프로세스 재시작이 유일한 소멸 경로) · **프로세스 폭**(싱글턴). 결함은 그 사실들이 아니라 **감사 불가능성**이었다.

- **고친 다섯 자리** — ① `set[str]` → `dict[str, AlwaysAllowGrant]`(시각·근거·횟수 보존) ② 읽기 표면(`always_allowed_grants()` + `GET /api/approval/always-allowed`, **`/{request_id}` 보다 먼저 선언**) ③ `record_auto_approval()`(집행 지점·자동 승인 지점이 세고 **순수 조회는 세지 않는다**) ④ **경로 순서**(전용 경로를 만들자 `GET /{request_id}` 가 삼켜 404 — 계약을 돌려서 발견) ⑤ 동의 문구 + 화면의 부여 목록·해제, 그리고 **해제가 무엇을 되돌렸는지 이름을 댄다**(`revoked`).

- **계약** — `tests/test_cr14_always_allow_scope.py` **15건** + `ApprovalQueue.test.tsx` **4건** + `approvalApi.test.ts` **3건**(대시보드 신규 2파일).

- **검증(측정 완료)** — required gate **21/21 을 커밋된 후보 `a2f6f724` 에서 되돌리기 0회·단일 지문 `57e32c9a…` 에서 완주**(python-tests **6320 passed / 13 skipped / 16 deselected**(544.02s) · dashboard-test **82 files / 855 passed** · api-e2e 9 · accessibility 35 · python-benchmark 16 · clean-machine-runtime 41.6s(3018 파일) · docker-build 227.0s · master-e2e ✅6/❌0 · mypy 482 files clean · 드리프트 **0**(`dashboard_dist` 포함) · 실행 후 지문 재측정 동일). 세 배치가 별개 프로세스로 이어받았고, 편입 뒤 **마감 검사 PASS(exit 0)** — 편입 전에는 같은 검사가 FAIL exit 1 이었다.

- **재선언(D-52)** — 첫 선언 `440c5e06`(지문 `e8e464c6…`)은 **측정 전에** 낡았다: `src/antigravity_k/dashboard_dist/` 가 **추적되는 산출물**(F-01)이라 소스를 고치면 번들도 함께 움직여야 하고, fast 배치의 `dashboard-build` 가 실제로 29 삭제 + 29 생성 + 1 수정을 냈다(그때 게이트가 "다른 작업 트리"라며 이어받기를 **거부한 것은 옳다**). 번들을 후보 **안으로** 가져와 다시 선언했고, 빌드는 **두 번 돌려 바이트 동일**임을 확인했다 — `440c5e06` 은 **측정되지 않았다**.

- **한계** — **R-17**(부여의 범위·수명은 **드러낸 사실**이고 **정책 결정은 하지 않았다** — 선별 부여는 새 능력) · **R-18**(감사 기록은 **인메모리** — 부여 자체와 같은 수명) · **R-19**(대시보드 화면 계약은 **소스 계약 + vitest** 까지 — 사람이 보는 확인은 `manual-qa.md`) · 추적되는 빌드 산출물은 소스와 **같은 후보**에 · R-13 · R-14 · R-15 · R-2/R-3/R-4/R-6/R-7 · `/benchmark run` 을 끝까지 실행해 보지는 않았다. 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-025/`.

## 2026-09-13 CR-14 attempt-024 — **게이트 전수가 자기 스킵을 소유한다 (R-16 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-024).** attempt-021 이 등록부(`scripts/gate_skip_register.json`)를 만들면서 **스스로 한계로 적어 둔 문장**을 닫았다: "다른 파이프라인(개발자 ambient·CI matrix·weekly job)의 스킵은 이 등록부의 소관이 아니다." 그런데 같은 후보가 **required gate 21개**로 초록을 만들고 **그중 다섯이 테스트를 돈다** — 나머지 넷의 스킵은 **아무도 세지 않았고**, 한 게이트가 테스트를 조용히 빼도 초록은 그대로였다. 이 attempt 는 **스킵을 되찾은 것이 아니라**(스킵 13 → 13) 이미 도는 것들의 **가시성·소유**를 넓혔다. (attempt-023 이전의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다.)

후보: **커밋된 후보 `e288573490b56faa9d7673b1563f70f3e1ee389b`** · 코드 지문 **`7ae9af28…`**(`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `8aa01a42`(docs 전용).

- **먼저 셈했다 (넓히고 나서 세지 않았다)** — 러너별 스킵 표기를 스크래치 프로브로 **실측**(주장 아님): vitest **기본 리포터는 건수만** 낸다(`Tests 1 passed | 1 skipped (2)`) · `--reporter=verbose` 는 `↓ <파일> > <describe> > <테스트>` 를 낸다 · playwright `list` 리포터는 **이미 이름을 낸다**(`- 1 [chromium] › <파일>:<줄> › <이름>`) · 마커 없는 pytest `-q` 단독은 `N skipped` 만 남긴다.
- **세 자리를 닫았다** — ① `api-e2e`(`pytest … -q --tb=short` 단독)는 스킵이 생겨도 **어느 테스트인지 없었다**(등록부가 세야 할 대상이 이름을 잃으면 소유가 성립하지 않는다) → `-rs` ② `dashboard-test`(vitest 기본 리포터) → `--reporter=verbose` ③ `clean-machine-runtime` — 스크립트가 `--skip-e2e`·`--skip-wheel` 을 갖고 켜지면 요약에 `SKIP` 행이 생기면서 **게이트는 exit 0** 인데, **그 사실이 어디에도 적혀 있지 않았다** → 등록부가 `skip_channels` 로 선언하고 계약이 **스크립트의 모든 스킵 표기 ⊆ 선언**과 **게이트 명령이 그 플래그를 쓰지 않음**을 잰다. `accessibility-e2e` 는 **고칠 것이 없었다** — 그 성질을 계약으로 **고정**했다(리포터를 바꾸면 계약이 멈춘다).
- **소유를 세 겹으로 잠갔다** — **전수성**(`test_every_required_gate_is_classified_for_skip_visibility` 가 manifest 의 required 21개와 등록부 분류 21개를 대조 — 게이트를 추가하면 분류도 적어야 한다. 개수 고정이 아니라 목록 고정) + **귀속**(pytest `-v`/`-rs` · vitest verbose · playwright `list` 를 **실제 명령·설정에서** 확인, vitest·playwright 수집 소스의 스킵 마커는 tripwire 로 0건 유지) + **실제 실행**(마감 검사 `verify_attempt_close.py` **조항 8** 이 편입된 보고서에서 `close_check` 게이트의 스킵 건수를 읽는다 — 러너 요약 건수 + 색상 이스케이프를 벗긴 셸 `SKIP` 행. 게이트 안에서는 보고서가 아직 없어 순환하므로 **마감 단계가 유일한 자리**, F-24 와 같은 위치). 등록부를 읽을 수 없으면 마감 검사는 **침묵하지 않는다**.
- **검증** — **required gate 21/21 을 커밋된 후보 `e2885734` 에서 되돌리기 0회·단일 지문 `7ae9af28…` 에서 완주**: python-tests **6302 passed / 13 skipped / 16 deselected** 549.70s · python-benchmark **16 passed · 스킵 0건** · dashboard-test **81 files / 849 passed · 스킵 0건** · api-e2e **9 passed · 스킵 0건**(`-rs` 가 붙은 뒤 첫 실행) · accessibility-e2e **35 passed · 스킵 0건** · clean-machine **`SKIP` 행 0건**(41.72s) · docker-build 30.42s · master-e2e ✅6/❌0 · mypy 482 files clean · **드리프트 0** · 실행 후 지문 재측정 동일. 증가분 +11건은 등록부 계약 신규 5 + 마감 검사 이빨 6. **명령 2줄이 바뀌어 manifest sha256 이 이동**했다(`a18ff1e5…` → `86c40edc…`) — 마감 검사 조항 ④가 그 일치를 요구하므로 21개를 다시 돌렸다. 보고서 편입 뒤 **마감 검사 PASS**(편입 전 FAIL exit 1 — 사본으로 재구성해 실측).
- **증인** — `attempt-024/repro/r16_gate_skip_visibility_witness.py` — **고침 전 exit 1 / 고침 후 exit 0(5/5)**: A 테스트 게이트가 스킵을 테스트 단위로 귀속 · B 등록부가 required 게이트를 전수 분류(21 == 21) · C `close_check` 게이트의 실제 실행 스킵이 0건 · D 스크립트 게이트가 스킵 플래그를 쓰지 않는다(`{'clean-machine-runtime': ['--skip-e2e', '--skip-wheel', 'SKIP_E2E', 'SKIP_WHEEL']}`) · E vitest·playwright 수집 소스의 마커 0건.
- **마감 검사 이빨** — `tests/test_cr14_attempt_close.py::test_teeth_skip_reported_by_a_close_check_gate_is_rejected` 가 가짜 보고서에 `2 skipped` 를 심어 **실제로 거부되는지** 본다(증인 검사 C 와 다른 자리에서 같은 성질을 확인).
- **한계** — 등록부는 여전히 **required 게이트의 환경**만 본다(비-required·ambient·CI matrix·weekly job 은 각자 소유자) · 마감 검사가 보는 것은 **건수**다(러너가 건수를 내지 않는 형태로 스킵을 만들면 그 자리는 보이지 않는다 — 그래서 `per_test` 게이트가 귀속 플래그를 갖는 것이 계약이다) · R-13 · R-14 · R-15 · R-2/R-3/R-4/R-6/R-7 · **`/benchmark run` 을 끝까지 실행해 보지는 않았다** · **`ApprovalManager` 의 '항상 허용' 상태가 제품 경로에서 언제 만료되는지**는 재지 않았다. 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-024/`.

---

## 2026-09-13 CR-14 attempt-023 — **스킵된 에이전트 루프는 제품 결함이 아니라 계약 드리프트로 죽어 있었다 (F-32 · `orchestrator-refactor-rewrite` 폐쇄)** (판정 NO-GO 유지)

> **이 절은 attempt-023 의 실측이다.** 등록부의 **마지막 미검증 능력** `orchestrator-refactor-rewrite`(2건)를 닫아 **소유자 없는 스킵 0건 · 미검증 능력 0건**이 됐다. 두 테스트는 `OrchestratorAgent` 리팩토링 뒤 **조건 없는** `@pytest.mark.skip` 이 되어 어떤 환경에서도 돌지 않았지만, **제품 코드는 고칠 필요가 없었다** — 관측하니 두 루프는 **돌고 있었다**. 막은 것은 **계약 드리프트**였다: 더블이 리팩토링 이전 인터페이스를 흥내냈고(`manager.router` 부재 · 인자를 요구하는 `get_model_info`), 승인 게이트·셀 경로 경계는 그 테스트보다 **나중에** 생겼다. 고침은 **게이트를 하나도 약화하지 않았다**(동의는 제품의 승인 경로로, 경계는 그대로, 재시도 예산은 고정). (attempt-022 이전의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다.)

후보: **커밋된 후보 `ed9e225a72a0447e9655a44e13bde5b875e2991f`** · 코드 지문 **`37b76cb8…`**(`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `87cd7440`·단일 사이트 정정 `bc8e8d1a`(둘 다 docs 전용).

- **무엇을 닫았나 — "고칠 것이 남았다"가 "고칠 것이 제품에 있었다"는 뜻은 아니다** — 조건 없는 스킵은 ① 제품이 못 하는 일 ② 재는 도구가 대상을 놓친 일을 **같은 표기**로 만든다. 등록부는 ①로 적어 두었고("state graph 구조에 맞게 재작성"), 그 판단은 **증거 없이** 내려진 것이었다. 관측(고침 **전** 코드를 스킵 해제해 돌리면 `2 failed, 4 passed`)이 답을 줬다: 실패 스택이 **제품 코드 안**에서 난다 — 제품 루프는 돌고 있었다.
- **막은 다섯 자리** — ① 더블 2개에 `manager.router` 가 없다(`tool_loop.run_loop` 는 `manager.router.get_combo(...)` 를 무조건 부르고, 실제 `ModelManager` 는 생성자에서 항상 만든다) ② 더블의 `get_model_info(name)` 이 인자를 요구한다(실제는 `status()` 별칭·**무인자** — 틀린 쪽은 더블) ③ 도구 호출이 **승인 게이트**에서 멈춘다(CR-04/CR-05 가 그 테스트 이후에 생겼다) ④ 스크립트가 프로젝트 루트 **밖** 인터프리터로 실행하려 해 **셀 경로 경계가 정당하게 거부**한다 ⑤ `calls == 2` 가 더블의 이중 계산과 **패키지 기본 config 의 재시도 예산**에 걸려 있다.
- **고침(게이트 약화 0건)** — 동의는 **제품의 승인 경로**(`get_approval_manager()` + `ApprovalDecision.ALWAYS_ALLOW`)로 만들고 · 경계는 그대로 두고 명령을 **루트 기준 상대 경로**로 바꾸고 · 더블이 `_answer()` 한 곳에서 한 턴을 한 번만 세고 · 재시도 예산을 1로 **고정**한다. 두 테스트는 조건 없이 돌며 **6 passed / 0 skipped**.
- **닫아도 관측은 줄지 않는다** — 등록부는 두 파일을 `closed` 로 옮기되 **`observed_files` 에 남겼다**(무조건 스킵이 돌아오면 대조가 즉시 실패). 곁들여 `KNOWN_GAP` **0건**이 계약의 침묵이 되지 않도록, 0건일 때는 경계 문서가 **"미검증 능력 0건"을 명시**해야 한다.
- **검증** — **required gate 21/21 을 커밋된 후보 `ed9e225a` 에서 되돌리기 0회·단일 지문 `37b76cb8…` 에서 완주**: python-tests **6291 passed / 13 skipped / 16 deselected** 559.48s · python-benchmark 16 · dashboard-test 849(81 files) · docker-build 35.82s · clean-machine 43.64s · master-e2e ✅6/❌0 · api-e2e 9 · accessibility 35 · dependency-audit-python high/critical 0건 · mypy 482 files clean · **드리프트 0** · 실행 후 지문 재측정 동일. 보고서 편입 뒤 **마감 검사 PASS**(편입 전 FAIL exit 1 — 사본으로 재구성해 실측).
- **증인** — `attempt-023/repro/f32_contract_drift_witness.py` **9/9**(A: 고침 전 **기준 커밋 `fba13c6c` 의 실제 코드**를 /tmp 사본에서 스킵 해제하면 실패하고 그 실패가 `manager.router`·`get_model_info` 에서 난다 · B: 고침 후 6 passed / SKIPPED 0 · C: 닫힌 파일에 무조건 스킵을 **다시 심으면** 그 스킵이 관측되어 등록부 대조가 실패).
- **한계** — **소유자 없는 스킵 0건**(남은 13건은 mlx 4 · unsloth 7 · access-pin 2 로 전부 소유자가 있다) · ~~R-16~~(**attempt-024 에서 닫혔다** — 등록부가 required 게이트 21개 전수 분류를 갖고, `api-e2e` `-rs` · `dashboard-test` `--reporter=verbose` · `clean-machine-runtime` `skip_channels` 를 계약이 실제 명령에서 재며, 마감 검사 조항 8 이 편입된 보고서에서 게이트별 스킵 건수를 읽는다 · 스킵 13 → 13) · R-13 · R-14 · R-15 · R-2/R-3/R-4/R-6/R-7 · **`/benchmark run` 을 끝까지 실행해 보지는 않았다**(로컬 모델 pull 필요 — attempt-022 가 확인한 것은 라우팅 해석까지다) · **`ApprovalManager` 의 '항상 허용' 상태가 제품 경로에서 언제 만료되는지**는 재지 않았다(테스트 범위 밖이지만 보안 질문이다). 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-023/`.

---

## 2026-09-13 CR-14 attempt-022 — **배포된 코드가 config 에서 찾는 이름을 config 가 소유한다 (F-31 · `config-models-unregistered` 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-022).** 등록부(`scripts/gate_skip_register.json`)의 미검증 능력 중 `config-models-unregistered` 를 **삭제가 아니라 능력 복원으로** 닫았고, 그 과정에서 그 항목의 한 축이 **테스트만의 약속이 아니라 배포 경로**임을 찾아 **F-31** 을 함께 닫았다: `/benchmark run`(인자 없음)의 기본 타겟은 `BenchmarkHarness._default_targets()` 가 **코드에 갖고 있는** 콤보 이름 `collective-council` 인데, 2026-05 세대 정리(`e462a8aa` · `d131dc71`)가 그 콤보를 **의도 기록 없이** 지운 뒤에도 코드가 남아 **매 실행마다 오류 행(점수 0)** 을 기록했다(`_execute_single` 이 `ComboNotFoundError` 를 삼킨다 — 사용자에게는 "집단지성이 단일 모델보다 나쁘다"로 보인다). 유일한 회귀 테스트가 `registry._raw` 에 **합성 매핑을 주입**해 **실제 config 가 무엇을 소유하는지는 결코 묻지 않았던 것**이 오래 숨긴 이유다(F-18/F-24/F-27/F-28/F-29/F-30 에 이어 **일곱 번째** 같은 병). **제품 런타임 코드 변경은 0줄**이다(바뀐 것은 설정·테스트·계약·등록부). (attempt-021 이전의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다: F-30/R-8 — 스킵 감사 · F-29/R-5 — CR-12 소관 재확인 · F-28/R-11 — 파이프라인이 마감 절차를 부른다 · F-27/R-12 — 이어받기 판단을 게이트 규칙에 위임 · F-26 · F-25/R-10)

후보: **커밋된 후보 `d7e66a59c13ff57951422baef89c343cb146a2b6`** · 코드 지문 **`6a51100f…`**(`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `de62e509`(docs 전용).

- **F-31(제품 결함 — 배포된 `/benchmark` 의 기본 경로) — 발견·폐쇄.** 재현(실제 config): 기본 타겟은 `['collective-council']` **하나**이고 그 이름은 콤보도 모델도 아니며 `route("collective-council")` 은 `ComboNotFoundError` 로 끝난다. 고침은 **설정 복원**이다 — `config.yaml`(워크스페이스 + 패키지 **2부**, 바이트 동일이 계약)에 `collective-council` 을 `strategy: collective` 콤보로 되돌리고(멤버는 현재 로스터가 소유한 로컬 3모델: `qwen3.8` · `hf.co/unsloth/gemma-4-31B-it-GGUF:Q5_K_M` · `deepseek-r1:70b`), gemma-4-31B 를 reasoning 로스터에 복원했다(`provider: ollama` 명시 — 이름에 슬래시가 있어 `_infer_provider` 가 클라우드로 오인한다). 이로써 `RouteStrategy.COLLECTIVE` 경로가 **설정에서 처음으로 도달 가능**해지고, 스킵돼 있던 두 테스트(`Issue #57`)가 조건 없이 돈다.
- **계약(실제 파일로만 잰다)** — `tests/test_cr14_default_target_config_contract.py` 6건: 기본 타겟이 config 소유인가 · 비교가 성립하는가(평의회 + 개별 모델) · 콤보가 `collective` 전략에 참여 3개 이상인가 · config 안의 참조가 로스터에 있는가 + **이빨 2건**(tmp 에 **실제 YAML 을 써서** 콤보를 지우거나 멤버를 빼면 같은 검사가 실패한다 — 실패해야 할 입력에서 실패하지 않는 계약은 장식이다).
- **F-31a — 등록부의 구멍도 함께 닫았다.** 관측 목록을 선언(`entries`)에서 파생시키면 항목을 닫는 순간 그 파일이 관측에서 **사라져** 다시 스킵돼도 아무도 모른다 — **닫는 일이 관측을 줄이는** 구조였다(F-30 의 병을 한 층 위에서 반복). 관측 대상을 `observed_files` 로 **고정**하고 닫힌 항목을 `closed` 에 적어 그 파일이 계속 관측된다.
- **스킵 17 → 15** — 되살린 테스트 2건이 조건 없이 돈다(`tests/test_upgrade_v6_9.py` **21 passed / 0 skipped**). 남은 15건은 mlx 4 · unsloth 7 · access-pin 2 · **에이전트 실행 루프 2(`orchestrator-refactor-rewrite`, review_due 2026-10-15)** 이다.
- **검증** — **required gate 21/21 을 커밋된 후보 `d7e66a59` 에서 되돌리기 0회·단일 지문 `6a51100f…` 에서 완주**(python-tests **6289 passed / 15 skipped / 16 deselected** 549.42s · python-benchmark 16 · dashboard-test 81 files/849 tests · docker-build 226.74s · clean-machine 42.58s · master-e2e ✅6/❌0 · api-e2e 9 · accessibility 35 · dependency-audit-python high/critical 0건 · 드리프트 0 · 실행 후 지문 재측정 동일) + 보고서 편입 뒤 **마감 검사 PASS** — 편입 전에는 같은 검사가 FAIL exit 1(사본으로 재구성). 세 배치가 **별개 프로세스**로 스스로 이어받았다(18 → 19 → 21).
- **증인** — `attempt-022/repro/f31_default_target_witness.py`(실물 0건 · 콤보 제거 재구성 1건 + `ComboNotFoundError` · 멤버 제거 드러남) · `f31a_register_observation_witness.py`(고친 전 규칙에서 닫힌 파일이 관측에서 사라진다 · 게이트 환경 실제 스킵 15건 · 닫힌 파일 0건).
- **한계** — `config-models-unregistered` 는 닫혔다(능력으로 되돌렸다) · **`orchestrator-refactor-rewrite`(등록부의 마지막 미검증 능력 2건)는 남는다** · R-16 · R-13 · R-14 · R-15 · R-2/R-3/R-4/R-6/R-7 · **`/benchmark run` 을 끝까지 실행해 보지는 않았다**(로컬 모델 pull 필요 — 확인한 것은 라우팅 해석까지다). 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-022/`.

---

## 2026-09-13 CR-14 attempt-021 — **게이트에서 조용히 사라지는 테스트를 소유한다 (F-30 / R-8 감사)** (판정 NO-GO 유지)

> **직전 실측(attempt-021 — 최신은 위 attempt-022 절).** attempt-013 이 스스로 "이 감사를 하지 않았다"고 적어 둔 항목(R-8)을 수행했다: **어느 테스트가 왜 조건부로 스킵되는지, 그중 제품 능력을 실제로 재는 것이 있는지**. 게이트 환경을 lock 에 고정한 F-18 은 도구 출처를 바로잡았지만 그 대가가 조용했다 — 스킵이 **6~13 → 40** 으로 뛰었고 그중 **23건은 출하 능력(PDF/DOCX 수집)** 인데 **어떤 파이프라인도 그 extra 를 설치하지 않았다**. **제품 런타임 변경은 0건**이다. (attempt-020 이전의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다: F-29/R-5 — CR-12 소관 재확인 · F-28/R-11 — 파이프라인이 마감 절차를 부른다 · F-27/R-12 — 이어받기 판단을 게이트 규칙에 위임 · F-26 — 그 절차를 직접 돌려 찾은 조용한 손실 · F-25/R-10 — 마감을 명령 하나로 · F-24/R-9 — 마감 검사.)

후보: **커밋된 후보 `1b0a024c790c79b58a5c377f865bfec7dc82bbea`** · 코드 지문 **`15e79e84…`** (`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `3cce93f2`(docs 전용).

- **감사의 출발점은 "고침"이 아니라 "세는 일"이었다** — 각 attempt 의 `gate-report.json` 에서 직접 인용: attempt-011 `6200/13`(ambient) · 012 `6215/6`(ambient) · 013 `6174/40`(**lock 고정**) · 020 `6251/40` · **021 `6280/17`**. 수집 총계로 보정하면 **돌던 테스트 34건이 스킵으로 옮겨졌고 아무도 세지 않았다.**
- **F-30 — 어느 파이프라인이 그 능력을 재는가를 파일에서 확인했다**: `grep -rn "extra documents\|pypdf" .github/ scripts/` 가 **비어 있다**(아무도 설치하지 않는다) · mlx 는 `ci.yml` 매트릭스(`deps: [base, rag, mlx]`)와 `weekly-drift.yml`(64행) · unsloth 는 `weekly-drift.yml`(99행) · access-pin 은 `tests/test_cr04_shell_api_boundary.py` 가 게이트 안에서 PIN 을 세우고 401 을 잰다(121·176행). **남는 것은 소유자 없는 4건뿐**이다.
- **미검증 능력 4건(이 감사의 가장 값어치 있는 결과)** — `OrchestratorAgent` 리팩토링 뒤 두 테스트가 **조건 없는** `@pytest.mark.skip` 이 되어 **어떤 환경에서도 돌지 않는다**(에이전트가 프로그램을 만들고 실행하는가 · 코드 전용 답변에서 품질 재시도가 도는가). 그리고 `config.yaml` 에 gemma-4-31B · collective-council 이 없어 **제품 설정의 약속이 이행됐는지를 아무도 재지 않는다**. 둘 다 `KNOWN_GAP` 으로 owner·plan·만료(2026-10-15)를 갖고 `docs/ga/CR14_GATE_COVERAGE_BOUNDARY.md` 에 게시됐다.
- **계약(조용한 변화 금지)** — `tests/test_cr14_gate_skip_register.py` 가 등록부와 **실제로 돌린 게이트 환경**을 한 건씩 대조한다. `--extra` 목록은 게이트 파일에서 읽으므로 누가 `documents` 를 빼면 23건이 되돌아와 **거기서** 드러난다. 증인 **12/12**(이빨 ⑦ 이 그것을 **실행으로** 확인).
- **검증** — **required gate 21/21 을 커밋된 후보 `1b0a024c` 에서 되돌리기 0회·단일 지문 `15e79e84…` 에서 완주**(python-tests 538.61s · python-benchmark 16 · docker-build 237.44s · clean-machine 42.11s · 드리프트 0 · 실행 후 지문 재측정 동일) + 보고서 편입 뒤 **마감 검사 PASS**. 세 배치가 **별개 프로세스**로 스스로 이어받았다(18 → 19 → 21).
- **곁들여 찾은 내 결함** — 증인 ⑥ 이 처음 아무것도 물지 못했는데, 원인은 **계약이 *측정*이 아니라 *주장*(등록부)을 읽고 있었던 것**이었다(F-29 와 같은 병이 내 계약에 있었다). 증인을 계약에 맞추는 대신 **계약을 고쳤다**. F-18/F-24/F-27/F-28/F-29 에 이어 **여섯 번째** 같은 병이며, 이번에는 계약을 만드는 과정에서 잡혔다.
- **한계** — R-8 닫힘 · **R-16(신규)** 등록부는 `python-tests` 의 환경만 소유한다 · R-11 닫힘 · R-13 · R-14 · R-15 · R-2/R-3/R-4/R-6/R-7 · **미검증 능력 4건은 이름을 갖고 남았다**(닫지 않은 것이 아니라 **결정을 기다리는 것**이다). 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-021/`.

---

## 2026-09-13 CR-14 attempt-020 — **CR-12 소관 재확인(R-5): 개정된 계약이 요구를 지키는가 (F-29 폐쇄)** (판정 NO-GO 유지)

> **직전 실측(attempt-020 — 최신은 위 attempt-021 절).** attempt-014(F-22)는 CR-12 의 계약(`tests/test_cr12_docs_alignment.py`)을 개정했다 — README 가 SHA **리터럴**을 담으라는 성립 불가능한 요구를 "값을 소유한 문서를 **가리킬 것**"으로 바꿨다. 그 개정을 **CR-12 소관으로 다시 재는** 것이 판정서 §6 의 `0-h`(R-5)였다. 재확인은 문장을 다시 읽는 일이 아니라 **요구를 다시 재는** 일이고, 재어 보니 두 자리에서 **확인이 의도와 달랐다** — **제품 런타임 변경은 0건**이다. (attempt-016~019 의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다: F-24/R-9 — 마감 검사 · F-25/R-10 — 마감을 명령 하나로 · F-26 — 그 절차를 직접 돌려 찾은 조용한 손실 · F-27/R-12 — 이어받기 판단을 게이트 규칙에 위임 · F-28/R-11 — 파이프라인이 마감 절차를 부르고 릴리스가 그것에 막힌다.)

후보: **커밋된 후보 `a590786513403b5da535ec13eef0807ea51e4676`** · 코드 지문 **`aad2601c…`** (`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `8cd03b8c`(docs 전용).

- **F-29 — 두 자리 모두 "검사가 대상이 아니라 대상의 옛 모습/그림자를 본다"**: ① `README_VALUE_OWNER in text` — 요구는 "README 가 값을 소유한 문서를 **가리킨다**"인데 확인은 "그 **이름**이 어딘가 있다"였다: 산문에 이름만 적거나, 링크를 **다른 문서**로 바꾸거나, 소유자 이름을 링크하면서 **그 파일이 없어도** 통과했다(F-28 과 같은 병 — 의도가 아니라 표기). 이제 **실재하는 링크**를 요구한다(링크 대상의 파일명이 소유자이고 그 파일이 저장소에 있다). ② `"미커밋" in checklist` 는 attempt-001 에서는 참이었지만 후보를 커밋한(attempt-009) 뒤로는 **과거 attempt 기록 행**이 그 문자열을 계속 공급해 조항이 **항상 참**이 됐다(아무것도 보지 않았고, 메시지는 현재에 대해 거짓을 말했다) — 요구를 **현재 상태 줄**(`**현재:` 로 시작하는 그 한 줄)로 좁혀, 커밋된 후보·GA 승인 없음을 말하고 그 줄이 미커밋을 주장하면 실패하게 했다(과거 행의 "미커밋" 은 **기록**이므로 그대로 둔다 — 기록을 조항에 맞춰 고치지 않는다).
- **요구를 약화시킨 자리는 없다** — 계약 26 → **28건**(이빨 2 신규)이고, 실물 README·체크리스트가 개정 전·후 **둘 다** 통과하는 것을 증인이 보인다. 곁들여 docs/17 의 C12-05 수용 기준 문장이 attempt-001 시점 그대로여서 "코드 미커밋"을 현재 요구처럼 적고 있던 자리도 계약에 맞춰 정정했다.
- **증인 — 규칙을 흉내내지 않는다**: `CR-12/attempt-002/repro/cr12_r5_review_witness.py` **12/12**. 개정 **전** 규칙은 `git show 3fb3fcb9:tests/test_cr12_docs_alignment.py` 로 **실제 코드를 읽어** 임시 트리에 놓고 돌린다(attempt-018 의 교훈 — 스텁은 규칙이 바뀌면 조용히 죽는다). A 실물 문서는 개정 전·후 둘 다 통과 · B 품질 낮은 입력 3종(산문만 · 다른 문서 링크 · 없는 파일 링크)은 **전자만** 통과(구멍의 실증)이고 정상 링크는 기준선으로 통과 · C 과거 기록의 "미커밋" 은 통과하되 현재 줄이 주장하면 거부.
- **검증** — **required gate 21/21 을 커밋된 후보 `a5907865` 에서 되돌리기 0회·단일 지문 `aad2601c…` 에서 완주**(python-tests **6251 passed / 40 skipped / 16 deselected** 522.15s — 증가분 24건은 attempt-019(배선 계약 22건)와 이번 계약 26 → 28건이며 skipped·deselected 는 불변이다 · python-benchmark 16 · dashboard-test **849 passed(81 files)** · docker-build 35.45s · clean-machine 42.16s(`git archive HEAD` 로 커밋된 트리 검증) · master-e2e 6/6 100% · api-e2e 9 · accessibility 34 · dependency-audit-dashboard 0건 · `data/`·`dashboard_dist` 드리프트 **0** · 실행 후 지문 재측정 **동일** · 인벤토리 변동 없음) + 보고서 편입 뒤 **마감 검사 PASS(exit 0)**(편입 전에는 같은 검사가 `FAIL exit 1` — `선언된 지문을 측정한 gate 보고서가 없다`). 세 배치가 **별개 프로세스**로 **스스로** 이어받았다(18 → 19 → 21) — F-26·F-27 이 만든 성질이 이 attempt 에서 다시 실측됐다.
- **일반 교훈(다음 attempt 에 그대로 쓸 수 있는 문장)** — **개정한 계약은 다시 재야 한다**: 요구를 옮긴 사람의 문장은 증거가 아니다. 그리고 계약을 만나면 먼저 물어라 — **이 확인은 의도가 실패해야 할 입력에서 실패하는가?** 그 입력을 증인에 넣지 않은 계약은 조항이 아니라 장식이다. 이 저장소에서 같은 병은 F-18·F-24·F-27·F-28·F-29 로 **다섯 번** 나왔고 처방은 매번 같았다: 규칙은 **한 곳**이 소유하고 다른 주체는 **묻는다**; 확인은 **의도**를 향하고 의도가 실패해야 할 입력으로 시험한다.
- **한계** — **R-5 는 닫혔다** · R-11(닫힘 — 이번 측정도 파이프라인이 부르는 **같은 명령**을 돌렸지만 시작은 사람이 했다) · R-13(기록 뒤 게이트 재개 시 의도된 중단) · **R-14**(러너에서의 실행은 러너만이 답한다) · **R-15**(태그 직전 버전 상향 커밋이 생기면 재선언 + 재측정 필요) · R-2 · R-3 · R-4 · R-6 · R-7. **C14-08(독립 검토·출시 책임자 배정)은 여전히 미배정**이며 그것이 NO-GO 의 첫 번째 이유다. 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-020/`(로그 4 + 서사 7) · `.../CR-12/attempt-002/`(증인·로그).

---

## 2026-09-13 CR-14 attempt-019 — **마감을 기계가 돌린다 (R-11 폐쇄) + F-28 폐쇄** (판정 NO-GO 유지)

> **직전 실측(attempt-019 — 최신은 위 attempt-020 절).** attempt-016~018 은 "선언한 초록의 출처"를 확인하는 장치 — 마감 검사(`scripts/verify_attempt_close.py`)와 마감 절차(`scripts/run_attempt_close.py`) — 를 만들었지만 **사람이 돌려야만** 작동했다. 계약은 **돌았을 때만** 문다. 이 attempt 는 그 마지막 구멍을 파이프라인으로 옮겼다 — **제품 런타임 변경은 0건**이다. (attempt-017·018 의 실측 기록은 판정서 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md) 의 같은 이름 절이 소유한다: F-25/R-10 — 마감을 명령 하나로 · F-26 — 그 절차를 직접 돌려 찾은 조용한 손실 · F-27/R-12 — 이어받기 판단을 게이트 규칙에 위임하고 거부를 조용하지 않게.)

후보: **커밋된 후보 `43cde98ea8ccf5d9d6a77996e571ecec209eefd3`** · 코드 지문 **`7f19c3a7…`** (`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `0c772245`(docs 전용).

- **무엇을 만들었나** — `.github/workflows/ga-close.yml` 이 마감 절차를 부른다(`--stage all`). 트리거 셋: `workflow_call`(릴리스가 부른다) · `workflow_dispatch` · **`schedule` 매주 월요일 03:00 UTC(스스로 돈다)**. `.github/workflows/release.yml` 의 `publish-pypi`·`github-release` 가 `needs: [build, ga-close]` — **마감 절차가 실패하면 출하 단계가 시작되지 않는다**. 릴리스는 `uses:` 한 줄로 **부르기만** 하고(스텝 복제 0), **게이트 목록도 순서도 워크플로에 없다**(매니페스트·절차 스크립트가 소유 — 매니페스트에 게이트가 늘면 워크플로는 고치지 않아도 따라간다). `fetch-depth: 0` 은 필수다(지문은 git 객체에서 계산되고 후보..HEAD 울타리도 이력으로 판정한다). 실패해도 보고서를 `if: always()` 로 아티팩트에 남긴다.
- **배선은 계약이 소유한다** — `tests/test_cr14_close_pipeline_contract.py` **22건**: 절차를 부르고 게이트 목록을 옮겨 적지 않는다 · 부를 수 있고 스스로 돈다 · publish 가 `needs` 사슬로 막힌다(직접·간접) · 부르기만 하고 허용 키만 쓴다 · 시도 이름이 **소유자의 글로브**(`verify_attempt_close.REPORT_GLOB`)에 맞고 아티팩트 경로가 **절차의 함수**(`_artifacts_output`)와 같다 · 전체 이력·`continue-on-error` 금지. 이빨 9건은 **배선을 실제로 풀어** 본다(`needs` 제거 · 간접 의존만 · 수동 실행 전용 · 게이트 목록 복제 · 글로브 밖 시도 이름 · 얕은 체크아웃 · `continue-on-error` · 스텝 복제 · 허용되지 않는 키).
- **F-28(신규/폐쇄)** — 그 배선이 `release.yml` 의 `needs` 를 늘리자 `python-tests` 가 **1 failed**(6248 passed / 535.60s) 였다: `tests/test_rel01_clean_build_sbom.py::TestWorkflowOrder::test_publish_is_gated_behind_build_job` 가 요구를 **문자열** `"needs: build"` 로 확인하고 있었다 — **의도**(publish 는 build 가 성공해야 시작한다)는 지켜졌는데 선행 조건이 하나 늘자 깨졌다. 요구는 그대로 두고 `needs` 목록을 **파싱**해 포함 여부를 본다(이빨 유지 — `needs: [ga-close]` → 실패). 그 수정이 지문을 옮겨 앞선 선언이 낡았고 attempt-019 **안에서 재선언**했다(측정 전 · 그 시점의 측정은 실패로 중단).
- **F-27 이 실제 흐름에서 작동했다** — 재선언 뒤 낡은 부분 보고서는 `ERROR 이어받을 수 없다: previous report is for candidate '43a947a5', not '0c772245'` + `rm <보고서>` 안내 + **exit 2** 로 막혔고 **덮어쓰지 않았다**(attempt-017 이라면 조용히 새로 시작해 앞 배치 초록을 버렸을 자리다). 증거: `attempt-019/logs/stale-report-refusal.txt`.
- **검증** — **required gate 21/21 을 커밋된 후보 `43cde98e` 에서 되돌리기 0회·단일 지문 `7f19c3a7…` 에서 완주**(python-tests **6249 passed / 40 skipped / 16 deselected** 535.13s · python-benchmark 16 · dashboard-test **849 passed(81 files)** · docker-build 231.66s · clean-machine 42.10s `ref: HEAD`(3010 파일) · api-e2e 9 · accessibility 35 · `data/`·`dashboard_dist` 드리프트 0 · 실행 후 지문 재측정 동일) + 보고서 편입 뒤 **마감 검사 PASS(exit 0)**(편입 전 FAIL exit 1). 증인 `attempt-019/repro/f28_close_pipeline_witness.py` **22/22**(실제 워크플로 파일 기준선 9 + 푼 변형 8 + **측정 동일성**(`--stage all` == `fast ∪ tests ∪ heavy`) 3 + 시도 이름·아티팩트 2).
- **한계** — **R-14(신규)** 배선은 계약이 정적으로 소유하지만 **이 저장소는 GitHub Actions 를 로컬에서 실행할 수 없다**: 러너에서의 21/21 은 러너만이 답한다(그래서 보고서를 아티팩트에 남긴다) · **R-15(신규)** 태그 직전 버전 상향 커밋(코드 스코프)이 생기면 선언이 낡아 `ga-close` 가 멈춘다 — 태그 전에 재선언 + 재측정이 필요하다(그것이 "기계가 확인한 주장"의 값이다) · R-13(기록 뒤 게이트 재개 시 중단 — 이 attempt 가 실제로 밟았고 시료를 남겼다) · R-2 · R-3 · R-4 · R-6 · R-7. 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-019/`.

## 2026-09-13 CR-14 attempt-016 — **선언한 초록의 출처를 게이트 밖에서 확인한다 (F-24, R-9 폐쇄)** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-016).** attempt-015 는 울타리 이동 탐지기를 계약으로 세우면서 한 가지를 정직하게 남겼다(R-9): 그 계약은 "보고서가 **있으면** 정합하다"는 것만 볼 수 있고 **보고서의 존재**를 요구할 수 없다 — 보고서는 게이트 실행이 끝날 때 쓰이므로 그 실행 **안에서는** 존재할 수 없다(순환). 그래서 attempt-013 의 21/21 이 HEAD 가 아닌 트리를 가리키게 됐을 때 "그 초록의 출처가 있는가"를 아무도 묻지 않았다. 이번 attempt 는 그 자리를 **게이트 밖의 마감 검사**로 채웠다 — **제품 런타임 변경은 0건**이다.

후보: **커밋된 후보 `0c33aa2e8149351cbf0e3b78e88cb1dbe2f3e913`** · 코드 지문 **`1b84209e…`** (`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `98e2edc5`(docs 전용).

- **왜 게이트가 아닌가** — 마감 검사를 게이트 인벤토리에 넣으면 게이트 실행이 끝날 때 쓰이는 보고서를 그 실행 **안에서** 요구해 순환한다. 검사의 **위치 자체가 설계**다: `scripts/verify_attempt_close.py` 는 attempt 마감 절차이고, "선언한 초록의 출처가 있는가"는 측정이 **끝난 뒤**에만 물을 수 있는 질문이다.
- **판정 7항목** — ① 선언 자리(후보 40hex·지문 64hex·게이트 수치 4개)가 각각 하나 ② **선언된 지문을 측정한 보고서가 있는가**(R-9) ③ 그 보고서가 **이름 붙인 커밋의 트리**를 쟀는가 ④ 보고서의 manifest sha256·required **목록**이 현재 manifest 와 같은가 ⑤ required 전부 passed·exit 0·같은 지문에 실패한 실행이 없는가 ⑥ **카드의 게이트 수치가 보고서 집계와 같은가**(손으로 적은 수치 금지) ⑦ 후보..HEAD 코드 스코프 변경이 없는가.
- **규칙 단일화** — 커밋 측 지문 계산이 세 곳에 흘어질 뻔했으므로 `scripts/ga_gate.py` 의 `tree_fingerprint_of_commit`·`code_scope_changes` 로 올렸고, 게이트·울타리 계약·마감 검사가 **그 함수를 그대로** 쓴다(계약의 자체 구현은 삭제 → 위임, 위임 뒤에도 계약 13건 통과).
- **게이트 전/후로 뒤집히는 것을 실측** — ① attempt-015 의 값이 선언된 실제 카드로 **PASS**(이미 옳게 닫힌 attempt 를 통과시킨다) ② 새 후보를 선언하고 게이트를 돌리기 **전**에 **FAIL exit 1**(`선언된 지문을 측정한 gate 보고서가 없다`) ③ 게이트 21/21 뒤 보고서를 증거 트리에 편입하자 **PASS exit 0**. 두 결과를 가른 것은 **보고서의 존재 하나**다. 증인은 실제 카드로 5개 상태를 두드려 **5/5 기대대로**(기준선 0건 · 보고서 없음 · 손으로 적은 수치 · 옛 후보 선언 → `fence` 위반 4개 경로 · 보고서 손상).
- **검증** — **required gate 21/21 을 커밋된 후보 `0c33aa2e` 에서 되돌리기 0회로 단일 지문 `1b84209e…` 에서 완주**(python-tests **6207 passed / 40 skipped / 16 deselected** 533.24s · python-benchmark 16 passed · docker 304.0s · clean-machine 41.4s `ref: HEAD` · `data/`·`dashboard_dist` 드리프트 0 · 실행 후 지문 재측정 동일) + **마감 검사 PASS(exit 0)**.
- **한계** — **R-10(신규)** 마감 검사는 사람이(또는 절차가) 돌려야 작동한다(게이트가 아니므로 자동 강제되지 않는다 — 다음 attempt 의 첫 후보이다) · R-2(값 자체의 옳음은 보고서·카드가 소유) · R-3(`clean-machine-runtime` 은 `ref: HEAD` 시점 의존) · R-4(`vault_data`) · R-6(스코프 불일치는 C14-F23-3 소관) · R-7(심볼릭 링크 전제는 계약이 검사). 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-016/`.

## 2026-09-13 CR-14 attempt-015 — **사람이 눈으로 찾던 울타리 이동을 계약이 찾는다 (F-23, R-1 폐쇄)** (판정 NO-GO 유지)

> **이 절은 attempt-015 시점의 실측이다 — 최신은 위의 attempt-016 절.** attempt-014 는 F-22 로 **원인**(README 의 휘발성 값)을 닫았지만, attempt-013 의 이동을 찾아낸 것이 **사람의 눈**이었다는 사실을 한계 **R-1**(“지문 이동에 사후 탐지 계약이 없다”)로 남겼다. 이번 attempt 는 그 문장을 계약으로 바꿨다 — **제품 런타임 변경은 0건**이다(바뀐 것은 검증 장치와 그를 강제하는 계약).

후보: **커밋된 후보 `b5729b61efdbc034327a644b92a7de89921af3d8`** · 코드 지문 **`b637d8b9…`** (`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다) · 선언 커밋 `13ff9140`(docs 전용).

- **탐지기의 핵심 선택** — **작업 트리를 쓰지 않고 git 객체만으로** 커밋의 코드 지문을 계산한다(`git ls-tree` + `git cat-file --batch`). 그래서 “그때의 초록이 지금도 이 후보의 것인가”를 **미커밋 진행분과 무관하게** 물을 수 있다 — R-1 이 “진행 중 상태와 구분해야 해서 단순 동등 비교로는 만들 수 없다”고 한 지점이 여기서 성립한다(계약이 보는 것은 **커밋된 이력**이고, 진행 중분은 커밋되는 순간 후보가 되어 첫 조항이 값을 요구한다). 지문 함수는 게이트가 **실제로 쓰는** `_tree_fingerprint` 를 그대로 가져다 쓴다(복제하면 게이트 규칙이 바뀌어도 옛 규칙을 검사하는 거짓 통과가 된다 — attempt-013 F-18 과 같은 병).
- **조항 4개** — ① 선언된 지문 == 선언된 후보 커밋 **트리** 지문 ② 후보..HEAD 사이 **코드 스코프 변경 0건**(F-22 의 탐지기) ③ 지문 함수와 `git status` 가 코드 스코프 청결에 대해 **같은 말**(제외 목록을 넘혀 파일을 조용히 무시하면 깨진다) ④ 보고서가 이름 붙인 커밋의 트리 == 보고서의 지문. ②는 “울타리가 **움직였는가**”, ③은 “울타리가 **보이는가**”를 본다.
- **이빨** — 실제 저장소 건드리지 않고 `/tmp` 의 `git worktree` 사본에서 후보 뒤에 `README.md`(지문 **안**)를 고치는 커밋을 심었다: 기준선 **11 passed / 2 skipped** → **2 failed**(경로를 이름으로 댐: `README.md`). 합성 이빨은 임시 저장소의 **실제 커밋**으로 ①~④ 를 확인했고, **이 저장소 자신의 이력**에 남은 F-22(`0593dd27` → 기록 커밋 `f95f22b9`)도 탐지기가 `['README.md']` 로 집는다.
- **검증** — **required gate 21/21 을 커밋된 후보 `b5729b61` 에서 되돌리기 0회로 단일 지문 `b637d8b9…` 에서 완주**(python-tests **6192 passed / 40 skipped / 16 deselected** 528.97s · python-benchmark 16 passed · docker 256.3s · clean-machine 41.3s `ref: HEAD` · `data/`·`dashboard_dist` 드리프트 0 · 실행 후 지문 재측정 동일). 이번에는 **선언을 측정 전에 커밋**했다 — `python-tests` 가 이 계약을 실행하므로 그 순서가 필요하고, 그래서 보고서의 `git.sha`(`13ff9140`)와 후보(`b5729b61`)는 **같은 코드 트리**다(D-52).
- **한계** — **R-9(신규)** 조항 ④는 보고서가 **있으면** 정합성을 보지만 **존재**는 요구하지 않는다(보고서는 게이트 실행이 끝날 때 쓰이므로 그 실행 **안에서는** 존재할 수 없다 — 순환). 그래서 attempt 마다 보고서를 증거팩에 복사해 두고 카드 수치와 검토자가 대조해야 한다 · R-2(값 자체의 옳음은 보고서·카드가 소유) · R-3(`clean-machine-runtime` 은 `ref: HEAD` 시점 의존) · R-4(`vault_data`) · R-6(③의 기준선 스코프가 문서와 어긋나면 `C14-F15-4` 가 먼저 깨진다) · R-7(심볼릭 링크가 코드 스코프에 들어오면 커밋 측 지문 계산을 확장해야 한다 — 지금은 전제를 검사로 막아 두었다). 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-015/`.

## 2026-09-13 CR-14 attempt-014 — **기록이 증거를 낡게 만드는 경로를 닫았다: 휘발성 값이 README 에 있었다 (F-22)** (판정 NO-GO 유지)

> **이 절은 attempt-014 시점의 실측이다 — 최신은 위의 attempt-015 절.** attempt-013 은 21/21 을 `0593dd27`(지문 `2c5a15c8…`)에서 측정하고 그 결과를 **기록 커밋 `f95f22b9`** 로 옮겼는데, 그 커밋이 `README.md`(지문 **안**)의 값을 갱신해 **지문을 `b9590b01…` 로 옮겼다** — 그 순간 그 초록은 HEAD 가 아닌 트리를 가리키게 됐다(F-07/F-14 와 같은 병). **제품 런타임 변경은 0건**이다(바뀐 것은 기록 방식과 그를 강제하는 계약).

후보: **커밋된 후보 `3fb3fcb935a771090ea0233695c27f7efb5c7f34`** · 코드 지문 **`b6494f40…`** (`docs/`·`.omo/` 제외 — 값의 전체 자리는 판정서 §5 카드가 소유한다).

- **어떻게 드러났나** — 증인(`attempt-014/repro/f22_fingerprint_scope_witness.py`)이 **git 객체에서** 지문을 독립 계산해 확정했다: `0593dd27` → `2c5a15c8…`, 기록 커밋 `f95f22b9` → `b9590b01…`(**MOVE=True**), 후보 `3fb3fcb9` → `b6494f40…`. 그 커밋에서 **지문 안에서 바뀐 파일은 `README.md` 하나**이고 `docs/**` 5개는 아무 영향도 주지 않았다.
- **근본 원인** — README 가 **손으로 갱신해야 하는 값**을 담고 있었다. 그런데 **최종 커밋의 SHA 는 그 커밋 전에는 알 수 없으므로 README 의 값은 어떤 순서로도 최신일 수 없다**(실측: README 는 `54e4169a` 를 가리킨 채 후보가 `1207118d` → `0593dd27` → `ded52af6` 로 진행했다). 단순히 "그 커밋에서 README 를 고치지 말았어야 한다"로 끝내면 다음 attempt 에서 반복된다.
- **수정** — ① README 에서 값을 제거하고 판정서 §5 판정 카드를 소유자로 지목 ② `C14-F22-1/2/3` 신규(오탐 방지로 hex 토큰은 최소 한 글자 a–f 를 요구 — 날짜·버전은 미탐) ③ **CR-12 계약 개정**: `tests/test_cr12_docs_alignment.py` 가 "README 가 후보 SHA 리터럴을 담을 것"을 요구해 **성립 불가능한 값을 강제**하고 있었다 → "값을 소유한 문서를 가리킬 것" + 리터럴 금지로 옮기고, 의도(커밋은 승인이 아니다)는 그대로 유지했다.
- **이빨** — 테스트 안에만 심지 않고 **실제 README** 로 확인: `3fb3fcb9` + `required gate 21/21` 을 심으면 계약 **3건 실패**, `git checkout -- README.md` 로 원복하면 지문 `b6494f40…` **정확 복귀** + `39 passed`. 이빨 테스트는 **오염된 기준선에서 스스로 실패**한다.
- **검증** — **required gate 21/21 을 커밋된 후보 `3fb3fcb9` 에서 되돌리기 0회로 단일 지문 `b6494f40…` 에서 완주**(python-tests **6179 passed / 40 skipped / 16 deselected** 509.3s · python-benchmark 16 passed · docker 226.2s · clean-machine 41.9s `ref: HEAD` · `data/`·`dashboard_dist` 드리프트 0 · 실행 후 지문 재측정 동일). 코드를 측정 전에 커밋해 HEAD 의존 재실행이 필요 없었다(D-52).
- **한계** — R-1(지문 이동을 **사후 탐지하는 계약이 아직 없다** — 이번엔 사람이 눈으로 찾았다; clean 커밋 트리와 진행 중 트리를 구분해야 해서 단순 동등 비교로는 만들 수 없고, 만들면 그 자체가 지문을 옮긴다(D-55)) · R-5(**CR-12 계약 개정의 재확인이 필요** — CR-12 소관) · R-2(값 자체의 옳음은 보고서·카드가 소유) · R-3(`clean-machine-runtime` 은 `ref: HEAD` 시점 의존) · R-4(`vault_data`). 증거: `.omo/evidence/commercial-reliability/CR-14/attempt-014/`.

## 2026-09-13 CR-14 attempt-013 — **검증 장치가 거짓말하고 있었다: 게이트 환경 비고정(F-18·F-19) · 테스트 격리 누수(F-20) · 부하 의존 임계값(F-21)** (판정 NO-GO 유지)

> **이 절은 attempt-013 시점의 실측이다 — 최신은 위의 attempt-032 절.** attempt-012 는 "같은 lock 3종 sha256 인데 게이트 환경이 달랐다"를 **원인 미특정 한계(R-6)**로 남겼다. 이번 attempt 는 그 관측을 끝까지 따라가 네 건을 닫았고, 결과적으로 **게이트 인벤토리(20 → 21)·`uv.lock`·"이전 초록이 무엇을 증명했는가"의 해석**이 바뀌었다.

후보: **커밋된 후보 `0593dd27dbea4a7bc4796ad9807d14b9f3a62165`** · 코드 지문 **`2c5a15c88570c8e1f56172c6967592860863c140aa6e971890bf4f1ae1567a6f`** (`docs/`·`.omo/` 제외).

- **F-18 (검증 장치)** — 게이트 명령은 `uv run --isolated --frozen <tool>` 이면 hermetic 하다고 전제했지만, dev 도구는 `[project.optional-dependencies].dev` 에 있고 `uv run` 은 그 extra 를 설치하지 **않는다**: 임시환경(64 패키지)에 pytest 가 없고(`find_spec('pytest') is None`), 도구가 없으면 uv 는 **호출 셀의 PATH** 로 떨어진다(`VIRTUAL_ENV` 무관 — PATH 우선순위가 결정). 증거는 같은 `uv.lock` sha256 을 가진 두 게이트 보고서다: attempt-011 `.../.venv/bin/python3` + pytest 9.1.1 + 수집 6213 + skipped 13 vs attempt-012 `/Users/mr.k/miniforge3/bin/python3.13` + pytest 9.0.3 + 수집 6221 + skipped 6. 차이의 정체는 `TestAgainstInstalled` 7건이다(그 클래스 가드가 `import trl; import unsloth`). 증인은 PATH 앞에 가짜 도구를 두고 게이트를 그대로 실행한다 — 수정 전 **HIJACKED 4/4**, 수정 후 pinned. 같은 결함이 범주를 가리지 않았다: 보안 게이트의 `bandit` 은 pyproject 에 **선언조차 없어** conda base 의 1.9.4 를 실행하고 있었다. 수정: 게이트에 필요한 extra 명시 + `bandit` 을 dev extra 에 선언하고 `uv lock`(추가: bandit 1.9.4·stevedore 5.9.1).
- **F-19 (검증 장치)** — 게이트를 실제로 고정하자 `python-tests` 가 `VectorStore requires chromadb but it is unavailable` 로 실패했다(dev 만: 해당 세 파일 `10 failed / 25 passed` · dev+rag: `35 passed`). chromadb 는 `rag` extra 이고 ambient 환경에 항상 있었기 때문에 20/20 초록이 나왔다 — 즉 그 초록은 “머심에 rag extra 가 설치돼 있었다”에 의존했다. 제품 코드는 바꾸지 않았다(`VectorStore` 는 chromadb 가 없으면 의도적으로 명확히 거부하고 `gbrain` 은 강등한다).
- **F-20 (테스트 격리)** — 로그인 보안 상태의 두 전역 기계(slowapi `5/minute`, credential gate lockout)가 키를 '호출자 IP'로 쓰고 TestClient 는 항상 같은 주소다. 순서만 다른 A/B: WS 단독 `7 passed` vs 번너+WS `5 failed(429)` · auth 두 파일 `1 failed(403)`. **두 누수가 서로를 가려 왔다는 사실**이 핵심이다 — 레이트리밋이 먼저 차면 lockout 이 켜지지 않는다. 기존 대응은 개별 테스트 우회였고(429만 처리) 실제 도착한 403 을 막지 못했다. 수정: `tests/conftest.py::_reset_login_security_state`(autouse).
- **F-21 (검증 장치)** — 고립 2250~2265ms 인 성능 테스트가 6200여 개를 도는 같은 프로세스 안에서 **6084ms**(임계값 6000ms)였다. 수정은 검사를 빼는 것이 아니라 **옮기는 것**: `python-tests` 는 `-m "not benchmark"`, **신규 required 게이트 `python-benchmark`** 가 `-m benchmark` 로 조용한 프로세스에서 돈다(16 passed / 16.9s).
- **증거** — 계약 3종 신규(9건) + 이빨 확인(게이트 `--extra` 제거 → 3 failed · `security-bandit` extra 제거 → 2 failed · conftest 무력화 → 1 failed · 성능 마커 제거 → 3 failed · 인벤토리 목록 편집 → 1 failed, 원복은 shasum 일치) · **required gate 21/21 을 커밋된 후보에서 되돌리기 0회로 단일 지문 `2c5a15c8…` 에서 완주**(python-tests **6174 passed / 40 skipped / 16 deselected** 506.6s · python-benchmark 16 passed · dashboard 81 files/849 · docker 223.0s · clean-machine 39.1s `ref: HEAD` · `data/` 드리프트 0 · 실행 후 지문 재측정 동일) · 로그 6종·증인 5종은 `attempt-013/`.
- **한계** — R-8(다른 extra 의 조건부 수집 미감사: pinned skipped 40 vs ambient 6/13) · R-10(계약이 `uv run` 을 중첩 실행) · R-11(성능 임계값은 여전히 wall-clock) · R-12(격리는 하네스 수준, 제품은 IP 단일 키) · R-13(`vault_data`).
- **다음 한 단계** — ① C14-08 배정 + EX-01~06 발송 → ② C14-03/04/05 → ③ 조건부 수집 감사(R-8) → ④ 태그 SHA 에서 `clean-machine-runtime` 마지막 재실행 + `evidence_kind: release` 번들 → 재판정.

> **이 절은 그 시점의 실측이다 — 최신은 위의 attempt-032 절.** attempt-012 는 attempt-011 이 한계(R-4)로 남긴 `job.view` 무잠금 쓰기를 결함으로 승격해(F-16) 닫았고, 그 정리에서 드러난 F-17(취소가 이벤트 루프를 1010.7ms 세웠다 → 6.8ms)까지 닫았다.

## 2026-09-13 CR-14 attempt-012 — **attempt-011 이 한계로 남긴 R-4 를 결함으로 승격(F-16) + 그 정리에서 드러난 F-17** (판정 NO-GO 유지)

> **이 절은 이전 실측이다(attempt-012).** attempt-011 은 "F-15 는 분류만 고쳤고 `job.view` 무잠금 쓰기 구조는 그대로다" 를 한계(R-4)로 적었다. 이번 attempt 는 **한계 문장을 재현 가능한 결함으로 바꾸는 것**에서 시작했고, 그 정리 과정에서 두 번째 결함이 드러났다.

후보: **커밋된 후보 `1207118d45cdb643b3a3e7bdd5743a5fb7b6ab7d`** · 코드 지문 **`7ecb4fc25f8b85af77f550f2d5482016f428ac0ddbc04ab7a8ce73b071d7ae0a`** (`docs/`·`.omo/` 제외).

- **F-16 — 종결 기록에 소유자가 없었다** — 종결 상태(`status`/`termination`/`error`/`finished_at`)를 쓰는 주체가 둘(취소 라우트·잡 스레드)인데 "누가 최종 기록을 쓰는가" 규칙이 없어 **나중에 쓴 쪽이 이겼다**. 증인 A(취소가 먼저 기록되고 watchdog 의 `timeout` 이 0.35초 뒤 도착 — 실제 경로에서도 성립하는 순서)에서 **관측된 종결 기록이 두 개**였다: `[('failed','cancelled','cancelled by user'), ('failed','timeout','exit_code=-15')]`. API 는 `200 {"ok": true}` 로 취소를 접수했다고 답했는데 정착한 기록은 `timeout` 이다 — 사용자가 취소했다는 사실이 사라진다. 게다가 `GET` 이 **살아 있는 dict** 를 돌려줘 종결 필드가 한 세트로 읽히지 않았다.
- **수정(D-59~D-61)** — 쓰기 단일 지점 `_Job.finalize()`(**먼저 확정한 쪽이 소유**, 재호출은 no-op 으로 `False` 반환) + `note()`(진행) + `snapshot()`(dict+log_tail 복사본) + `claim_cancel()`(1회 접수). 취소는 **프로세스 종료보다 먼저** 기록을 쓴다(종료는 최대 2×grace 블로킹이라, 그 뒤에 쓰면 늦게 도착한 `timeout` 이 기록을 가져간다). **계약을 하나 좁혔다**: 소유하지 못한 취소는 `{"ok": false, "detail": "job already finished"}` — 예전에는 그 창에서 **완료된 잡의 기록을 덮고 `ok:true`** 를 돌려줬다.
- **F-17 — 취소가 이벤트 루프를 세웠다** — cancel 라우트가 `async def` 인데 본체가 `terminate_process_group`(내부 `proc.wait(grace)` 두 번 = 최대 2×grace)을 그대로 호출했다. 실측(heartbeat 최대 간격): 수정 전 실제 라우트 **1010.7ms**(1.06초 요청 동안 tick 9회) · 수정 후 **6.8ms**(tick 172회) · 같은 본체를 루프에서 구동한 옛 모양은 1007.3ms 로 남는다. **요청 소요는 ~1.05초로 불변** — 빨라진 것이 아니라 서버가 멈추지 않게 됐다. 수정은 `def` 라우트 한 단어다(FastAPI 스레드풀).
- **증거** — 증인 exit 1 → 0(A: 기록 2개 → 1개 · D: 1010.7ms → 6.8ms) · 회귀 **8건 신규**(구 코드로 되돌리면 6건 실패, HTTP 회귀는 `assert 'timeout' == 'cancelled'` 로 **동작 실패**) · 대상 파일 25 passed · 소비자 4개 파일 44 passed · **required gate 20/20 을 커밋된 후보에서 되돌리기 0회로 단일 지문 `7ecb4fc2…` 에서 완주**(python-tests **6215 passed / 6 skipped / 수집 6221** 464.6s · dashboard 81 files/849 · docker 230.4s · clean-machine 41.8s `ref: HEAD` · dashboard-build 드리프트 0 · `data/` 드리프트 0 · **실행 후 지문 재측정 동일**) · 코드를 측정 **전에** 커밋해 HEAD 의존 재실행이 불필요(D-52).
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · 독립 검토·출시 책임자 미배정(C14-08) · C14-03(**취소·중단 경로 포함** 전 구간) · C14-04(EX-03) · C14-05(EX-01/EX-05) · C14-01 의 'worktree 완전 clean' 기준(F-13). **기술 결함은 0건**이다.
- **다음 한 단계** — ① `ok:false` 창의 UI 문구 검토(R-3) · `job.proc` 까지 단일 쓰기 지점으로(R-4) · 게이트 환경 재현성 조사(R-6 — 같은 lock 인데 skip 집합이 달랐다) → ② **C14-03** → ③ C14-08 배정 + EX-01~06 발송 → ④ 태그 SHA 에서 `clean-machine-runtime` 마지막 재실행 + `evidence_kind: release` 번들.

---

## 2026-09-13 CR-14 attempt-011 — **계약화 + required gate 가 드러낸 제품 결함 F-15 폐쇄** (판정 NO-GO 유지)

> **이 절은 그 시점의 실측이다 — 최신은 위의 attempt-032 절.** 기술 축이 닫힌 상태에서 두 가지를 더 했다 — 규율을 **계약**으로 옮기고, 그 계약이 드러낸 **제품 결함**을 닫았다.

후보: **clean HEAD `d72b17111ceca8518d3f9f1fb1f3a22a04c176aa`** · 코드 지문 **`e428aacc29ec5516b311c831880376a0e128c805429486ddf32a83c68cd9877a`**.

- **규율 → 계약(D-56)** — `tests/test_cr14_fingerprint_scope_contract.py` 9건(**5건은 위반을 심어 확인하는 이빨**): README 는 지문 값을 담지 않고 소유 문서를 가리킨다 · 지문 스코프(README·`tests/**`)는 선언된 현재 지문을 인용하지 않는다 · 제외 목록(`FINGERPRINT_EXCLUDED_PREFIXES`)이 바뀌면 계약이 먼저 깨진다 · 세 기록 문서가 경계를 말한다. **만드는 행위 자체가 지문을 옮겼다**(`d4a42ab8…` → `cdfbbb96…`) — 새 지문에서 20 gate 를 다시 완주했다.
- **required gate 의 일회성 실패는 flake 가 아니었다(F-15, D-57)** — 그 지문에서 `python-tests` 가 1건 실패(`assert 'completed' == 'cancelled'`)했고 **단독 실행은 5/5 통과**했다. 증인을 쓰니 A 3/3 · B **12/12** 로 재현됐다: API cancel 은 event set 과 **동시에** 종료하는데 watchdog 은 0.2초 폴링이라 프로세스가 먼저 죽으면 사유를 세우지 못한 채 루프를 빠져나가고, 감독이 취소를 **`completed`** 로 분류해 잡 스레드가 `job.view["termination"]` 을 덮어쓴다(사용자는 취소했는데 `status=failed, termination=completed, exit_code=-15`).
- **수정(D-58)** — 분류를 **관측이 아니라 사실**로: `cancel_event.is_set()` + 비정상 종료 코드 → `cancelled`. 정상 완료는 오분류되지 않고, 그 방향을 회귀가 고정한다. 기존 API 검사는 **정착한 뷰**를 보도록 강화했지만, 그것은 확률적 그물이다(R-1) — 결정적 보증은 모듈 수준 회귀.
- **증거** — 증인 exit 1 → 0(A 0/3 · B 0/12 · C 유지) · 수정을 끄면 결정적 회귀 1건 실패(이빨) · `tests/test_trn02_timeout_resource.py` 17 passed · **required gate 20/20 을 동결된 clean HEAD 에서 되돌리기 0회로 단일 지문 `e428aacc…` 에서 완주**(python-tests **6200 passed / 13 skipped** 467.75s · docker 233.3s · clean-machine 41.3s `ref: HEAD` · dashboard-build 24.1s 드리프트 0 · `data/` 드리프트 0) · **코드를 측정 전에 커밋해 HEAD 의존 재실행이 불필요**(attempt-010 의 순서 위반을 고친 실증).
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · 독립 검토·출시 책임자 미배정(C14-08) · C14-03(**취소·중단 경로 포함** 전 구간) · C14-04(EX-03) · C14-05(EX-01/EX-05) · **F-15 의 구조적 잔여**(`job.view` 무잠금 쓰기 — R-4) · C14-01 의 'worktree 완전 clean' 기준(F-13). **기술 결함은 0건**이다.
- **다음 한 단계** — ① `job.view` 상태 전이 단일화 → ② C14-03 → ③ C14-08 배정 + EX-01~06 발송 → ④ 태그 SHA 에서 `clean-machine-runtime` 마지막 재실행 + `evidence_kind: release` 번들 → CR-14 attempt-012.

---

## 2026-09-13 CR-14 attempt-010 — **지문 경계 실측 + 동결 트리에서 20/20 재검증**: 기록이 증거를 낡게 만들던 경계를 찾았다 (판정 NO-GO 유지)

> **이 절은 그 시점의 실측이다(attempt-010).** attempt-009 가 측정한 코드 내용은 그대로이고, 그 내용을 **동결된 커밋 트리**에 묶었다. 대신 그 과정에서 이 저장소가 전제해 온 가정 하나가 **틀렸음**이 드러났다.

후보: **clean HEAD `5ccb938e5d31411b16f2a69e3015fc8fb826455d`**(커밋 4개 — `5a717c4a` 후보 → `54e4169a` F-12 → `7347c5ee` attempt-009 기록 → `5ccb938e` README 지문 제거), 코드 지문 **`d4a42ab87697ba299129719d054c9259a717628a1bc8f80d00cd03ae0e372ce7`**.

- **드러난 경계** — gate 코드 지문의 제외 목록은 `("docs/", ".omo/")` 이고 **경로 접두사 비교**다. 따라서 `README.md`(루트)·`tests/**` 는 **지문 안**이다. attempt-009 기록을 쓰면서 계약 파일(`tests/test_cr12_docs_alignment.py`)을 고치자 지문이 `dd34a76b…` → `003205f2…` → `d4a42ab8…` 로 이동했다. 즉 **"결과 문서를 쓰는 것만으로는 증거가 낡지 않는다"는 `docs/` 안에 쓸 때만 참이다.**
- **수정** — README 에서 지문 **값**을 제거하고 **출처**(판정서·보고서)를 가리키게 했다(D-51). 최신 값을 손으로 갱신하는 대안은 **갱신하는 행위가 값을 낡게 만들어** 자기모순이다.
- **증거** — 코드 경로를 동결해 커밋한 뒤(**커밋은 내용 hash 기반 지문을 옮기지 않는다**: 미커밋 `d4a42ab8…` == 커밋 후 `d4a42ab8…`), **required gate 20개를 되돌리기 0회로 단일 지문에서 20/20 PASS**. python-tests **6189 passed / 13 skipped**(463.3s) · dashboard-test **81 files/849** · `docker-build` 233.7s · `clean-machine-runtime` 41.0s(`ref: HEAD` **3001 파일**) · `dashboard-build` 24.6s(**드리프트 0**) · `data/` 드리프트 0 · 실행 후 ` M vault_data` 한 줄뿐.
- **HEAD 의존 gate 분리 재실행** — `git HEAD` 에 의존하는 것은 `dashboard-build`(핀을 읽어야 드리프트 0)와 `clean-machine-runtime`(`git archive HEAD`)뿐이라, 이 둘만 clean HEAD 에서 다시 돌려 별도 보고서(`gate-report-clean-head.json`, 2/2 PASS)에 남겼다. 전체 인벤토리는 `gate-report.json`(20/20)이고, 단독 보고서의 `2 passed / total 2` 를 '18개 미실행'으로 읽으면 안 된다(D-53).
- **F-14(신규/폐쇄)** — attempt-009 기록의 `frontend 846 passed(80 files)` 는 **같은 attempt 의 보고서(`Tests 849 passed (849)` · `Test Files 81 passed (81)`)** 와 달랐다. F-12 가 추가한 테스트 3건 이전 값이 그대로 넘어온 것이고, 이 저장소가 반복해 잡아 온 **'주장 ≠ 측정'** 병과 같은 모양이다. 수치는 **그 attempt 의 `gate-report.json` 에서 직접 인용**하도록 정정했다(D-54).
- **남은 blocker** — 변화 없음. 필수 외부 승인·조건(EX-01~06) · 독립 검토·출시 책임자 미배정(C14-08) · C14-03(재시작·이력 복구 포함 전 구간) · C14-04(EX-03) · C14-05(EX-01/EX-05) · C14-01 의 'worktree 완전 clean' 기준 결정(F-13). **기술 결함은 0건**이다.
- **다음 한 단계** — R-4 계약(문서가 지문·수치를 인용하지 않는다)을 **게이트 실행 직전에** 추가 → C14-03 → C14-08 배정 + EX-01~06 발송 → 태그 SHA 에서 `clean-machine-runtime` 마지막 재실행 + `evidence_kind: release` 번들 → CR-14 attempt-011.

---

## 2026-09-13 CR-14 attempt-009 — **후보 커밋 + F-12·F-07 폐쇄**: 기술 축을 모두 닫았다 (판정 NO-GO 유지)

> **이 절은 그 시점의 실측이다 — 최신은 위의 attempt-032 절.** 달라진 것은 **커밋된 후보에서 20/20 을 완주**했고 **clean-machine 이 후보를 검증**했다는 점이다. 이제 남은 차단 사유는 사람의 영역(승인·검토·장기 검증)뿐이다.

후보: **clean full SHA `54e4169a947d4ba0cbe3fabf92b0c8590b8ccef6`**(커밋 `5a717c4a` + F-12 수정 `54e4169a`), 코드 지문 **`dd34a76bf076ebc09be8c575ad733c52a0a647faa4d5d9758f3b01cf6f667f37`**.

- **커밋이 막혔는데 그것이 옳았다** — pre-commit 의 `trailing-whitespace` 가 **생성 번들 11개를 다시 썼고** `check-added-large-files`(maxkb=1024)가 워커(MB 단위)를 거부해 중단됐다. 훅이 생성물을 소스처럼 다루면 커밋된 바이트와 `pnpm run build` 결과가 갈라진다(F-01/F-12 의 멱등성 파괴). `--no-verify` 가 아니라 **생성 경로를 훅 대상에서 제외**하고 다시 커밋했다.
- **F-12 — "빌드는 멱등"은 고정 HEAD 에서만 참이었다** — 커밋 직후 `dashboard-build` 가 자산 **22개를 교체**하고 지문을 옮겼다(같은 HEAD 에서 두 번째 빌드는 no-op). 원인은 `buildStamp.ts` 가 `AGK_BUILD_ID` 기본값으로 `git short SHA` 를 쓴 것 — **커밋된 번들은 자기 커밋의 SHA 를 담을 수 없다**(치킨-에그). `dashboard-build` 가 required gate 인 한 **커밋된 후보에서 단일 지문 20/20 이 불가능**했다. 수정: **커밋된 핀**(`dashboard/build-provenance.json`)을 해석 순서에 넣고(`env → 핀 → git → null`) 번들을 핀 값으로 재생성.
- **F-07 폐쇄** — `clean-machine-runtime` 이 `ref: HEAD` 로 **후보 전체(3001 파일, 직전 2877 = 낡은 HEAD)** 를 아카이브해 exit 0. 이제 이 초록은 후보의 근거다. **순서 규율은 남는다**: 릴리스는 태그 SHA 에서 이 gate 를 마지막으로 다시 돌려야 한다.
- **증거** — 증인 `cr14_f12_build_drift_witness.py` exit 0(핀 유효·번들이 핀 보유·재빌드 digest 불변), 회귀 **9건**(핀 값을 바꾸면 pytest 2건 실패 — 이빨), 전체 suite **6189 passed / 13 skipped**(452.1s, `data/` 드리프트 0), **required gate 20개가 커밋된 후보에서 되돌리기 0회로 단일 지문에서 20/20 PASS**(docker 227.3s · clean-machine 42.5s · dashboard-build 24.0s · api-e2e 18.4s)이고 **실행 후 지문 불변**.
- **F-13(신규, advisory)** — `git status` 의 유일한 줄은 ` M vault_data` 이고 그 안은 훅 런타임 이벤트 로그(+3537줄)다. gitlink SHA 는 불변이라 커밋에는 영향이 없지만 보고서에 `git.dirty: true` 가 남아 **'clean 후보' 판정을 흐린다**(선택지 3개를 D-50 에 기록).
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · 독립 검토·출시 책임자 미배정(C14-08) · C14-03(재시작·이력 복구 포함 전 구간) · C14-04(EX-03) · C14-05(EX-01/EX-05) · **C14-01 의 'worktree 완전 clean' 기준 결정**(F-13). **기술 결함은 0건**이다.
- **다음 한 단계** — C14-03 → C14-04/05(외부 승인 필요) → C14-08 배정 + EX-01~06 발송 → CR-14 attempt-010(릴리스 번들 `evidence_kind: release` + GO/NO-GO 재판정).

---

## 2026-09-13 CR-14 attempt-008 — **F-10·F-11 폐쇄 + F-09 의 `qs` 편차 실행 검증** (판정 NO-GO 유지)

> 판정은 attempt-001~007과 같이 **NO-GO** 다. 달라진 것은 **측정 도구가 살아나고 그 도구가 검증하던 유일한 소비자 경로까지 끝까지 확인**했다는 점이다(남은 기술 축: **F-07 하나**).

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`6641446ef41e0562118dd0741637f57eae6412f18fdf18813ea87f777d0b0076`**(attempt-007 의 `c36327ef…` 에서 이동).

- **F-10 은 오류 메시지를 잘못 읽으면 진단이 뒤집히는 사례다** — `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 죽는데, 이는 러너 미설치가 아니라 **탐색 경로** 문제다. Stryker 의 자동 플러그인 탐색은 **자기 자신의 설치 디렉터리**를 스캔하고, pnpm 격리 레이아웃의 `.pnpm/@stryker-mutator+core@*/node_modules/@stryker-mutator` 에는 core 의 의존(api·instrumenter·util)만 있으며 devDependency 인 러너는 루트에만 있다. 수정은 `stryker.config.mjs` 의 한 줄(`plugins: ['@stryker-mutator/vitest-runner']`)이다 — 설치된 조합(9.6.1 ↔ vitest 4.x)은 peer 계약(`vitest: >=2.0.0`)을 만족하고 dry-run 843 테스트가 실제로 돈다.
- **도구가 살아나자 F-09 의 '미검증' 이 닫혔다** — 그 도구가 `qs` override 의 **유일한 소비자 경로**였다. 소스로 지목한 경로(`@stryker-mutator/core → typed-rest-client RestClient → Util.getUrl → qs.stringify`, 여기서 `encodeValuesOnly` 가 **기본값**)에서 `qs 6.15.1`(벤더 정확 고정값)은 **실제 크래시**(`TypeError: Cannot read properties of null (reading 'length')`, `Util.getUrl`·`RestClient.get` 두 축 모두)하고 `6.16.0` 은 정상이다. 근거가 "advisory 하한" 에서 "우리 경로에서 재현되는 크래시의 수정" 으로 강화됐다 — 이 override 를 revert 하는 것이 **더 위험한 선택**이 됐다.
- **에 도구를 돌리자 새 결함 F-11 이 드러났다** — `--mutate A --mutate B` 는 **마지막 하나만** 적용한다. 스크립트는 2개 파일을 선언했는데 보고서에는 `outputStore.ts` 만 들어갔고(82.35%) **exit 0** 이었다. 통제 실험(단일 플래그로 `terminalStore.ts` 만 → 96.92%, 정상)으로 원인을 **파일 선택이 아니라 반복 플래그**로 분리한 뒤, 쉼표 단일 플래그로 고쳤다 — 수정 후 두 파일 모두(All files **91.92%** = 91 kill / 8 survive, exit 0). 이는 F-07 과 **같은 병**이다: exit 0 이 검증한 대상과 확인하려는 대상이 다르다.
- **증거** — 증인 `cr14_f09_qs_consumer_probe.cjs`: `6.15.1` 에서 A·B 두 축 모두 CRASH(exit 1) → `6.16.0` 에서 A·B OK(exit 0). 회귀 **9건**(`tests/test_cr14_stryker_toolchain_contract.py` — `plugins` 한 줄 제거 시 1건 · 스크립트를 반복 플래그로 되돌리면 2건 실패로 이빨 확인). 전체 suite **6183 passed / 13 skipped**(457.9초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문 `6641446ef41e0562…` 에서 20/20 PASS**(python-tests 459.9s · docker 46.0s · clean-machine 41.8s · dashboard-build 25.3s · api-e2e 18.3s)이고 **실행 후 지문이 불변**임을 재측정했다.
- **정직한 한계** — ① `qs` 검증은 우리가 소스로 지목한 소비자 경로에 대한 것이고 `stryker init` 을 실행한 것은 아니다(R-1) ② 91.92% 는 **quick 범위(2 파일)** 의 점수이고 전체 `stryker`(10 파일)는 비용 때문에 돌리지 않았다(R-3) ③ `reports/mutation/mutation.json` 은 JsonReporter 미설정으로 **7월 21일 파일이 남아 있다**(그 안의 break 는 50) — 현재 결과로 인용하면 틀린다(D-44).
- **F-11b 는 advisory 다** — quick 범위 생존 변이 8건(outputStore 6 · terminalStore 2)은 임계값(`high 80`·`break 55`)을 통과한다. 도구가 이제 이 신호를 **측정 가능**하게 만들었다는 사실이 진전이다.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(두 lock·`dashboard_dist`·release 문서 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(**`clean-machine-runtime` 이 마지막 기술 축**) → **F-11b 판단**(생존 변이 정책) → 독립 검토·출시 책임자 배정 + EX-01~06 발송 → CR-14 attempt-009.
- **출하 문서 정정(D-45)** — `dashboard.cdx.json` 은 **241 항목 / 207 고유 패키지**다(attempt-007 이 "구성요소 207" 로 적은 것은 고유 이름 수였다). 해시(`666a2ea3…`)는 불변이다.

---

## 2026-09-13 CR-14 attempt-007 — **F-09 폐쇄**: dev 도구 체인 취약과 출하 경계 (판정 NO-GO 유지)

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`c36327effafcc6dbe4a80970682f5e82eccd98f81951b000c758e888e7b0130a`**(attempt-006 의 `3a9a7d66…` 에서 이동).

- **F-09 은 '게이트 초록 + dev 취약 잔존'이었다** — `dependency-audit-dashboard` 가 `--prod` 이므로 dev 도구 체인은 감사 범위 밖이다. 실측(수정 전): high 1건(`eslint → @eslint/eslintrc → js-yaml`, `<4.3.2`) + moderate 3건(`@stryker-mutator/core → typed-rest-client → qs`, `<6.16.0`).
- **절반은 또 두 진실원 갈라짐이었다** — `js-yaml` 이 **pnpm 4.3.1(취약) / npm 4.3.2(패치)** 로 갈라져 있었다. F-03(고지문↔SBOM)·F-06(uuid)에 이어 **세 번째** 같은 병이다. `qs` 는 양쪽 모두 6.15.1 이었다.
- **출하 경계를 측정으로 남겼다** — 두 패키지 모두 출하 SBOM(`dashboard.cdx.json`, 241 항목 / 207 고유 패키지)·`THIRD_PARTY_NOTICES.txt` 에 **없다**(수치는 attempt-008 에서 정정 — D-45). "dev 니까 출하물에 영향 없다"를 회귀(C14-F09-6)로 고정했다.
- **수정** — `js-yaml: 4.3.2` 는 상류(`@eslint/eslintrc`)가 `js-yaml: ^4.3.0` 을 선언하므로 **편차가 아니라 최소 패치**다. `qs: 6.16.0` 은 **의도된 편차**다 — `typed-rest-client@2.3.1` 이 `qs: 6.15.1` 로 정확히 고정했고 수정판은 3.x(`^6.16.0`)에만 있는데 stryker 는 `~2.3.0` 만 허용해 **선언 범위 안에 수정판이 없다.** 두 override 를 양쪽 설정(`pnpm-workspace.yaml` + `package.json`)에 선언하고 두 lock 을 재생성했다.
- **증거** — 증인 `cr14_f09_dev_audit_witness.py` 는 하한·두 lock 일치·출하 closure 부재를 분리 측정해 수정 전 exit 1(위반 4건) → 수정 후 exit 0. **전체 트리 audit 0/0/0/0/0**(advisories 0), `pnpm run lint` 0 errors(js-yaml 정상 로드) · vitest 846 passed · build exit 0 · 출하 문서 불변. 전체 suite **6174 passed / 13 skipped**(466.1초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문 `c36327ef…` 에서 20/20 PASS**(docker 240.9s · clean-machine 41.9s · dashboard-build 27.6s · accessibility 10.3s). 회귀 7건.
- **닫는 중 나온 새 결함 F-10** — `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 exit 1. **통제 실험**(F-09 override 제거 후 같은 명령 → 동일 실패)으로 **기존 결함**임을 확정했다(stryker 9.6.1 ↔ vitest 4.1.11). required gate 는 아니지만 ① 변이 점수 측정 수단 부재 ② **`qs` 편차의 유일한 소비자 경로가 실행되지 않아 그것이 end-to-end 로 검증되지 않았다**는 두 가지를 남긴다.
- **정직한 한계** — pnpm 은 override 를 지워도 해석을 즉시 되돌리지 않으므로(lock 보존) 선언 검사가 해석 검사와 짝으로 필요하다. `qs` 편차의 근거는 그 시점에 advisory 하한·같은 벤더 후속 메이저의 선언·minor 상향 세 가지였고, **실행 검증은 attempt-008 에서 마쳤다**(소비자 경로에서 `6.15.1` 크래시 → `6.16.0` 정상). 상세 D-36·D-41, `attempt-007/review.md` R-1~R-7.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · **F-10(stryker 도구 체인 — 게이트 아님)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(두 lock·`dashboard_dist`·release 문서 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-10 판단**(고친 뒤 `qs` override 재검증) → 독립 검토·출시 책임자 배정 → CR-14 attempt-008.

## 2026-09-13 CR-14 attempt-006 — **F-06 폐쇄**: 대시보드 `uuid` 하한과 출하 바이트 (판정 NO-GO 유지)

> **이 절은 그 시점의 실측이다 — 최신은 위의 attempt-032 절.** 판정은 attempt-001~005와 같이 **NO-GO** 다. 달라진 것은 **게이트 범위의 기술 결함이 0건**이 됐다는 점이다(남은 축: 커밋·외부 승인·F-07·F-09).

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`3a9a7d66909e2fafaf31b4c429d2338f262d50b0d0d8ef3b5f00b5be0ca41e2d`**(attempt-005 의 `1981bfb5…` 에서 이동).

- **F-06 은 두 축으로 나뉘어 있었다** — 등록 서술은 "mermaid 경유 `uuid@9.0.1` moderate(`<11.1.1`)인데 감사 임계값이 `high` 라 차단되지 않는다"였다. 실측하니 ⓐ **의존 하한 위반**(pnpm·npm **두 lock 모두** `uuid@9.0.1` — pnpm 은 설치·빌드, npm 은 SBOM·고지 진실원)이고 ⓑ **취약 서명 미도달**(mermaid 의 erDiagram 청크는 `import { v5 } from "uuid"` 후 `v5(str, NAMESPACE)` — 인자 2개이므로 취약 서명 `buf` 전달이 아니다)이었다. 즉 악용 경로가 아니라 **하한 문제**였고, 상류 `mermaid 10.9.8` 이 이미 `uuid: ^9.0.0 || ^10 || ^11.1.0 || ^12 || ^13 || ^14.0.0` 로 **패치 버전을 허용하고 있었다**.
- **수정** — `dashboard/pnpm-workspace.yaml` 과 `dashboard/package.json`(npm `overrides`) **양쪽에** `uuid: 11.1.1`. 한쪽만 하면 npm 은 mermaid 범위의 **최고 가지(14.x)** 를 골라 설치 코드와 고지 코드가 갈라진다(F-03 과 같은 병 — 회귀 `C14-F06-2b` 가 두 lock 일치를 고정). 11.1.1 은 취약 범위를 벗어나는 **최소 패치**이고 `exports` 가 ESM·CJS 를 모두 제공하는 것을 확인했다(12+ 는 이번에 검증한 범위가 아니다). 두 lock 재생성 + **출하 번들 재빌드**(추적 산출물: 청크가 `…Ca1Z6rrW.js` → `…DK8mMXpA.js` 로 교체) + release 문서 재생성.
- **증인은 세 축을 분리해 측정한다** — A) 잠금 하한, B) 취약 서명 도달성(참고), **C) 출하 바이트**(번들에 uuid v35 구현이 있으면 패치 마커 `out of buffer bounds` 도 있어야 한다). C 축이 필요한 이유: **잠금만 올리고 재빌드하지 않으면 출하물에는 옛 코드가 남는다**(F-03 의 교훈). 수정 전 exit 1(하한 위반 3건) → 수정 후 exit 0. 별개로 게이트 관점에서는 수정 전에도 `pnpm audit --prod --audit-level high` 가 **exit 0** 이었다 — moderate 는 임계값 미만이므로 **초록인 채로 미패치 의존이 남아 있었다**.
- **증거** — 증인 `cr14_f06_uuid_reachability.py`(수정 전/후), `pnpm audit --prod` **취약 0건**(moderate 포함 0), CR-09 실브라우저 **4/4 PASS + 전 시나리오 `blockedExternal: []`**(mermaid 가 uuid 11.1.1 로 실제 렌더), 전체 suite **6167 passed / 13 skipped**(448.5초, `data/` 드리프트 0), 대시보드 80 files/846 passed, **20 required gate 가 되돌리기 없이 단일 지문 `3a9a7d66…` 에서 20/20 PASS**(docker 223.8s · clean-machine 41.5s)이며 **실행 후에도 지문이 불변**임을 재측정했다. 회귀 8건(`tests/test_cr14_dashboard_dependency_floor.py`; override 선언 2곳을 제거하면 3건 실패 — 이빨 확인).
- **skip 증가는 후보의 성질이 아니다** — 13건 중 7건은 `TestAgainstInstalled`(unsloth/trl)로, 두 패키지는 `uv.lock` 에 **0건**이다(pyproject §87-90: extra 가 아니라 주간 drift CI 담당). attempt-005 는 오버레이가 있는 환경에서 같은 7건을 PASS 로 기록했다(D-32).
- **신규 잔여 위험 F-09** — dev 도구 체인에 **high 1건**(`eslint → @eslint/eslintrc → js-yaml <4.3.2`)·moderate 3건(`@stryker-mutator → typed-rest-client → qs`). 게이트가 `--prod` 이므로 차단되지 않는다 — **"감사 통과"가 "위험 0"은 아니라는 사실이 이 attempt 로 한 번 더 실증됐다.** 삭제/상향 여부는 출시 책임자 결정.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · **F-09(dev 도구 체인 취약, 게이트 범위 밖)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(갱신된 **두 lock**·`dashboard_dist`·release 문서 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-09 결정** → 독립 검토·출시 책임자 배정 → CR-14 attempt-007.

## 2026-09-13 CR-14 attempt-005 — **F-03 폐쇄**: release 라이선스 판독이 고지문↔SBOM 으로 갈라져 있었다 (판정 NO-GO 유지)

> 판정은 attempt-001~004와 같이 **NO-GO** 다. 달라진 것은 **남은 기술 결함이 F-06 하나**가 됐다는 점이다. **(이후 attempt-006 에서 F-06 도 닫혔다 — 위 절 참조.)**

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`1981bfb5143d3f9eac947826bf6ee53655c47194f5be9c4a5bf755ba982a1844`**.

- **F-03 폐쇄(원인을 둘로 분해해 실측)** — 등록 서술은 "실행 환경에 따라 라이선스 값이 달라진다"였지만 실제로는 ⓐ **판독 실패**(환경과 무관하게 틀린다) ⓑ **환경 의존**(플랫폼 마커에만 남는다)로 나뉘었고, 실질 결함은 ⓐ였다. `THIRD_PARTY_NOTICES.txt` 의 파이썬 절만 `License` 필드를 직접 읽었고 `python.cdx.json` 은 PEP 639 `License-Expression` → License → 분류기 → 별명표 순으로 읽었다 — 즉 **같은 실행의 두 산출물이 같은 패키지에 다른 답**을 했다(파이썬 구성요소 61개 중 **42건 불일치**, 그중 **35건은 환경 메타데이터를 직접 읽어 반증한 판독 실패** — `fastapi`=MIT, `click`=BSD-3-Clause, `cryptography`=Apache-2.0, `networkx`=BSD-3-Clause). 고지문은 **wheel/sdist 에 동봉되는 법적 문서**이고 `release_sbom verify` 가 저장소 사본과의 **바이트 일치**를 강제한다 — 41줄의 `license metadata unavailable` 이 그대로 출하물에 실려 있었다.
- **수정** — 고지문이 SBOM 과 **같은 판독 체인**을 쓰도록 통일(SPDX id → 정규화 불가 시 원문 `License` 필드를 **공백만 정규화**해 한 줄 유지 → 미상 표기; 값을 합성하지 않는다). 저장소 사본 재생성으로 미상이 41건 → 2건이 됐고, `python.cdx.json` 은 **수정 전후 바이트 동일**이었다(SBOM 쪽 판독은 옳았고 결함은 고지문 쪽이었다). 남은 2건(colorama·pywin32)은 **추정 라이선스를 선언하지 않고**(검증되지 않은 주장 금지), `미해결 ⊆ THIRD_PARTY_PROVENANCE.toml 의 marker_platform_packages` 를 회귀 17건(`tests/test_cr14_python_license_determinism.py`)이 고정한다. 재생성이 커밋된 라이선스를 미상으로 되돌리면(부실한 생성 환경) 테스트가 실패한다.
- **증거** — 증인 `cr14_f03_notices_sbom_divergence.py`: 수정 전 exit 1(불일치 42건 · 판독 실패 35건 · 미해결 41건) → 수정 후 exit 0(불일치 0건 · 판독 실패 0건 · 미해결=정책 선언). 전체 suite **6166 passed / 6 skipped**(453초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문 `1981bfb5…` 에서 20/20 PASS**(docker 231.4s · clean-machine 41.3s · accessibility 35 · api-e2e 9 · 대시보드 80 files/846).
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · **F-06(uuid 경유 moderate — 유일한 기술 결함)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(갱신된 `THIRD_PARTY_NOTICES.txt`·`dashboard.cdx.json`·`dashboard_dist` 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-06** → 독립 검토·출시 책임자 배정 → CR-14 attempt-006.

## 2026-09-12 CR-14 attempt-002 — P1·Docker OOM 폐쇄, **required gate 20/20 PASS** (판정 NO-GO 유지, 기록)

> **이 절은 그 시점의 실측이다 — 최신은 위의 attempt-032 절.** 판정 자체(출시 준비 관문)는 attempt-001과 같은 **NO-GO** 다 — 달라진 것은 차단 사유의 성격이다. attempt-001의 차단 사유는 기술적(required gate 실패·미실행, P1)이었지만, attempt-002의 차단 사유는 **사람과 커밋 위생**(필수 외부 승인 부재 · source mismatch)이다.

attempt-001이 남긴 P1을 닫고, attempt-001에서 **미실행**이던 required gate가 처음 돌면서 드러난 OOM까지 닫았다. 후보는 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`ebbbd7f06fab3fb2d10008336ef96ba0d7949ee72007774c6372fc07f1bba0b5`**(2544 files).

- **판정: NO-GO 유지.** 계획서 판정 규칙의 네 조건 중 **P1과 required gate 실패/미실행은 해소**됐으나, **필수 외부 승인 부재(EX-01~EX-06)**와 **source mismatch(미커밋 → clean full SHA 없음)**가 남았다. 두 조건 모두 규칙상 NO-GO 사유다. GA 승인 없음 · CR-14 DONE 아님.
- **gate 실측: 20/20 실행 · 20/20 PASS**(attempt-001은 15실행/14PASS/1FAIL/4NOT_RUN). 단일 코드 지문 위에서 완주 — `python-tests`가 재작성한 `data/benchmark_results.json`(F-02)을 되돌려 지문을 유지했고, `dashboard-build`·`sbom-generate`는 자산명이 내용 해시라 멱등이어서 지문이 깨지지 않았다.
- **F-04(P1) 폐쇄**: `mermaid` `10.6.1 → 10.9.8`(lock 3종 동기화)로 `dependency-audit-dashboard`가 **PASS**(high 0). 승격이 **새 보안 회귀**를 드러냈다 — 10.9.8은 라벨의 raw `<img>`를 DOM에 **남겨** 절대 URL이면 **외부 요청(비컨)이 실제로 나간다**(실브라우저 캡처: `https://beacon.invalid/leak.png`). 컴파일된 계약 `C09-03`이 승격 직후 실패하며 드러났고, **출력 정화만으로는 늦다**(mermaid가 측정용 임시 DOM에 라벨을 넣어 정화 전에 요청이 나간다). `mermaidRuntime`에서 **입력 중화(deny-list) + 출력 구조 정화** 두 단계로 막았고, 이제 `C09-03`이 `blockedExternal: []`로 상시 감시한다.
- **F-05(신규) 폐쇄**: required gate `docker-build`가 처음 돌자 **14.5초에 heap OOM**(3/3 재현). 원인은 콜드 `tsc -b`이고, `node:22.13-alpine` 기본 V8 힙 상한이 **2096MB로 고정**(`--memory=4g`/`12g` 모두 동일 — 호스트 메모리로 회피 불가). dashboard-builder 스테이지에 빌드 한정 `ENV NODE_OPTIONS=--max-old-space-size=4096`를 추가해 **PASS(246.8s)**. 이미지 빌드에서 타입체크를 빼지 않았다.
- **신규 잔여 위험 F-06**: mermaid 경유 `uuid@9.0.1` moderate(`<11.1.1`). 감사 gate 임계값이 `high`라 차단되지 않는다 — **"게이트 초록"과 "위험 0"은 다르다.**
- **검증**: `pytest` **6124 passed / 6 skipped**(428초) · 대시보드 Vitest **80 files/846 passed** · 실브라우저 CR-09 4/4 · `accessibility-e2e` 35 passed · `docker-build` PASS · `clean-machine-runtime` PASS · ruff/format/mypy/basedpyright 0 errors.
- **남은 blocker**: 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · F-01(`dashboard_dist` 추적 — 이후 attempt-003 실측으로 **GA blocker 에서 내려감**: 빌드는 멱등) · F-02(pytest 재작성 — attempt-003 에서 폐쇄) · F-03(라이선스 환경 의존) · F-06(uuid moderate) · 독립 검토·출시 책임자 미배정 · C14-04/C14-05 NOT_RUN.
- **다음 한 단계**: F-02(`data/benchmark_results.json` 격리) → F-01(`dashboard_dist` 정책) → CR-01~14 커밋·clean full SHA → 그 SHA에서 20-gate 재실행 → 독립 검토·출시 책임자 배정 → CR-14 attempt-003.

## 2026-09-12 CR-14 attempt-001 최종 후보 검증 — **판정 NO-GO** (기록)

> **이 절은 attempt-001 시점의 기록이며 최신 실측이 아니다.** 당시 기준을 그대로 보존한다 — 과거 FAIL을 PASS로 재라벨링하지 않는다. 출시 준비 판정의 단일 원본은 [17번 체크리스트](./17_COMMERCIAL_RELIABILITY_CHECKLIST.md)이고, 이번 판정의 상세 근거와 재개 순서는 [ga/CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md)에 있다.

CR-01~CR-13을 통합한 후보(기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 `11979d6c…`)에서 계획서 §CR-14의 전체 검증을 수행했다.

- **판정: NO-GO. GA 승인 없음. CR-14는 DONE이 아니다.** 계획서의 판정 규칙 5개 조건이 모두 해당한다: P1 미해결 · required gate 실패 · required gate 미실행 · 필수 외부 승인 부재 · clean full SHA 없음.
- **gate 실측**: 20 required gate 인벤토리 중 **15 실측 = 14 PASS / 1 FAIL / 4 NOT_RUN**.
  - FAIL 1건: `dependency-audit-dashboard` — `mermaid@10.6.1` ∈ 취약 범위 `<=10.9.2`, GHSA-m4gq-x24j-jpmf (**high**), patched `>=10.9.3`. **로컬에서 재현되는 P1이며 외부 조건과 무관하다.** 이 gate는 이번에 처음 실행됐다(CR-11은 파이썬 감사만 확장했고, CR-09이 mermaid를 정식 의존성으로 승격한 시점에도 대시보드 감사는 돌지 않았다).
  - NOT_RUN 4건: `docker-build` · `master-e2e` · `accessibility-e2e` · `clean-machine-runtime`.
- **닫은 결함**: ① CR-13의 승인 우회로 — `required_gates`를 비우면 gate 검사를 통째로 건너뛰고 `PASS`를 냈다. 이제 `evidence_kind`(`release`|`reference`)가 필수이고 `release`는 빈 목록을 거부하며, 참고 번들은 `REFERENCE_ONLY`(exit 3)로 분리된다. ② 검증 실행이 추적 중인 `src/antigravity_k/release/*`를 덮어쓰던 REL-01 테스트 경로 — `tmp_path`로 옮기고 저장소 드리프트 검사 2건을 새로 만들었으며, 그 과정에서 저장소 사본이 CR-09 이후 낡아 있던 사실이 드러나 재생성했다. ③ `ga_gate.py --merge-into`(같은 후보 SHA·manifest·코드 지문일 때만 단계별 결과를 이어받음).
- **신규 결함 4건**: **F-01** 추적 중인 `src/antigravity_k/dashboard_dist/`가 빌드마다 자산 39개 삭제 + 87개 신규 생성(총 127 변경) — ← **attempt-003 실측으로 정정: 빌드는 바이트 단위 멱등이고 지문도 불변이다. dirty 의 원인은 커밋된 HEAD 번들이 낡은 것**이다(`docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md §0-B`). CR-10/CR-11 “stale bundle” blocker와 `clean-machine` gate가 낡은 UI를 포장하는 문제의 뿌리. **F-02** 상용 pytest suite가 `data/benchmark_results.json`을 재작성(CR-13 R03 드리프트의 뿌리). **F-03** release 문서의 파이썬 라이선스가 `importlib.metadata`로 실행 환경에서 읽혀 같은 후보·같은 lock인데도 값이 달라짐 — **attempt-005 실측으로 정정·폐쇄: 실질 원인은 환경이 아니라 고지문과 SBOM 이 각자 다른 함수로 판독한 것이다(42건 불일치, 35건은 판독 실패).** **F-04** mermaid high(P1).
- **검증**: `python-tests` **6123 passed / 7 skipped**(447초), 나머지 13개 실측 gate 전부 exit 0(ruff·format·mypy·basedpyright·bandit·package-build·dashboard install/lint/typecheck/test(80 files/840 passed)·sbom-generate·api-e2e). 신규 회귀 `tests/test_cr14_candidate_evidence.py` 13건.
- **재개 순서(권장)**: F-04(mermaid) → F-02 → F-01 → 코드 커밋·clean full SHA → 20-gate 전부 실행 → 독립 검토 배정 → 외부 조건 확보 후 C14-03/04/05. **(attempt-003 실측 정정: F-02 는 닫혔고 F-01 은 "비결정성"이 아니라 "낡은 HEAD 번들" 문제로 내려갔다 — 순서는 "갱신된 번들을 포함해 커밋 → 새 SHA 에서 20-gate 재실행"이 된다.)**

## 2026-09-12 상용 신뢰성 개선(CR-01 ~ CR-13) REVIEW

2026-09-11 상용 검토(`docs/qa/2026-09-11-commercial-review/BASELINE.md`)의 발견을 기준 SHA `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f`에서 재분류하고, 새 경계 13건(CR-01~CR-13)을 구현했다. 계획·체크리스트는 [16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md](./16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md) · [17_COMMERCIAL_RELIABILITY_CHECKLIST.md](./17_COMMERCIAL_RELIABILITY_CHECKLIST.md)이며, **이 시점부터 출시 준비 판정의 단일 원본은 10번이 아니라 17번 체크리스트다.**

- **상태**: CR-00 DONE(사용자 위임 개방) / CR-01 ~ CR-14 **REVIEW**(코드 **미커밋**, 독립 검토 미배정) / **GA 승인 없음**. REVIEW는 독립 검토자 동일 SHA 승인 전이므로 DONE이 아니다. (이 절의 표기는 `CR-14 TODO`였으나, CR-11~14 구현이 끝나 REVIEW로 올라가면서 정정했다 — 계획서·체크리스트와 동일하게 맞춘다.)
- **닫은 결함**: 대화 ID 충돌·저장 형식 이전(CR-01) · 세션 저장 0바이트 유실·동시 writer(CR-02) · sandbox 읽기 누출(CR-03) · API shell의 권한 모드 무시·env 상속(CR-04) · provider 키의 브라우저 영속(CR-05) · 설정 화면이 서버 진실 미반영(CR-02/06) · 오류 경계·404 부재(CR-07) · provider 입력의 접근성 이름 부재·팔레트 modal 계약 부재·IME 조합 Enter 오인(CR-08) · 필수 렌더링의 CDN 의존과 오프라인에서 편집기가 뜨지 않던 문제(CR-09 — Monaco CDN 로더는 그때 실측으로 추가 발견) · **고정 운영 지표와 빌드 provenance 부재(CR-10 — BUILD/UPTIME/NODE/CTRL 하드코딩, 업타임이 프로세스가 아니었고 화면이 percent를 MB로 표시)** · **설치 전에 src-layout 모듈을 실행하던 CI/release 부트스트랩과 출하되지 않는 의존성만 감사하던 경로(CR-11 — `[rag]`가 한 번도 감사되지 않아 chromadb 권고 4건이 gate에 도달하지 못했고, 예외 레지스트리 id도 도구 출력과 불일치)** · **확장 README가 없는 능력("Automatic reconnection and offline support")을 광고하던 문제와 승인 미완료가 상태로 표시되지 않던 문제·인수 절차 부재·과거 RP와 현재 CR 상태 혼동(CR-12 — 배경 재연결·오프라인 큐는 계획대로 신설하지 않고 문구를 실제 계약으로 교체)** · **이전 후보 증거의 재사용과 비불변 artifact(R03 — RP-13 manifest의 artifact 1건 드리프트에도 `manifest_verifier: PASS` 선언이 남았고 참조 11개가 전부 호스트 절대 경로였음; R04 — RP-12 후보 증거가 현재 후보 검증에 그대로 쓰일 수 있었음. CR-13 — 증거를 자기완결 번들로 만들고 후보 SHA·gate·soak에 묶음)**. 구체 계약은 `08_CHANGELOG.md`의 2026-09-12 절과 각 attempt의 `decision.md`에 있다.
- **검증**: CR-01~13 게이트 통과 — 전체 Python suite **6102 passed/13 skipped**(CR-13 기준, 449s), 대시보드 Vitest **80 files/840 passed**, Playwright 실제 chromium: CR-10 텔레메트리 4 passed·CR-09 오프라인 4 passed·접근성·키보드·복구 회귀 79 passed, `tsc -b`·`eslint`(0 errors)·`vite build` exit 0, ruff·format·mypy exit 0, basedpyright 0 errors, `test_dashboard_wheel_assets.py` 1 passed. CR-12는 정적 증인으로 HEAD 트리에서 **5/5 문서·문구 결함 재현(exit 1)** 후 현재 트리에서 **0건(exit 0)**을, 같은 HEAD 트리에서 새 회귀 테스트 **15 failed** 후 현재 트리 **25 passed**를 실측했다. CR-11은 HEAD 트리에서 같은 프로브로 **4/4 결함 재현(rc=1)** 후 현재 트리에서 **4/4 해소(rc=0)**를 실측했고, 감사 게이트·저장소 밖 wheel/sdist 검증·번들 hash 대조를 모두 exit 0으로 통과했다. 재현→수정→회귀 순서와 로그 원문은 `.omo/evidence/commercial-reliability/CR-0X/attempt-001/logs/`에 보존했다.
- **남은 blocker**: ① 독립 검토 미배정(CR-01~13 전부 — CR-12는 증인의 부정문 판정 로직, CR-13은 `required_gates`를 비우면 gate 검사를 건너뛰는 우회 경로가 검토 대상이다). 그리고 **법무·개인정보·보안·provider 약관 승인 미취득**(`BLOCKED_EXTERNAL`, 해제 주체는 외부 당사자뿐이고 CR-14 GO/NO-GO에서 열린 blocker로 유지 — CR-12가 상태로 표시한 것이지 해소한 것이 아니다) ② 커밋 full SHA 미확정 — 승인 전 동일 SHA에서 전체 게이트 재실행 필요 ③ **커밋 재빌드 정책 미정** — attempt-002에서 mermaid 승격을 반영해 `dashboard_dist`를 **재빌드된 상태로 남겼다**(HEAD로 되돌리지 않았다. HEAD 번들은 소스와 다른 취약한 코드를 담는다). 추적 자체를 계속할지·커밋 시점에 재빌드할지는 출시 책임자 결정이다(F-01). CR-11부터 CI·릴리스는 패키징 전에 재빌드하고 새 번들이 wheel에 들어갔는지 hash로 대조하지만, `clean-machine` gate는 `git archive HEAD`를 쓰므로 **추적 번들이 낡아 있으면 그 gate는 낡은 UI를 포장한다** ④ 실제 스크린리더 낭독·Firefox/Safari 접근성 미실측(자동 gate만 통과)와 CR-10의 다중 worker `process_id`·장기 stale 전이 미실측 ⑤ CR-03의 Linux/Docker sandbox backend 미실측 ⑥ CSP의 CDN 허용 목록 정리(CR-09 D-08)와 Mermaid 클로저의 EPL-2.0(elkjs) 고지 요건은 보안/법무 검토 대기 ⑦ chromadb 탐지 4건의 예외 만료 **2026-12-08**(상류 fix 확인 필요) ⑧ hosted GitHub Actions 실행 미실측(새 job 배선은 YAML 파싱·스크립트 직접 실행·계약 테스트로만 검증).
- **해소**: CR-07이 남긴 "접근성 게이트 매트릭스에 404 화면 미포함"은 CR-08 D-06이 닫았다(UI-01·UI-02 매트릭스 16 → 17 route, 404 화면 위반 0).
- **운영 영향**: CR-01은 legacy 대화 파일 잔존 시 503 fail-closed(런북 이전 필요), CR-02는 구버전 프로세스와 동시 실행 미지원, CR-04는 `security.sandbox_enabled=false` 배포에서 `/api/agent/tools/shell/run`이 동작하지 않음, CR-05는 `GET /api/settings` 응답 형태 변경(파괴적 변경)과 legacy 키 재입력 가능성, CR-08은 팔레트가 열린 동안 배경이 `inert`(사이드바·상단 바 포함)이고 공용 훅은 팔레트에만 적용(다른 모달은 아직 미적용), CR-09는 필수 렌더링이 더 이상 CDN에 의존하지 않으나(폰트 시스템 스택·테마 로컬 번들·Mermaid 지연 import·Monaco 로컬 워커) Mermaid 클로저가 런타임 의존성으로 늘어나 SBOM/notice가 커지고 `declared_licenses` 유지보수가 필요하다. CR-10은 헤더 지표가 더 이상 고정 문자열이 아니게 됐다 — `BUILD`는 실제 서버 버전, `UPTIME`은 프로세스 monotonic 가동 시간(재시작 시 0부터), 값이 없으면 `UNKNOWN`, 연결이 끊기면 `healthy: null`로 `NOMINAL`을 주장하지 않음, `MEM`은 `%`(`memory_percent`), `LINK`가 `LIVE`/`STALE`(30s 초과)/`OFFLINE`(고정 `CTRL` 문구는 삭제). legacy `memory_mb` 키는 percent 값인 채로 남아 있고, `uptime_seconds`의 의미가 "벽시계 차이"에서 "프로세스 가동 시간"으로 바뀐다(호스트 업타임이 필요하면 별도 지표가 필요하다). 계약은 [런타임 텔레메트리 문서](./ga/CR10_RUNTIME_TELEMETRY.md). **CR-11은 CI·릴리스가 설치 없는 src-layout 실행과 출하되지 않는 의존성 감사에 기대지 않게 했다** — Python 게이트는 `uv sync --locked --no-editable --extra dev` 한 환경에서 돌고 감사는 base + 출하 extra(`[rag]`)를 대상으로 하며(입력 기록·음성 입력 거부), Node/pnpm은 Node 22.13 + pnpm 11.3.0으로 통일됐다. 그 결과 **chromadb 1.5.9 권고 4건이 처음으로 gate에 도달**했고 REL-03 예외(owner·만료 2026-12-08)로 판정된다. 릴리스는 패키징 전에 대시보드를 재빌드해 새 번들이 wheel에 들어갔는지 hash로 대조하고, `dry_run` 입력이 실제로 소비되어 수동 실행은 아무 것도 배포하지 않는다. 계약은 [릴리스 부트스트랩 문서](./ga/CR11_RELEASE_BOOTSTRAP_AND_AUDIT.md). **CR-12는 지원·운영 문구를 실제 동작에 맞췄다** — VS Code 확장은 context-sync companion이고 **배경 재연결 타이머·오프라인 큐가 없다**(엔진이 죽어 있으면 다음 편집기 이벤트에 재시도)이므로 “자동 재연결·오프라인 지원”으로 설명하는 문구는 더 이상 쓸 수 없다. 미완료 승인은 주장 레지스트리·지원 매트릭스에서 `BLOCKED_EXTERNAL`(해제 주체 명시)로 보존되며 **플랫폼·provider 분류는 하나도 승격되지 않았다**(전부 Experimental/Unsupported). 런북 3종(세션 저장 실패 · 키 재입력 · sandbox unavailable)이 운영 절차의 단일 원본이다.
- **운영 영향(CR-14 attempt-002)**: ① `Dockerfile` dashboard-builder 스테이지의 `ENV NODE_OPTIONS=--max-old-space-size=4096`를 지우면 `docker-build`가 다시 콜드 `tsc -b` heap OOM으로 실패한다(로컬 빌드 성공은 컨테이너 성공을 의미하지 않는다). ② 라벨 주입 차단은 `mermaidRuntime`의 **두 지점**에 의존한다 — 한쪽만 남기면 비컨이 되살아난다(`dashboard/e2e/tests/cr09-offline-assets.spec.ts`의 `C09-03`이 상시 감시자이며, 이 단언을 약화시키는 변경은 F-04를 되돌리는 것이다). ③ `python-tests` 실행 뒤 `git checkout -- data/benchmark_results.json`을 하지 않으면 새 코드 지문이 생겨 단계별 gate 병합이 거부된다.
- **운영 영향(CR-13)**: 릴리스 증거는 **자기완결 번들**로만 승인 가능하다 — artifact가 번들 안 상대 경로에 복사되고, hash는 redaction 이후 바이트에서 계산되며, `--expected-sha`로 후보 SHA에 묶인다(다른 후보 증거 재사용은 거부). 번들은 `verdict`/`status` 자기 승인을 적을 수 없고(판정은 검증기 출력), **`required_gates`를 비우면 gate 검사가 사라진다** — CR-14가 반드시 채워야 한다. 과거 후보 증거는 `historical: true` 참고용만 가능하며 gate/soak 근거가 될 수 없다. 계약·절차는 [증거 번들 문서](./ga/CR13_EVIDENCE_BUNDLE.md).
- **다음 작업**: **CR-14 attempt-003**(최종 후보 전체 검증과 GO/NO-GO). 순서는 F-02(`data/benchmark_results.json` 격리) → F-01(`dashboard_dist` 정책) → CR-01~14 커밋·clean full SHA 확정 → 그 SHA에서 20-gate 재실행 → `scripts/evidence_bundle.py build`로 릴리스 번들을 만들고 `required_gates`를 **반드시 채운** 뒤 `verify --expected-sha`로 고정 → 독립 검토·출시 책임자 배정 → C14-03/04/05. attempt-002에서 required gate 20/20 PASS를 달성했으므로 **다음 변경은 그 지문 위에서 다시 검증**해야 한다.
