const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  normalizePlacePanel,
  parseSearchResultsHtml,
  searchNearbyBarsByLocationQuery,
  selectAnchorCandidate
} = require("../src/index");

const fixturesDir = path.join(__dirname, "fixtures");
const anchorSearchHtml = fs.readFileSync(path.join(fixturesDir, "anchor-search.html"), "utf8");
const barSearchHtml = fs.readFileSync(path.join(fixturesDir, "bar-search.html"), "utf8");
const anchorPanel = JSON.parse(fs.readFileSync(path.join(fixturesDir, "anchor-panel.json"), "utf8"));
const openBarPanel = JSON.parse(fs.readFileSync(path.join(fixturesDir, "open-bar-panel.json"), "utf8"));
const closedBarPanel = JSON.parse(fs.readFileSync(path.join(fixturesDir, "closed-bar-panel.json"), "utf8"));
const nonBarPanel = JSON.parse(fs.readFileSync(path.join(fixturesDir, "non-bar-panel.json"), "utf8"));

test("parseSearchResultsHtml extracts Kakao mobile search cards with open-status and phone fields", () => {
  const items = parseSearchResultsHtml(barSearchHtml);

  assert.equal(items.length, 3);
  assert.deepEqual(items[0], {
    id: "2001",
    name: "데이브루펍",
    category: "맥주,호프",
    address: "서울 중구 칠패로 31",
    phone: "02-1111-2222",
    openStatusLabel: "영업중",
    openStatusText: "영업시간 12:00 ~ 23:30"
  });
});

test("selectAnchorCandidate prefers the obvious station/landmark match for the location query", () => {
  const anchor = selectAnchorCandidate("서울역", parseSearchResultsHtml(anchorSearchHtml));

  assert.equal(anchor.id, "1001");
  assert.equal(anchor.name, "서울역");
  assert.equal(anchor.category, "기차역");
});

test("normalizePlacePanel keeps menu, seating, phone, distance, and open-now hints", () => {
  const item = normalizePlacePanel(openBarPanel, {
    id: "2001",
    phone: "02-1111-2222",
    openStatusLabel: "영업중",
    openStatusText: "영업시간 12:00 ~ 23:30"
  }, {
    latitude: 37.55472,
    longitude: 126.97068
  });

  assert.equal(item.id, "2001");
  assert.equal(item.name, "데이브루펍");
  assert.equal(item.phone, "02-1111-2222");
  assert.equal(item.isOpenNow, true);
  assert.equal(item.openStatus.label, "영업 중");
  assert.equal(item.openStatus.detail, "23:30 라스트오더");
  assert.deepEqual(item.menuSamples, ["수제맥주 샘플러", "감바스", "페퍼로니 피자"]);
  assert.deepEqual(item.seatingKeywords, ["단체석", "바테이블"]);
  assert.equal(item.capacityHint, "단체 방문 가능");
  assert.ok(item.distanceMeters > 0);
});

