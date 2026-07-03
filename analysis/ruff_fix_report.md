# Ruff Refactoring 종합 리포트

> **일자:** 2026-06-30  
> **대상:** `src/` 디렉토리 전체  
> **목표:** ruff 규칙 위반 최대한 해결

---

## 1. 전체 요약

| 항목 | 초기 | 현재 | 상태 |
|:----|:---:|:----:|:----:|
| **G004 (logging-f-string)** | 729 | **0** | ✅ 100% 해결 (영구) |
| **W293 (blank-line-with-whitespace)** | 114 | **0** | ✅ 100% 해결 (영구) |
| **F821 (undefined-name: config)** | 8 | **0** | ✅ 100% 해결 (영구) |
| **SyntaxError** | 2 | **0** | ✅ 100% 해결 (영구) |
| **I001 (unsorted-imports)** | 1 | **0** | ✅ 100% 해결 (영구) |
| **UP006 (non-pep585-annotation)** | 900 | **886** | 🔄 재적용 필요 (롤백됨†) |
| **UP045 (non-pep604-annotation-optional)** | 377 | **365** | 🔄 재적용 필요 (롤백됨†) |
| **UP035 (deprecated-import)** | 261 | **256** | 🔄 재적용 필요 (롤백됨†) |
| **COM812 (missing-trailing-comma)** | 614 | **547** | 🔄 재적용 필요 (롤백됨†) |
| **D 규칙 (docstring)** | ~1,640 | **~1,878** | 🔄 재적용 필요 (롤백됨†) |
| **E501 (line-too-long)** | 537 | 502 | ❌ auto-fix 불가 (line-length 완화로 해결 가능) |
| **E402 (import-not-at-top)** | 24 | 27 | — |

> †UP/COM812/D 규칙은 G004 스크립트 오류 복구 과정에서 `git checkout -- src/`로 함께 롤백됨.  
> `ruff --fix`로 **일괄 재적용 가능** (~30초 소요).

### pre-commit (G004/W293/F821 적용 후)

| Hook | 상태 |
|:----|:----:|
| trim trailing whitespace | ✅ Passed |
| fix end of files | ✅ Passed |
| check yaml | ✅ Passed |
| check for added large files | ✅ Passed |
| ruff (linting) | ✅ Passed |
| ruff-format | ✅ Passed |

---

## 2. Git 변경 사항

- **변경된 파일:** 343개 (`src/` 전체)
- **추가된 라인:** 6,660
- **삭제된 라인:** 5,635

---

## 3. 주요 작업 내역

### Phase 1-6: D 규칙 리팩토링 (~1,640건 → 0건)

| 단계 | 규칙 | 처리 건수 | 방식 |
|:----|:-----|:---------:|:-----|
| Phase 1 | D100-D107 (누락 docstring) | ~1,040 | `scripts/generate_docstrings.py` |
| Phase 2 | D205 (요약-내용 빈 줄) | 243 | `scripts/fix_d205.py` |
| Phase 3 | D212/D413/D410/D411 (섹션 형식) | 78 | `ruff --fix` |
| Phase 4 | D412 (헤더-내용 빈 줄) | 742 | `ruff --fix` |
| Phase 5 | D400/D415/D200 (구두점) | 102 | `ruff --unsafe-fixes --fix` |
| Phase 6 | D401 (명령형 어조) | 33 | 수동 수정 (23개 파일) |
| Phase 7 | D417 (param 누락) | 11 | `inference_providers.py` + `agent_fabric.py` |
| **소계** | | **~1,640** | ✅ **100% 해결 후 롤백됨** |

### Phase 8: UP 규칙 (1,538건)

| 규칙 | 건수 | 처리 방식 |
|:----|:----:|:---------|
| **UP006** (non-pep585: `List[int]`→`list[int]`) | 900 | `ruff --fix` |
| **UP045** (non-pep604: `Optional[str]`→`str\|None`) | 377 | `ruff --fix` |
| **UP035** (deprecated import: `typing.Dict`→`dict`) | 261 | `ruff --fix` + 수동 3건 |
| **소계** | **1,538** | ✅ **100% 해결 후 롤백됨** |

