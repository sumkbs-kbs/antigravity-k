# 마켓컬리 상품 조회 가이드

## 이 기능으로 할 수 있는 일

- 마켓컬리 상품 키워드 검색
- 현재 가격 확인
- 필요하면 원가/할인가 여부 확인
- 품절 여부와 배송 타입 확인
- 상품 링크 반환

## 먼저 필요한 것

- 인터넷 연결
- `node` 18+

## 입력값

- 상품명 또는 검색어
  - 예: `우유`
  - 예: `딸기`
  - 예: `닭가슴살`

## 공식 표면

- search list: `https://api.kurly.com/search/v4/sites/market/normal-search?keyword=<keyword>&page=1`
- search count: `https://api.kurly.com/search/v3/sites/market/normal-search/count?keyword=<keyword>&filters=&allow_replace=true`
- goods detail page: `https://www.kurly.com/goods/<productNo>`

## 기본 흐름

1. 상품명/검색어가 없으면 먼저 물어봅니다.
2. `normal-search` 로 상품 후보를 찾습니다.
3. 후보가 너무 많으면 `count` endpoint 로 검색 결과 규모를 먼저 보여 줍니다.
4. 결과에서 상품명, 현재 가격, 할인율, 품절 여부, 배송 타입, 링크를 짧고 **보수적으로** 정리합니다.
5. 필요하면 `goods/<productNo>` 페이지의 `__NEXT_DATA__` 를 읽어 상세 정보를 보조 확인합니다.
6. 가격/품절/노출 정보는 시점에 따라 달라질 수 있으므로 조회 시각 기준 참고값이라고 답합니다.

## 예시

```js
const { countProducts, getProductDetail, searchProducts } = require("market-kurly-search")

async function main() {
  const count = await countProducts("우유")
  const search = await searchProducts("우유")
  const detail = await getProductDetail(search.items[0].productNo)

  console.log({ count, firstItem: search.items[0], detail })
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
```

## 실전 운영 팁

- 검색어가 너무 넓으면 브랜드, 용량, 맛, 카테고리를 다시 물어보는 편이 안전합니다.
- 할인 상품은 `discountedPrice` 가 현재 가격이고 `salesPrice` 가 기준 가격일 수 있습니다.
- 품절 여부가 `false` 여도 실제 결제 시점에는 달라질 수 있으니 주문 가능을 확정처럼 말하면 안 됩니다.
- 비로그인 조회로는 장바구니/주문/주소 기반 배송 가능 여부를 확정할 수 없습니다.

## 라이브 확인 메모

2026-04-09 기준 아래 공개 호출이 로그인 없이 응답했습니다.

- `GET /search/v4/sites/market/normal-search?keyword=우유&page=1` → `no`, `name`, `salesPrice`, `discountedPrice`, `discountRate`, `isSoldOut`, `deliveryTypeNames` 확인
- `GET /search/v3/sites/market/normal-search/count?keyword=우유&filters=&allow_replace=true` → `count = 468` 확인
- `GET /goods/5063110` → `__NEXT_DATA__` 에서 상품명, 가격, 품절 여부, 배송 타입 확인

즉, **2026-04-09 기준으로는 마켓컬리 상품 검색과 가격 조회를 로그인 없이 구현할 수 있음** 을 다시 검증했습니다. 다만 이 표면은 웹 내부 사용 경로이므로 이후 스키마/헤더 요구사항이 바뀌면 수정이 필요할 수 있습니다.
