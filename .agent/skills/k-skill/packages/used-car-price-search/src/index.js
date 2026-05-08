const skTagoBuy = require("./providers/sk-tagobuy")
const { filterCarsByQuery, summarizeMatches } = require("./search")

const providers = {
  "sk-tagobuy": skTagoBuy
}

const DEFAULT_PROVIDER = "sk-tagobuy"

function resolveProvider(options = {}) {
  const id = options.provider || DEFAULT_PROVIDER
  const resolved = providers[id]

  if (!resolved) {
    const available = Object.keys(providers).join(", ")
    throw new Error(`Unknown provider "${id}". Available: ${available}`)
  }

  return resolved
}

async function fetchInventory(options = {}) {
  const providerModule = resolveProvider(options)
  return providerModule.fetchInventory(options)
}

async function lookupPrices(query, options = {}) {
  const limit = Number(options.limit || 10)
  const inventory = await fetchInventory(options)
  const allMatches = filterCarsByQuery(inventory.items, query)
  const matches = allMatches.slice(0, limit)

  return {
    provider: inventory.provider,
    fetchedAt: inventory.fetchedAt,
    query: String(query || "").trim(),
    totalInventory: inventory.total,
    matchedCount: allMatches.length,
    summary: summarizeMatches(allMatches),
    items: matches
  }
}

module.exports = {
  providers,
  fetchInventory,
  lookupPrices,
  // back-compat aliases
  fetchUsedCarInventory: fetchInventory,
  lookupUsedCarPrices: lookupPrices
}
