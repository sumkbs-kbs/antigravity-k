const LATEST_ROUND_PATTERN = /id="opt_val"[^>]*value="(\d+)"/i;

/**
 * @param {string} html
 * @returns {number}
 */
function extractLatestRoundFromHtml(html) {
  const match = html.match(LATEST_ROUND_PATTERN);

  if (!match) {
    throw new Error("Unable to locate the latest round on the dhlottery result page.");
  }

  return Number.parseInt(match[1], 10);
}

/**
 * @param {number} value
 * @returns {string}
 */
function formatWon(value) {
  return `${value.toLocaleString("ko-KR")}원`;
}

/**
 * @param {string} raw
 * @returns {string}
 */
function formatYmd(raw) {
  if (!/^\d{8}$/.test(raw)) {
    throw new Error(`Unexpected date format: ${raw}`);
  }

  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

/**
 * @param {unknown} payload
 * @param {number} round
 * @returns {Record<string, any>}
 */
function selectRoundItem(payload, round) {
  if (!payload || typeof payload !== "object") {
    throw new Error("Expected a JSON object from dhlottery.");
  }

  const data = /** @type {{ data?: { list?: Array<Record<string, any>> } }} */ (payload).data;
  const list = data?.list;

  if (!Array.isArray(list) || list.length === 0) {
    throw new Error(`No lotto result items were returned for round ${round}.`);
  }

  const item = list.find((entry) => Number(entry.ltEpsd) === round);

  if (!item) {
    throw new Error(`Round ${round} was not present in the dhlottery response.`);
  }

  return item;
}

/**
 * @param {Record<string, any>} item
 * @returns {{
 *   round: number,
 *   drawDate: string,
 *   numbers: number[],
 *   bonus: number,
 *   totalSalesAmount: number,
 *   carryoverSalesAmount: number,
 *   winnersByPurchaseType: null | { auto: number, manual: number, semiAuto: number },
 *   payouts: Array<{ rank: number, winners: number, prizeAmount: number, totalPrizeAmount: number, prizeAmountLabel: string, totalPrizeAmountLabel: string }>,
 *   raw: Record<string, any>
 * }}
 */
function normalizeRoundItem(item) {
  const numbers = [item.tm1WnNo, item.tm2WnNo, item.tm3WnNo, item.tm4WnNo, item.tm5WnNo, item.tm6WnNo]
    .map((value) => Number(value));

  const bonus = Number(item.bnsWnNo);

  return {
    round: Number(item.ltEpsd),
    drawDate: formatYmd(String(item.ltRflYmd)),
    numbers,
    bonus,
    totalSalesAmount: Number(item.wholEpsdSumNtslAmt),
    carryoverSalesAmount: Number(item.rlvtEpsdSumNtslAmt),
    winnersByPurchaseType: Number(item.winType0) === 0
      ? {
          auto: Number(item.winType1),
          manual: Number(item.winType2),
          semiAuto: Number(item.winType3)
        }
      : null,
    payouts: [
      buildPayoutRow(1, item.rnk1WnNope, item.rnk1WnAmt, item.rnk1SumWnAmt),
      buildPayoutRow(2, item.rnk2WnNope, item.rnk2WnAmt, item.rnk2SumWnAmt),
      buildPayoutRow(3, item.rnk3WnNope, item.rnk3WnAmt, item.rnk3SumWnAmt),
      buildPayoutRow(4, item.rnk4WnNope, item.rnk4WnAmt, item.rnk4SumWnAmt),
      buildPayoutRow(5, item.rnk5WnNope, item.rnk5WnAmt, item.rnk5SumWnAmt)
    ],
    raw: item
  };
}

/**
 * @param {number} rank
 * @param {unknown} winners
 * @param {unknown} prizeAmount
 * @param {unknown} totalPrizeAmount
 */
function buildPayoutRow(rank, winners, prizeAmount, totalPrizeAmount) {
  const normalizedPrize = Number(prizeAmount);
  const normalizedTotal = Number(totalPrizeAmount);

  return {
    rank,
    winners: Number(winners),
    prizeAmount: normalizedPrize,
    totalPrizeAmount: normalizedTotal,
    prizeAmountLabel: formatWon(normalizedPrize),
    totalPrizeAmountLabel: formatWon(normalizedTotal)
  };
}

/**
 * @param {ReadonlyArray<number>} ticketNumbers
 * @returns {number[]}
 */
function normalizeTicket(ticketNumbers) {
  if (!Array.isArray(ticketNumbers) || ticketNumbers.length !== 6) {
    throw new Error("ticketNumbers must contain exactly 6 values.");
  }

  const normalized = ticketNumbers.map((value) => Number(value));

  if (normalized.some((value) => !Number.isInteger(value) || value < 1 || value > 45)) {
    throw new Error("ticketNumbers must be integers between 1 and 45.");
  }

  const uniqueCount = new Set(normalized).size;
  if (uniqueCount !== 6) {
    throw new Error("ticketNumbers must not contain duplicates.");
  }

  return normalized.sort((left, right) => left - right);
}

/**
 * @param {ReturnType<typeof normalizeRoundItem>} detail
 * @param {ReadonlyArray<number>} ticketNumbers
 */
function evaluateTicket(detail, ticketNumbers) {
  const normalizedTicket = normalizeTicket(ticketNumbers);
  const matchedNumbers = normalizedTicket.filter((number) => detail.numbers.includes(number));
  const bonusMatched = normalizedTicket.includes(detail.bonus);
  const rank = determineRank(matchedNumbers.length, bonusMatched);

  return {
    round: detail.round,
    drawDate: detail.drawDate,
    ticketNumbers: normalizedTicket,
    winningNumbers: [...detail.numbers],
    bonus: detail.bonus,
    matchedNumbers,
    bonusMatched,
    matchCount: matchedNumbers.length,
    rank,
    outcome: rank === null ? "낙첨" : `${rank}등`
  };
}

/**
 * @param {number} matchCount
 * @param {boolean} bonusMatched
 * @returns {number | null}
 */
function determineRank(matchCount, bonusMatched) {
  if (matchCount === 6) {
    return 1;
  }

  if (matchCount === 5 && bonusMatched) {
    return 2;
  }

  if (matchCount === 5) {
    return 3;
  }

  if (matchCount === 4) {
    return 4;
  }

  if (matchCount === 3) {
    return 5;
  }

  return null;
}

module.exports = {
  evaluateTicket,
  extractLatestRoundFromHtml,
  normalizeRoundItem,
  selectRoundItem
};
