# 서울 지하철 도착정보 가이드

## 이 기능으로 할 수 있는 일

- 역 기준 실시간 도착 예정 열차 조회
- 상/하행 또는 외/내선 정보 확인
- 첫 번째/두 번째 도착 메시지 확인
- 개인 OpenAPI key 없이 `k-skill-proxy` 경유 조회

## 먼저 필요한 것

- [공통 설정 가이드](../setup.md) 완료
- [보안/시크릿 정책](../security-and-secrets.md) 확인
- self-host 또는 배포 확인이 끝난 proxy base URL: `KSKILL_PROXY_BASE_URL`

## 필요한 환경변수

- `KSKILL_PROXY_BASE_URL` (필수: self-host 또는 배포 확인이 끝난 proxy base URL)

사용자가 서울 열린데이터 광장 OpenAPI key를 직접 발급할 필요는 없다. 대신 `KSKILL_PROXY_BASE_URL` 은 `/v1/seoul-subway/arrival` route가 실제로 배포된 proxy를 가리켜야 한다. upstream key는 proxy 서버에서만 관리한다.

### Proxy resolution order

1. **`KSKILL_PROXY_BASE_URL` 이 있으면** 그 값을 사용합니다.
2. **없으면** 사용자/운영자에게 self-host 또는 배포 확인이 끝난 proxy URL 을 먼저 확보합니다.
3. **직접 proxy를 운영하는 경우에만** proxy 서버 upstream key를 서버 쪽에만 설정합니다.

## 입력값

- 역명
- 선택 사항: 가져올 건수

## 기본 흐름

1. `KSKILL_PROXY_BASE_URL` 로 self-host 또는 배포 확인이 끝난 proxy base URL 을 확인합니다.
2. `/v1/seoul-subway/arrival?stationName=...` 로 역명 기준 실시간 도착정보를 조회합니다.
3. 호선, 진행 방향, 도착 메시지, 조회 시점을 함께 요약합니다.

## 예시

```bash
curl -fsS --get 'https://your-proxy.example.com/v1/seoul-subway/arrival' \
  --data-urlencode 'stationName=강남'
```

범위를 줄이거나 늘리고 싶으면:

```bash
curl -fsS --get 'https://your-proxy.example.com/v1/seoul-subway/arrival' \
  --data-urlencode 'stationName=서울역' \
  --data-urlencode 'startIndex=0' \
  --data-urlencode 'endIndex=4'
```

## 주의할 점

- 실시간 데이터라 몇 초 단위로 바뀔 수 있습니다.
- 역명 표기가 다르면 결과가 비어 있을 수 있습니다.
- 일일 호출 제한이나 quota 초과 가능성이 있습니다.
- public hosted route rollout 이 끝나기 전까지는 `KSKILL_PROXY_BASE_URL` 을 반드시 명시합니다.
- self-host proxy 설정은 [k-skill 프록시 서버 가이드](k-skill-proxy.md)를 봅니다.
