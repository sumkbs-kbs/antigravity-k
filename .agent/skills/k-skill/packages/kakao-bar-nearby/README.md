# kakao-bar-nearby

카카오맵 검색 + 장소 패널 JSON 을 사용해 근처 술집을 찾는 Node.js 패키지입니다.

## 설치

배포 후:

```bash
npm install kakao-bar-nearby
```

이 저장소에서 개발할 때:

```bash
npm install
```

## 사용 원칙

- 유저 위치는 자동으로 추적하지 않습니다.
- 먼저 **현재 위치를 먼저 물어본다** 는 규칙을 지키세요.
- `서울역 술집`, `강남 술집`, `사당 술집` 같은 질의를 카카오맵 모바일 검색으로 조회합니다.
- 영업 중인 결과를 먼저 정렬하고, 대표 메뉴·좌석 힌트·전화번호를 함께 반환합니다.

## 공식 Kakao Map 표면

- 모바일 검색: `https://m.map.kakao.com/actions/searchView`
- 장소 패널 JSON: `https://place-api.map.kakao.com/places/panel3/<confirmId>`
- 장소 상세 페이지: `https://place.map.kakao.com/<confirmId>`

## 사용 예시

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

## Live smoke snapshot

2026-03-29 에 `사당`, `limit=3`, `panelLimit=8` 로 실제 호출했을 때 상위 결과 예시는 아래와 같았습니다.

```json
{
  "anchor": { "name": "사당1동먹자골목상점가" },
  "meta": { "openNowCount": 4 },
  "items": [
    { "name": "우미노식탁", "open": "영업 중", "detail": "24:00 까지" },
    { "name": "방배을지로골뱅이술집포차 사당역점", "open": "영업 중", "detail": "24:00 까지" },
    { "name": "커먼테이블", "open": "영업 중", "detail": "01:00 까지" }
  ]
}
```

## 공개 API

- `parseSearchResultsHtml(html)`
- `selectAnchorCandidate(locationQuery, items)`
- `normalizePlacePanel(panel, searchItem, anchorPoint)`
- `searchNearbyBarsByLocationQuery(locationQuery, options?)`