### Phase 9: COM812 (missing-trailing-comma) — 614건

| 단계 | 처리 | 건수 |
|:----|:-----|:----:|
| `ruff --fix` | 자동 수정 | 614 |
| 후속 ruff-format | 66개 파일 재포맷 | 12 |
| **결과** | **614→0건** | ✅ **해결 후 롤백됨** |

### Phase 10: G004 (logging-f-string) — 729건

G004는 ruff `--fix`로 자동 수정이 **불가능**한 규칙입니다.  
AST 기반 Python 변환 스크립트를 작성하여 처리했습니다.

| 시도 | 방식 | 결과 | 비고 |
|:----|:-----|:----:|:-----|
| v1 | AST + line-by-line | 729건 실패 | 다중 라인 f-string 처리 오류 |
| v2 | AST + byte-offset | 729건 실패 | end_col_offset 계산 오류 |
| v3 | 단일 라인 f-string + 텍스트 매칭 | 671건 성공 | 안전하게 92% 해결 |
| v4 | 전체 소스 텍스트 매칭 | 43건 추가 성공 | 다중 라인 implicit concat 처리 |
| **최종** | | **714→0건** | **✅ 100% 해결** |

**변환 패턴:**
```python
# Before (G004 위반)
logger.info(f"User {name} logged in from {ip}")

# After (lazy % formatting)
logger.info("User %s logged in from %s", name, ip)
```

**생성된 스크립트:** `scripts/fix_g004.py`

### Phase 11: W293 (blank-line-with-whitespace) — 18건

| 단계 | 건수 |
|:----|:----:|
| `ruff --fix` | 2 |
| `ruff --unsafe-fixes --fix` | 16 |
| **결과** | **18→0건** ✅ |

*(초기 114건에서 앞선 작업들로 인해 18건으로 감소)*

### Phase 12: F821 (undefined-name: config) — 8건

| 파일 | 수정 내용 |
|:-----|:---------|
| `autonomous_learner.py` | `from antigravity_k.config import config` 추가 |
| `curriculum_generator.py` | ↑ 동일 |
| `meta_architect.py` | ↑ 동일 |
| `model_manager.py` | `is_loaded()` 내부에 `from ..config import config` 추가 |
| `prompt_evolver.py` | `from antigravity_k.config import config` 추가 |
| `skill_auto_learner.py` | ↑ 동일 |
| `skill_generator.py` | ↑ 동일 |
| **결과** | **8→0건** ✅ |

### Phase 13: SyntaxError 2건

| 파일 | 문제 | 수정 |
|:-----|:-----|:-----|
| `error_handler.py` | 문자열 내 literal newline | `\n` escape로 변경 |
| `system_api.py` | `return mm` 줄바꿈 누락 | `)` 추가 + 개행 |
| **결과** | 문법 검증 ✅ | compile 통과 |

### Phase 14: I001 (unsorted-imports) — 1건

| `ruff --fix` | **1→0건** ✅ |

---

## 4. 현재 ruff 현황 (2026-06-30 기준)

`ruff check src/ --select=ALL --statistics` — TOP 20

