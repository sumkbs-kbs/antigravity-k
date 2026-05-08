const test = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")

const {
  providers,
  fetchInventory,
  lookupPrices
} = require("../src/index")
const { extractNextData, parseInventory } = require("../src/providers/sk-tagobuy")
const { summarizeMatches } = require("../src/search")

const fixturesDir = path.join(__dirname, "fixtures")
const inventoryHtml = fs.readFileSync(path.join(fixturesDir, "tb-page.html"), "utf8")
const emptyInventoryHtml = fs.readFileSync(path.join(fixturesDir, "tb-empty.html"), "utf8")

test("extractNextData reads the official Next.js inventory payload from SK direct HTML", () => {
  const nextData = extractNextData(inventoryHtml)

  assert.equal(nextData.page, "/pc/tb")
  assert.equal(nextData.props.pageProps.carListProd.length, 3)
})

test("sk-tagobuy parseInventory exposes public used-car price fields", () => {
  const inventory = parseInventory(inventoryHtml)

  assert.equal(inventory.provider.name, "SK렌터카 다이렉트 타고BUY")
  assert.equal(inventory.total, 3)
  assert.deepEqual(inventory.items[0], {
    id: "MP0000099027",
    providerProductClass: "타고BUY",
    maker: "현대",
    model: "캐스퍼",
    displayName: "현대 캐스퍼 1.0 가솔린 모던",
    color: "아틀라스 화이트",
    monthlyPrice: 350100,
    buyoutPrice: 10466815,
    buyoutPriceManwon: 1047,
    mileageKm: 64581,
    fuel: "휘발유",
    transmission: "오토",
    seats: 4,
    registrationYearMonth: "2022-11",
    modelYear: 2022,
    stock: 1,
    imageUrl: "https://image.skrentok.com/example/casper.jpg",
    searchText: "현대 캐스퍼 1.0 가솔린 모던 모던 아틀라스 화이트"
  })
})

test("summarizeMatches calculates price bands for matched cars", () => {
  const inventory = parseInventory(inventoryHtml)
  const summary = summarizeMatches(inventory.items)

  assert.deepEqual(summary, {
    count: 3,
    monthlyPriceMin: 350100,
    monthlyPriceMax: 392100,
    buyoutPriceMin: 10466815,
    buyoutPriceMax: 12900000,
    mileageKmMin: 61931,
    mileageKmMax: 100570
  })
})

test("lookupPrices filters the inventory by car keyword and sorts the cheapest buyout first", async () => {
  const originalFetch = global.fetch
  global.fetch = async () => makeHtmlResponse(inventoryHtml)

  try {
    const result = await lookupPrices("현대 아반떼", { limit: 5 })

    assert.equal(result.query, "현대 아반떼")
    assert.equal(result.matchedCount, 1)
    assert.equal(result.items[0].model, "아반떼")
    assert.equal(result.items[0].buyoutPrice, 12900000)
    assert.deepEqual(result.summary, {
      count: 1,
      monthlyPriceMin: 392100,
      monthlyPriceMax: 392100,
      buyoutPriceMin: 12900000,
      buyoutPriceMax: 12900000,
      mileageKmMin: 61931,
      mileageKmMax: 61931
    })
  } finally {
    global.fetch = originalFetch
  }
})

test("lookupPrices returns a matched K3 result and a conservative empty result when nothing matches", async () => {
  const originalFetch = global.fetch
  global.fetch = async () => makeHtmlResponse(inventoryHtml)

  try {
    const k3 = await lookupPrices("K3", { limit: 5 })
    assert.equal(k3.matchedCount, 1)
    assert.equal(k3.items[0].maker, "기아")

    const nothing = await lookupPrices("쏘렌토", { limit: 5 })
    assert.equal(nothing.matchedCount, 0)
    assert.deepEqual(nothing.items, [])
    assert.equal(nothing.summary, null)
  } finally {
    global.fetch = originalFetch
  }
})

test("lookupPrices reports summary and matchedCount from all matches before applying the item limit", async () => {
  const originalFetch = global.fetch
  global.fetch = async () => makeHtmlResponse(inventoryHtml)

  try {
    const result = await lookupPrices("현대", { limit: 1 })

    assert.equal(result.matchedCount, 2)
    assert.equal(result.items.length, 1)
    assert.equal(result.items[0].model, "캐스퍼")
    assert.deepEqual(result.summary, {
      count: 2,
      monthlyPriceMin: 350100,
      monthlyPriceMax: 392100,
      buyoutPriceMin: 10466815,
      buyoutPriceMax: 12900000,
      mileageKmMin: 61931,
      mileageKmMax: 64581
    })
  } finally {
    global.fetch = originalFetch
  }
})

test("fetchInventory uses the official 타고BUY page and tolerates an empty inventory snapshot", async () => {
  const originalFetch = global.fetch
  let requestedUrl = null
  global.fetch = async (url) => {
    requestedUrl = String(url)
    return makeHtmlResponse(emptyInventoryHtml)
  }

  try {
    const inventory = await fetchInventory()

    assert.equal(requestedUrl, "https://www.skdirect.co.kr/tb")
    assert.equal(inventory.total, 0)
    assert.deepEqual(inventory.items, [])
  } finally {
    global.fetch = originalFetch
  }
})

test("providers registry exposes sk-tagobuy by default", () => {
  assert.ok(providers["sk-tagobuy"])
  assert.equal(providers["sk-tagobuy"].provider.name, "SK렌터카 다이렉트 타고BUY")
})

test("fetchInventory rejects an unknown provider", async () => {
  await assert.rejects(
    () => fetchInventory({ provider: "nonexistent" }),
    (err) => {
      assert.match(err.message, /Unknown provider/)
      return true
    }
  )
})

function makeHtmlResponse(body) {
  return new Response(body, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8"
    }
  })
}
