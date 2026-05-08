const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  getKLeagueSummary,
  getMatchResults,
  getStandings
} = require("../src/index");
const {
  normalizeLeagueId,
  normalizeScheduleResponse,
  normalizeStandingsResponse
} = require("../src/parse");

const fixturesDir = path.join(__dirname, "fixtures");
const schedulePayload = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "schedule-kleague1-2026-03.json"), "utf8")
);
const standingsPayload = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "standings-kleague1-2026.json"), "utf8")
);

test("normalizeLeagueId accepts K League numeric and Korean aliases", () => {
  assert.equal(normalizeLeagueId(1), 1);
  assert.equal(normalizeLeagueId("K리그1"), 1);
  assert.equal(normalizeLeagueId("k league 2"), 2);
  assert.equal(normalizeLeagueId("kleague2"), 2);
  assert.throws(() => normalizeLeagueId("K리그3"), /leagueId/);
});

test("normalizeScheduleResponse filters a date and team alias from the official monthly payload", () => {
  const result = normalizeScheduleResponse(schedulePayload, {
    date: "2026-03-22",
    leagueId: 1,
    team: "FC서울"
  });

  assert.equal(result.queryDate, "2026-03-22");
  assert.equal(result.leagueId, 1);
  assert.equal(result.matches.length, 1);
  assert.equal(result.matches[0].competitionName, "하나은행 K리그1 2026");
  assert.equal(result.matches[0].round, 5);
  assert.equal(result.matches[0].status.code, "FE");
  assert.equal(result.matches[0].status.label, "종료");
  assert.equal(result.matches[0].homeTeam.code, "K09");
  assert.equal(result.matches[0].homeTeam.name, "서울");
  assert.equal(result.matches[0].homeTeam.fullName, "FC서울");
  assert.equal(result.matches[0].awayTeam.name, "광주");
  assert.deepEqual(result.matches[0].score, { home: 5, away: 0 });
  assert.equal(result.matches[0].venue.name, "서울 월드컵 경기장");
  assert.equal(result.filteredTeam.normalized, "FC서울");
});

test("normalizeStandingsResponse keeps the official K League table shape", () => {
  const table = normalizeStandingsResponse(standingsPayload, { leagueId: 1, year: 2026 });
  const seoul = table.rows.find((row) => row.team.code === "K09");

  assert.equal(table.leagueId, 1);
  assert.equal(table.year, 2026);
  assert.equal(table.isSplitRank, false);
  assert.equal(table.rows.length, 12);
  assert.equal(seoul.rank, 1);
  assert.equal(seoul.team.name, "서울");
  assert.equal(seoul.points, 12);
  assert.equal(seoul.played, 4);
  assert.deepEqual(seoul.form.slice(0, 4), ["승", "승", "승", "승"]);
});

test("public fetchers compose day results with current standings via mocked fetch", async () => {
  const originalFetch = global.fetch;
  const calls = [];

  global.fetch = async (url, options = {}) => {
    const target = String(url);
    calls.push({
      target,
      method: options.method || "GET",
      body: options.body || null,
      headers: options.headers || {},
    });

    if (target.endsWith("/getScheduleList.do")) {
      return makeResponse(schedulePayload);
    }

    if (target.includes("/record/teamRank.do?leagueId=1&year=2026&stadium=all&recordType=rank")) {
      return makeResponse(standingsPayload);
    }

    throw new Error(`unexpected url: ${target}`);
  };

  try {
    const matches = await getMatchResults("2026-03-22", { leagueId: "K리그1", team: "서울" });
    assert.equal(matches.matches.length, 1);
    assert.equal(matches.matches[0].homeTeam.fullName, "FC서울");

    const standings = await getStandings({ leagueId: 1, year: 2026 });
    assert.equal(standings.rows[0].team.name, "서울");

    const summary = await getKLeagueSummary("2026-03-22", {
      leagueId: 1,
      team: "FC서울",
      includeStandings: true
    });

    assert.equal(summary.matches.length, 1);
    assert.equal(summary.standings.rows[0].rank, 1);
    assert.equal(summary.standings.rows[0].team.fullName, "FC서울");
    assert.equal(
      calls.filter((call) => call.target.endsWith("/getScheduleList.do")).length,
      2
    );
    assert.ok(
      calls.some((call) => call.body && String(call.body).includes('"month":"03"')),
      "expected schedule fetch to send the official month payload"
    );
    assert.ok(
      calls.every((call) => call.headers["accept-language"]?.includes("ko-KR")),
      "expected live requests to pin Korean-language payloads",
    );
  } finally {
    global.fetch = originalFetch;
  }
});

test("getMatchResults rejects impossible calendar dates before fetching", async () => {
  let fetchCalled = false;

  await assert.rejects(
    () =>
      getMatchResults("2026-13-40", {
        leagueId: "K리그1",
        fetchImpl: async () => {
          fetchCalled = true;
          return makeResponse(schedulePayload);
        },
      }),
    /date must be a valid Date or YYYY-MM-DD string\./,
  );

  assert.equal(fetchCalled, false);
});

function makeResponse(body) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      "content-type": "application/json"
    }
  });
}
