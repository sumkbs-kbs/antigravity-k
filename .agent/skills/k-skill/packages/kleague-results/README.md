# kleague-results

공식 K리그 JSON 엔드포인트를 감싼 재사용 가능한 Node.js 클라이언트입니다. 날짜별 경기 결과와 현재 순위를 함께 조회할 수 있습니다.

## Install

```bash
npm install kleague-results
```

## Official surfaces

- 일정/결과: `https://www.kleague.com/getScheduleList.do`
- 팀 순위: `https://www.kleague.com/record/teamRank.do`

## Usage

```js
const { getKLeagueSummary, getMatchResults, getStandings } = require("kleague-results");

(async () => {
  const results = await getMatchResults("2026-03-22", {
    leagueId: "K리그1",
    team: "FC서울",
  });

  const standings = await getStandings({
    leagueId: 1,
    year: 2026,
  });

  const summary = await getKLeagueSummary("2026-03-22", {
    leagueId: "K리그1",
    team: "FC서울",
    includeStandings: true,
  });

  console.log(results.matches[0]);
  console.log(standings.rows[0]);
  console.log(summary);
})();
```

## API

### `getMatchResults(date, options)`

- `date`: `YYYY-MM-DD` 또는 `Date`
- `options.leagueId`: `1`, `2`, `K리그1`, `K리그2`
- `options.team`: short name / full name / team code alias

### `getStandings(options)`

- `options.leagueId`: `1` 또는 `2`
- `options.year`: 시즌 연도, 기본값은 한국 시간 현재 연도

### `getKLeagueSummary(date, options)`

- 날짜 결과와 현재 순위를 한 번에 반환합니다.

## Notes

- 공식 K리그 JSON 엔드포인트 기준이라 HTML 크롤링보다 유지보수가 단순합니다.
- `getScheduleList.do` 는 월 단위 응답이므로 라이브러리가 요청 날짜만 다시 필터링합니다.
- `teamRank.do` 는 `stadium=all` 기준 현재 순위를 조회합니다.
