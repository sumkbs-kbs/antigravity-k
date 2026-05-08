# SRT 예매 가이드

## 이 기능으로 할 수 있는 일

- 수서 출발 SRT 열차 조회
- 좌석 가능 여부 확인
- 예약 진행
- 예약 내역 확인
- 예약 취소

## 먼저 필요한 것

- Python 3.10+
- `python3 -m pip install SRTrain`
- [공통 설정 가이드](../setup.md) 완료
- [보안/시크릿 정책](../security-and-secrets.md) 확인

## 필요한 환경변수

- `KSKILL_SRT_ID`
- `KSKILL_SRT_PASSWORD`

### Credential resolution order

1. **이미 환경변수에 있으면** 그대로 사용한다.
2. **에이전트가 자체 secret vault(1Password CLI, Bitwarden CLI, macOS Keychain 등)를 사용 중이면** 거기서 꺼내 환경변수로 주입해도 된다.
3. **`~/.config/k-skill/secrets.env`** (기본 fallback) — plain dotenv 파일, 퍼미션 `0600`.
4. **아무것도 없으면** 유저에게 물어서 2 또는 3에 저장한다.

## 입력값

- 출발역
- 도착역
- 날짜: `YYYYMMDD`
- 희망 시작 시각: `HHMMSS`
- 인원 수
- 좌석 선호

## 기본 흐름

1. `SRTrain` 패키지가 없으면 다른 방법으로 우회하지 말고 먼저 전역 설치합니다.
2. `KSKILL_SRT_ID`, `KSKILL_SRT_PASSWORD` 가 없으면 credential resolution order에 따라 확보합니다.
3. 먼저 열차를 조회합니다.
4. 후보 열차의 출발/도착 시각, 좌석 여부, 운임을 보여줍니다.
5. 대상 열차가 명확할 때만 예약합니다.
6. 예약 확인/취소는 예약을 다시 식별한 뒤 진행합니다.

## 예시

```bash
python3 - <<'PY'
import os
from SRT import SRT

srt = SRT(os.environ["KSKILL_SRT_ID"], os.environ["KSKILL_SRT_PASSWORD"])
trains = srt.search_train("수서", "부산", "20260328", "080000", time_limit="120000")

for idx, train in enumerate(trains[:5], start=1):
    print(idx, train)
PY
```

## 주의할 점

- credential은 환경변수로 주입합니다.
- 결제 완료까지 자동화하는 문서는 아닙니다.
- 매진 시 공격적인 재시도 루프는 피합니다.
