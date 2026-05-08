const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  evaluateTicket,
  getDetailResult,
  getLatestRound,
  getResult
} = require("../src/index");
const {
  extractLatestRoundFromHtml,
  normalizeRoundItem,
  selectRoundItem
} = require("../src/parse");

const fixturesDir = path.join(__dirname, "fixtures");
const latestResultHtml = fs.readFileSync(path.join(fixturesDir, "latest-result.html"), "utf8");
const round1216Payload = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "round-1216.json"), "utf8")
);

test("extractLatestRoundFromHtml parses the latest round from the official result page", () => {
  assert.equal(extractLatestRoundFromHtml(latestResultHtml), 1216);
});

test("normalizeRoundItem maps official JSON into the public detail shape", () => {
  const detail = normalizeRoundItem(selectRoundItem(round1216Payload, 1216));

  assert.equal(detail.round, 1216);
  assert.equal(detail.drawDate, "2026-03-21");
  assert.deepEqual(detail.numbers, [3, 10, 14, 15, 23, 24]);
  assert.equal(detail.bonus, 25);
  assert.equal(detail.payouts[0].rank, 1);
  assert.equal(detail.payouts[0].winners, 14);
  assert.equal(detail.winnersByPurchaseType?.auto, 8);
});

test("evaluateTicket returns the right rank for an exact match", () => {
  const detail = normalizeRoundItem(selectRoundItem(round1216Payload, 1216));
  const checked = evaluateTicket(detail, [3, 10, 14, 15, 23, 24]);

  assert.equal(checked.rank, 1);
  assert.equal(checked.outcome, "1등");
  assert.deepEqual(checked.matchedNumbers, [3, 10, 14, 15, 23, 24]);
});

test("evaluateTicket rejects duplicate numbers", () => {
  const detail = normalizeRoundItem(selectRoundItem(round1216Payload, 1216));

  assert.throws(() => {
    evaluateTicket(detail, [3, 3, 14, 15, 23, 24]);
  }, /duplicates/);
});

test("public fetchers can consume injected fixtures via mocked fetch", async () => {
  const originalFetch = global.fetch;

  global.fetch = async (url) => {
    if (String(url).includes("/lt645/result")) {
      return makeResponse(true, latestResultHtml);
    }

    return makeResponse(true, round1216Payload);
  };

  try {
    assert.equal(await getLatestRound(), 1216);
    assert.deepEqual(await getResult(1216), {
      round: 1216,
      drawDate: "2026-03-21",
      numbers: [3, 10, 14, 15, 23, 24],
      bonus: 25
    });

    const detail = await getDetailResult(1216);
    assert.equal(detail.payouts[1].rank, 2);
  } finally {
    global.fetch = originalFetch;
  }
});

/**
 * @param {boolean} ok
 * @param {string|object} body
 */
function makeResponse(ok, body) {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status: ok ? 200 : 500,
    headers: {
      "content-type": typeof body === "string" ? "text/html" : "application/json"
    }
  });
}
