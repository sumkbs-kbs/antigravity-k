# 1MB 초과 증거 파일 매니페스트 (커밋 정책: pre-commit check-added-large-files --maxkb=1024)

이 파일들은 카드의 원본 증거지만 `.pre-commit-config.yaml` 의 크기 상한(1,024 KB)을 넘어
**커밋하지 않았다**(우회하지 않는다: 정책은 우회하는 순간 정책이 아니다). 원본은 작업 트리에
그대로 남아 있고, 아래 sha256 으로 동일성을 검증할 수 있다.

검증: `shasum -a 256 <path>` 가 아래 값과 같아야 한다.

(기준: 2026-09-16 커밋 `1bd95e7d` — 이 시점에 존재한 게이트 리포트 중 1MB 초과분. 커밋 `89dd383b`
기준으로 추가된 것은 `promote004` 하나다.)

- `docs/qa/2026-09-16-followup/nx10/gate-report-promote004.json` — 1,244,862 B — sha256 `f57f5872304de722b1cc105045f40e492da282f03cf20761f1860b22a4458002`

- `docs/qa/2026-09-16-followup/nx10/gate-report-promote001.json` — 1,299,969 B — sha256 `9cc9a85bb475400387caf84e98b25b44e575e5c92005de51d66dfc853d7d9df0`
- `docs/qa/2026-09-16-followup/nx10/gate-report-freeze002.json` — 1,290,610 B — sha256 `c0f1090384d5199490d771f20d0fcc9b046a32671cd4644c661b7146a2b3a578`
- `docs/qa/2026-09-16-followup/nx10/gate-report-full001.json` — 1,287,374 B — sha256 `1f95e7f2d776737c043cd9de1c2dd73cb8844a257ff233490e65f302a9900347`
- `docs/qa/2026-09-16-followup/nx10/gate-report-promote003.json` — 1,244,246 B — sha256 `9209519ec48727686a8775c5cde3e8fd827d9ebe7f92cbf39b72429d97025d86`
- `docs/qa/2026-09-16-followup/nx10/gate-report-promote002.json` — 1,236,044 B — sha256 `97d181c2e57ef224d172c46ad7753b6ea4f89474edeea3b2acc9ac63f13970bd`

리포트별 의미(값 소유자는 [GATE_LEDGER.md](./GATE_LEDGER.md)):
- `full001` — 승격 이전 트리, 22개 중 21 passed
- `freeze002` — 동결 배치 트리 `157311cf…`, 22개 중 21 passed
- `promote001` — 승격 직후(측정 중 편집으로 지문이 갈린 attempt, 참고용)
- `promote002` — 승격 반영 트리 `0f345d0c…`, 22개 중 21 passed
- `promote003` — **커밋된 후보 `89dd383b`, 23개 중 22 passed · 1 failed · 0 not_run**
- `promote004` — **커밋된 후보 `1bd95e7d`(회수 판정기 수정), 23개 중 22 passed · 1 failed · 0 not_run**(실패는 타 레인 `python-tests` 뿐)

작은 동반 증거(`gate_verify-*.txt`)는 커밋되어 있다.
