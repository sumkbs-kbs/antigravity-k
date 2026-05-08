# used-car-price-search

한국 중고차(렌터카 출신) 가격/인수가를 조회하는 Node.js helper 입니다. 공급자(provider) 구조로 되어 있어 새 업체를 추가할 수 있습니다.

## 현재 지원 공급자

| id | 업체 | 출처 |
| --- | --- | --- |
| `sk-tagobuy` | SK렌터카 다이렉트 타고BUY | `https://www.skdirect.co.kr/tb` (`__NEXT_DATA__`) |

## API

```js
const { lookupPrices, fetchInventory, providers } = require("used-car-price-search")

// 키워드 검색 (기본 공급자: sk-tagobuy)
const result = await lookupPrices("아반떼", { limit: 5 })

// 특정 공급자 지정
const result = await lookupPrices("아반떼", { provider: "sk-tagobuy", limit: 5 })

// 전체 inventory 조회
const inventory = await fetchInventory()

// 등록된 공급자 목록
console.log(Object.keys(providers))
```

## 공급자 추가 방법

`src/providers/` 아래에 아래 인터페이스를 따르는 모듈을 만들고 `src/index.js`의 `providers` 레지스트리에 등록하면 됩니다.

```js
module.exports = {
  provider: { id, name, siteUrl, ... },
  fetchInventory(options) → { provider, total, items, fetchedAt }
}
```

`items`의 각 항목은 공통 필드(`maker`, `model`, `displayName`, `monthlyPrice`, `buyoutPrice`, `mileageKm`, `fuel`, `searchText` 등)를 포함해야 합니다.

## Notes

- 공개 HTML 안의 데이터를 읽는 방식이라 별도 로그인이나 비공개 API key 가 필요하지 않습니다.
- 결과는 `월 렌트료`와 `인수가`를 함께 노출합니다.
- 검색은 현재 inventory snapshot 기준 키워드 매칭입니다.

## Disclaimer

이 패키지는 각 공급자의 공개 데이터를 조회합니다. 어떤 업체와도 제휴·광고·후원 관계가 없으며, 공식 제품이 아닙니다. 광고 및 제휴 제안은 언제든 환영합니다.
