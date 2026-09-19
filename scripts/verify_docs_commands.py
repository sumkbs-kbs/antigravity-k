#!/usr/bin/env python
"""NX-10 마감 전 점검 — **문서가 시키는 명령·환경변수·경로가 실제로 존재하는가**.

왜: 이 카드는 문서 오류를 이미 하나 겪었다. `SCOPE.md` 가 `clean-machine-runtime` 을
`BLOCKED_EXTERNAL`(깨끗한 호스트 필요)로 적어 두었지만, 스크립트를 읽어보니 클린룸 재현 검사였고
실제로 통과했다. 즉 **문서를 믿고 다음 사람이 움직이면 시간을 버린다**. 마감 절차(CLOSURE_RUNBOOK)와
운영 가이드(09)가 시키는 것들을 실행 전에 검사한다.

검사하는 것:
  1. 문서에 적힌 CLI 플래그가 그 스크립트의 `--help` 에 실제로 있는가
  2. 문서에 언급된 `AGK_*` 환경변수가 코드에 실제로 있는가(이름 변경·삭제된 변수를 안내하지 않는가)
  3. 문서가 참조하는 로컬 경로가 존재하는가
  4. **커밋 대상 스캔**: dirty/untracked 중 코드 파일에 비밀·자격 증명 패턴이 있는가(커밋 전 점검)

어떤 것도 수정하지 않는다(측정·점검만).

실행(승격 뒤 — 이 파일은 `scripts/` 에 있다):
    python3 scripts/verify_docs_commands.py
승격 전 스테이징 위치에서도 그대로 돈다 — 저장소 루트를 **자기 깊이가 아니라** `pyproject.toml`
로 찾기 때문이다(실측: `parents[4]` 시절 `scripts/` 로 옮기자 죽었고, 승격 게이트가 롤백했다).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """저장소 루트 — **자기 파일 위치의 깊이에 의존하지 않는다**.

    이 파일은 스테이징(`docs/qa/2026-09-16-followup/…`)과 승격 위치(`scripts/`) **양쪽에서**
    실행된다. `parents[4]` 같은 깊이 가정은 한쪽에서만 맞고, 다른 쪽에서는 조용히 엉뚱한
    디렉터리를 저장소로 믿는다 — 실측: `scripts/` 로 이동한 뒤 이 검사기가
    `FileNotFoundError: /Users/…/program/.gitignore` 로 죽었고, 승격 배치의 게이트가
    그것을 잡아 롤백했다(이동 0건).
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("저장소 루트를 찾지 못했다(pyproject.toml 없음)")


REPO = _repo_root()
# 인터프리터: 저장소 venv 가 있으면 그것을(게이트 환경과 같은 도구를 본다), 없으면 지금 돌고 있는
# 파이썬을 쓴다. `.venv` 를 **하드 요구**하면 승격 뒤 다른 트리(리허설 미러·새 클론·CI 샌드박스)에서
# 이 검사기가 `FileNotFoundError` 로 죽는다 — 실제로 리허설 미러에서 그 났다.
_VENV_PY = REPO / ".venv" / "bin" / "python"
PY = str(_VENV_PY) if _VENV_PY.is_file() else sys.executable

DOCS = (
    "docs/qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md",
    "docs/09_OPERATION_GUIDE.md",
    "docs/qa/2026-09-16-followup/nx10/BATCH_FREEZE.md",
    "docs/qa/2026-09-16-followup/nx10/PROMOTION_PLAN.md",
    "docs/qa/2026-09-16-followup/nx02/damaged-conversation-disposal.md",
)

