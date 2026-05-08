# K리그 결과 가이드

## 이 기능으로 할 수 있는 일

- 날짜별 K리그1 / K리그2 경기 일정 및 결과 조회
- 특정 팀(`FC서울`, `서울 이랜드`, 팀 코드 등) 경기만 필터링
- 현재 순위 확인

## 먼저 필요한 것

- Node.js 18+
- `npm install -g kleague-results`

## 입력값

- 날짜: `YYYY-MM-DD`
- 리그: `K리그1` 또는 `K리그2`
- 선택 사항: 팀명, 풀네임, 팀 코드

## 공식 표면

이 기능은 HTML scraping 대신 공식 JSON 표면을 직접 사용한다.

- K League 일정/결과 JSON: `https://www.kleague.com/getScheduleList.do`
- K League 팀 순위 JSON: `https://www.kleague.com/record/teamRank.do`

## 기본 흐름

1. 패키지가 없으면 다른 방법으로 우회하지 말고 먼저 `kleague-results` 를 전역 설치한다.
2. `getScheduleList.do` 로 해당 월 데이터를 받고 요청한 날짜(`YYYY-MM-DD`)만 정확히 필터링한다.
3. 요청 팀이 있으면 `서울`, `FC서울`, `K09` 같은 alias 를 같은 팀으로 인식해 걸러낸다.
4. `teamRank.do` 로 현재 순위를 가져와 경기 결과와 함께 보여준다.

## 예시

```bash
GLOBAL_NPM_ROOT="$(npm root -g)" node --input-type=module - <<'JS'
import path from "node:path";
import { pathToFileURL } from "node:url";

const entry = pathToFileURL(
  path.join(process.env.GLOBAL_NPM_ROOT, "kleague-results", "src", "index.js"),
).href;
const { getKLeagueSummary } = await import(entry);

const summary = await getKLeagueSummary("2026-03-22", {
  leagueId: "K리그1",
  team: "FC서울",
  includeStandings: true,
});

console.log(JSON.stringify(summary, null, 2));
JS
```

## 주의할 점

- `getScheduleList.do` 는 월 단위 데이터를 주므로 반드시 날짜를 다시 필터링해야 한다.
- 순위는 `stadium=all` 기준 현재 표를 사용한다. 필요하면 추후 홈/원정 표로 확장할 수 있다.
- `서울` 같은 짧은 이름은 리그가 다르면 다른 팀을 뜻할 수 있다. K리그2라면 `서울 이랜드` 여부를 확인한다.
- 경기 종료 전 날짜는 `예정` 또는 `진행 중` 상태가 반환될 수 있다.
- 새 패키지이므로 배포 전까지는 로컬 워크스페이스/pack artifact 로 검증하고, 머지 후 publish 를 요청해야 한다.
