const { cleanText, normalizeSearchKey } = require("./util")

function filterCarsByQuery(items, query) {
  const queryText = cleanText(query)
  if (!queryText) {
    throw new Error("query is required.")
  }

  const rawTokens = queryText.split(/\s+/).map(normalizeSearchKey).filter(Boolean)
  const fullQueryKey = normalizeSearchKey(queryText)

  return items
    .filter((item) => {
      const haystack = normalizeSearchKey(item.searchText)
      return rawTokens.every((token) => haystack.includes(token))
    })
    .map((item) => ({
      item,
      score: computeMatchScore(item, fullQueryKey, rawTokens)
    }))
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score
      }

      return compareBuyout(left.item, right.item)
    })
    .map((entry) => entry.item)
}

function computeMatchScore(item, fullQueryKey, rawTokens) {
  const modelKey = normalizeSearchKey(item.model)
  const displayKey = normalizeSearchKey(item.displayName)
  const haystack = normalizeSearchKey(item.searchText)

  let score = 0

  if (modelKey === fullQueryKey) {
    score += 10
  }

  if (displayKey.includes(fullQueryKey)) {
    score += 5
  }

  if (haystack.includes(fullQueryKey)) {
    score += 3
  }

  score += rawTokens.filter((token) => modelKey.includes(token)).length * 2
  score += rawTokens.filter((token) => displayKey.includes(token)).length

  return score
}

function compareBuyout(left, right) {
  return Number(left.buyoutPrice || 0) - Number(right.buyoutPrice || 0)
}

function summarizeMatches(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null
  }

  return {
    count: items.length,
    monthlyPriceMin: minValue(items, "monthlyPrice"),
    monthlyPriceMax: maxValue(items, "monthlyPrice"),
    buyoutPriceMin: minValue(items, "buyoutPrice"),
    buyoutPriceMax: maxValue(items, "buyoutPrice"),
    mileageKmMin: minValue(items, "mileageKm"),
    mileageKmMax: maxValue(items, "mileageKm")
  }
}

function minValue(items, key) {
  return Math.min(...items.map((item) => Number(item[key] || 0)))
}

function maxValue(items, key) {
  return Math.max(...items.map((item) => Number(item[key] || 0)))
}

module.exports = {
  filterCarsByQuery,
  summarizeMatches
}