# 문서가 실제로 안내하는 스크립트와 그 플래그.
DOCUMENTED_CLI: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("CLOSURE_RUNBOOK.md §3.2 / ledger §2", "scripts/ga_gate.py", ("--manifest", "--output", "--only", "--merge-into")),
    ("CLOSURE_RUNBOOK.md §0·§4", "scripts/ga_gate_verify.py", ("--report", "--manifest")),
    (
        "docs/09 (CR-01 migration)",
        "scripts/migrate_conversation_storage.py",
        ("--storage-dir", "--apply", "--dry-run", "--verify-only", "--backup-dir", "--report"),
    ),
    ("nx02/damaged-conversation-disposal.md §4", "scripts/run_dashboard_e2e_ambient.py", ()),
    ("docs/09 (SC-1~6 soak)", "scripts/val02_staging.py", ()),
    ("docs/09 (clean-room gate)", "scripts/verify_clean_machine.sh", ("--ref",)),
)

REFERENCED_PATHS: tuple[str, ...] = (
    "scripts/ga_gate.py",
    "scripts/ga_gate_verify.py",
    "scripts/migrate_conversation_storage.py",
    "scripts/val02_staging.py",
    "scripts/run_dashboard_e2e_ambient.py",
    "scripts/verify_clean_machine.sh",
    "scripts/dr_rehearsal.py",
    "scripts/commercial_ga_gates.json",
    "docs/qa/2026-09-16-followup/nx10/run_nx10_soak.sh",
    "docs/qa/2026-09-16-followup/nx10/schedule_nx10_soak.sh",
    "docs/qa/2026-09-16-followup/nx10/run_clean_machine_gate.sh",
    "docs/qa/2026-09-16-followup/nx10/run_freeze_gates.sh",
    "docs/09_OPERATION_GUIDE.md",
    "docs/ga/CR01_CONVERSATION_STORAGE_MIGRATION_RUNBOOK.md",
    "docs/ga/CR02_SESSION_STORAGE_FAILURE_RUNBOOK.md",
    "docs/ga/CR05_KEY_REENTRY_RUNBOOK.md",
    "docs/ga/CR12_SANDBOX_UNAVAILABLE_RUNBOOK.md",
    "docs/runbooks/worktree_orphan_recovery.md",
    "src/antigravity_k/engine/conversation_retention.py",
    "src/antigravity_k/api/sse_revocation.py",
    "src/antigravity_k/engine/summary_memory.py",
    # 2026-09-16 승격본(이 검사기 자신을 포함) — 승격 뒤에는 이 위치가 정본이다.
    # 여기 적어 두면 다음 사람이 `docs/` 스테이징 경로를 다시 안내하는 것을 이 검사기가 잡는다.
    "scripts/verify_docs_commands.py",
    "scripts/collect_soak_result.py",
    "scripts/cue_lexicon_probe.py",
    "docs/qa/2026-09-16-followup/nx10/promote/apply_promotion.sh",
    "docs/qa/2026-09-16-followup/nx10/promote/paths.sh",
    "docs/qa/2026-09-16-followup/nx10/promote/gates.sh",
    "docs/qa/2026-09-16-followup/nx10/run_promote_gates.sh",
    "tests/test_docs_toolchain_contract.py",
    "tests/test_soak_recovery_judge.py",
    "tests/test_cue_lexicon_contract.py",
)

