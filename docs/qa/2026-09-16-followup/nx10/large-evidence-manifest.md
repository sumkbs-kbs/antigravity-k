# 1MB 초과 증거 파일 매니페스트 (커밋 정책: pre-commit check-added-large-files --maxkb=1024)

이 파일들은 카드의 원본 증거지만 `.pre-commit-config.yaml` 의 크기 상한(1,024 KB)을 넘어
**커밋하지 않았다**(우회하지 않는다: 정책은 우회하는 순간 정책이 아니다). 원본은 작업 트리에
그대로 남아 있고, 아래 sha256 으로 동일성을 검증할 수 있다.

검증: `shasum -a 256 <path>` 가 아래 값과 같아야 한다.

(기준: 2026-09-16 커밋 `1bd95e7d` — 이 시점에 존재한 게이트 리포트 중 1MB 초과분. 커밋 `89dd383b`
기준으로 추가된 것은 `promote004` 하나다.)

- `docs/qa/2026-09-16-followup/nx10/gate-report-promote004.json` — 1,244,862 B — sha256 `f57f5872304de722b1cc105045f40e492da282f03cf20761f1860b22a4458002`
- `docs/qa/2026-09-16-followup/nx10/gate-report-tailfix001.json` — 1,307,420 B — sha256 `99d3e26c94abdc32db0213be465cc2726f986983c1424573950f1eec9fb6a207`
  (커밋 `7d8c25b5`·`099cfc8b` 뒤 지문 `98855031…` = HEAD 에서 23개 전수 — **22 passed · 1 failed · 0 not_run**.
  이 리포트도 1MiB 를 넘으므로 정책대로 커밋하지 않는다 — 값은 [GATE_LEDGER.md](./GATE_LEDGER.md) §17 이 소유한다.)

- `docs/qa/2026-09-16-followup/nx10/gate-report-promote2b.json` — 1,318,584 B — sha256 `f2521acaa36e32d229e5c971bbd21610d4b480d164de698bdcb4e10cbbf6cc44`
- `docs/qa/2026-09-16-followup/nx10/gate-report-promote2c.json` — 1,247,722 B — sha256 `04a5eb814a40d00baa0e036621877caaaa54c4cab546f5c5108eaf7888e20f27`
- `docs/qa/2026-09-16-followup/nx10/gate-report-promote001.json` — 1,299,969 B — sha256 `9cc9a85bb475400387caf84e98b25b44e575e5c92005de51d66dfc853d7d9df0`
- `docs/qa/2026-09-16-followup/nx10/gate-report-freeze002.json` — 1,290,610 B — sha256 `c0f1090384d5199490d771f20d0fcc9b046a32671cd4644c661b7146a2b3a578`
- `docs/qa/2026-09-16-followup/nx10/gate-report-sc3fix001.json` — 1,309,851 B — sha256 `e9b75c79db4c43229e13393f844eb5c09b7e438ed953289b80fc9e804a32bf27`
- `docs/qa/2026-09-16-followup/nx10/gate-report-full001.json` — 1,287,374 B — sha256 `1f95e7f2d776737c043cd9de1c2dd73cb8844a257ff233490e65f302a9900347`
- `docs/qa/2026-09-16-followup/nx10/gate-report-promote003.json` — 1,244,246 B — sha256 `9209519ec48727686a8775c5cde3e8fd827d9ebe7f92cbf39b72429d97025d86`
- `docs/qa/2026-09-16-followup/nx10/gate-report-promote002.json` — 1,236,044 B — sha256 `97d181c2e57ef224d172c46ad7753b6ea4f89474edeea3b2acc9ac63f13970bd`

리포트별 의미(값 소유자는 [GATE_LEDGER.md](./GATE_LEDGER.md)):
- `full001` — 승격 이전 트리, 22개 중 21 passed
- `freeze002` — 동결 배치 트리 `157311cf…`, 22개 중 21 passed
- `promote001` — 승격 직후(측정 중 편집으로 지문이 갈린 attempt, 참고용)
- `promote002` — 승격 반영 트리 `0f345d0c…`, 22개 중 21 passed
- `promote003` — **커밋된 후보 `89dd383b`, 23개 중 22 passed · 1 failed · 0 not_run**
- `promote004` — **커밋된 후보 `1bd95e7d`(회수 판정기 수정), 23개 중 22 passed · 1 failed · 0 not_run**(실패는 타 레인 `python-tests` 5건)
- `tailfix001` — **커밋된 후보 `099cfc8b`(꼬리 창 수정), 23개 중 22 passed · 1 failed · 0 not_run** — 실패 목록이 `promote004` 와 **시험 단위로 동일**(새 실패 0건), `clean-machine-runtime` passed 43.0s
- `sc3fix001` — **커밋된 후보 `c522b256`(SC-3 경합 + 하네스 무한 대기 수정), 23개 중 22 passed · 1 failed · 0 not_run**, 시작 = 종료 = `5c90b637…` — 실패 목록은 여전히 `promote004` 와 시험 단위 동일(새 실패 0건), 통과 수 **6621 → 6626**(+5 = 새 계약 시험)
- `promote2b` — **커밋된 후보 `bde261dc`(2차 승격), 23개 중 21 passed · 2 failed · 0 not_run**, 시작 = 종료 = `50b82dd1…` — **승격이 처음으로 검사한 두 도구에서 타입 오류 12건**(`python-basedpyright` 신규 red). 회귀가 아니라 편입 효과다([PROMOTION_PLAN §1d](./PROMOTION_PLAN.md))
- `promote2c` — **커밋된 후보 `5c979c0f`(타입 수정), 23개 중 22 passed · 1 failed · 0 not_run**, 시작 = 종료 = `b6a74304…` — basedpyright **초록**, `clean-machine-runtime` passed, 남은 실패는 `python-tests` 하나
- `promote2d` — **697 KB 라 정책대로 커밋했다**(1MiB 미만): 같은 지문 `b6a74304…` 에서 `python-tests` **단독** 재측정 — 5 failed · 6640 passed(618.94s) · 실패 5건은 위와 시험 단위 동일 · sha256 `2049da4b4cc50cfaa2af6f514c95911b3d38e72cb9aa67ad833abe759da6caf4`

작은 동반 증거(`gate_verify-*.txt`)는 커밋되어 있다.
