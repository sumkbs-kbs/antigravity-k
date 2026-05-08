const SEARCH_ITEM_PATTERN = /<li\s+class="search_item\s+base"([\s\S]*?)<\/li>/giu;
const TAG_PATTERN = /<[^>]+>/g;
const NON_WORD_PATTERN = /[^\p{L}\p{N}]+/gu;
const ANCHOR_STATION_PATTERN = /(역|기차역|전철역|지하철역|환승역)$/u;
const ANCHOR_CATEGORY_PATTERN =
  /(기차역|전철역|지하철역|역사|광장|공원|거리|테마거리|관광명소|랜드마크|먹자골목|교차로|주차장|정류장|환승센터)/u;
const BAR_CATEGORY_PATTERN = /(술집|주점|와인바|바\(BAR\)|\bBAR\b|맥주,호프|호프|이자카야|칵테일|포차|요리주점|일본식주점)/iu;

function decodeHtml(value) {
  return String(value || "")
    .replace(/&amp;/g, "&")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function stripTags(value) {
  return decodeHtml(String(value || "").replace(TAG_PATTERN, " "))
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(NON_WORD_PATTERN, "");
}

function extractAttribute(fragment, name) {
  const match = fragment.match(new RegExp(`${name}="([^"]*)"`, "iu"));
  return match ? decodeHtml(match[1]).trim() : "";
}

function extractInnerText(fragment, className) {
  const match = fragment.match(
    new RegExp(`<[^>]+class="[^"]*${className}[^"]*"[^>]*>([\\s\\S]*?)<\\/[^>]+>`, "iu"),
  );

  return match ? stripTags(match[1]) : "";
}

function parseSearchResultsHtml(html) {
  const items = [];
  let match;

  while ((match = SEARCH_ITEM_PATTERN.exec(String(html || ""))) !== null) {
    const fragment = match[1];
    const id = extractAttribute(fragment, "data-id");
    const name = extractAttribute(fragment, "data-title") || extractInnerText(fragment, "tit_g");

    if (!id || !name) {
      continue;
    }

    const addressMatches = [...fragment.matchAll(/<span class="txt_g">([\s\S]*?)<\/span>/giu)]
      .map((entry) => stripTags(entry[1]))
      .filter(Boolean);

    items.push({
      id,
      name,
      category: extractInnerText(fragment, "txt_ginfo"),
      address: addressMatches.at(-1) || "",
      phone: extractAttribute(fragment, "data-phone") || extractInnerText(fragment, "num_phone"),
      openStatusLabel: extractInnerText(fragment, "tag_openoff"),
      openStatusText: extractInnerText(fragment, "txt_openoff")
    });
  }

  return items;
}

function scoreAnchorCandidate(query, item) {
  const normalizedQuery = normalizeText(query);
  const normalizedName = normalizeText(item.name);
  const normalizedAddress = normalizeText(item.address);
  const normalizedCategory = normalizeText(item.category);
  let score = 0;

  if (!normalizedQuery) {
    return score;
  }

  if (normalizedName === normalizedQuery) {
    score += 1_000;
  }

  if (normalizedName === `${normalizedQuery}역` || normalizedName === normalizedQuery.replace(/역$/u, "")) {
    score += 950;
  }

  if (normalizedName.startsWith(normalizedQuery)) {
    score += 800;
  }

  if (normalizedName.includes(normalizedQuery)) {
    score += 600;
  }

  if (normalizedAddress.includes(normalizedQuery)) {
    score += 120;
  }

  if (ANCHOR_STATION_PATTERN.test(item.name) || ANCHOR_CATEGORY_PATTERN.test(item.category)) {
    score += 250;
  }

  if (BAR_CATEGORY_PATTERN.test(item.category) || BAR_CATEGORY_PATTERN.test(item.name)) {
    score -= 200;
  }

  if (normalizedCategory.includes("기차역") || normalizedCategory.includes("전철역")) {
    score += 80;
  }

  if (!/^\d+$/.test(String(item.id || ""))) {
    score -= 500;
  }

  return score;
}

function selectAnchorCandidate(query, items) {
  const ranked = [...(items || [])].sort((left, right) => {
    const scoreDelta = scoreAnchorCandidate(query, right) - scoreAnchorCandidate(query, left);

    if (scoreDelta !== 0) {
      return scoreDelta;
    }

    return left.name.localeCompare(right.name, "ko");
  });

  if (ranked.length === 0) {
    throw new Error("No Kakao Map place candidate matched that location query.");
  }

  return ranked[0];
}

function calculateDistanceMeters(originLatitude, originLongitude, latitude, longitude) {
  if (![originLatitude, originLongitude, latitude, longitude].every(Number.isFinite)) {
    return null;
  }

  const toRadians = (value) => (value * Math.PI) / 180;
  const earthRadiusMeters = 6_371_000;
  const latitudeDelta = toRadians(latitude - originLatitude);
  const longitudeDelta = toRadians(longitude - originLongitude);
  const haversine =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(toRadians(originLatitude)) *
      Math.cos(toRadians(latitude)) *
      Math.sin(longitudeDelta / 2) ** 2;

  return Math.round(2 * earthRadiusMeters * Math.asin(Math.sqrt(haversine)));
}

function collectMenuSamples(panel) {
  return [...new Set(
    (panel.menu?.menus?.items || [])
      .map((item) => String(item.name || "").trim())
      .filter(Boolean),
  )].slice(0, 5);
}

function collectSeatingKeywords(panel) {
  const keywords = new Set();
  const aiMate = panel.ai_mate || {};

  for (const value of aiMate.summary?.contents || []) {
    if (value) {
      keywords.add(String(value).trim());
    }
  }

  for (const sheet of aiMate.bottom_sheet?.sheets || []) {
    for (const item of sheet.list || []) {
      if (item.title === "좌석 옵션") {
        for (const keyword of item.keywords || []) {
          if (keyword) {
            keywords.add(String(keyword).trim());
          }
        }
      }
    }
  }

  return [...keywords];
}

function deriveCapacityHint(seatingKeywords) {
  if (seatingKeywords.some((keyword) => /단체석|룸|대관/u.test(keyword))) {
    return "단체 방문 가능";
  }

  if (seatingKeywords.some((keyword) => /바테이블|혼술/u.test(keyword))) {
    return "소규모/혼술 위주";
  }

  return seatingKeywords[0] || null;
}

function normalizeOpenStatus(panel, searchItem = {}) {
  const headline = panel.open_hours?.headline || {};
  const label = headline.display_text || searchItem.openStatusLabel || null;
  const detail = headline.display_text_info || searchItem.openStatusText || null;
  const code = headline.code || null;
  const today = panel.open_hours?.week_from_today?.week_periods
    ?.flatMap((period) => period.days || [])
    ?.find((day) => day.is_highlight);
  const todayHours = today?.on_days?.start_end_time_desc || null;
  const isOpenNow = /영업\s*중/u.test(label || "") || code === "OPEN" || code === "OPEN_NOW";

  return {
    code,
    label,
    detail,
    todayHours,
    isOpenNow
  };
}

function normalizeAnchorPanel(panel, searchItem = {}) {
  const summary = panel.summary || {};

  return {
    id: String(summary.confirm_id || searchItem.id || ""),
    name: summary.name || searchItem.name || "",
    category: summary.category?.name3 || summary.category?.name2 || searchItem.category || "",
    address: summary.address?.disp || searchItem.address || "",
    phone: summary.phone_numbers?.[0]?.tel || searchItem.phone || null,
    latitude: Number(summary.point?.lat),
    longitude: Number(summary.point?.lon),
    sourceUrl: summary.confirm_id ? `https://place.map.kakao.com/${summary.confirm_id}` : null
  };
}

function isAnchorLikePlace(place = {}) {
  return (
    !BAR_CATEGORY_PATTERN.test(`${place.name || ""} ${place.category || ""}`) &&
    (ANCHOR_STATION_PATTERN.test(place.name || "") || ANCHOR_CATEGORY_PATTERN.test(place.category || ""))
  );
}

function isBarCategoryValue(value) {
  return BAR_CATEGORY_PATTERN.test(String(value || ""));
}

function isBarPanel(panel, searchItem = {}) {
  const summary = panel.summary || {};
  return [
    summary.category?.name3,
    summary.category?.name2,
    searchItem.category,
    summary.name,
    searchItem.name
  ].some(isBarCategoryValue);
}

function normalizePlacePanel(panel, searchItem = {}, anchorPoint = {}) {
  const summary = panel.summary || {};
  const latitude = Number(summary.point?.lat);
  const longitude = Number(summary.point?.lon);
  const openStatus = normalizeOpenStatus(panel, searchItem);
  const seatingKeywords = collectSeatingKeywords(panel);
  const menuSamples = collectMenuSamples(panel);

  return {
    id: String(summary.confirm_id || searchItem.id || ""),
    name: summary.name || searchItem.name || "",
    category: summary.category?.name3 || summary.category?.name2 || searchItem.category || "",
    address: summary.address?.disp || searchItem.address || "",
    phone: summary.phone_numbers?.[0]?.tel || searchItem.phone || null,
    latitude,
    longitude,
    distanceMeters: calculateDistanceMeters(anchorPoint.latitude, anchorPoint.longitude, latitude, longitude),
    isOpenNow: openStatus.isOpenNow,
    openStatus: {
      code: openStatus.code,
      label: openStatus.label,
      detail: openStatus.detail,
      todayHours: openStatus.todayHours
    },
    menuSamples,
    seatingKeywords,
    capacityHint: deriveCapacityHint(seatingKeywords),
    tags: panel.place_add_info?.tags || [],
    summary:
      panel.ai_mate?.bottom_sheet?.summary ||
      panel.ai_mate?.summary?.title ||
      null,
    sourceUrl: summary.confirm_id ? `https://place.map.kakao.com/${summary.confirm_id}` : null
  };
}

module.exports = {
  SEARCH_ITEM_PATTERN,
  calculateDistanceMeters,
  isAnchorLikePlace,
  isBarPanel,
  normalizeAnchorPanel,
  normalizePlacePanel,
  parseSearchResultsHtml,
  selectAnchorCandidate
};
