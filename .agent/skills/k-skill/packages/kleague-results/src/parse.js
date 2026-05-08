const LEAGUE_ALIAS_MAP = new Map([
  ["1", 1],
  ["K1", 1],
  ["KLEAGUE1", 1],
  ["K리그1", 1],
  ["2", 2],
  ["K2", 2],
  ["KLEAGUE2", 2],
  ["K리그2", 2],
]);

const STATUS_MAP = {
  FE: { state: "finished", label: "종료" },
  NS: { state: "scheduled", label: "예정" },
  LIVE: { state: "live", label: "진행 중" },
  IN: { state: "live", label: "진행 중" },
  HT: { state: "halftime", label: "하프타임" },
  PP: { state: "postponed", label: "연기" },
  CAN: { state: "cancelled", label: "취소" },
};

function normalizeLeagueId(value = 1) {
  if (value === null || value === undefined || value === "") {
    return 1;
  }

  if (Number.isInteger(value) && (value === 1 || value === 2)) {
    return value;
  }

  const token = normalizeToken(value);
  const leagueId = LEAGUE_ALIAS_MAP.get(token);

  if (!leagueId) {
    throw new Error(`leagueId must resolve to K League 1 or 2. Received: ${value}`);
  }

  return leagueId;
}

function normalizeDateInput(value) {
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      throw new Error("date must be a valid Date or YYYY-MM-DD string.");
    }

    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = formatter.formatToParts(value).reduce((acc, part) => {
      if (part.type !== "literal") {
        acc[part.type] = part.value;
      }
      return acc;
    }, {});

    return buildDateParts(parts.year, parts.month, parts.day);
  }

  const match = String(value || "").trim().match(/^(\d{4})[-.](\d{2})[-.](\d{2})$/);
  if (!match) {
    throw new Error("date must be a valid Date or YYYY-MM-DD string.");
  }

  if (!isValidCalendarDate(match[1], match[2], match[3])) {
    throw new Error("date must be a valid Date or YYYY-MM-DD string.");
  }

  return buildDateParts(match[1], match[2], match[3]);
}

function normalizeToken(value) {
  return String(value || "")
    .normalize("NFKC")
    .toUpperCase()
    .replace(/[^0-9A-Z가-힣]+/g, "");
}

function buildDateParts(year, month, day) {
  return {
    year: String(year),
    month: String(month).padStart(2, "0"),
    day: String(day).padStart(2, "0"),
    isoDate: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
    dottedDate: `${year}.${String(month).padStart(2, "0")}.${String(day).padStart(2, "0")}`,
  };
}

function isValidCalendarDate(year, month, day) {
  const numericYear = Number(year);
  const numericMonth = Number(month);
  const numericDay = Number(day);

  if (!Number.isInteger(numericYear) || !Number.isInteger(numericMonth) || !Number.isInteger(numericDay)) {
    return false;
  }

  if (numericMonth < 1 || numericMonth > 12 || numericDay < 1) {
    return false;
  }

  const maxDay = [31, isLeapYear(numericYear) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][numericMonth - 1];
  return numericDay <= maxDay;
}

