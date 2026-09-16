# 1MB 초과 증거 파일 매니페스트 (커밋 정책: pre-commit check-added-large-files --maxkb=1024)

이 파일들은 카드의 원본 증거지만 `.pre-commit-config.yaml` 의 크기 상한(1,024 KB)을 넘어
**커밋하지 않았다**(우회하지 않는다: 정책은 우회하는 순간 정책이 아니다). 원본은 작업 트리에
그대로 남아 있고, 아래 sha256 으로 동일성을 검증할 수 있다.

검증: `shasum -a 256 <path>` 가 아래 값과 같아야 한다.

- `docs/qa/2026-09-16-followup/nx10/gate-report-promote001.json` — 1,299,969 B — sha256 `9cc9a85bb475400387caf84e98b25b44e575e5c92005de51d66dfc853d7d9df0`
- `docs/qa/2026-09-16-followup/nx10/gate-report-freeze002.json` — 1,290,610 B — sha256 `c0f1090384d5199490d771f20d0fcc9b046a32671cd4644c661b7146a2b3a578`
- `docs/qa/2026-09-16-followup/nx10/gate-report-full001.json` — 1,287,374 B — sha256 `1f95e7f2d776737c043cd9de1c2dd73cb8844a257ff233490e65f302a9900347`
- `docs/qa/2026-09-16-followup/nx10/gate-report-promote002.json` — 1,236,044 B — sha256 `97d181c2e57ef224d172c46ad7753b6ea4f89474edeea3b2acc9ac63f13970bd`
