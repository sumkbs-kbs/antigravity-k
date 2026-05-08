const {
  isAnchorLikePlace,
  isBarPanel,
  normalizeAnchorPanel,
  normalizePlacePanel,
  parseSearchResultsHtml,
  selectAnchorCandidate
} = require("./parse");

const SEARCH_VIEW_URL = "https://m.map.kakao.com/actions/searchView";
const PLACE_PANEL_URL_BASE = "https://place-api.map.kakao.com/places/panel3";
const DEFAULT_PANEL_LIMIT = 8;
const STATIONISH_CATEGORY_PATTERN = /(기차역|전철역|지하철역|환승역|수도권\d+호선|역)$/u;
const NON_WORD_PATTERN = /[^\p{L}\p{N}]+/gu;
const DEFAULT_BROWSER_HEADERS = {
  accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "accept-language": "ko,en-US;q=0.9,en;q=0.8",
  "user-agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
};
const DEFAULT_PANEL_HEADERS = {
  ...DEFAULT_BROWSER_HEADERS,
  accept: "application/json, text/plain, */*",
  appVersion: "6.6.0",
  origin: "https://place.map.kakao.com",
  pf: "PC",
  referer: "https://place.map.kakao.com/",
  "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
  "sec-ch-ua-mobile": "?0",
  "sec-ch-ua-platform": '"macOS"',
  "sec-fetch-dest": "empty",
  "sec-fetch-mode": "cors",
  "sec-fetch-site": "same-site"
};

async function request(url, options = {}, responseType = "text") {
  const fetchImpl = options.fetchImpl || global.fetch;

  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required.");
  }

  const response = await fetchImpl(url, {
    headers: {
      ...(responseType === "json" ? DEFAULT_PANEL_HEADERS : DEFAULT_BROWSER_HEADERS),
      ...(options.headers || {})
    },
    signal: options.signal
  });

  if (!response.ok) {
    throw new Error(`Kakao bar lookup request failed with ${response.status} for ${url}`);
  }

  return responseType === "json" ? response.json() : response.text();
}

async function fetchSearchResults(query, options = {}) {
  const url = new URL(SEARCH_VIEW_URL);
  url.searchParams.set("q", String(query || "").trim());
  return request(url.toString(), options, "text");
}

async function fetchPlacePanel(confirmId, options = {}) {
  return request(`${PLACE_PANEL_URL_BASE}/${confirmId}`, options, "json");
}

function sortBars(items) {
  return [...items].sort((left, right) => {
    if (left.isOpenNow !== right.isOpenNow) {
      return Number(right.isOpenNow) - Number(left.isOpenNow);
    }

    const leftDistance = left.distanceMeters ?? Number.POSITIVE_INFINITY;
    const rightDistance = right.distanceMeters ?? Number.POSITIVE_INFINITY;

    if (leftDistance !== rightDistance) {
      return leftDistance - rightDistance;
    }

    return left.name.localeCompare(right.name, "ko");
  });
}

function rankAnchorQueue(query, anchorCandidates) {
  const preferredAnchor = selectAnchorCandidate(query, anchorCandidates);
  return [preferredAnchor, ...anchorCandidates.filter((candidate) => candidate.id !== preferredAnchor.id)];
}

function isUsableAnchor(anchor) {
  return Boolean(
    anchor?.sourceUrl &&
    Number.isFinite(anchor?.latitude) &&
    Number.isFinite(anchor?.longitude)
  );
}

function normalizeQueryText(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(NON_WORD_PATTERN, "");
}

function isStationLikeQuery(query) {
  return /역$/u.test(query);
}

function matchesAnchorQueryPrefix(query, anchor = {}) {
  const normalizedQuery = normalizeQueryText(query);

  if (!normalizedQuery) {
    return false;
  }

  return [anchor.name, anchor.category]
    .map((value) => normalizeQueryText(value))
    .some((value) => value && (value.startsWith(normalizedQuery) || normalizedQuery.startsWith(value)));
}

function shouldAcceptAnchor(query, anchor) {
  if (!isUsableAnchor(anchor)) {
    return false;
  }

  if (!isStationLikeQuery(query)) {
    return true;
  }

  return isAnchorLikePlace(anchor) && matchesAnchorQueryPrefix(query, anchor);
}

async function resolveAnchor(query, options = {}) {
  const anchorSearchHtml = await fetchSearchResults(query, options);
  const anchorCandidates = parseSearchResultsHtml(anchorSearchHtml);
  const anchorQueue = rankAnchorQueue(query, anchorCandidates);

  for (const candidate of anchorQueue) {
    try {
      const anchorPanel = await fetchPlacePanel(candidate.id, options);
      const anchor = normalizeAnchorPanel(anchorPanel, candidate);

      if (shouldAcceptAnchor(query, anchor)) {
        return {
          anchor,
          anchorCandidates
        };
      }
    } catch (error) {
      if (!/404/.test(String(error.message || error))) {
        throw error;
      }
    }
  }

  throw new Error(`No usable Kakao Map place panel was available for ${query}.`);
}

function shouldRetryWithStationQuery(query, anchor) {
  return (
    !isStationLikeQuery(query) &&
    (!isUsableAnchor(anchor) || (!STATIONISH_CATEGORY_PATTERN.test(anchor.category) && !isAnchorLikePlace(anchor)))
  );
}

async function searchNearbyBarsByLocationQuery(locationQuery, options = {}) {
  const query = String(locationQuery || "").trim();

  if (!query) {
    throw new Error("locationQuery is required.");
  }

  let { anchor, anchorCandidates } = await resolveAnchor(query, options);

  if (shouldRetryWithStationQuery(query, anchor)) {
    try {
      const stationResolution = await resolveAnchor(`${query}역`, options);
      if (isUsableAnchor(stationResolution.anchor)) {
        anchor = stationResolution.anchor;
        anchorCandidates = stationResolution.anchorCandidates;
      }
    } catch (_error) {
      // Keep the original anchor when the station fallback is unavailable.
    }
  }

  const searchHtml = await fetchSearchResults(`${query} 술집`, options);
  const searchItems = parseSearchResultsHtml(searchHtml);
  const panelLimit = Math.max(1, Number(options.panelLimit || DEFAULT_PANEL_LIMIT));
  const panels = await Promise.all(
    searchItems.slice(0, panelLimit).map(async (searchItem) => ({
      searchItem,
      panel: await fetchPlacePanel(searchItem.id, options)
    })),
  );

  const normalizedItems = sortBars(
    panels
      .filter(({ panel, searchItem }) => isBarPanel(panel, searchItem))
      .map(({ panel, searchItem }) =>
        normalizePlacePanel(panel, searchItem, {
          latitude: anchor.latitude,
          longitude: anchor.longitude
        }),
      ),
  );

  return {
    anchor,
    anchorCandidates,
    items: normalizedItems.slice(0, options.limit ?? 5),
    meta: {
      evaluatedAt: new Date().toISOString(),
      totalSearchResults: searchItems.length,
      openNowCount: normalizedItems.filter((item) => item.isOpenNow).length,
      fetchedPanels: panels.length
    }
  };
}

module.exports = {
  DEFAULT_PANEL_LIMIT,
  PLACE_PANEL_URL_BASE,
  SEARCH_VIEW_URL,
  fetchPlacePanel,
  fetchSearchResults,
  normalizePlacePanel,
  parseSearchResultsHtml,
  searchNearbyBarsByLocationQuery,
  selectAnchorCandidate
};
