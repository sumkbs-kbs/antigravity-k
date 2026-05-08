# 로또 결과 가이드

## 이 기능으로 할 수 있는 일

- 최신 회차 확인
- 특정 회차 당첨번호 조회
- 번호 대조로 몇 등인지 확인
- 상세 당첨금 정보 확인

## 먼저 필요한 것

- Node.js 18+
- 배포 후: `npm install -g k-lotto`
- 실행 전: `export NODE_PATH="$(npm root -g)"`
- 이 저장소에서 개발할 때: 루트에서 `npm install`

## 입력값

- 회차 번호 또는 `latest`
- 선택 사항: 사용자의 번호 6개

## 기본 흐름

1. 패키지가 없으면 다른 방법으로 우회하지 말고 먼저 전역 설치합니다.
2. 최신 회차 또는 요청 회차를 확인합니다.
3. 당첨번호와 추첨일, 당첨금 분포를 요약합니다.
4. 사용자 번호가 있으면 일치 번호와 등수를 계산합니다.

## 예시

```bash
NODE_PATH="$(npm root -g)" node - <<'JS'
const lotto = require("k-lotto");
lotto.getDetailResult(1216).then((result) => console.log(JSON.stringify(result, null, 2)));
JS
```

## 주의할 점

- 사용자 번호는 영구 저장하지 않는 것을 기준으로 합니다.
- 최신 회차는 결과 페이지 HTML에서 읽고, 상세 결과는 공식 JSON 응답을 사용합니다.