test("searchNearbyBarsByLocationQuery returns open bars first and drops non-bar categories", async () => {
  const responses = new Map([
    [buildSearchUrl("서울역"), makeResponse(anchorSearchHtml, "text/html")],
    [buildSearchUrl("서울역 술집"), makeResponse(barSearchHtml, "text/html")],
    ["https://place-api.map.kakao.com/places/panel3/1001", makeResponse(anchorPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/2001", makeResponse(openBarPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/2002", makeResponse(closedBarPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/2003", makeResponse(nonBarPanel, "application/json")]
  ]);

  const calls = [];
  const fetchImpl = async (url) => {
    const resolved = String(url);
    calls.push(resolved);

    const response = responses.get(resolved);
    if (!response) {
      throw new Error(`unexpected url: ${resolved}`);
    }

    return response;
  };

  const result = await searchNearbyBarsByLocationQuery("서울역", {
    limit: 5,
    panelLimit: 3,
    fetchImpl
  });

  assert.equal(result.anchor.name, "서울역");
  assert.equal(result.anchor.category, "기차역");
  assert.equal(result.anchorCandidates[0].id, "1001");
  assert.equal(result.meta.totalSearchResults, 3);
  assert.equal(result.meta.openNowCount, 1);
  assert.equal(result.items.length, 2);
  assert.deepEqual(
    result.items.map((item) => [item.name, item.isOpenNow]),
    [["데이브루펍", true], ["밤산책와인바", false]]
  );
  assert.ok(!result.items.some((item) => item.name === "서울역국밥"));
  assert.ok(calls.some((url) => url.endsWith("/places/panel3/2001")));
});

test("searchNearbyBarsByLocationQuery skips unusable station-like anchor panels and keeps distances", async () => {
  const query = "사당";
  const fallbackAnchorSearchHtml = buildSearchResultsHtml([
    {
      id: "21160811",
      name: "사당역",
      category: "수도권2호선",
      address: "서울 동작구 사당동"
    },
    {
      id: "3001",
      name: "사당역 4호선",
      category: "전철역",
      address: "서울 동작구 사당동"
    }
  ]);
  const nearbyBarSearchHtml = buildSearchResultsHtml([
    {
      id: "2001",
      name: "데이브루펍",
      category: "맥주,호프",
      address: "서울 중구 칠패로 31",
      phone: "02-1111-2222",
      openStatusLabel: "영업중",
      openStatusText: "영업시간 12:00 ~ 23:30"
    }
  ]);
  const validSadangAnchorPanel = {
    summary: {
      confirm_id: "3001",
      name: "사당역",
      category: {
        name2: "전철역",
        name3: "전철역"
      },
      point: {
        lat: 37.47659,
        lon: 126.98163
      },
      address: {
        disp: "서울 동작구 사당동"
      }
    }
  };
  const invalidStationPanel = {
    subway_station_id: "21160811"
  };
  const responses = new Map([
    [buildSearchUrl(query), makeResponse(fallbackAnchorSearchHtml, "text/html")],
    [buildSearchUrl(`${query}역`), makeResponse(fallbackAnchorSearchHtml, "text/html")],
    [buildSearchUrl(`${query} 술집`), makeResponse(nearbyBarSearchHtml, "text/html")],
    ["https://place-api.map.kakao.com/places/panel3/21160811", makeResponse(invalidStationPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/3001", makeResponse(validSadangAnchorPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/2001", makeResponse(openBarPanel, "application/json")]
  ]);

  const result = await searchNearbyBarsByLocationQuery(query, {
    limit: 1,
    panelLimit: 1,
    fetchImpl: async (url) => {
      const response = responses.get(String(url));
      if (!response) {
        throw new Error(`unexpected url: ${url}`);
      }

      return response;
    }
  });

  assert.equal(result.anchor.id, "3001");
  assert.equal(result.anchor.name, "사당역");
  assert.equal(result.anchor.sourceUrl, "https://place.map.kakao.com/3001");
  assert.equal(result.items.length, 1);
  assert.ok(Number.isFinite(result.items[0].distanceMeters));
});

test("searchNearbyBarsByLocationQuery keeps a usable landmark anchor for area queries instead of overwriting it with a station-business fallback", async () => {
  const query = "사당";
  const areaAnchorSearchHtml = buildSearchResultsHtml([
    {
      id: "11220631014",
      name: "사당역",
      category: "서울 서초구 방배2동",
      address: "버스 정류장 번호 :"
    },
    {
      id: "792176818",
      name: "사당1동먹자골목상점가",
      category: "먹자골목",
      address: "서울 동작구 사당동 1101"
    }
  ]);
  const stationFallbackSearchHtml = buildSearchResultsHtml([
    {
      id: "21160811",
      name: "사당역 2호선",
      category: "수도권2호선",
      address: "서울 동작구 사당동"
    },
    {
      id: "211389635",
      name: "삼육가 사당역1호점",
      category: "육류,고기",
      address: "서울 서초구 방배동"
    },
    {
      id: "23371032",
      name: "사당역 공영주차장",
      category: "공영주차장",
      address: "서울 서초구 방배동"
    }
  ]);
  const nearbyBarSearchHtml = buildSearchResultsHtml([
    {
      id: "2001",
      name: "데이브루펍",
      category: "맥주,호프",
      address: "서울 중구 칠패로 31",
      phone: "02-1111-2222",
      openStatusLabel: "영업중",
      openStatusText: "영업시간 12:00 ~ 23:30"
    }
  ]);
  const themeStreetAnchorPanel = {
    summary: {
      confirm_id: "792176818",
      name: "사당1동먹자골목상점가",
      category: {
        name2: "관광,명소",
        name3: "테마거리"
      },
      point: {
        lat: 37.47835510628598,
        lon: 126.98071247669172
      },
      address: {
        disp: "서울 동작구 사당동 1101"
      }
    }
  };
  const invalidBusStopResponse = makeResponse({ error: "not found" }, "application/json", 404);
  const invalidStationPanel = {
    subway_station_id: "21160811"
  };
  const businessAnchorPanel = {
    summary: {
      confirm_id: "211389635",
      name: "삼육가 사당역1호점",
      category: {
        name2: "한식",
        name3: "육류,고기"
      },
      point: {
        lat: 37.47742921471774,
        lon: 126.98296478218445
      },
      address: {
        disp: "서울 서초구 방배동"
      }
    }
  };
  const publicAnchorPanel = {
    summary: {
      confirm_id: "23371032",
      name: "사당역 공영주차장",
      category: {
        name2: "교통시설",
        name3: "주차장"
      },
      point: {
        lat: 37.475555162992165,
        lon: 126.98330436588915
      },
      address: {
        disp: "서울 서초구 방배동"
      }
    }
  };
  const calls = [];
  const responses = new Map([
    [buildSearchUrl(query), makeResponse(areaAnchorSearchHtml, "text/html")],
    [buildSearchUrl(`${query}역`), makeResponse(stationFallbackSearchHtml, "text/html")],
    [buildSearchUrl(`${query} 술집`), makeResponse(nearbyBarSearchHtml, "text/html")],
    ["https://place-api.map.kakao.com/places/panel3/11220631014", invalidBusStopResponse],
    ["https://place-api.map.kakao.com/places/panel3/792176818", makeResponse(themeStreetAnchorPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/21160811", makeResponse(invalidStationPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/211389635", makeResponse(businessAnchorPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/23371032", makeResponse(publicAnchorPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/2001", makeResponse(openBarPanel, "application/json")]
  ]);

  const result = await searchNearbyBarsByLocationQuery(query, {
    limit: 1,
    panelLimit: 1,
    fetchImpl: async (url) => {
      const resolved = String(url);
      calls.push(resolved);
      const response = responses.get(resolved);
      if (!response) {
        throw new Error(`unexpected url: ${resolved}`);
      }

      return response;
    }
  });

  assert.equal(result.anchor.id, "792176818");
  assert.equal(result.anchor.name, "사당1동먹자골목상점가");
  assert.ok(Number.isFinite(result.items[0].distanceMeters));
  assert.ok(!calls.includes(buildSearchUrl("사당역")));
});

test("searchNearbyBarsByLocationQuery keeps station-like queries on public anchors instead of unrelated businesses", async () => {
  const query = "사당역";
  const stationSearchHtml = buildSearchResultsHtml([
    {
      id: "21160811",
      name: "사당역 2호선",
      category: "수도권2호선",
      address: "서울 동작구 사당동"
    },
    {
      id: "21160829",
      name: "사당역 4호선",
      category: "수도권4호선",
      address: "서울 동작구 사당동"
    },
    {
      id: "211389635",
      name: "삼육가 사당역1호점",
      category: "육류,고기",
      address: "서울 서초구 방배동"
    },
    {
      id: "23371032",
      name: "사당역 공영주차장",
      category: "공영주차장",
      address: "서울 서초구 방배동"
    }
  ]);
  const nearbyBarSearchHtml = buildSearchResultsHtml([
    {
      id: "2001",
      name: "데이브루펍",
      category: "맥주,호프",
      address: "서울 중구 칠패로 31",
      phone: "02-1111-2222",
      openStatusLabel: "영업중",
      openStatusText: "영업시간 12:00 ~ 23:30"
    }
  ]);
  const invalidStationPanel = {
    subway_station_id: "21160811"
  };
  const invalidSecondStationPanel = {
    subway_station_id: "21160829"
  };
  const businessAnchorPanel = {
    summary: {
      confirm_id: "211389635",
      name: "삼육가 사당역1호점",
      category: {
        name2: "한식",
        name3: "육류,고기"
      },
      point: {
        lat: 37.47742921471774,
        lon: 126.98296478218445
      },
      address: {
        disp: "서울 서초구 방배동"
      }
    }
  };
  const publicAnchorPanel = {
    summary: {
      confirm_id: "23371032",
      name: "사당역 공영주차장",
      category: {
        name2: "교통시설",
        name3: "주차장"
      },
      point: {
        lat: 37.475555162992165,
        lon: 126.98330436588915
      },
      address: {
        disp: "서울 서초구 방배동"
      }
    }
  };
  const responses = new Map([
    [buildSearchUrl(query), makeResponse(stationSearchHtml, "text/html")],
    [buildSearchUrl(`${query} 술집`), makeResponse(nearbyBarSearchHtml, "text/html")],
    ["https://place-api.map.kakao.com/places/panel3/21160811", makeResponse(invalidStationPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/21160829", makeResponse(invalidSecondStationPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/211389635", makeResponse(businessAnchorPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/23371032", makeResponse(publicAnchorPanel, "application/json")],
    ["https://place-api.map.kakao.com/places/panel3/2001", makeResponse(openBarPanel, "application/json")]
  ]);

  const result = await searchNearbyBarsByLocationQuery(query, {
    limit: 1,
    panelLimit: 1,
    fetchImpl: async (url) => {
      const response = responses.get(String(url));
      if (!response) {
        throw new Error(`unexpected url: ${url}`);
      }

      return response;
    }
  });

  assert.equal(result.anchor.id, "23371032");
  assert.equal(result.anchor.name, "사당역 공영주차장");
  assert.equal(result.anchor.category, "주차장");
  assert.ok(Number.isFinite(result.items[0].distanceMeters));
});

function makeResponse(body, contentType, status = 200) {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: {
      "content-type": contentType
    }
  });
}

function buildSearchResultsHtml(items) {
  return `
    <ul>
      ${items.map((item) => `
        <li class="search_item base" data-id="${item.id}" data-title="${item.name}"${item.phone ? ` data-phone="${item.phone}"` : ""}>
          <strong class="tit_g">${item.name}</strong>
          <span class="txt_ginfo">${item.category || ""}</span>
          ${item.openStatusLabel ? `<span class="tag_openoff">${item.openStatusLabel}</span>` : ""}
          ${item.openStatusText ? `<span class="txt_openoff">${item.openStatusText}</span>` : ""}
          <span class="txt_g">${item.address || ""}</span>
        </li>
      `).join("\n")}
    </ul>
  `;
}

function buildSearchUrl(query) {
  return `https://m.map.kakao.com/actions/searchView?q=${encodeURIComponent(query).replace(/%20/g, "+")}`;
}
