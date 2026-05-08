function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim()
}

function normalizeSearchKey(value) {
  return cleanText(value)
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "")
}

function toNumber(value) {
  const amount = Number(String(value ?? "").replace(/,/g, ""))
  return Number.isFinite(amount) ? amount : 0
}

function toManwonRounded(value) {
  const amount = toNumber(value)
  return amount ? Math.round(amount / 10000) : 0
}

function toYearMonth(value) {
  const digits = String(value || "").replace(/\D/g, "")
  if (digits.length < 6) {
    return ""
  }

  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}`
}

function uniqueJoin(parts) {
  return [...new Set(parts.map(cleanText).filter(Boolean))].join(" ")
}

module.exports = {
  cleanText,
  normalizeSearchKey,
  toNumber,
  toManwonRounded,
  toYearMonth,
  uniqueJoin
}