function isLeapYear(year) {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function buildClubDirectory(clubList = []) {
  const directory = new Map();

  for (const club of clubList) {
    const code = club.teamId || club.code;
    if (!code) {
      continue;
    }

    const name = club.teamNameShort || club.teamName || club.name || club.teamNameFull || club.fullName || code;
    const fullName = club.teamNameFull || club.teamName || club.fullName || club.name || name;
    const aliasTokens = new Set(
      [code, name, fullName, club.teamName, club.teamNameShort, club.name, club.fullName]
        .filter(Boolean)
        .map(normalizeToken),
    );

    directory.set(code, {
      code,
      name,
      fullName,
      homepage: club.homepage || null,
      leagueId: club.leagueId ?? null,
      aliasTokens,
    });
  }

  return directory;
}

function normalizeScheduleResponse(payload, options = {}) {
  const data = payload?.data || payload || {};
  const clubDirectory = buildClubDirectory(data.clubList || options.clubs || []);
  const queryDate = options.date ? normalizeDateInput(options.date) : null;
  const leagueId = normalizeLeagueId(options.leagueId ?? data.scheduleList?.[0]?.leagueId ?? data.clubList?.[0]?.leagueId ?? 1);
  const requestedTeam = options.team ? resolveTeamQuery(options.team, clubDirectory) : null;
  const scheduleList = Array.isArray(data.scheduleList) ? data.scheduleList : [];

  const matches = scheduleList
    .filter((item) => !queryDate || item.gameDate === queryDate.dottedDate)
    .filter((item) => !requestedTeam || itemMatchesRequestedTeam(item, requestedTeam, clubDirectory))
    .map((item) => normalizeScheduleItem(item, clubDirectory))
    .sort(compareMatches);

  return {
    queryDate: queryDate?.isoDate ?? null,
    leagueId,
    filteredTeam: requestedTeam
      ? {
          input: requestedTeam.input,
          normalized: requestedTeam.fullName || requestedTeam.name || requestedTeam.input,
          code: requestedTeam.code || null,
        }
      : null,
    clubs: [...clubDirectory.values()].map((club) => ({
      code: club.code,
      name: club.name,
      fullName: club.fullName,
      homepage: club.homepage,
      leagueId: club.leagueId,
    })),
    matches,
  };
}

function normalizeScheduleItem(item, clubDirectory) {
  const status = normalizeMatchStatus(item);
  const homeTeam = getClub(item.homeTeam, item.homeTeamName, item.leagueId, clubDirectory);
  const awayTeam = getClub(item.awayTeam, item.awayTeamName, item.leagueId, clubDirectory);
  const score = {
    home: normalizeNumber(item.homeGoal),
    away: normalizeNumber(item.awayGoal),
  };

  return {
    leagueId: normalizeLeagueId(item.leagueId),
    competitionName: item.meetName || null,
    round: normalizeNumber(item.roundId),
    gameId: normalizeNumber(item.gameId),
    date: item.gameDate ? item.gameDate.replace(/\./g, "-") : null,
    dateLabel: item.gameDate || null,
    kickOff: item.gameTime || null,
    status,
    homeTeam: stripAliasTokens(homeTeam),
    awayTeam: stripAliasTokens(awayTeam),
    score,
    winner: determineWinner(score, status),
    venue: {
      shortName: item.fieldName || null,
      name: item.fieldNameFull || item.fieldName || null,
    },
    audience: normalizeNumber(item.audienceQty),
    broadcastChannels: splitChannels(item.broadcastName),
    matchCenterUrl:
      item.gameId && item.meetSeq
        ? `https://www.kleague.com/match.do?year=${item.year}&leagueId=${item.leagueId}&gameId=${item.gameId}&meetSeq=${item.meetSeq}`
        : null,
  };
}

function normalizeStandingsResponse(payload, options = {}) {
  const data = payload?.data || payload || {};
  const leagueId = normalizeLeagueId(options.leagueId ?? data.teamRank?.[0]?.leagueId ?? 1);
  const clubDirectory = buildClubDirectory(options.clubs || options.clubList || []);
  const seen = new Set();
  const rows = [];

  for (const item of data.teamRank || []) {
    if (item.teamId && seen.has(item.teamId)) {
      continue;
    }

    if (item.teamId) {
      seen.add(item.teamId);
    }

    const team = getClub(item.teamId, item.teamName, leagueId, clubDirectory, item.homepage);
    rows.push({
      rank: normalizeNumber(item.rank),
      team: stripAliasTokens(team),
      points: normalizeNumber(item.gainPoint) ?? 0,
      played: normalizeNumber(item.gameCount) ?? 0,
      win: normalizeNumber(item.winCnt) ?? 0,
      draw: normalizeNumber(item.tieCnt) ?? 0,
      loss: normalizeNumber(item.lossCnt) ?? 0,
      goalsFor: normalizeNumber(item.gainGoal) ?? 0,
      goalsAgainst: normalizeNumber(item.lossGoal) ?? 0,
      goalDifference: normalizeNumber(item.gapCnt) ?? 0,
      form: [item.game01, item.game02, item.game03, item.game04, item.game05, item.game06]
        .map((value) => String(value || "").trim())
        .filter(Boolean),
      homepage: item.homepage || team.homepage || null,
      stadium: item.stadium || null,
    });
  }

  rows.sort((left, right) => {
    if (left.rank !== right.rank) {
      return left.rank - right.rank;
    }
    if (left.points !== right.points) {
      return right.points - left.points;
    }
    return left.team.name.localeCompare(right.team.name, "ko");
  });

  return {
    leagueId,
    year: normalizeNumber(options.year ?? data.year) ?? null,
    isSplitRank: Boolean(data.isSplitRank),
    notice: String(data.ClubRankMsg || "").trim() || null,
    rows,
  };
}

function normalizeMatchStatus(item) {
  const code = item.gameStatus || (item.endYn === "Y" ? "FE" : "NS");
  const mapped = STATUS_MAP[code] || {
    state: item.endYn === "Y" ? "finished" : "scheduled",
    label: item.endYn === "Y" ? "종료" : "예정",
  };

  return {
    code,
    state: mapped.state,
    label: mapped.label,
    finished: mapped.state === "finished",
  };
}

function resolveTeamQuery(query, clubDirectory) {
  const input = String(query || "").trim();
  const token = normalizeToken(input);

  for (const club of clubDirectory.values()) {
    if (club.aliasTokens.has(token)) {
      return {
        ...club,
        input,
        token,
      };
    }
  }

  return {
    code: null,
    name: input,
    fullName: input,
    input,
    token,
  };
}

function itemMatchesRequestedTeam(item, requestedTeam, clubDirectory) {
  const homeTeam = getClub(item.homeTeam, item.homeTeamName, item.leagueId, clubDirectory);
  const awayTeam = getClub(item.awayTeam, item.awayTeamName, item.leagueId, clubDirectory);

  return homeTeam.aliasTokens.has(requestedTeam.token) || awayTeam.aliasTokens.has(requestedTeam.token);
}

function getClub(code, fallbackName, leagueId, clubDirectory, homepage = null) {
  const existing = clubDirectory.get(code);

  if (existing) {
    return existing;
  }

  const aliasTokens = new Set([code, fallbackName].filter(Boolean).map(normalizeToken));
  return {
    code: code || null,
    name: fallbackName || code || null,
    fullName: fallbackName || code || null,
    homepage,
    leagueId: leagueId ?? null,
    aliasTokens,
  };
}

function compareMatches(left, right) {
  const leftKey = `${left.date || ""}T${left.kickOff || "00:00"}`;
  const rightKey = `${right.date || ""}T${right.kickOff || "00:00"}`;

  if (leftKey !== rightKey) {
    return leftKey.localeCompare(rightKey);
  }

  return (left.gameId ?? 0) - (right.gameId ?? 0);
}

function splitChannels(value) {
  return [...new Set(String(value || "")
    .split(/\/\/|\|/)
    .map((part) => part.trim())
    .filter(Boolean))];
}

function determineWinner(score, status) {
  if (!status.finished || score.home === null || score.away === null) {
    return null;
  }

  if (score.home === score.away) {
    return "draw";
  }

  return score.home > score.away ? "home" : "away";
}

function normalizeNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function stripAliasTokens(team) {
  return {
    code: team.code,
    name: team.name,
    fullName: team.fullName,
    homepage: team.homepage,
    leagueId: team.leagueId,
  };
}

module.exports = {
  buildClubDirectory,
  normalizeDateInput,
  normalizeLeagueId,
  normalizeMatchStatus,
  normalizeScheduleResponse,
  normalizeStandingsResponse,
};
