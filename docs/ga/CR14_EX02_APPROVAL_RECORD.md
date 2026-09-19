# CR-14 EX-02 승인 기록 — 제품·법무·개인정보 (제품 책임자 자체 승인)

- 기록일: **2026-09-15**
- 검토자: **강병석** (제품 / 법무·개인정보 소유자 역할 — **자체 배정**)
- 코드 후보 full SHA: `b6003205365606407cadfd6cbb1c813110beef0f`
- 코드 지문(`docs/`·`.omo/` 제외): `02349a8d06945e438bdc60799ed770a87d6bb67d33d27f09b52008d242536ed6`
- 제어 ADR: [ADR-0003](../adr/0003-ga-product-scope.md)
- 연계: [C14-08 NO-GO](./CR14_C14_08_RELEASE_OWNER_VERDICT.md) · [EX 실행 대장](./CR14_EX_EXECUTION_LEDGER.md)

## 0. 고지 (필수)

1. **겸직** — 출시 책임자·제품 소유자·법무/개인정보 검토자가 동일인(강병석)이다.
2. **제3자 법무 독립 검토 아님** — 이 기록은 외부 변호사·독립 counsel 승인이 **아니다**. `BLOCKED_EXTERNAL`(legal/privacy approver) 행을 해제하지 않는다.
3. **이 기록이 GA GO를 만들지 않음** — C14-08 NO-GO·CR-14 DONE·지원표 Supported 승격·마케팅 Allowed 전환을 허가하지 않는다. EX-01~05 미완·독립 검토 미충족은 그대로다.
4. **독립성 면제(self-assigned)** — 사용자 지시로 본인이 EX-02를 수행한다. 겸직 위험을 출시 책임자가 수용한 제품 해석 기록이며, 법무 외부 게이트를 대체하지 않는다.
5. 처분 라벨 **`PRODUCT_SELF_APPROVAL`** 은 ADR-0003이 이미 허용한 **제품 범위 해석**(target-scope / 단일 운영자 등)에만 쓴다. 레지스터가 legal/privacy/security 외부 승인을 요구하는 마케팅 주장은 **REMAINS BLOCKED**로 유지한다.

## 1. 검토한 산출물

| 산출물 | 경로 | 확인 |
|---|---|---|
| ADR-0003 GA product scope | `docs/adr/0003-ga-product-scope.md` | 읽음 · 범위 기준 |
| Claims / review register | `docs/ga/GA_CLAIMS_AND_REVIEW_REGISTER.md` | 읽음 · 행별 처분 |
| Support matrix | `docs/ga/GA_SUPPORT_MATRIX.md` | 읽음 · **Experimental→Supported 변경 없음** |
| C14-08 release-owner verdict | `docs/ga/CR14_C14_08_RELEASE_OWNER_VERDICT.md` | 읽음 · NO-GO 유지 |
| EX execution ledger | `docs/ga/CR14_EX_EXECUTION_LEDGER.md` | 읽음 · EX-01 IN_PROGRESS |
| Project license | `LICENSE` | 존재 확인 |
| NOTICE | `NOTICE` | 존재 확인 |
| Third-party provenance | `THIRD_PARTY_PROVENANCE.toml` | 존재 확인 |
| Bundled notices | `src/antigravity_k/release/THIRD_PARTY_NOTICES.txt` | 존재 확인 (본문 미첨부) |

고지·라이선스 **파일 존재**만 확인했다. 가용/모호 메타데이터 해소·후보 artifact용 SBOM/NOTICE 재생성·외부 legal sign-off는 **미완**이며 REL-03 / `BLOCKED_EXTERNAL`로 남긴다. 비밀값·토큰·PIN 원문은 기록하지 않는다.

## 2. 처분 어휘 (이 기록)

| 라벨 | 의미 |
|---|---|
| `APPROVED (product-scope only)` / `PRODUCT_SELF_APPROVAL` | ADR-0003이 이미 허용한 범위 문구만. 마케팅 “delivered capability” 아님. |
| `CONDITIONAL` | EX-01 실호출·staging SHA 증거 또는 운영 리허설 필요. EX-01은 대장상 **IN_PROGRESS**. |
| `REJECTED` / `REMAINS BLOCKED` | ADR 제외·Prohibited·또는 `BLOCKED_EXTERNAL`. 이 자체 승인으로 해제 불가. |
| Experimental 유지 | 지원표 분류를 Supported로 **올리지 않음**. |

## 3. Claim-to-gate 처분 (GA_CLAIMS_AND_REVIEW_REGISTER)

