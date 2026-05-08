# 토스증권 조회 가이드

## 이 기능으로 할 수 있는 일

- `tossctl` 기반 토스증권 계좌 목록 / 계좌 요약 조회
- 포트폴리오 보유 종목 / 자산 비중 조회
- 단일 종목 / 다중 종목 시세 조회
- 미체결 주문 / 월간 체결 내역 조회
- 관심종목 목록 조회

## 먼저 필요한 것

- macOS + Homebrew
- `tossctl` 설치
- `tossctl auth login` 으로 브라우저 세션 확보
- `node` 18+

## upstream 설치와 로그인

이 기능은 `JungHoonGhae/tossinvest-cli` 의 `tossctl` 을 그대로 사용한다.

```bash
brew tap JungHoonGhae/tossinvest-cli
brew install tossctl
tossctl doctor
tossctl auth doctor
tossctl auth login
```

로그인이 끝나기 전에는 계좌/포트폴리오 조회를 시도하지 않는다.

## 지원하는 read-only 명령

- `tossctl account list --output json`
- `tossctl account summary --output json`
- `tossctl portfolio positions --output json`
- `tossctl portfolio allocation --output json`
- `tossctl quote get TSLA --output json`
- `tossctl quote batch TSLA 005930 VOO --output json`
- `tossctl orders list --output json`
- `tossctl orders completed --market all --output json`
- `tossctl watchlist list --output json`

## Node.js 예시

```js
const {
  getAccountSummary,
  getPortfolioPositions,
  getQuote,
  listCompletedOrders
} = require("toss-securities");

async function main() {
  const summary = await getAccountSummary();
  const positions = await getPortfolioPositions();
  const quote = await getQuote("TSLA");
  const completed = await listCompletedOrders({ market: "all" });

  console.log(summary.data);
  console.log(positions.data);
  console.log(quote.data);
  console.log(completed.data);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
```

## 운영 팁

- 계좌 요약과 포트폴리오는 로그인 세션이 있어야만 동작한다.
- `TSLA`, `VOO`, `005930` 같이 심볼을 그대로 넘기면 된다.
- 주문 관련 답변은 **조회 결과만** 정리하고, 실거래로 이어지는 행동은 권하지 않는다.
- 민감한 계좌 정보는 꼭 필요한 값만 답한다.

## 주의할 점

- `tossctl` 은 비공식 CLI 이므로 웹 내부 API 변경에 영향을 받을 수 있다.
- 브라우저 세션이 만료되면 `tossctl auth login` 을 다시 해야 할 수 있다.
- 이 레포의 `toss-securities` 패키지는 read-only wrapper 이며, 거래 mutation 명령은 공개 API에 포함하지 않는다.