# 커밋 대상에서 훑을 비밀 패턴 (값은 절대 출력하지 않는다 — 파일·줄번호만).
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{12,}")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("bearer_literal", re.compile(r"(?i)authorization\s*[:=]\s*['\"]?bearer\s+[A-Za-z0-9._-]{20,}")),
    (
        "password_assign",
        re.compile(r"(?i)\b(password|passwd|api_key|apikey|secret_key|access_token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    ),
)

# 검사기 자체가 거둔 교훈 두 가지(첫 실행에서 오탐 두 개를 내고 고쳤다):
#  ① 값이 자리표시자(test/dummy/example…)면 비밀이 아니다.
#  ② pydantic 설정은 `env_prefix="AGK_SERVER_"` + 필드 `port` → `AGK_SERVER_PORT` 로 **파생**되므로
#     코드에 그 문자열이 없다고 STALE 이 아니다.
PLACEHOLDER_RE = re.compile(
    r"(?i)^(test|dummy|fake|example|sample|placeholder|changeme|your|xxx|redacted|none|ollama|lm-studio)"
)
ENV_PREFIX_RE = re.compile(r"env_prefix\s*=\s*['\"]([A-Z0-9_]+)['\"]")

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'OK  ' if ok else 'STALE'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def help_text(script: str) -> str:
    if script.endswith(".sh"):
        proc = subprocess.run(["bash", str(REPO / script), "--help"], cwd=REPO, capture_output=True, text=True)
    else:
        proc = subprocess.run([PY, str(REPO / script), "--help"], cwd=REPO, capture_output=True, text=True)
    return proc.stdout + proc.stderr


def main() -> int:
    print("=== 1. 문서가 안내한 CLI 플래그가 실제로 있는가 ===")
    for where, script, flags in DOCUMENTED_CLI:
        if not (REPO / script).is_file():
            check(f"{script} ({where})", False, "스크립트 없음")
            continue
        text = help_text(script)
        missing = [f for f in flags if f not in text]
        check(f"{where} → {script}", not missing, f"없는 플래그: {missing}" if missing else f"{len(flags)}개 확인")

    print("\n=== 2. 문서의 AGK_* 환경변수가 코드에 있는가 ===")
    code_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in list((REPO / "src").rglob("*.py")) + list((REPO / "scripts").glob("*.py"))
    )
    documented: dict[str, set[str]] = {}
    for rel in DOCS:
        doc = REPO / rel
        if not doc.is_file():
            check(f"{rel} 존재", False)
            continue
        for name in re.findall(r"\bAGK_[A-Z0-9_]+\b", doc.read_text(encoding="utf-8")):
            documented.setdefault(name, set()).add(Path(rel).name)
    prefixes = set(ENV_PREFIX_RE.findall(code_text))
    stale_env = []
    derived_env = []
    for name, sources in sorted(documented.items()):
        if name in code_text:
            continue
        derived = next((p for p in prefixes if name.startswith(p) and len(name) > len(p)), None)
        if derived:
            derived_env.append(f"{name} (= {derived} + 필드명 파생)")
            continue
        stale_env.append(name)
        check(f"{name} ({', '.join(sorted(sources))})", False, "코드 어디에도 없음")
    if not stale_env:
        check(
            f"문서에 나온 AGK_* 변수 {len(documented)}개",
            True,
            f"직접 존재 또는 파생 {len(derived_env)}개: {derived_env}",
        )

    print("\n=== 3. 문서가 참조하는 경로가 존재하는가 ===")
    missing_paths = [p for p in REFERENCED_PATHS if not (REPO / p).exists()]
    check(
        f"참조 경로 {len(REFERENCED_PATHS)}개",
        not missing_paths,
        f"없음: {missing_paths}" if missing_paths else "전부 존재",
    )

    print("\n=== 4. 커밋 대상 비밀 스캔 (dirty + untracked, 값은 출력하지 않음) ===")
    # git 작업 트리가 아니면 이 단계는 **성립하지 않는다** — 검사할 대상(dirty/untracked)이 정의되지 않는다.
    # 그래도 조용히 넘기지 않는다: 건너댐을 문장으로 말하고, 본 트리(게이트가 도는 곳)에서는 항상 돈다.
    in_git_tree = (REPO / ".git").exists()
    status: list[str] = []
    if in_git_tree:
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    else:
        print("  [SKIP] git 작업 트리가 아니다(승격 리허설 미러 등) — 스캔 대상이 정의되지 않는다")
    candidates = []
    for line in status:
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ")[-1]
        if not path or path.endswith("/"):
            continue
        candidates.append(path)
    text_exts = {".py", ".ts", ".tsx", ".js", ".json", ".md", ".sh", ".yaml", ".yml", ".toml", ".txt", ""}
    scanned = 0
    hits: list[str] = []
    for rel in candidates:
        p = REPO / rel
        if not p.is_file() or p.suffix not in text_exts:
            continue
        try:
            if p.stat().st_size > 2_000_000:
                continue
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(body):
                quoted = re.findall(r"['\"]([^'\"]+)['\"]", match.group(0))
                if quoted and all(PLACEHOLDER_RE.match(q) or len(q) < 12 for q in quoted):
                    continue  # 테스트 자리표시자 — 비밀이 아니다
                line_no = body[: match.start()].count("\n") + 1
                hits.append(f"{rel}:{line_no} ({label})")
    check(
        f"파일 {scanned}개 스캔" if in_git_tree else "비밀 스캔(건너댐 — git 없음)",
        not hits,
        f"의심 {len(hits)}건: {hits[:8]}" if hits else ("패턴 일치 없음" if in_git_tree else "SKIP"),
    )

    print("\n=== 5. 스테이징 제외 대상 확인 (소유 불명 파일) ===")
    for rel in ("data/auth_hash.bak.pre-0000", "vault_data"):
        exists = (REPO / rel).exists()
        tracked = (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel], cwd=REPO, capture_output=True, text=True
            ).returncode
            == 0
        )
        print(f"  [note] {rel}: exists={exists} tracked={tracked}")
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("vault_data", "data/auth_hash"):
        check(f".gitignore 에 '{pattern}' 규칙", pattern in gitignore)
    # 인증 해시 **백업본**(``.bak.pre-0000``)은 0644 이고 `git add -A` 에 걸린다. 2026-09-16 승격
    # 배치가 `data/auth_hash.bak*` 규칙을 넣어 닫았으므로, 여기서는 **조건을 본다** — 규칙이 없으면
    # WARN 이고, 있으면 종결을 확인한다(문구를 상시 WARN 으로 두면 고쳐도 영원히 경고가 된다).
    bak_present = (REPO / "data" / "auth_hash.bak.pre-0000").exists()
    ignored = subprocess.run(
        ["git", "check-ignore", "data/auth_hash.bak.pre-0000"], cwd=REPO, capture_output=True, text=True
    )
    if not bak_present:
        print("  [note] data/auth_hash.bak.pre-0000 자체가 없다(스캔에서 제외)")
    elif ignored.returncode == 0:
        pattern = next((ln.strip() for ln in ignored.stdout.splitlines() if ".gitignore" in ln), ".gitignore")
        print(f"  [OK  ] data/auth_hash.bak.pre-0000 이 무시된다 — {pattern} (git add -A 안전)")
    else:
        print(
            "  [WARN] data/auth_hash.bak.pre-0000 이 무시되지 않은 채 남아 있다 — "
            "`git add -A` 금지(경로 명시 스테이징) 및 `.gitignore` 에 `data/auth_hash.bak*` 필요."
        )

    print("\n=== 6. 문서 로컬 상대 링크가 실재하는 파일을 가리키는가 ===")
    markdown = [REPO / rel for rel in DOCS] + sorted((REPO / "docs" / "qa" / "2026-09-16-followup").rglob("*.md"))
    broken: list[str] = []
    checked = 0
    for doc in markdown:
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            bare = target.split("#")[0].split(" ")[0]
            if not bare or target.startswith(("http://", "https://", "mailto:", "/", "#")):
                continue  # 절대경로·앵커·외부 링크는 이 검사의 대상이 아니다
            if re.match(r"^[\w./-]+:\d+$", target):
                continue  # file.py:123 형태
            checked += 1
            if not (doc.parent / bare).resolve().exists():
                broken.append(f"{doc.relative_to(REPO)} → {target}")
    check(f"로컬 상대 링크 {checked}개", not broken, f"깨짐 {len(broken)}건: {broken[:6]}" if broken else "전부 실재")

    print(f"\n결과: {'ALL OK' if not FAILURES else f'STALE {len(FAILURES)}건 — ' + ', '.join(FAILURES)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
