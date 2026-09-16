---
title: NX-05 before (HEAD ffb0ebb3, PIN 변경이 기존 세션을 폐기하지 않음)
created: 2026-09-16
tags: [nx-05, before, evidence, auth]
---

# NX-05 before — PIN 을 바꿔도 이전 세션은 그대로 살아 있었다

## 1. 기준 계약의 원문 (HEAD)

```python
# src/antigravity_k/api/auth_routes.py (HEAD)
def _persist_pin_hash_atomic(new_hash: str) -> Path:
    """Write ``new_hash`` to ``pin_hash_file`` atomically with mode 0600."""
    ...
    handle.write(new_hash)      # ← 파일에는 hash 한 줄만. 세대(epoch) 개념이 없다.
```

```python
# src/antigravity_k/engine/auth.py (HEAD)
payload = {"sub": subject, "iat": now, "exp": now + self._ttl, "iss": _JWT_ISSUER}
# 발급 후 검증은 서명·만료·issuer 만 본다 — 폐기를 표현할 claim 이 없다.
```

즉 PIN 변경은 **저장 hash 만** 교체하고, 이미 발급된 JWT 는 만료(TTL 기본 43,200초)까지
유효하다. 인증 우회가 아니라 **세션 폐기 정책의 공백**이다(카드가 명시한 유형 그대로).

## 2. 재현 (기준 트리 = HEAD 를 읽기 전용으로 추출)

```sh
rm -rf /tmp/nx05-before && mkdir -p /tmp/nx05-before
git archive HEAD src | tar -x -C /tmp/nx05-before     # 작업 트리는 건드리지 않는다
NX05_TREE=before PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/nx05-before/src \
  .venv/bin/python docs/qa/2026-09-16-followup/nx05/repro_nx05_pin_change_revocation.py
# → exit 3
```

`before-run-output.json` (발췌):

```json
{
  "epoch_support_present": false,
  "state_document_is_json": false,
  "change_pin_response_keys": ["detail", "ok"],
  "change_pin_reports_reauth": false,
  "old_bearer_status_after_change": 200,
  "old_bearer_accepted_after_change": true,
  "old_pin_accepted_after_change": false,
  "new_pin_accepted_after_change": true,
  "open_ws_revocation_api_present": false,
  "stale_ws_ticket_subject_after_change": "nx05",
  "stale_ws_ticket_reusable": true,
  "old_pin_accepted_after_external_change": true,
  "revoked_and_rejected": false,
  "still_valid_credentials": [
    "old_bearer_accepted_after_change",
    "old_pin_accepted_after_external_change",
    "stale_ws_ticket_reusable"
  ]
}
```

확인된 사실 네 가지.

1. **이전 bearer 가 살아 있다** — PIN 변경(POST /api/auth/change-pin 200) 뒤에도 같은 토큰으로
   보호 경로가 200 이다. 사용자에게는 "PIN 을 바꿨는데 다른 기기/세션이 그대로 남는다".
2. **다른 프로세스가 바꾼 PIN 을 이 프로세스가 모른다** — 저장 파일을 외부에서 교체한 뒤
   구 PIN 로그인이 **200** 이다(`old_pin_accepted_after_external_change: true`). 이 프로세스는
   시작 시 읽은 hash 를 계속 쓰므로, 구 PIN 으로 **새 토큰**을 발급해 준다.
   → 폐기가 무력해지는 경로이며, 단순 정책 공백이 아니라 캐시 결함이다.
3. **연결형 채널도 그대로다** — PIN 변경 전에 발급한 단기(30초) WS ticket 이 변경 뒤에도
   소비된다(`stale_ws_ticket_subject_after_change: "nx05"`).
4. **폐기할 API 자체가 없다** — 열려 있는 WS 를 닫는 경로가 제품에 없다
   (`open_ws_revocation_api_present: false`).

## 3. 소실·권한 위험

| 위험 | 근거 |
|---|---|
| 인증 세션 무효화 없음(만료 TTL 까지 최대 43,200초) | 위 1 |
| 구 PIN 이 다른 프로세스에서 계속 유효 → 폐기 우회 | 위 2 |
| WS 티켓 재사용 창 | 위 3(카드: 연결형 채널 폐기 관측 필요) |
| 중간 상태 노출 | hash 만 교체하므로 "hash 는 새 값, 개념적 세대 없음" 상태가 정상 경로가 된다(§1) |

## 4. 실증하지 못한 것 (INCONCLUSIVE)

- 실제 다중 배포(원격 노출) 환경에서의 폐기 지연 실측 — 드라이버는 같은 프로세스의 관측만 담는다.
  프로세스 2개 판정은 `tests/test_nx05_auth_epoch_revocation.py` 의 spawn 시험이 담당한다.
- 외부 provider API 키 회전 — 카드가 명시적으로 범위 밖(무관)이라고 했다.
