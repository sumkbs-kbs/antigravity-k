# Commercial GA final goal review

- **Recommendation:** FAIL
- **Reviewed HEAD:** `8794aaecabf5664a7ee560b104e0115d915aabb7`
- **Recorded RC:** `2ae967ad7c57513de9b6d3f8e1753e1a5be243b9`
- **Review date:** 2026-09-10
- **Mode:** read-only final gate; no product fixes

## Original intent

Ship a commercial-GA release whose blocking checklist is complete and whose 100/100 claim is backed by reproducible evidence from one immutable full commit SHA. The plan specifically requires a clean environment, a real local and cloud provider, persistent Chroma, real MLX or CUDA training, an eight-hour soak, and independent code, security, manual-QA, and release reviews of that same SHA.

## Desired outcome

The current release HEAD should have one evidence chain that identifies `8794aaecabf5664a7ee560b104e0115d915aabb7`, demonstrates every mandatory real-provider/hardware/soak/release gate on that SHA, and contains independent review artifacts sufficient to reproduce the 100/100 and GO conclusions.

## User outcome review

That outcome is not established. Some narrower results are credible: the artifacts show a real Ollama request, persistent Chroma activity, and an MLX training/checkpoint/resume/fuse probe. The GA claim still fails because the cloud-provider requirement has no execution evidence, the only recorded soak lasted 60 seconds, the RC evidence names an older SHA, and the current HEAD contains material production changes after that RC. The current checkout is also dirty (`vault_data` submodule), so it is not itself a clean release state.

## Blockers

### B1 — Current HEAD has no same-SHA final gate

- **violatedCriterion:** `PLAN-RC-01-SAME-SHA` — `docs/11_COMMERCIAL_GA_100_PLAN.md:654-661`; `PLAN-DEFINITION-6` — `docs/11_COMMERCIAL_GA_100_PLAN.md:26`
- **observation:** RC-01 records candidate `2ae967ad7c57513de9b6d3f8e1753e1a5be243b9`, while reviewed HEAD is `8794aaecabf5664a7ee560b104e0115d915aabb7`. `git rev-list --count 2ae967a..HEAD` returns 17. The full range changes 197 files; its scoped product/test/build subset changes 90 files (5,293 insertions, 138 deletions), including API, orchestration, tool, dashboard, dependency, DR, and evaluation code. These are not evidence-only changes. No gate/review artifact identifies the current full SHA.
- **evidencePointer:** `.omo/evidence/commercial-ga-100/RC-01/READINESS_REPORT.md:3-8,29,56-63`; `docs/13_COMMERCIAL_GA_100_PROGRESS.md:1041-1070`; command evidence: `git diff --stat 2ae967ad7c57513de9b6d3f8e1753e1a5be243b9..8794aaecabf5664a7ee560b104e0115d915aabb7 -- src tests scripts dashboard/src dashboard/e2e .github Dockerfile pyproject.toml uv.lock dashboard/package.json dashboard/pnpm-lock.yaml`
- **gapType:** missing required current-SHA evidence, plus direct SHA mismatch

### B2 — Required cloud-provider scenario was not run

- **violatedCriterion:** `VAL-01-AC1` — `docs/11_COMMERCIAL_GA_100_PLAN.md:606-610`; checklist claim `docs/12_COMMERCIAL_GA_100_CHECKLIST.md:373-374`
- **observation:** VAL-01 metadata marks AC-1 passed while explicitly stating that no cloud key was available and a cloud run remains necessary. The machine-readable artifact contains only four Ollama provider scenarios. A local-provider matrix cannot satisfy the explicit “Ollama/local and at least one supported cloud provider” criterion.
- **evidencePointer:** `.omo/evidence/commercial-ga-100/VAL-01/metadata.json:17-20,53-55`; `.omo/evidence/commercial-ga-100/VAL-01/artifact.json:7-53`
- **gapType:** missing required external execution evidence; no cloud failure was observed because the scenario was not run

### B3 — The eight-hour soak criterion was replaced by a 60-second rehearsal

