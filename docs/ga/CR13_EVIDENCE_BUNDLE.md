---
title: CR-13 증거 번들 계약 (자기완결·불변·후보 SHA 결합)
status: REVIEW (독립 검토 미배정, 코드 미커밋)
date: 2026-09-12
baseline_sha: 08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f
evidence: .omo/evidence/commercial-reliability/CR-13/attempt-001/
related: [../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md, ../17_COMMERCIAL_RELIABILITY_CHECKLIST.md]
tags: [ga, evidence, release, immutability, runbook]
---

# CR-13 증거 번들 계약

이 문서는 **릴리스 증거를 어떻게 포장하고 검증하는지**를 고정한다. 실제 릴리스 번들은
CR-14에서 만들고, 여기서는 수집기·검증기와 그 계약을 정의한다.

## 1. 왜 바뀌었는가 (문제)

RP-13 attempt-002의 `release-manifest.json`은 증거 11개를 **호스트 절대 경로**로 가리켰다.

| 문제 | 실측 |
|---|---|
| 번들이 아니다 | artifact 11개 중 증거 폴더 내부 경로 **0개**(`/tmp`, 다른 worktree 절대 경로 11개) |
| 원본이 바뀌면 깨진다 | `benchmark-results`가 현재 파일과 sha256·size 모두 불일치 → 검증기 exit 1 (**R03**) |
| 선언과 원문이 어긋난다 | 같은 attempt `metadata.json`은 `manifest_verifier: PASS`인데 실제 검증은 FAIL |
| 다른 후보 증거를 재사용할 수 있다 | manifest `source_sha`는 RP-12 후보 `4b202113…`, 이번 기준은 `08b8bb2e…` (**R04**) |
| 탈출·절대 경로를 거부하지 않는다 | 기존 검증기는 `../`·`/absolute` 경로를 통과시킨다(중복 id만 거부) |

## 2. 계약

```
uv run scripts/evidence_bundle.py build  --spec spec.json --output bundle [--source-root .]
uv run scripts/evidence_bundle.py verify --bundle bundle [--expected-sha <40-hex>] [--min-soak-seconds N]
```

- `build`는 artifact를 `<bundle>/artifacts/<id>/<name>`으로 **복사**하고, redaction을 적용한
  **뒤에** size·sha256을 계산한다. manifest에는 번들 상대 경로만 남는다.
- `verify`는 **번들만** 보고 판정한다. 원본 경로·원본 파일이 필요 없다.
- 판정(PASS/FAIL)은 `verify`의 출력이다. manifest에 `verdict`/`status`/`manifest_verifier`를
  넣으면 검증이 거부한다.

### 거부 규칙

| 기준 | 거부 대상 |
|---|---|
| C13-01 | 절대 경로, `..`, 번들 밖 경로, 심볼릭 링크 artifact |
| C13-02 | 누락, 중복 id, sha256 불일치, size 불일치, manifest 변조(sidecar `manifest.sha256` 불일치) |
| C13-03 | `--expected-sha` 불일치, 필수 gate 누락/실패, 짧은 soak, gate 요약 재계산 불일치 |
| C13-04 | `historical` 증거가 gate/soak 역할을 채우는 경우 |
| C13-05 | 번들의 자기 PASS 주장, redaction 후에도 남은 호스트 경로, 수집 시 secret 형태 내용 |

### spec 형식 (`bundle-spec.json`)

| 키 | 의미 |
|---|---|
| `source_sha` | 후보 full 40-hex (필수). `verify --expected-sha`가 이 값과 대조된다 |
| `required_gates` | `scripts/commercial_ga_gates.json`의 필수 gate id. **비우면 gate 검사를 건너뛴다** |
| `soak` | `{scenario, actual_duration_s, min_seconds}` — `actual < min`이면 FAIL |
| `redaction` | 지울 문자열 목록(홈·저장소 루트는 자동 포함) |
| `artifacts[]` | `{id, role, source, historical?, origin_sha?}`. `role`은 `gate-report`/`log`/`package`/`reference`/`tool` 등 |
| `candidate`·`tool`·`environment`·`commands`·`lockfiles` | 재현에 필요한 맥락(도구·명령·exit·lock hash) |

## 3. CR-14에서 할 일 (릴리스 번들 만들기)

1. 후보 full SHA 확정 → `spec.source_sha`에 기입.
2. `required_gates`를 **반드시** 채운다(비우면 gate 검사가 사라진다).
3. gate report·soak 결과·wheel/sdist·SBOM·notice·로그를 artifact로 넣는다.
   과거 후보 증거는 `historical: true` + `origin_sha`로 **참고용**으로만 넣는다(gate 역할 금지).
4. `verify --expected-sha <후보 SHA>`가 exit 0인지 확인하고 원문을 남긴다.
5. `BLOCKED_EXTERNAL`(법무·개인정보·보안·provider 약관)은 열린 blocker로 최종 판정에 반영한다.

## 4. 롤백·재검증

- 번들은 자기완결이므로 **다른 위치로 복사해도** 같은 판정이 나온다(원본 트리 불필요).
- 검증 실패 시 번들을 고쳐 PASS로 만들지 않는다. 새 attempt를 만들고 실패한 번들은 보존한다.
- 과거 attempt의 드리프트는 사후에 고치지 않는다 — "그때의 증거"와 "지금 파일"의 차이가
  기록이기 때문이다(CR-13에서 RP-13 드리프트를 그대로 남긴 이유).

## 5. 남은 위험 / 지원 범위

- `required_gates`가 비면 gate 검사가 없다(우회 경로). CR-14에서 채워야 하며, 상시 gate로
  승격할지는 그때 결정한다(현재 `scripts/commercial_ga_gates.json`은 손대지 않았다).
- sidecar 재계산 편집 자체는 막지 못한다(서명·불변 스토리지는 범위 밖). 다만 artifact hash와
  원문 요약 재계산이 그 뒤를 받친다.
- redaction은 문자열 치환이므로 압축·이미지 내부 경로는 잡지 못한다.
- secret은 redaction하지 않고 **수집을 거부**한다(키가 섞인 산출물은 만들지 않는 쪽이 안전).
- 실 28,800초 soak·실 배포 산출물로 만든 릴리스 번들은 아직 없다(CR-14).
