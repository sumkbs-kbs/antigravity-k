# 근처 술집 조회 가이드

## 이 기능으로 할 수 있는 일

- 서울역/강남/사당/논현 같은 위치 질의를 카카오맵 기준 술집 검색으로 변환
- **현재 영업 상태** 기준으로 영업 중인 술집을 먼저 정리
- 대표 메뉴, 좌석 옵션(단체석/바테이블 등), 전화번호를 함께 제공
- 역/랜드마크 anchor 와 술집 결과의 거리를 대략적으로 계산

## 가장 먼저 할 일

이 기능은 **반드시 현재 위치를 먼저 물어본 뒤** 실행합니다.

권장 질문 예시:

```text
현재 위치를 알려주세요. 서울역/강남/사당 같은 역명이나 동네명으로 보내주시면 카카오맵 기준 근처 술집을 찾아볼게요.
```

## 입력값

- 역명: `서울역`, `사당`, `강남`, `신논현`, `논현`
- 동네/랜드마크: `해방촌`, `코엑스`, `성수동`

위치가 넓거나 애매하면 가까운 역명으로 한 번 더 좁히는 편이 정확합니다.

## 공식 Kakao Map 표면

- 모바일 검색: `https://m.map.kakao.com/actions/searchView?q=<query>`
- 장소 패널 JSON: `https://place-api.map.kakao.com/places/panel3/<confirmId>`
- 장소 상세 페이지: `https://place.map.kakao.com/<confirmId>`

기본 흐름은 `위치 query` → `위치 anchor 후보 선택` → `위치 + 술집 검색` → `panel3 정규화` 입니다.

## 정규화되는 핵심 필드

- 술집명 / 카테고리
- 현재 영업 상태 (`영업 중`, `영업 전`, `휴무일`)
- 대표 메뉴
- 좌석 옵션 / 인원 수용 힌트 (`단체석`, `바테이블` 등)
- 전화번호
- 거리(가능하면)

## Node.js 예시

```js
const { searchNearbyBarsByLocationQuery } = require("kakao-bar-nearby");

async function main() {
  const result = await searchNearbyBarsByLocationQuery("서울역", {
    limit: 5
  });

  console.log(result.anchor);
  console.log(result.items);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
```

## 검증된 live smoke 예시

아래 값은 **2026-03-29** 에 `사당`, `limit=3`, `panelLimit=8` 로 실제 호출해 확인한 결과 일부입니다.

```json
{
  "anchor": {
    "name": "사당1동먹자골목상점가"
  },
  "meta": {
    "openNowCount": 4
  },
  "items": [
    {
      "name": "우미노식탁",
      "openStatus": { "label": "영업 중", "detail": "24:00 까지" },
      "seatingKeywords": ["단체석", "케이크 반입 가능", "바테이블"]
    },
    {
      "name": "방배을지로골뱅이술집포차 사당역점",
      "openStatus": { "label": "영업 중", "detail": "24:00 까지" },
      "menuSamples": ["을지로골뱅이(골뱅이무침)", "백골뱅이탕 (중)", "먹태"]
    },
    {
      "name": "커먼테이블",
      "openStatus": { "label": "영업 중", "detail": "01:00 까지" },
      "phone": "010-7730-1056"
    }
  ]
}
```

## 운영 팁

- 영업 중인 결과가 있으면 먼저 보여주고, 없으면 곧 오픈하는 곳을 같이 보여준다.
- 메뉴가 비어 있으면 카카오맵 카테고리와 소개 문구로 `대략적인 메뉴` 를 설명한다.
- `단체석`, `룸`, `바테이블` 같은 좌석 옵션으로 인원 수용을 근사치로 설명한다.
- 바로 예약/주문까지 가지 말고 조회 결과만 제공한다.

## 주의할 점

- panel3 JSON 은 브라우저와 유사한 헤더가 없으면 406 이 날 수 있습니다.
- 카카오맵의 장소 패널 구조가 바뀌면 메뉴/영업 정보 필드도 달라질 수 있습니다.
- exact seating capacity 숫자는 제공되지 않을 수 있으므로 `단체 방문 가능` 같은 근사 힌트로 안내합니다.
