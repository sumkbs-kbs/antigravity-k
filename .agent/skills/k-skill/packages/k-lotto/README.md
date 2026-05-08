# k-lotto

동행복권 공식 결과 페이지와 JSON 응답을 이용해 한국 로또 6/45 당첨 결과를 조회하는 Node.js 패키지입니다.

## 설치

배포 후:

```bash
npm install k-lotto
```

이 저장소에서 개발할 때:

```bash
npm install
```

## 사용 예시

```js
const lotto = require("k-lotto");

async function main() {
  const latestRound = await lotto.getLatestRound();
  const detail = await lotto.getDetailResult(latestRound);
  const checked = await lotto.checkNumber(latestRound, [3, 10, 14, 15, 23, 24]);

  console.log({ latestRound, detail, checked });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
```

## 공개 API

- `getLatestRound()`
- `getResult(round)`
- `getDetailResult(round)`
- `checkNumber(round, ticketNumbers)`
- `evaluateTicket(detailResult, ticketNumbers)`