- **violatedCriterion:** `VAL-02-AC4` — `docs/11_COMMERCIAL_GA_100_PLAN.md:624-629`; checklist claim `docs/12_COMMERCIAL_GA_100_CHECKLIST.md:388`
- **observation:** Both the lane artifact and the RC copy record `duration_s: 60`. The independent lane review expressly says the formal 28,800-second soak was not run and accepts the 60-second rehearsal as a proportional proxy. The stated criterion requires the result after eight hours; extrapolation does not meet it.
- **evidencePointer:** `.omo/evidence/commercial-ga-100/VAL-02/staging-report.json:68-71`; `.omo/evidence/commercial-ga-100/RC-01/rc01-val02.json:67-71`; `.omo/evidence/commercial-ga-100/VAL-02/review.md:33-35`; `docs/13_COMMERCIAL_GA_100_PROGRESS.md:969-976`
- **gapType:** actual duration contradicts the claimed eight-hour execution

### B4 — VAL-01 and final independent review coverage are incomplete

- **violatedCriterion:** `PLAN-DEFINITION-6` — `docs/11_COMMERCIAL_GA_100_PLAN.md:26`; `RC-01-REVIEWS` — `docs/11_COMMERCIAL_GA_100_PLAN.md:649-660`; checklist `docs/12_COMMERCIAL_GA_100_CHECKLIST.md:409-412`
- **observation:** VAL-01 metadata remains `IMPLEMENTATION_DONE_REVIEW_PENDING` and names its reviewer as “assignment pending.” No VAL-01 `review.md` is tracked. The RC readiness report summarizes review status but does not provide a dedicated independent candidate-SHA code/security/manual-QA/release review artifact or an evidence matrix binding those reviews to the candidate, much less to current HEAD.
- **evidencePointer:** `.omo/evidence/commercial-ga-100/VAL-01/metadata.json:6-15`; tracked-file check `git ls-files .omo/evidence/commercial-ga-100/VAL-01`; `.omo/evidence/commercial-ga-100/RC-01/READINESS_REPORT.md:56-63`
- **gapType:** exact required review artifacts/coverage missing

### B5 — Release manifest is not a complete reproducible artifact chain

- **violatedCriterion:** `RC-01-MANIFEST` — `docs/11_COMMERCIAL_GA_100_PLAN.md:661`; checklist `docs/12_COMMERCIAL_GA_100_CHECKLIST.md:406`
- **observation:** The report lists wheel and sdist hashes, but neither artifact is present in RC-01. The RC directory has no provenance artifact and no benchmark artifact/link. The staging JSON files do not embed a commit SHA, so they cannot independently prove the report's same-candidate-SHA assertion. Moreover, the RC evidence files were not present in the candidate tree; they were committed after candidate creation.
- **evidencePointer:** `.omo/evidence/commercial-ga-100/RC-01/READINESS_REPORT.md:25-34`; directory inventory `.omo/evidence/commercial-ga-100/RC-01/`; `git show 2ae967ad7c57513de9b6d3f8e1753e1a5be243b9:.omo/evidence/commercial-ga-100/RC-01/rc01-val01.json` returns path-not-in-commit; `.omo/evidence/commercial-ga-100/RC-01/rc01-val01.json:1-3`; `.omo/evidence/commercial-ga-100/RC-01/rc01-val02.json:1-4`
- **gapType:** missing required artifacts and SHA binding; listed hashes alone do not reproduce binaries

### B6 — Chroma delete evidence reports the opposite observable result

- **violatedCriterion:** `VAL-01-AC2` — `docs/11_COMMERCIAL_GA_100_PLAN.md:611`; checklist `docs/12_COMMERCIAL_GA_100_CHECKLIST.md:375`
- **observation:** The `chroma_delete` scenario is marked `ok: true`, yet its observable field is `deleted_file_unsearchable: false`. The staging implementation computes that field as `not results` but never asserts it, so `_record` treats a returned false metric as a successful scenario. This proves the delete acceptance evidence is invalid. It does not by itself prove a VectorStore product defect because the search may have returned semantically similar chunks from another source; the checker must assert absence of the deleted source identity.
- **evidencePointer:** `.omo/evidence/commercial-ga-100/VAL-01/artifact.json:86-94`; `.omo/evidence/commercial-ga-100/RC-01/rc01-val01.json` corresponding `chroma_delete` entry; `scripts/val01_staging.py:195-204`
- **gapType:** actual validation-harness/evidence failure; underlying product behavior remains unproven

