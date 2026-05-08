# 식품 안전 체크 가이드

## 이 기능으로 할 수 있는 일

- 식약처 공식 부적합 식품 목록 조회
- 식품안전나라 회수·판매중지 공개 목록 확인
- 제품명/업체명 기준 로컬 필터링 요약
- 증상 언급 시 **인터뷰-first** 흐름으로 red flag 확인
- 사용자 API key 없이 `k-skill-proxy` 경유 조회

## 먼저 필요한 것

- 인터넷 연결
- `python3`
- 설치된 `mfds-food-safety` skill 안에 `scripts/mfds_food_safety.py` helper 포함
- `k-skill-proxy`의 `/v1/mfds/food-safety/search` route가 있는 hosted/self-host 프록시 접근
- `DATA_GO_KR_API_KEY` / 선택적 `FOODSAFETYKOREA_API_KEY` 는 사용자 쪽이 아니라 **프록시 운영 서버** 환경에 있어야 한다

> 이 helper 는 **직접 진단**을 하지 않는다. 먹어도 되는지 바로 단정하지 않는다. 증상이 있으면 바로 단정하지 말고 먼저 되묻는다.

## 공식 표면

- 공공데이터포털 문서: `https://www.data.go.kr/data/15056516/openapi.do`
- 부적합 식품 endpoint: `https://apis.data.go.kr/1471000/PrsecImproptFoodInfoService03/getPrsecImproptFoodList01`
- 식품안전나라 회수·판매중지 문서: `https://www.data.go.kr/data/15074318/openapi.do`
- 식품안전나라 API 안내: `https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=661&show_cnt=10&start_idx=1&svc_no=I0490&svc_type_cd=API_TYPE06`
- 식품안전나라 회수 sample: `https://openapi.foodsafetykorea.go.kr/api/sample/I0490/json/1/5`
- 프록시 route: `https://k-skill-proxy.nomadamas.org/v1/mfds/food-safety/search`

## 권장 인터뷰 질문

증상이나 섭취상황이 있으면 먼저 아래를 확인한다.

- 누가 먹었는지 (본인/아이/임산부/고령자)
- 무엇을 언제 얼마나 먹었는지
- 같이 먹은 음식/술/약
- 복통/구토/설사/발진 등 증상과 시작 시점
- 기저질환, 임신 여부, 알레르기
- 응급 red flag: `혈변`, `탈수`, `호흡곤란`, `의식저하`, `심한 복통/고열`

red flag 가 있으면 **즉시 응급실·119·의료진** 안내가 우선이다.

## 기본 흐름

1. `python3 .agent/skills/k-skill/scripts/mfds_food_safety.py interview ...` 로 되묻기 질문 세트를 준비한다.
2. `search` 로 프록시 route를 조회한다.
3. 프록시가 준비된 upstream key에 따라 부적합 식품 live 결과와 식품안전나라 회수 live/sample 결과를 합쳐 준다.
4. 제품명/업체명/사유 기준으로 로컬 필터링 후 짧게 정리한다.
5. 먹어도 되는지 단정하지 않고, 증상이 있으면 의료진 상담을 우선한다.

## CLI 예시

```bash
python3 .agent/skills/k-skill/scripts/mfds_food_safety.py interview \
  --question "이 김밥 먹어도 되나요?" \
  --symptoms "복통과 설사"
```

```bash
python3 .agent/skills/k-skill/scripts/mfds_food_safety.py search --query "김밥" --limit 5
```

## 출력 예시 포맷

```json
{
  "query": "김밥",
  "items": [
    {
      "source": "foodsafetykorea_recall",
      "product_name": "맛있는김밥",
      "company_name": "예시식품",
      "reason": "대장균 기준 규격 부적합"
    }
  ],
  "warnings": [
    "FOODSAFETYKOREA_API_KEY is not configured on the proxy server, so recall results use the public sample feed."
  ],
  "proxy": {
    "name": "k-skill-proxy"
  }
}
```

## 검증 메모

2026-04-13 기준 로컬에서 아래를 실제 실행해 helper 동작을 확인했다.

- `python3 .agent/skills/k-skill/scripts/mfds_food_safety.py --help`
- `python3 .agent/skills/k-skill/scripts/mfds_food_safety.py interview --question "이 김밥 먹어도 되나요?" --symptoms "복통과 설사"`
- 프록시 route 기준으로 `search` 호출 URL 구성이 `/v1/mfds/food-safety/search` 로 향하는지 검증

즉, helper 자체와 인터뷰 흐름은 검증했고, live 성공 경로는 프록시 서버에 `DATA_GO_KR_API_KEY` / `FOODSAFETYKOREA_API_KEY` 가 준비된 환경에서 바로 이어서 검증할 수 있다.
