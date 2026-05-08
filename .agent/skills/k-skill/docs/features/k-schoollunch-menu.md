# 학교 급식 식단 조회 가이드

## 이 기능으로 할 수 있는 일

- 시도교육청 이름(자연어) + 학교 이름으로 학교 코드 조회
- 특정 일자 급식 식단(조·중·석) 조회
- 나이스(NEIS) Open API 인증키는 프록시 서버(`KEDU_INFO_KEY`)에서만 관리

## 가장 중요한 규칙

1. 클라이언트는 **`KEDU_INFO_KEY`를 들고 있지 않는다.** `k-skill-proxy`만 upstream `KEY`를 붙인다.
2. 학교 식별은 **하드코딩 금지**. 반드시 **`/v1/neis/school-search` → `/v1/neis/school-meal`** 순서로 조합한다.

## 먼저 필요한 것

- 인터넷 연결
- 프록시 base URL (기본: `https://k-skill-proxy.nomadamas.org`)

## 기본 조회 흐름

### 1) 학교 검색

```bash
curl -fsS --get 'https://k-skill-proxy.nomadamas.org/v1/neis/school-search' \
  --data-urlencode 'educationOffice=서울특별시교육청' \
  --data-urlencode 'schoolName=미래초등학교'
```

응답에 `resolved_education_office`와 `schoolInfo` 블록이 붙는다. `row`에서 `ATPT_OFCDC_SC_CODE`, `SD_SCHUL_CODE`, `SCHUL_NM`, 주소 필드를 확인한다.

### 2) 급식 조회

```bash
curl -fsS --get 'https://k-skill-proxy.nomadamas.org/v1/neis/school-meal' \
  --data-urlencode 'educationOfficeCode=B10' \
  --data-urlencode 'schoolCode=7010123' \
  --data-urlencode 'mealDate=20260410'
```

`educationOfficeCode` / `schoolCode`는 1단계 검색 결과에서 가져온다.

선택: `mealKindCode=1` (조식), `2` (중식), `3` (석식).

## 파라미터 요약

| 단계 | 주요 쿼리 |
| --- | --- |
| school-search | `educationOffice`, `schoolName` (별칭: `office`, `school`, …) |
| school-meal | `educationOfficeCode`, `schoolCode`, `mealDate` (`YYYYMMDD` 또는 `YYYY-MM-DD`) |

## 자주 보는 필드 (급식)

- `MLSV_YMD`: 급식일
- `MMEAL_SC_NM` / `MMEAL_SC_CODE`: 끼니 구분
- `DDISH_NM`: 메뉴(HTML `<br/>` 구분이 많음)
- `CAL_INFO`, `NTR_INFO`: 칼로리·영양 정보(있는 경우)

## 참고 링크

- 나이스 교육정보 개방 포털: `https://open.neis.go.kr/`
- 프록시 구현·엔드포인트 목록: [k-skill 프록시 서버 가이드](k-skill-proxy.md)
