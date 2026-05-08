const { cleanText, toNumber, toManwonRounded, toYearMonth, uniqueJoin } = require("../util")

const SK_TAGOBUY_URL = "https://www.skdirect.co.kr/tb"
const NEXT_DATA_PATTERN = /<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/

const DEFAULT_BROWSER_HEADERS = {
  accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "accept-language": "ko,en-US;q=0.9,en;q=0.8",
  "user-agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}

const provider = {
  id: "sk-tagobuy",
  name: "SK렌터카 다이렉트 타고BUY",
  siteUrl: SK_TAGOBUY_URL,
  inventoryPath: "/tb",
  extraction: "next-data"
}

function extractNextData(html) {
  const source = String(html || "")
  const match = source.match(NEXT_DATA_PATTERN)

  if (!match) {
    throw new Error("Unable to locate SK direct __NEXT_DATA__ inventory payload.")
  }

  return JSON.parse(match[1])
}

function normalizeCar(raw) {
  const maker = cleanText(raw.carMakerNm)
  const model = cleanText(raw.modeProdNm || raw.cartypeNm)
  const carType = cleanText(raw.cartypeNm)
  const grade = cleanText(raw.carGradeNm)
  const trim = cleanText(raw.crtrClsNm1)
  const color = cleanText(raw.colorNm)
  const displayName = uniqueJoin([maker, model, grade])
  const searchText = uniqueJoin([maker, carType, model, grade, trim, color])

  return {
    id: cleanText(raw.prodId),
    providerProductClass: cleanText(raw.prodClsNm),
    maker,
    model,
    displayName,
    color,
    monthlyPrice: toNumber(raw.realPaymentAmt),
    buyoutPrice: toNumber(raw.tkvAmt),
    buyoutPriceManwon: toManwonRounded(raw.tkvAmt),
    mileageKm: toNumber(raw.travelDtc),
    fuel: cleanText(raw.fuelNm),
    transmission: cleanText(raw.grbxNm),
    seats: toNumber(raw.seaterClsNm),
    registrationYearMonth: toYearMonth(raw.carRegDt),
    modelYear: toNumber(raw.yearType),
    stock: toNumber(raw.prodStock),
    imageUrl: cleanText(raw.repCarImg),
    searchText
  }
}

function compareCars(left, right) {
  return (
    compareNumbers(left.buyoutPrice, right.buyoutPrice) ||
    compareNumbers(left.monthlyPrice, right.monthlyPrice) ||
    compareNumbers(left.mileageKm, right.mileageKm) ||
    String(left.displayName).localeCompare(String(right.displayName), "ko")
  )
}

function compareNumbers(left, right) {
  return Number(left || 0) - Number(right || 0)
}

function parseInventory(input) {
  const nextData = typeof input === "string" ? extractNextData(input) : input
  const carList = nextData?.props?.pageProps?.carListProd

  if (!Array.isArray(carList)) {
    throw new Error("Expected carListProd in the SK direct inventory payload.")
  }

  const items = carList.map(normalizeCar).sort(compareCars)

  return { provider, total: items.length, items }
}

async function fetchInventory(options = {}) {
  const fetchImpl = options.fetchImpl || global.fetch

  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required.")
  }

  const response = await fetchImpl(options.url || SK_TAGOBUY_URL, {
    headers: {
      ...DEFAULT_BROWSER_HEADERS,
      ...(options.headers || {})
    },
    signal: options.signal
  })

  if (!response.ok) {
    throw new Error(`SK direct request failed with ${response.status} for ${options.url || SK_TAGOBUY_URL}`)
  }

  const html = await response.text()
  const inventory = parseInventory(html)

  return {
    ...inventory,
    fetchedAt: new Date().toISOString()
  }
}

module.exports = {
  provider,
  extractNextData,
  parseInventory,
  fetchInventory
}
