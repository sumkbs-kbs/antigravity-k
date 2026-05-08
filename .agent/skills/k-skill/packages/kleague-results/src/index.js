const {
  normalizeDateInput,
  normalizeLeagueId,
  normalizeScheduleResponse,
  normalizeStandingsResponse,
} = require("./parse");

const SCHEDULE_URL = "https://www.kleague.com/getScheduleList.do";
const TEAM_RANK_URL = "https://www.kleague.com/record/teamRank.do";
const DEFAULT_HEADERS = {
  accept: "application/json, text/plain, */*",
  "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
  "content-type": "application/json; charset=utf-8",
  "user-agent": "k-skill/kleague-results",
};

async function requestJson(url, options = {}) {
  const fetchImpl = options.fetchImpl || global.fetch;

  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required.");
  }

  const response = await fetchImpl(url, {
    method: options.method || "GET",
    headers: {
      ...DEFAULT_HEADERS,
      ...(options.headers || {}),
    },
    body: options.body,
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(`K League request failed with ${response.status} for ${url}`);
  }

  return response.json();
}

async function fetchScheduleMonth({ year, month, leagueId, fetchImpl, signal }) {
  return requestJson(SCHEDULE_URL, {
    method: "POST",
    body: JSON.stringify({
      year: String(year),
      month: String(month).padStart(2, "0"),
      leagueId: normalizeLeagueId(leagueId),
    }),
    fetchImpl,
    signal,
  });
}

async function fetchStandings({ leagueId, year, stadium = "all", recordType = "rank", fetchImpl, signal }) {
  const url = new URL(TEAM_RANK_URL);
  url.searchParams.set("leagueId", String(normalizeLeagueId(leagueId)));
  url.searchParams.set("year", String(year));
  url.searchParams.set("stadium", stadium);
  url.searchParams.set("recordType", recordType);

  return requestJson(url.toString(), {
    method: "POST",
    fetchImpl,
    signal,
  });
}

async function getMatchResults(date, options = {}) {
  const queryDate = normalizeDateInput(date);
  const leagueId = normalizeLeagueId(options.leagueId);
  const payload = options.schedulePayload || await fetchScheduleMonth({
    year: queryDate.year,
    month: queryDate.month,
    leagueId,
    fetchImpl: options.fetchImpl,
    signal: options.signal,
  });

  return normalizeScheduleResponse(payload, {
    date: queryDate.isoDate,
    leagueId,
    team: options.team,
  });
}

async function getStandings(options = {}) {
  const leagueId = normalizeLeagueId(options.leagueId);
  const year = Number(options.year || getCurrentKoreaYear());
  const payload = options.standingsPayload || await fetchStandings({
    leagueId,
    year,
    fetchImpl: options.fetchImpl,
    signal: options.signal,
  });

  return normalizeStandingsResponse(payload, {
    leagueId,
    year,
    clubs: options.clubs,
  });
}

async function getKLeagueSummary(date, options = {}) {
  const matches = options.matchesResponse || await getMatchResults(date, options);
  const summary = {
    queryDate: matches.queryDate,
    leagueId: matches.leagueId,
    filteredTeam: matches.filteredTeam,
    matches: matches.matches,
  };

  if (options.includeStandings !== false) {
    summary.standings = await getStandings({
      leagueId: matches.leagueId,
      year: Number(matches.queryDate.slice(0, 4)),
      clubs: matches.clubs,
      fetchImpl: options.fetchImpl,
      signal: options.signal,
      standingsPayload: options.standingsPayload,
    });
  }

  return summary;
}

function getCurrentKoreaYear() {
  return Number(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
  }).format(new Date()));
}

module.exports = {
  fetchScheduleMonth,
  fetchStandings,
  getKLeagueSummary,
  getMatchResults,
  getStandings,
};
