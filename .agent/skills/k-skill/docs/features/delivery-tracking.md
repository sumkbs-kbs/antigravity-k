# 택배 배송조회 가이드

## 이 기능으로 할 수 있는 일

- CJ대한통운 송장 조회
- 우체국 송장 조회
- 현재 상태와 최근 이벤트 요약
- 같은 스킬 안에서 택배사별 carrier adapter 규칙 유지

## 먼저 필요한 것

- 인터넷 연결
- `python3`
- `curl`

별도 npm/Python 패키지 설치 없이 공식 endpoint 기준으로 바로 조회한다.

## 입력값

- 택배사: `cj` 또는 `epost`
- 송장번호
  - CJ대한통운: 숫자 10자리 또는 12자리
  - 우체국: 숫자 13자리

## 기본 흐름

1. 택배사별 validator로 자리수를 먼저 확인한다.
2. CJ는 공식 페이지에서 `_csrf` 를 읽은 뒤 `tracking-detail` JSON endpoint 로 조회한다.
3. 우체국은 `sid1` 을 `trace.RetrieveDomRigiTraceList.comm` 에 POST해서 HTML 결과를 받는다.
4. 결과를 공통 포맷으로 정리한다.
5. 새 택배사를 붙일 때는 같은 carrier adapter 필드(validator / entrypoint / transport / parser / status map / retry policy)를 채운다.

## CJ대한통운 예시

- 진입 페이지: `https://www.cjlogistics.com/ko/tool/parcel/tracking`
- 상세 endpoint: `https://www.cjlogistics.com/ko/tool/parcel/tracking-detail`
- 파라미터: `_csrf`, `paramInvcNo`

```bash
tmp_body="$(mktemp)"
tmp_cookie="$(mktemp)"
tmp_json="$(mktemp)"
invoice="1234567890"

curl -sS -L -c "$tmp_cookie" \
  "https://www.cjlogistics.com/ko/tool/parcel/tracking" \
  -o "$tmp_body"

csrf="$(python3 - <<'PY' "$tmp_body"
import re
import sys
text = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
print(re.search(r'name="_csrf" value="([^"]+)"', text).group(1))
PY
)"

curl -sS -L -b "$tmp_cookie" \
  -H "Content-Type: application/x-www-form-urlencoded; charset=UTF-8" \
  --data-urlencode "_csrf=$csrf" \
  --data-urlencode "paramInvcNo=$invoice" \
  "https://www.cjlogistics.com/ko/tool/parcel/tracking-detail" \
  -o "$tmp_json"

python3 - <<'PY' "$tmp_json"
import json
import sys

status_map = {
    "11": "상품인수",
    "21": "상품이동중",
    "41": "상품이동중",
    "42": "배송지도착",
    "44": "상품이동중",
    "82": "배송출발",
    "91": "배달완료",
}

payload = json.load(open(sys.argv[1], encoding="utf-8"))
events = payload["parcelDetailResultMap"]["resultList"]
if not events:
    raise SystemExit("조회 결과가 없습니다.")

latest = events[-1]
normalized_events = [
    {
        "timestamp": event.get("dTime"),
        "location": event.get("regBranNm"),
        "status_code": event.get("crgSt"),
        "status": status_map.get(event.get("crgSt"), event.get("scanNm") or "알수없음"),
    }
    for event in events
]
print(json.dumps({
    "carrier": "cj",
    "invoice": payload["parcelDetailResultMap"]["paramInvcNo"],
    "status_code": latest.get("crgSt"),
    "status": status_map.get(latest.get("crgSt"), latest.get("scanNm") or "알수없음"),
    "timestamp": latest.get("dTime"),
    "location": latest.get("regBranNm"),
    "event_count": len(events),
    "recent_events": normalized_events[-min(3, len(normalized_events)):],
}, ensure_ascii=False, indent=2))
PY

rm -f "$tmp_body" "$tmp_cookie" "$tmp_json"
```

### CJ 공개 출력 예시

아래 값은 2026-03-27 기준 live smoke test(`1234567890`)에서 확인한 정규화 결과다.

```json
{
  "carrier": "cj",
  "invoice": "1234567890",
  "status_code": "91",
  "status": "배달완료",
  "timestamp": "2026-03-21 12:22:13",
  "location": "경기광주오포",
  "event_count": 3,
  "recent_events": [
    {
      "timestamp": "2026-03-10 03:01:45",
      "location": "청원HUB",
      "status_code": "44",
      "status": "상품이동중"
    },
    {
      "timestamp": "2026-03-21 10:53:19",
      "location": "경기광주오포",
      "status_code": "82",
      "status": "배송출발"
    },
    {
      "timestamp": "2026-03-21 12:22:13",
      "location": "경기광주오포",
      "status_code": "91",
      "status": "배달완료"
    }
  ]
}
```

CJ는 JSON 응답이므로 `parcelDetailResultMap.resultList` 를 기준으로 상태를 읽는 편이 가장 안정적이다. 문서 예시는 공통 결과 스키마(`carrier`, `invoice`, `status`, `timestamp`, `location`, `event_count`, `recent_events`, 선택적 `status_code`)만 남기고, 담당자 이름이나 휴대폰 번호가 포함될 수 있는 `crgNm` 원문은 그대로 출력하지 않는다.

