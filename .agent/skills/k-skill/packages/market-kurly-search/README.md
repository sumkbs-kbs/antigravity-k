# market-kurly-search

마켓컬리 웹이 실제로 사용하는 **비로그인 검색/상품 상세 표면**을 사용해 상품 후보와 현재 가격을 조회하는 Node.js 패키지입니다.

## 설치

배포 후:

```bash
npm install market-kurly-search
```

이 저장소에서 개발할 때:

```bash
npm install
```

## 사용 원칙

- 로그인 없이 확인 가능한 공개 웹 표면만 사용합니다.
- 현재 가격은 `discountedPrice` 가 있으면 그 값을, 없으면 `salesPrice` 를 사용합니다.
- 가격/품절/배송 문구는 시점에 따라 달라질 수 있으므로 조회 시각 기준 참고값으로만 답해야 합니다.
- 장바구니/주문/주소 기반 배송 가능 여부 같은 회원/액션 기능은 범위 밖입니다.

## 사용 예시

```js
const { countProducts, getProductDetail, searchProducts } = require("market-kurly-search")

async function main() {
  const searchResult = await searchProducts("우유")
  const detailResult = await getProductDetail(searchResult.items[0].productNo)
  const countResult = await countProducts("우유")

  console.log(countResult)
  console.log(searchResult.items[0])
  console.log(detailResult)
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
```

## 공개 API

- `searchProducts(keyword, options?)`
- `countProducts(keyword, options?)`
- `getProductDetail(productNo, options?)`

## Live smoke snapshot

2026-04-09 기준 live smoke test 에서 아래 공개 표면이 로그인 없이 응답했습니다.

```json
{
  "count": {
    "query": "우유",
    "count": 468
  },
  "firstSearchItem": {
    "productNo": 5063110,
    "name": "[연세우유 x 마켓컬리] 전용목장우유 900mL",
    "currentPrice": 2780,
    "isSoldOut": false,
    "goodsUrl": "https://www.kurly.com/goods/5063110"
  },
  "detail": {
    "productNo": 5063110,
    "name": "[연세우유 x 마켓컬리] 전용목장우유 900mL",
    "currentPrice": 2780,
    "deliveryTypeNames": [
      "샛별배송(내일 아침)"
    ]
  }
}
```
