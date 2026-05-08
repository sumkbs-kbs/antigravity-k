const {
  KURLY_WEB_BASE_URL,
  extractNextDataJson,
  findProductDetail,
  normalizeCountResponse,
  normalizeKeyword,
  normalizeProductNo,
  normalizeSearchResponse
} = require("./parse")

const KURLY_API_BASE_URL = "https://api.kurly.com"
const DEFAULT_BROWSER_HEADERS = {
  accept: "application/json, text/plain, */*",
  "accept-language": "ko,en-US;q=0.9,en;q=0.8",
  "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}

async function request(url, options = {}) {
  const fetchImpl = options.fetchImpl || global.fetch

  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required.")
  }

  const response = await fetchImpl(url, {
    method: options.method || "GET",
    headers: {
      ...DEFAULT_BROWSER_HEADERS,
      ...(options.headers || {})
    },
    signal: options.signal
  })

  if (!response.ok) {
    throw new Error(`Market Kurly request failed with ${response.status} for ${url}`)
  }

  return response
}

async function requestJson(url, options = {}) {
  const response = await request(url, options)
  return response.json()
}

async function requestText(url, options = {}) {
  const response = await request(url, {
    ...options,
    headers: {
      accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      ...(options.headers || {})
    }
  })

  return response.text()
}

async function searchProducts(keyword, options = {}) {
  const normalizedKeyword = normalizeKeyword(keyword)
  const url = new URL(`${KURLY_API_BASE_URL}/search/v4/sites/market/normal-search`)

  url.searchParams.set("keyword", normalizedKeyword)
  url.searchParams.set("page", String(options.page || 1))

  const payload = await requestJson(url.toString(), options)
  return normalizeSearchResponse(payload, normalizedKeyword)
}

async function countProducts(keyword, options = {}) {
  const normalizedKeyword = normalizeKeyword(keyword)
  const url = new URL(`${KURLY_API_BASE_URL}/search/v3/sites/market/normal-search/count`)

  url.searchParams.set("keyword", normalizedKeyword)
  url.searchParams.set("filters", options.filters || "")
  url.searchParams.set("allow_replace", options.allowReplace === false ? "false" : "true")

  const payload = await requestJson(url.toString(), options)
  return normalizeCountResponse(payload, normalizedKeyword)
}

async function getProductDetail(productNo, options = {}) {
  const normalizedProductNo = normalizeProductNo(productNo)
  const html = await requestText(`${KURLY_WEB_BASE_URL}/goods/${normalizedProductNo}`, options)
  const nextData = extractNextDataJson(html)

  return findProductDetail(nextData)
}

module.exports = {
  countProducts,
  getProductDetail,
  searchProducts
}
