# 한국어 글자 수 세기 가이드

## 이 기능으로 할 수 있는 일

- 한국어 텍스트의 글자 수를 `Intl.Segmenter` 기반 grapheme contract로 계산
- 줄 수를 `CRLF`/`LF`/`CR`/`U+2028`/`U+2029` 기준으로 계산
- UTF-8 byte 수를 실제 인코딩 길이로 계산
- `neis` 호환 byte 프로필로 다시 계산
- 텍스트 직접 입력, 파일 입력, stdin 파이프 입력 처리

## 왜 별도 스킬이 필요한가

- 자기소개서/지원서 폼은 1자 차이도 민감하다.
- LLM이 글자 수를 대충 추정하면 같은 입력에서 결과가 흔들릴 수 있다.
- 이 저장소의 목적은 **계산 계약을 고정한 helper** 를 제공하는 것이다.

## 기본 계약

### `default` profile

- characters: `Intl.Segmenter` 기반 Unicode extended grapheme clusters
- bytes: `Buffer.byteLength(text, "utf8")`
- lines:
  - 빈 문자열은 `0`
  - 비어 있지 않으면 줄바꿈 시퀀스 수 + `1`
  - `CRLF` 는 줄바꿈 `1회`

이 계약은 입력을 임의로 trim 하거나 정규화하지 않는다. 공백, 개행, emoji, 조합형 자모도 원문 그대로 센다.

### `neis` profile

- characters: `default` 와 동일
- lines: `default` 와 동일
- bytes:
  - 한글 grapheme `3B`
  - ASCII grapheme `1B`
  - Enter/줄바꿈 시퀀스 `2B`
  - 나머지는 UTF-8 byte fallback

즉 `neis` 는 **byte 계산만** 한국 교육행정 호환 규칙으로 바꾼 compatibility profile이다.

## CLI 사용 예시

### 기본 JSON 출력

```bash
node .agent/skills/k-skill/scripts/korean_character_count.js --text "가나다"
```

예상 출력:

```json
{
  "profile": "default",
  "contract": {
    "characters": "Unicode extended grapheme clusters via Intl.Segmenter",
    "bytes": "Actual UTF-8 encoded byte length",
    "lines": "Empty string => 0 lines; otherwise count CRLF, LF, CR, U+2028, U+2029 as one line break each and add 1"
  },
  "counts": {
    "characters": 3,
    "characters_without_whitespace": 3,
    "code_points": 3,
    "utf16_code_units": 3,
    "lines": 1,
    "bytes": 9,
    "bytes_utf8": 9,
    "bytes_neis": 9
  }
}
```

### 줄바꿈 + 호환 byte 프로필

```bash
node .agent/skills/k-skill/scripts/korean_character_count.js --text $'첫 줄\n둘째 줄🙂' --profile neis --format text
```

예상 출력:

```text
profile: neis
characters: 9
lines: 2
bytes: 23
```

### 파일 입력

```bash
node .agent/skills/k-skill/scripts/korean_character_count.js --file ./essay.txt
```

### stdin 입력

```bash
cat essay.txt | node .agent/skills/k-skill/scripts/korean_character_count.js --profile neis
```

## 구현 메모

- `Intl.Segmenter` 는 `CRLF` 를 grapheme cluster 하나로 다뤄 Windows 줄바꿈에서도 과한 이중 카운트를 피한다.
- UTF-8 byte 수는 문자 종류를 암산하지 않고 실제 인코딩 길이를 쓴다.
- `neis` 는 byte 규칙만 바꾸는 compatibility layer라서, characters/lines 계약은 기본값과 동일하다.
- 제출처가 별도 계약을 문서로 명시하지 않으면 `default` 를 기본값으로 쓴다.

## 라이브 검증 메모

2026-04-08 기준으로 아래 로컬 smoke run을 확인했다.

- `node .agent/skills/k-skill/scripts/korean_character_count.js --text "가\r\n나"` 는 `characters=3`, `lines=2`, `bytes=8`을 반환한다.
- `node .agent/skills/k-skill/scripts/korean_character_count.js --text $'첫 줄\n둘째 줄🙂' --profile neis --format text` 는 `bytes=23`을 반환한다.
- `cat essay.txt | node .agent/skills/k-skill/scripts/korean_character_count.js` 경로도 JSON 출력이 동작한다.

## 참고 표면

- Unicode UAX #29: https://www.unicode.org/reports/tr29/
- WHATWG Encoding Standard: https://encoding.spec.whatwg.org/
- Node `Buffer.byteLength`: https://nodejs.org/api/buffer.html
- 경기도교육청 학교생활기록부 기재요령 PDF: https://www.goe.go.kr/resource/old/BBSMSTR_000000030136/BBS_202302211104253520.pdf
