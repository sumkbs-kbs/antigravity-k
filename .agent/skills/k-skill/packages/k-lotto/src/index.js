const {
  evaluateTicket,
  extractLatestRoundFromHtml,
  normalizeRoundItem,
  selectRoundItem
} = require("./parse");

const DEFAULT_HEADERS = {
  accept: "application/json, text/html;q=0.9",
  "user-agent": "k-skill/k-lotto"
};

const LATEST_RESULT_URL = "https://www.dhlottery.co.kr/lt645/result";
const ROUND_DETAIL_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do";

/**
 * @param {string} url
 * @returns {Promise<string>}
 */
async function fetchText(url) {
  const response = await fetch(url, { headers: DEFAULT_HEADERS });

  if (!response.ok) {
    throw new Error(`dhlottery request failed with ${response.status} for ${url}`);
  }

  return response.text();
}

/**
 * @param {string} url
 * @returns {Promise<unknown>}
 */
async function fetchJson(url) {
  const response = await fetch(url, { headers: DEFAULT_HEADERS });

  if (!response.ok) {
    throw new Error(`dhlottery request failed with ${response.status} for ${url}`);
  }

  return response.json();
}

/**
 * @returns {Promise<number>}
 */
async function getLatestRound() {
  const html = await fetchText(LATEST_RESULT_URL);
  return extractLatestRoundFromHtml(html);
}

/**
 * @param {number} round
 * @returns {Promise<ReturnType<typeof normalizeRoundItem>>}
 */
async function getDetailResult(round) {
  assertValidRound(round);

  const url = new URL(ROUND_DETAIL_URL);
  url.searchParams.set("srchDir", "center");
  url.searchParams.set("srchLtEpsd", String(round));

  const payload = await fetchJson(url.toString());
  const item = selectRoundItem(payload, round);

  return normalizeRoundItem(item);
}

/**
 * @param {number} round
 */
async function getResult(round) {
  const detail = await getDetailResult(round);

  return {
    round: detail.round,
    drawDate: detail.drawDate,
    numbers: [...detail.numbers],
    bonus: detail.bonus
  };
}

/**
 * @param {number} round
 * @param {ReadonlyArray<number>} ticketNumbers
 */
async function checkNumber(round, ticketNumbers) {
  const detail = await getDetailResult(round);
  return evaluateTicket(detail, ticketNumbers);
}

/**
 * @param {number} round
 */
function assertValidRound(round) {
  if (!Number.isInteger(round) || round < 1) {
    throw new Error("round must be a positive integer.");
  }
}

module.exports = {
  checkNumber,
  evaluateTicket,
  getDetailResult,
  getLatestRound,
  getResult
};
