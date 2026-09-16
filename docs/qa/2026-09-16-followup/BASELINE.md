---
title: 2026-09-16 후속 검토 기준 및 증거 보충
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
status: NO-GO
---

# 후속 검토 기준

## 현재 결론

8시간 재soak JSON은 SC-1~6 모두 PASS다. 기존 정밀 검토의 ‘최종 결과 대기’는 이 관측으로 갱신한다. 다만 로그 종료값141의 원인·시험 당시 후보 귀속은 미확정이다. 반복 요약의 요구사항 소실 및 삭제 세션 부활은 별도 수정이 필요하므로 출시 NO-GO는 유지한다.

| 측정 | 결과 |
|---|---:|
| 실제 시험 시간 | 28,801.318초 |
| 성공 append / revision | 12,102,886 / 12,102,886 |
| 최종 view 메시지 | 26 (soft max64) |
| RSS 시작→마지막 | 65.7→114.4MB |
| RSS 증가 / 기준 | 48.7 / 64MB |
| FD 증가 / 오류 / orphan | 0 / 0 / 0 |
| SC-1~6 / all_pass | 모두 true / true |
| 래퍼 로그 마지막 | finished exit:141 |
| 현재 HEAD 전체 gate 인증 | 이번 후속 작업에서 실행하지 않음 |

[요약 JSON](soak-summary.json)은 원본 SHA256과 sample 배열의 count/min/max/first/last를 포함한다. 원본은 `.omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/val02_soak_28800_resoake.json`이며 수정하지 않았다. 같은 경로의 `.log` 시작은2026-09-15 15:08:33 KST, JSON `generated_at`은06:08:33 UTC이다. harness는 시작 시각을 해당 필드에 쓰므로 이를 완료 시각으로 보지 않는다. 파일 수정 시각은15일23:08로 관측했지만 독립 종료 증명은 아니다.

`exit:141`은 SIGPIPE와 일치하는 종료값이지만 실제 원인은 래퍼/파이프 명령을 확인해야 한다. JSON을 먼저 파일로 기록하고 stdout으로 출력하는 harness 코드와는 양립하나, 이 설명을 입증된 원인으로 기록하지 않는다. JSON 지표 PASS 자체를 FAIL로 바꾸지도 않고 정상 exit0을 추정하지도 않는다.

## 보존한 이전 증거

- [원본 정밀 검토](REPORT.md): 당시 상태의 기록. 현재 soak 상태만 이 문서가 우선한다. 저장소 밖의 원래 절대 링크도 포함되어 있으므로 이 폴더의 동명 증거 파일을 이용할 수 있다.
- [독립 재검토](independent-review.md).
- [기존 좁은 회귀 로그](tests.log): 21passed. 이번 후속 문서 작업에서 새로 실행한 제품 테스트가 아니다.
- [실행 증거](runtime-evidence.txt): 이전 반복 요약 재현 등의 관측.

전체 파일 정독·전체 제품 동작 검증을 주장하지 않는다. 현재 기준은 위험 중심 정밀 검토이며 미검증 동선과 환경은 새 개발계획 NX-08~11에서 다룬다. 원본 검토의 과거23/23은 현재 HEAD 인증이 아니며, 로그가 보존되지 않은58PASS/1FAIL 보고는 공식 합산하지 않는다.

## 이번 산출물 및 변경 경계

- [상세 개발계획](../../18_RELIABILITY_AND_CONNECTOME_DEVELOPMENT_PLAN.md).
- [실행 체크리스트](../../19_RELIABILITY_AND_CONNECTOME_CHECKLIST.md).
- 제품 구현·gate/8시간 재시험·외부 provider 호출·패키징 재개·Git commit/push는 수행하지 않았다.
- 기존 `vault_data` 변경 및 인증 백업 경로를 보존했다. 비밀 내용은 읽거나 출력하지 않았다.
- 조사 후속 NX-00은 JSON 확인 부분만 끝났고 종료/후보 귀속은 미해결이다. 모든 개발 카드는 TODO, 패키징은 기존 pause로 BLOCKED다.