## 우체국 예시

- 진입 페이지: `https://service.epost.go.kr/trace.RetrieveRegiPrclDeliv.postal?sid1=`
- 조회 endpoint: `https://service.epost.go.kr/trace.RetrieveDomRigiTraceList.comm`
- 파라미터: `sid1`

```bash
tmp_html="$(mktemp)"
python3 - <<'PY' "$tmp_html"
import html
import json
import re
import subprocess
import sys

invoice = "1234567890123"
output_path = sys.argv[1]

subprocess.run(
    [
        "curl",
        "--http1.1",
        "--tls-max",
        "1.2",
        "--silent",
        "--show-error",
        "--location",
        "--retry",
        "3",
        "--retry-all-errors",
        "--retry-delay",
        "1",
        "--max-time",
        "30",
        "-o",
        output_path,
        "-d",
        f"sid1={invoice}",
        "https://service.epost.go.kr/trace.RetrieveDomRigiTraceList.comm",
    ],
    check=True,
)

page = open(output_path, encoding="utf-8", errors="ignore").read()
summary = re.search(
    r"<th scope=\"row\">(?P<tracking>[^<]+)</th>.*?"
    r"<td>(?P<sender>.*?)</td>.*?"
    r"<td>(?P<receiver>.*?)</td>.*?"
    r"<td>(?P<delivered_to>.*?)</td>.*?"
    r"<td>(?P<kind>.*?)</td>.*?"
    r"<td>(?P<result>.*?)</td>",
    page,
    re.S,
)
if not summary:
    raise SystemExit("기본정보 테이블을 찾지 못했습니다.")

def clean(raw: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())

def clean_location(raw: str) -> str:
    text = clean(raw)
    return re.sub(r"\s*(TEL\s*:?\s*)?\d{2,4}[.\-]\d{3,4}[.\-]\d{4}", "", text).strip()

events = re.findall(
    r"<tr>\s*<td>(\d{4}\.\d{2}\.\d{2})</td>\s*"
    r"<td>(\d{2}:\d{2})</td>\s*"
    r"<td>(.*?)</td>\s*"
    r"<td>\s*<span class=\"evtnm\">(.*?)</span>(.*?)</td>\s*</tr>",
    page,
    re.S,
)

normalized_events = [
    {
        "timestamp": f"{day} {time_}",
        "location": clean_location(location),
        "status": clean(status),
    }
    for day, time_, location, status, _detail in events
]

latest_event = normalized_events[-1] if normalized_events else None

print(json.dumps({
    "carrier": "epost",
    "invoice": clean(summary.group("tracking")),
    "status": clean(summary.group("result")),
    "timestamp": latest_event["timestamp"] if latest_event else None,
    "location": latest_event["location"] if latest_event else None,
    "event_count": len(normalized_events),
    "recent_events": normalized_events[-min(3, len(normalized_events)):],
}, ensure_ascii=False, indent=2))
PY
rm -f "$tmp_html"
```

### 우체국 공개 출력 예시

아래 값은 2026-03-27 기준 live smoke test(`1234567890123`)에서 확인한 정규화 결과다.

```json
{
  "carrier": "epost",
  "invoice": "1234567890123",
  "status": "배달완료",
  "timestamp": "2025.12.04 15:13",
  "location": "제주우편집중국",
  "event_count": 2,
  "recent_events": [
    {
      "timestamp": "2025.12.04 15:13",
      "location": "제주우편집중국",
      "status": "배달준비"
    },
    {
      "timestamp": "2025.12.04 15:13",
      "location": "제주우편집중국",
      "status": "배달완료"
    }
  ]
}
```

우체국은 HTML 응답이라 기본정보 `table_col` 과 상세 `processTable` 을 파싱해야 한다. 문서 예시는 CJ와 같은 공통 결과 스키마(`carrier`, `invoice`, `status`, `timestamp`, `location`, `event_count`, `recent_events`)만 남기고, 이벤트 location에 섞일 수 있는 `TEL` 번호 조각도 제거한 뒤 수령인/상세 메모 원문은 그대로 출력하지 않는다.

## 결과 정리 기준

### 공통 결과 스키마

- `carrier`: 택배사 식별자 (`cj` 또는 `epost`)
- `invoice`: 정규화된 송장번호
- `status`: 현재 배송 상태
- `timestamp`: 마지막 이벤트 시각
- `location`: 마지막 이벤트 위치
- `event_count`: 전체 이벤트 수
- `recent_events`: 최근 최대 3개 이벤트 목록
- `status_code`: 필요할 때만 남기는 원본 상태 코드 (현재는 CJ 예시에서만 사용)

## 확장 규칙

다른 택배사를 붙일 때는 새 carrier adapter에 아래만 먼저 정의한다.

- validator
- official entrypoint
- transport(JSON / HTML / CLI)
- parser
- status map
- retry policy

## 주의할 점

- CJ는 `_csrf` 없이 바로 `tracking-detail` 만 호출하지 않는다.
- 우체국은 `curl --http1.1 --tls-max 1.2` 경로를 기본으로 유지한다.
- 우체국은 JSON이 아니라 HTML 응답이므로 regex/HTML 정리에 대비해야 한다.
- 비공식 통합 배송조회 서비스로 자동 우회하지 않는다.
