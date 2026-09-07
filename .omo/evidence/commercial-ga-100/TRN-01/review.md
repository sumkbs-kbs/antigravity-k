# TRN-01 독립 리뷰 — r1 APPROVE

- **Reviewer:** trn_01_verify (구현자 trn_01_impl과 상이한 세션 — Freebuff/Claude 세션, 2026-09-07)
- **검증 대상:** baseline에 병합된 `codex/trn-01-recipe-source` @ `717ee89` (merge `583911a`)
- **Verdict:** **APPROVE** — 발견 결함 0건. 수용기준 4건 전부 독립 재현으로 확인.

## 검증 방법

1. **구현자 테스트 재실행**: `test_trn01_recipe_single_source.py` **18 passed** (병합 후 baseline에서)
2. **독립 시나리오 재현** (구현자 테스트와 별개 스크립트, `hyperparameters.py` 직접 호출):
   - **AC-1 validation**: `iterations=0/-3`, `batch_size=99999`, 미지원 키, `learning_rate=1.5` 전부 실행 전 `HyperparameterValidationError` 거절 · 유효 LR(`2e-4`)은 정규화 통과 · mlx에서 unsloth 전용 키 거절 — **PASS**
   - **AC-2 capability**: mlx `executable=True`, unsloth `executable=False`(로컬 실행 불가 명시), 미지원 백엔드(`tpu`) 거절 — **PASS**
   - **AC-3 digest 결정성**: 동일 입력 → 동일 SHA-256, iterations 변경 → 다른 digest, **키 순서/LR 표기 차이(`2e-4` vs `2E-4`)에도 동일 digest** — **PASS**
   - **AC-4 단일 resolve**: `apply_recipe`에 `iterations=777, learning_rate=3e-4` 전달 → 생성된 mlx-lm 명령에 `--iters 777 --learning-rate 3e-4` 반영, config `hyperparameters`와 동일 값, `recipe_sha256` 동봉 — request→argv/config→digest가 한 경로로 일치 — **PASS**
3. **회귀 대조**: 구현 단계에서 base 대비 8건 신규 실패가 기존 테스트의 옛 비일관 동작(config는 auto→mlx 해석, dataset_path는 원본 파일) 의존임을 확인하고 9건을 새 계약으로 마이그레이션 — 병합 후 전체 스위트 실패 목록이 baseline과 byte-identical (9=9).

## 비고

- 레시피 카탈로그는 `jsonl-to-chat`/`csv-to-chat` 등 8종 — 리뷰 재현 시 `csv-qa-sft`(존재하지 않음) 오타로 1회 실패 후 올바른 이름으로 재현. API 오류 메시지가 지원 목록을 안내해 주어 UX 양호.
- `apply_recipe`의 mlx dataset_path는 train/valid 분할 디렉터 — 이것이 새 통합 계약이며 구현자 테스트와 일치.

## 결론

TRN-01 **DONE** 판정. 브랜치는 audit trail로 보존.