| Proposed claim | EX-02 disposition | 근거 |
|---|---|---|
| “Local-first desktop operator experience” | **APPROVED (product-scope only)** · `PRODUCT_SELF_APPROVAL` | ADR-0003 target. “native packaged desktop” 암시 금지. |
| “Self-hosted single tenant” | **APPROVED (product-scope only)** · `PRODUCT_SELF_APPROVAL` (범위 문구) / **CONDITIONAL** (운영·스테이징 증거) | ADR-0003 target. “Supported”·용량 숫자·SaaS 암시 금지. 단일 테넌트 ops 증거는 EX/VAL 대기. |
| “Supported on macOS or Linux” | **CONDITIONAL** / **REMAINS BLOCKED** as support claim | 지원표 Experimental. 후보 SHA staging·install/restart/restore 전 Allowed 아님. EX-01·EX-04 연계. |
| “Supports Windows, CUDA, or native desktop” | **REJECTED** / **REMAINS BLOCKED** (Prohibited) | ADR-0003 명시 제외. 새 ADR+검증 전 마케팅 금지. |
| “Supports Ollama, LM Studio, MLX, or cloud providers” | **CONDITIONAL** (Experimental 평가 문구만) / **REMAINS BLOCKED** as GA support claim | 지원표 전원 Experimental. EX-01 실측·terms/privacy 외부 검토 전 “Supported” 금지. |
| “Private,” “local,” or “your data never leaves your device” | **REJECTED** / **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`: legal) | 제품 자체 승인으로 해제 **불가**. egress·disclosure·legal 승인 필요. |
| “Secure” or “enterprise-ready” | **REJECTED** / **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`: security) | 보안 게이트·동일 후보 SHA 승인 전 금지. |
| “Delete/export your data” (unqualified) | **REJECTED** / **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`: ops rehearsal) | 완전 스토어 delete/export/backup 매트릭스·리허설 전 비한정 주장 금지. |
| “No telemetry” | **REJECTED** / **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`: privacy) | outbound inventory·disclosure·opt-out·승인 전 금지. |
| “SLA,” “uptime,” “RPO,” or “RTO” | **REJECTED** (Prohibited) | ADR·레지스터 Prohibited. |
| “Multi-tenant SaaS” | **REJECTED** (Prohibited) | ADR-0003 제외 · SaaS expansion gate. |
| “Supports N concurrent users” / multi-seat | **REJECTED** / **REMAINS BLOCKED** until verified | GA target = **single-operator only**. VAL-02 다좌석 제품 주장은 release-coordinator 대기. |
| “Approved for regulated / high-sensitivity data” | **REJECTED** (Prohibited / Excluded) | PHI/PCI/classified/children’s/special-category 제외. |
| “PII-ready” / GDPR or PIPA compliance | **REJECTED** / **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`: legal/privacy) | 외부 legal/privacy 아티팩트 전 금지. `PRODUCT_SELF_APPROVAL`로 마케팅 해제 **안 함**. |
| VS Code IDE sync / companion context-sync | **APPROVED (product-scope only)** · `PRODUCT_SELF_APPROVAL` | 문서화된 계약 범위만(동시 1요청·에러 기록·다음 에디터 이벤트 재시도·백그라운드 재연결 타이머·오프라인 큐 **없음**). reconnect/buffer/engine-down 지속 주장은 **Prohibited**. |

## 4. 지원 행렬 · provider 행 (GA_SUPPORT_MATRIX) — 분류 유지

**이 기록은 어떤 행도 Supported로 승격하지 않는다.** Experimental / Unsupported 유지.

### 4.1 Platform / hardware

| Surface | Matrix class (unchanged) | EX-02 disposition |
|---|---|---|
| macOS Apple Silicon + local Ollama | Experimental | **CONDITIONAL** — EX-01/EX-04 증거 전 support claim 금지 |
| macOS Apple Silicon + direct MLX | Experimental | **CONDITIONAL** — 하드웨어·model terms `BLOCKED_EXTERNAL` 유지 |
| Linux x86_64 containerized CPU/local | Experimental | **CONDITIONAL** — clean-host VAL-01 전 support claim 금지 |
| Linux x86_64 NVIDIA CUDA | Unsupported | **REJECTED** |
| Windows | Unsupported | **REJECTED** |
| Native packaged desktop app | Unsupported | **REJECTED** |

### 4.2 Providers / runtimes

| Provider/runtime | Matrix class (unchanged) | EX-02 disposition |
|---|---|---|
| Ollama loopback | Experimental | **CONDITIONAL** — EX-01 실측 진행 중; legal terms `BLOCKED_EXTERNAL` |
| LM Studio local | Experimental | **CONDITIONAL** — EX-01 + legal `BLOCKED_EXTERNAL` |
| Direct MLX | Experimental | **CONDITIONAL** — hardware + legal `BLOCKED_EXTERNAL` |
| OpenRouter | Experimental | **CONDITIONAL** — credentialed staging + legal `BLOCKED_EXTERNAL` |
| NVIDIA NIM | Experimental | **CONDITIONAL** — 동일 |
| OpenAI | Experimental | **CONDITIONAL** — 동일 (자리표시자 키는 미설정 취급; 비밀 미기록) |
| Google Gemini | Experimental | **CONDITIONAL** — 동일 |
| ZAI / Zhipu | Experimental | **CONDITIONAL** — 동일 |
| Unlisted provider/model/accelerator | Unsupported | **REJECTED** |

클라우드 선택 시 프롬프트·첨부·메타데이터가 고객 계정 하 해당 provider로 전송된다. local 라벨은 일반 “private” 주장을 허가하지 않는다.

### 4.3 Concurrent-user / tenancy

| Surface | Matrix / ADR | EX-02 disposition |
|---|---|---|
| Single interactive operator | GA target (not load cert) | **APPROVED (product-scope only)** · `PRODUCT_SELF_APPROVAL` |
| Concurrent multi-user on one instance | Experimental; multi-seat claim blocked | **REMAINS BLOCKED** as marketed capacity / **CONDITIONAL** on release-coordinator |
| Multi-tenant / multi-customer | Unsupported / excluded | **REJECTED** |

## 5. Third-party license / model / provider review register

| Subject | State after EX-02 | Note |
|---|---|---|
| Project license + bundled notices (files exist) | **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`: legal) · files confirmed present | 존재 확인 ≠ legal clearance. REL-03. |
| Python / dashboard deps · SBOM/NOTICE | **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`: legal) | 모호 메타데이터·후보 SBOM 미결 |
| Ollama / MLX / LM Studio runtimes & models | **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`) | EX-01 증거와 병행; legal 아티팩트 별도 |
| OpenRouter / NIM / OpenAI / Gemini / ZAI | **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`) | terms/privacy/DPA 외부 검토 |
| Telemetry / analytics destinations | **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`) | OBS-01 inventory·privacy 승인 |

