# CR-09 운영 문서 — 오프라인 로컬 표시 자산

> 상용 신뢰성 개선 CR-09(오프라인 로컬 표시 자산, 발견 F05)의 운영 계약.
> 증거: `.omo/evidence/commercial-reliability/CR-09/attempt-001/` · 상태: **REVIEW**(독립 검토 미배정).

## 1. 지켜야 할 계약

- **필수 렌더링 자산은 외부 CDN에 의존하지 않는다.** 폰트·코드 하이라이트 테마·Mermaid·Monaco는 모두
  로컬 번들(또는 시스템 폰트)에서 온다. 오프라인/폐쇄망에서 Chat·Markdown·코드·다이어그램·편집기/diff가 그대로 동작한다.
- **큰 라이브러리는 필요할 때만 로드한다.** Mermaid는 다이어그램을 실제로 그릴 때 동적 import되고,
  Monaco는 편집기 컴포넌트가 mount될 때만(React.lazy) 로드된다. 초기 로드에 붙지 않는다.
- **보안 기본값을 약화하지 않는다.** Mermaid `securityLevel: 'strict'`, Markdown `rehype-sanitize` 스키마,
  악성 라벨 비실행은 CR-09 이후에도 동일하다.
- **실제 cloud 추론의 오프라인 지원을 주장하지 않는다.** 사용자가 선택한 provider 통신은 여전히 네트워크가 필요하다.

## 2. 자산별 출처

| 자산 | 이전 | 지금 |
|---|---|---|
| 폰트 | Google Fonts CSS(Inter/JetBrains Mono/Newsreader) | 시스템 폰트 스택(`--font-*` 토큰), 로컬 설치 폰트가 있으면 사용 |
| 코드 하이라이트 테마 | highlight.js CDN CSS 11.9.0 | `highlight.js@11.11.2` 번들 CSS(`highlight.js/styles/tokyo-night-dark.css`) |
| Mermaid | CDN 동기 script 10.6.1 + `window.mermaid` | `mermaid@10.6.1` 정식 의존성, 지연 동적 import(`src/utils/mermaidRuntime.ts`) |
| Monaco | 로더 기본값 → jsDelivr `monaco-editor@0.55.1/min/vs` | 설치된 `monaco-editor@0.56.0` + 로컬 워커 chunk(`src/utils/monacoRuntime.ts`, `monacoWorkers.ts`) |
| diff2html CSS | CDN CSS | 사용처가 없어 제거 |

## 3. 검증 방법

```bash
# 브라우저 게이트(외부 차단 + cold cache + 로컬 stub 응답)
pnpm --dir dashboard build                      # dashboard_dist 재생성 (릴리스/e2e 전 필수)
pnpm --dir dashboard exec playwright test e2e/tests/cr09-offline-assets.spec.ts --reporter=list

# 정적 증인(HEAD blob 결함 마커 + 현재 트리 해소 마커)
uv run --no-sync python .omo/evidence/commercial-reliability/CR-09/attempt-001/repro/cr09_static_witness.py

# 라이선스/문서 정합성
uv run --no-sync python -m antigravity_k.engine.release_sbom generate --project-root . --release-root ./src/antigravity_k/release
uv run --no-sync python scripts/supply_chain_audit.py --skip-audits
```

e2e는 시나리오마다 `[C09-EVIDENCE] {…}` 한 줄(차단된 외부 URL·콘솔 메시지·실패 응답·폰트·하이라이트 적용)을 남긴다.
`failedResponses`에 앱 원점의 503/405가 보여도 그건 hermetic 개발 백엔드의 응답이며 외부 자산 실패가 아니다.

## 4. 의존성·라이선스 운영

- `dashboard/package.json`은 `mermaid`·`highlight.js`를 **exact 버전**으로 고정한다(번들·SBOM·notice의 동일성을 위해).
- `npm`(package-lock)·`pnpm`(pnpm-lock) 두 lock을 함께 갱신해야 한다: SBOM/notice는 `package-lock.json`을 읽고,
  CI 설치와 빌드는 `pnpm-lock.yaml`을 쓴다.
- 라이선스 메타데이터가 배포 lock/registry에 없는 패키지(현재 `npm:khroma@2.1.0`)는
  `THIRD_PARTY_PROVENANCE.toml`의 `declared_licenses`에 **근거와 함께 사람이 선언**한다. 선언하지 않으면
  license gate는 unknown으로 실패한다(합성 금지). 선언값은 SBOM의 `agk:license-source=provenance-declared`와
  notice 접미사로 드러나며, 상류가 메타데이터를 채우면 선언을 제거하고 lock 판독으로 돌아간다.
- Mermaid 클로저에는 **EPL-2.0(elkjs)** 이 포함된다(prohibited 목록에는 없음). GA 제출 시 라이선스 고지 요건을
  법무/릴리스 검토에서 확인한다.

## 5. 릴리스·배포 주의

- `src/antigravity_k/dashboard_dist`는 커밋되는 빌드 산출물이다. 이 문서 기준 시점에는 **HEAD 상태**로 복원되어 있으므로
  배포 전에 재빌드해야 CR-09 변경이 실제로 서빙된다(CI는 빌드 후 playwright를 돌린다).
- 빌드는 다이어그램 종류별 지연 chunk와 Monaco chunk를 만들어 `assets/`가 커진다. 초기 로드 크기와는 무관하다.
- CSP의 CDN 허용 목록(script/style/font-src)은 아직 남아 있다(허용이지 필수가 아님). 제거하면 CDN 회귀를 브라우저가
  직접 차단하므로 더 강해지지만, 이전 remediation이 동결한 보안 헤더라 보안 lane 승인 후 진행한다.