## Clean release assessment

The readiness report says gates ran on the older candidate, but it provides summaries rather than raw command logs with exit codes, environment identity, tree-clean state, and SHA binding. For current HEAD, `git status --porcelain=v2` reports modified submodule `vault_data`. This does not prove the old candidate run was dirty; it proves only that the current reviewed checkout cannot serve as clean current-HEAD evidence.

## Direct programming and AI-slop/overfit review

The required direct pass found material maintenance/test-confidence concerns in the post-RC range, but they are not additional blockers unless tied to a GA criterion:

- `src/antigravity_k/engine/optimizers/graphify_builder.py` and `src/antigravity_k/engine/unified_agent.py` exceed the skill's 250 pure-LOC ceiling, and `tests/evals/real_coding/tasks.py` is 571 source lines. This is a maintenance-burden note under the programming/remove-ai-slops criteria.
- The post-RC range adds a large evaluation harness and many tests. This review found no artifact-backed code-review report that explicitly covers the programming perspective plus overfit/slop classes (tautological tests, implementation mirroring, removal-only tests, unnecessary extraction/normalization). That missing perspective is relevant to B4's expressly required current-SHA code review. Counts of passing tests do not close it.
- No production edits or test additions were made during this gate review.

## Checked artifact paths

- `docs/11_COMMERCIAL_GA_100_PLAN.md`
- `docs/12_COMMERCIAL_GA_100_CHECKLIST.md`
- `docs/13_COMMERCIAL_GA_100_PROGRESS.md`
- `.omo/evidence/commercial-ga-100/VAL-01/artifact.json`
- `.omo/evidence/commercial-ga-100/VAL-01/metadata.json`
- `.omo/evidence/commercial-ga-100/VAL-02/staging-report.json`
- `.omo/evidence/commercial-ga-100/VAL-02/metadata.json`
- `.omo/evidence/commercial-ga-100/VAL-02/review.md`
- `.omo/evidence/commercial-ga-100/RC-01/READINESS_REPORT.md`
- `.omo/evidence/commercial-ga-100/RC-01/rc01-val01.json`
- `.omo/evidence/commercial-ga-100/RC-01/rc01-val02.json`
- `.omo/evidence/commercial-ga-100/RC-01/rc01-dr.json`
- `.omo/evidence/commercial-ga-100/RC-01/rc01-rollback.json`
- `.omo/evidence/commercial-ga-100/RC-01/rc01-checksums.txt`
- `.omo/evidence/commercial-ga-100/RC-01/rc01-sbom.json`
- `.omo/evidence/commercial-ga-100/RC-01/image.id`
- `.omo/evidence/commercial-ga-100/RC-01/sbom.sha256`

## Exact evidence gaps to close

1. Re-run the entire applicable release gate on one newly frozen full SHA containing all current product changes; record clean-tree/environment metadata and raw exit-code logs.
2. Run the required cloud provider through streaming, tool, cancel, and error scenarios and attach a secret-free machine-readable result bound to that SHA.
3. Run a real 28,800-second soak and attach start/end timestamps, duration, samples, leak/orphan/lock outcomes, environment, and SHA.
4. Resolve or rerun the Chroma delete scenario so its observable result demonstrates deletion.
5. Produce independent code, security, manual-QA, and release-gate reports naming the same full SHA; the code review must explicitly cover programming and overfit/slop criteria.
6. Preserve or link the wheel, sdist, container provenance, benchmark, SBOM, checksums, and staging reports in a manifest whose artifacts are retrievable and cryptographically bound to that SHA.

## Final determination

`8794aaecabf5664a7ee560b104e0115d915aabb7` is **not supported as a 100/100 commercial-GA release by the supplied evidence**. The findings establish missing or invalid evidence rather than a general claim that the product fails in production. The two direct contradictions are between the claimed gates and their recorded results: the soak lasted 60 seconds rather than eight hours, and the Chroma deletion checker labeled the scenario successful while recording its own deletion metric as false.