**제품 해석:** 공지 파일이 리포에 있다. **법무 해석:** 승인되지 않았다. 마케팅·출시 카피에 라이선스/provider “cleared” 문구를 쓰지 않는다.

## 6. Data-sensitivity (ADR-0003) — 제품 범위만

| Class | EX-02 disposition |
|---|---|
| Operator workspace under operator control | **APPROVED (product-scope only)** — 프라이버시 인증 암시 없음 |
| App config / non-secret ops metadata | **APPROVED (product-scope only)** |
| Provider credentials / PINs | Customer-held only; 문서·증거·로그·export 금지 — **REMAINS** security constraint |
| Secrets in prompts/logs/exports | **REJECTED** if found (release blocker) |
| Incidental PII / GDPR·PIPA “ready” | **REMAINS BLOCKED** (`BLOCKED_EXTERNAL`) |
| Regulated / high-sensitivity | **REJECTED** (Excluded) |
| Customer data to selected cloud provider | **CONDITIONAL** on selected-provider disclosure + legal terms review — 일반 private 주장 **REJECTED** |

## 7. 집계

| Disposition bucket | Count (이 기록 기준 major rows) |
|---|---|
| **APPROVED (product-scope only)** / `PRODUCT_SELF_APPROVAL` | **6** — local-first target; self-hosted single-tenant (범위 문구); single-operator; VS Code companion contract; operator workspace (operator control); app config/ops metadata |
| **CONDITIONAL** (EX-01 / staging / ops) | **12** — macOS/Linux support claim; provider “Supports …” claim; 8 provider/runtime Experimental rows; MLX platform; Linux container platform; cloud-data disclosure path (부분) |
| **REJECTED / REMAINS BLOCKED** (Prohibited, Unsupported, or `BLOCKED_EXTERNAL`) | **20+** — Windows/CUDA/native desktop; private/secure/enterprise/no-telemetry/unqualified delete-export; SLA; multi-tenant SaaS; concurrent-seat marketing; regulated data; PII/GDPR-PIPA claims; 전 third-party legal rows; telemetry destinations; multi-tenant tenancy; unlisted providers |

정확한 마케팅 Allowed 전환 수: **0**. Experimental→Supported 전환 수: **0**.

## 8. EX-02 종결 여부

| 질문 | 답 |
|---|---|
| 승인 **기록** 산출물 완료? | **예** — 본 문서. |
| 법무·개인정보 **외부** `BLOCKED_EXTERNAL` 해제? | **아니오**. |
| 지원표 Supported 승격? | **아니오** (의도적으로 편집하지 않음). |
| EX-02를 **완전 종결(DONE)** 로 부를 수 있나? | **아니오 — PARTIAL**. 제품 범위 `PRODUCT_SELF_APPROVAL`과 Prohibited/Blocked 고지는 완료했으나, 레지스터가 요구하는 제3자 legal/privacy 승인과 EX-01 의존 CONDITIONAL 행이 열려 있어 “모델/라이선스/개인정보·지원 승인” 목표 전체는 미달. |
| GA GO / CR-14 DONE? | **아니오**. C14-08 NO-GO 유지. |

재검토·만료: EX-01 실측 아티팩트 첨부 시 CONDITIONAL 재평가; 외부 counsel 아티팩트 없으면 legal 행은 계속 BLOCKED. 후보 SHA 변경 시 본 기록은 무효·재발행.

## 9. 서명

- 제품·법무·개인정보 소유자(겸직 · 자체 배정 · 독립성 면제): **강병석**
- 일자: **2026-09-15**
- 처분 요약: product-scope **APPROVED** 소수 · 다수 **CONDITIONAL** / **REMAINS BLOCKED** · **GA GO 아님**
