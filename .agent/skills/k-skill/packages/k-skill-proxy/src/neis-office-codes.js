/**
 * 시도교육청 코드(ATPT_OFCDC_SC_CODE) — 나이스 교육정보 개방 포털 학교기본정보·급식 등과 동일 체계.
 * 자연어 별칭은 사용자가 흔히 쓰는 교육청명·약칭을 포함한다.
 */

const OFFICES = [
  {
    code: "B10",
    labels: [
      "서울특별시교육청",
      "서울시교육청",
      "서울교육청",
      "서울특별시",
      "서울"
    ]
  },
  {
    code: "C10",
    labels: ["부산광역시교육청", "부산시교육청", "부산교육청", "부산광역시", "부산"]
  },
  {
    code: "D10",
    labels: ["대구광역시교육청", "대구시교육청", "대구교육청", "대구광역시", "대구"]
  },
  {
    code: "E10",
    labels: ["인천광역시교육청", "인천시교육청", "인천교육청", "인천광역시", "인천"]
  },
  {
    code: "F10",
    labels: ["광주광역시교육청", "광주시교육청", "광주교육청", "광주광역시", "광주"]
  },
  {
    code: "G10",
    labels: ["대전광역시교육청", "대전시교육청", "대전교육청", "대전광역시", "대전"]
  },
  {
    code: "H10",
    labels: ["울산광역시교육청", "울산시교육청", "울산교육청", "울산광역시", "울산"]
  },
  {
    code: "I10",
    labels: ["세종특별자치시교육청", "세종교육청", "세종특별자치시", "세종"]
  },
  {
    code: "J10",
    labels: ["경기도교육청", "경기교육청", "경기도", "경기"]
  },
  {
    code: "K10",
    labels: [
      "강원특별자치도교육청",
      "강원도교육청",
      "강원교육청",
      "강원특별자치도",
      "강원도",
      "강원"
    ]
  },
  {
    code: "M10",
    labels: ["충청북도교육청", "충북교육청", "충청북도", "충북"]
  },
  {
    code: "N10",
    labels: ["충청남도교육청", "충남교육청", "충청남도", "충남"]
  },
  {
    code: "P10",
    labels: [
      "전북특별자치도교육청",
      "전라북도교육청",
      "전북교육청",
      "전북특별자치도",
      "전라북도",
      "전북"
    ]
  },
  {
    code: "Q10",
    labels: ["전라남도교육청", "전남교육청", "전라남도", "전남"]
  },
  {
    code: "R10",
    labels: ["경상북도교육청", "경북교육청", "경상북도", "경북"]
  },
  {
    code: "S10",
    labels: ["경상남도교육청", "경남교육청", "경상남도", "경남"]
  },
  {
    code: "T10",
    labels: ["제주특별자치도교육청", "제주교육청", "제주특별자치도", "제주"]
  }
];

const KNOWN_CODES = new Set(OFFICES.map((o) => o.code));

function compactKo(value) {
  return String(value).trim().replace(/\s+/g, "");
}

/**
 * @param {string | null | undefined} rawHint
 * @returns {{ ok: true, code: string, matchedLabel: string } | { ok: false, reason: "unknown" } | { ok: false, reason: "ambiguous", codes: string[], hint: string }}
 */
function resolveEducationOfficeFromNaturalLanguage(rawHint) {
  const trimmed = rawHint === undefined || rawHint === null ? "" : String(rawHint).trim();
  if (!trimmed) {
    return { ok: false, reason: "unknown" };
  }

  const codeLike = trimmed.match(/^\s*([A-Za-z])(\d{2})\s*$/);
  if (codeLike) {
    const code = `${codeLike[1].toUpperCase()}${codeLike[2]}`;
    if (KNOWN_CODES.has(code)) {
      return { ok: true, code, matchedLabel: code };
    }
    return { ok: false, reason: "unknown" };
  }

  const h = compactKo(trimmed);
  if (h.length < 2) {
    return { ok: false, reason: "unknown" };
  }

  /** @type {{ code: string, label: string, score: number }[]} */
  const hits = [];

  for (const office of OFFICES) {
    for (const label of office.labels) {
      const l = compactKo(label);
      if (!l) {
        continue;
      }

      let score = 0;
      if (h === l) {
        score = 1000 + l.length;
      } else if (l.startsWith(h) || h.startsWith(l)) {
        score = 500 + Math.min(l.length, h.length);
      } else if (l.includes(h)) {
        score = 200 + h.length;
      } else if (h.includes(l) && l.length >= 4) {
        score = 100 + l.length;
      }

      if (score > 0) {
        hits.push({ code: office.code, label, score });
      }
    }
  }

  if (hits.length === 0) {
    return { ok: false, reason: "unknown" };
  }

  hits.sort((a, b) => b.score - a.score);
  const top = hits[0].score;
  const topCodes = [...new Set(hits.filter((x) => x.score === top).map((x) => x.code))];

  if (topCodes.length > 1) {
    return { ok: false, reason: "ambiguous", codes: topCodes, hint: trimmed };
  }

  const winner = hits.find((x) => x.score === top && x.code === topCodes[0]);
  return { ok: true, code: topCodes[0], matchedLabel: winner.label };
}

module.exports = {
  OFFICES,
  KNOWN_CODES,
  resolveEducationOfficeFromNaturalLanguage
};