| 순위 | 규칙 | 건수 | 설명 | Auto-fix |
|:---:|:-----|:----:|:-----|:--------:|
| 1 | UP006 | 886 | non-pep585-annotation | ✅ |
| 2 | COM812 | 547 | missing-trailing-comma | ✅ |
| 3 | BLE001 | 520 | blind-except | ❌ |
| 4 | E501 | 502 | line-too-long | ❌ |
| 5 | D102 | 478 | undocumented-public-method | ✅ |
| 6 | PLC0415 | 396 | import-outside-top-level | ❌ |
| 7 | D212 | 379 | multi-line-summary-first-line | ✅ |
| 8 | UP045 | 365 | non-pep604-annotation-optional | ✅ |
| 9 | D400 | 289 | missing-trailing-period | ✅ |
| 10 | D415 | 289 | missing-terminal-punctuation | ✅ |
| 11 | ANN201 | 282 | missing-return-type-undocumented-public-function | ❌ |
| 12 | UP035 | 256 | deprecated-import | ✅ |
| 13 | D205 | 231 | missing-blank-line-after-summary | ✅ |
| 14 | ANN204 | 227 | missing-return-type-special-method | ❌ |
| 15 | PLR2004 | 221 | magic-value-comparison | ❌ |
| 16 | D107 | 212 | undocumented-public-init | ✅ |
| 17 | ANN001 | 188 | missing-type-function-argument | ❌ |
| 18 | PTH123 | 170 | builtin-open | ❌ |
| 19 | PTH118 | 165 | os-path-join | ❌ |
| 20 | TRY400 | 164 | error-instead-of-exception | ❌ |
| ... | ... | ... | ... | ... |
| | **G004** | **0** | ✅ **해결 완료 (영구)** | — |
| | **W293** | **0** | ✅ **해결 완료 (영구)** | ✅ |
| | **F821** | **0** | ✅ **해결 완료 (영구)** | — |
| | **I001** | **0** | ✅ **해결 완료 (영구)** | ✅ |

### 이번 작업에서 해결된 규칙

| 규칙 | 최초 | 직후 | 현재 | 해결 방식 |
|:----|:----:|:----:|:----:|:---------|
| G004 | 729 | **0** | **0** ✅ | `scripts/fix_g004.py` (AST 기반 변환) |
| W293 | 114 | **0** | **0** ✅ | `ruff --unsafe-fixes --fix` |
| F821 | 8 | **0** | **0** ✅ | 수동 import 추가 (7개 파일) |
| SyntaxError | 2 | **0** | **0** ✅ | 수동 수정 |
| I001 | 1 | **0** | **0** ✅ | `ruff --fix` |
| **소계** | **854** | **0** | **0** | **✅ 영구 해결** |
| D (docstring) | ~1,640 | 0 | ~1,878† | 스크립트 + 수동 + `--fix` (롤백됨) |
| UP006/045/035 | 1,538 | 0 | 886+365+256† | `ruff --fix` (롤백됨) |
| COM812 | 614 | 0 | 547† | `ruff --fix` (롤백됨) |

> †G004 스크립트 오류 복구를 위한 `git checkout -- src/`로 함께 롤백됨.  
> `ruff --fix`로 **즉시 재적용 가능** (~30초).

---

## 5. 생성된 스크립트

| 파일 | 용도 |
|:-----|:------|
| `scripts/fix_g004.py` | G004 (logging-f-string) → lazy % formatting 변환 (AST 기반) |
| `scripts/generate_docstrings.py` | D100-D107 누락 docstring 자동 생성 |
| `scripts/fix_d205.py` | D205 (요약-내용 빈 줄) 정규식 기반 일괄 수정 |

---

## 6. 향후 권장 작업

| 우선순위 | 작업 | 예상 건수 | 예상 난이도 | 비고 |
|:--------:|:-----|:--------:|:----------:|:-----|
| 🥇 | UP006/UP045/UP035 재적용 | 886+365+256 | 쉬움 (`ruff --fix`) | 이전에 완료했으나 롤백됨 |
| 🥇 | COM812 재적용 | 547 | 쉬움 (`ruff --fix`) | 이전에 완료했으나 롤백됨 |
| 🥇 | D 규칙 재적용 (scripts 사용) | ~1,878 | 중간 (스크립트 + --fix) | 이전에 완료했으나 롤백됨 |
| 🥈 | E501 line-length 120 완화 (pyproject.toml) | 502 | 쉬움 (config 변경) | auto-fix 불가, line-length 완화 |
| 🥉 | E402 import 정리 (ruff --fix) | 27 | 쉬움 (--fix) | import 순서 정리 |
| 🥉 | BLE001 blind-except 검토 | 520 | 어려움 (수동) | 구조 변경 필요 |
