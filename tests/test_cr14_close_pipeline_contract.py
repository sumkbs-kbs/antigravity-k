"""CR-14 — **마감이 사람 없이도 돈다**: 파이프라인이 절차를 부르고, 릴리스가 그것에 막힌다(R-11).

왜 이 계약이 필요한가
=====================
attempt-016~018 이 만든 두 장치 — 마감 검사(`scripts/verify_attempt_close.py`)와 마감 절차
(`scripts/run_attempt_close.py`) — 는 "선언한 초록의 출처"를 확인한다. 그런데 **사람이 돌려야만**
작동했다. attempt-016 은 그 사실을 R-10 으로, attempt-017~018 은 R-11 로 남겼다:
"절차는 사람이 시작해야 한다 — CI/릴리스 파이프라인에 연결하지 않으면 '돌리지 않음'을 기계가
막지 못한다."

계약은 **돌았을 때만** 문다. 그래서 마지막 구멍은 계약 **안이 아니라 밖**에 있었다: 어떤 계약도
"파이프라인이 실제로 이 절차를 부르는가"를 묻지 않았다. 이 파일이 그 바깥을 잡는다.

  C14-R11-1  파이프라인이 **마감 절차를 부른다**(게이트 목록은 매니페스트 소유 — 여기 옮겨 적지 않는다)
  C14-R11-2  그 워크플로는 **부를 수 있고(reusable) 스스로도 돈다(schedule)** — "사람이 시작해야 한다"의 종료
  C14-R11-3  릴리스의 publish job 들은 **그 job 을 `needs` 로 갖는다**(검증 없이는 출하되지 않는다)
  C14-R11-4  릴리스는 그 워크플로를 **부르기만 한다**(스텝을 복제하지 않는다 — 갈라지면 F-18/F-24/F-27)
  C14-R11-5  시도 이름·아티팩트 경로가 **소유자의 규칙**(`REPORT_GLOB`·`_artifacts_output`)과 맞는다
  C14-R11-6  전체 이력을 체크아웃한다(`fetch-depth: 0`) · `continue-on-error` 로 실패를 삼키지 않는다

번호는 R-11 의 조항이다 — F 번호는 **결함**에 붙는 번호이고, 이 계약은 결함이 아니라 한계의
폐쇄를 고정한다(attempt-019).

이 파일이 검사하지 **않는** 것: GitHub 러너에서 21개 게이트가 전부 통과하는지(그것은 러너가
소유한다 — 이 저장소의 로컬 실측은 `attempt-0NN/gate-report.json` 이 소유한다). 여기서 고정하는
것은 **배선**이다: 기계가 부르는가, 막히는가, 그리고 그 배선이 조용히 풀릴 수 없는가.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
_GA_CLOSE_WORKFLOW = _WORKFLOW_DIR / "ga-close.yml"
_RELEASE_WORKFLOW = _WORKFLOW_DIR / "release.yml"
_PROCEDURE_SCRIPT = REPO_ROOT / "scripts" / "run_attempt_close.py"
_CLOSER_SCRIPT = REPO_ROOT / "scripts" / "verify_attempt_close.py"
_MANIFEST = REPO_ROOT / "scripts" / "commercial_ga_gates.json"

# 릴리스가 **부르는** 워크플로의 정본 경로 — 복제가 아니라 부름이어야 한다(C14-R11-4).
_GA_CLOSE_REFERENCE = "./.github/workflows/ga-close.yml"
# 출하 동작을 하는 액션 — 이 액션을 쓰는 job 이 "publish job" 이다(이름이 아니라 동작으로 찾는다).
_PUBLISH_ACTIONS = ("pypa/gh-action-pypi-publish", "softprops/action-gh-release")
# reusable workflow 를 **부르는** job 에서 GitHub 이 허용하는 키 — 문서가 소유한다
# (`Reusing workflow configurations` → "Supported keywords for jobs that call a reusable workflow").
# 여기서 복제하는 것이 아니라 **GitHub 의 규칙을 인용**한다: 배선이 스키마 오류로 조용히 죽으면
# "검증이 있다"는 주장만 남고 검증은 없다.
_SUPPORTED_CALLER_KEYS = frozenset(
    {"name", "uses", "with", "secrets", "strategy", "needs", "if", "concurrency", "permissions", "cache-mode"}
)
# 실패를 삼키는 키 — 마감 경로에 있으면 배선이 있어도 판정이 없다.
_SWALLOW_KEYS = ("continue-on-error",)


def _load_module(name: str, path: Path) -> ModuleType:
    """스크립트를 모듈로 부른다. `exec_module` 전에 `sys.modules` 에 등록해야 dataclass 가 산다."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"모듈로 부를 수 없다: {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_CLOSER = _load_module("cr14_close_pipeline_closer", _CLOSER_SCRIPT)
_PROCEDURE = _load_module("cr14_close_pipeline_procedure", _PROCEDURE_SCRIPT)


def report_glob() -> str:
    """보고서 발견 글로브 — **소유자**(마감 검사)의 상수를 읽는다(복제하지 않는다)."""
    return cast("str", getattr(_CLOSER, "REPORT_GLOB"))


def attempt_prefix() -> str:
    """글로브가 요구하는 디렉터리 접두사 — `<접두사>*<보고서 파일>` 모양에서 읽는다."""
    prefix, star, suffix = report_glob().partition("*")
    assert star and prefix and suffix == "/gate-report.json", (
        f"글로브 모양이 예상과 다르다(시도 디렉터리 */보고서 파일): {report_glob()}"
    )
    return prefix


def load_workflow(path: Path) -> dict[str, Any]:
    """워크플로 YAML 을 읽는다. `on:` 은 YAML 1.1 에서 **불리언 True** 로 파싱된다 — 아래 헬퍼가 흡수한다."""
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"워크플로가 매핑이 아니다: {path}"
    return cast("dict[str, Any]", parsed)


def triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    """`on:` 블록. PyYAML 은 `on` 을 `True` 로 읽으므로 두 키를 모두 본다."""
    for key in (True, "on"):
        if key in workflow:
            value = workflow[key]
            return cast("dict[str, Any]", value) if isinstance(value, dict) else {}
    return {}


def jobs(workflow: dict[str, Any]) -> dict[str, Any]:
    return cast("dict[str, Any]", workflow.get("jobs") or {})


def run_commands(workflow: dict[str, Any]) -> list[str]:
    """모든 job 의 `run` 문자열 — 배선이 아니라 **무엇을 실행하는가**를 본다."""
    commands: list[str] = []
    for job in jobs(workflow).values():
        for step in cast("Sequence[dict[str, Any]]", (job or {}).get("steps") or []):
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                commands.append(step["run"])
    return commands


def close_invocations(workflow: dict[str, Any]) -> list[str]:
    """마감 **절차**를 부르는 `run` 들 — 정본 스크립트 이름으로 찾는다."""
    needle = _PROCEDURE_SCRIPT.name
    return [command for command in run_commands(workflow) if needle in command]


def manifest_gate_ids() -> list[str]:
    """게이트 id — **매니페스트**가 소유한다. 워크플로가 이걸 옮겨 적으면 갈라진다(C14-R11-1)."""
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    return [str(gate["id"]) for gate in cast("Sequence[dict[str, Any]]", payload["gates"])]


def job_needs(job: dict[str, Any]) -> list[str]:
    raw = job.get("needs") or []
    if isinstance(raw, str):
        return [raw]
    return [str(item) for item in raw]


def transitive_needs(workflow: dict[str, Any], job_id: str) -> set[str]:
    """`needs` 를 따라 올라간 job id 집합(자기 자신은 제외)."""
    seen: set[str] = set()
    stack = [job_id]
    while stack:
        current = stack.pop()
        for dependency in job_needs(cast("dict[str, Any]", jobs(workflow).get(current) or {})):
            if dependency not in seen:
                seen.add(dependency)
                stack.append(dependency)
    return seen


def publish_job_ids(workflow: dict[str, Any]) -> list[str]:
    """출하 액션을 쓰는 job — 이름이 아니라 **동작**으로 찾는다."""
    found: list[str] = []
    for job_id, job in jobs(workflow).items():
        blob = json.dumps(job, ensure_ascii=False)
        if any(action in blob for action in _PUBLISH_ACTIONS):
            found.append(str(job_id))
    return sorted(found)


def close_producer_job_ids(workflow: dict[str, Any]) -> list[str]:
    """마감 워크플로를 **부르는** job 들(C14-R11-4)."""
    return sorted(
        str(job_id)
        for job_id, job in jobs(workflow).items()
        if _GA_CLOSE_REFERENCE in str((job or {}).get("uses") or "")
    )


# ---------------------------------------------------------------------------
# 규칙 — 각 함수가 조항 하나를 소유한다(이빨이 그 함수를 직접 두드릴 수 있게)
# ---------------------------------------------------------------------------


def procedure_wiring_violations(workflow: dict[str, Any], gate_ids: Sequence[str]) -> list[str]:
    """C14-R11-1 — 마감 절차를 부르고, 게이트 목록을 옮겨 적지 않는다."""
    violations: list[str] = []
    invocations = close_invocations(workflow)
    if not invocations:
        violations.append("마감 절차를 부르는 `run` 이 없다 — 파이프라인이 절차를 돌리지 않는다")
    for command in invocations:
        if "--stage all" not in command:
            violations.append(f"마감 절차를 `--stage all` 로 부르지 않는다(배치 하나만 돈다): {command!r}")
    text = "\n".join(run_commands(workflow)) + "\n" + json.dumps(workflow, ensure_ascii=False)
    duplicated = sorted(gate_id for gate_id in gate_ids if gate_id in text)
    if duplicated:
        violations.append(f"게이트 목록을 옮겨 적었다(소유자는 매니페스트다): {duplicated}")
    return violations


def self_run_violations(workflow: dict[str, Any]) -> list[str]:
    """C14-R11-2 — 부를 수 있고(reusable), 스스로도 돈다(schedule 또는 push)."""
    declared = triggers(workflow)
    violations: list[str] = []
    if "workflow_call" not in declared:
        violations.append("`workflow_call` 이 없다 — 릴리스가 선행 조건으로 부를 수 없다")
    if not {"schedule", "push"} & set(declared):
        violations.append("`schedule`/`push` 가 없다 — 사람이 시작하지 않으면 영원히 돌지 않는다(R-11)")
    return violations


def publish_gate_violations(workflow: dict[str, Any]) -> list[str]:
    """C14-R11-3 — publish job 이 마감 job 없이는 시작하지 않는다."""
    producers = close_producer_job_ids(workflow)
    if not producers:
        return ["publish 파이프라인에 마감 워크플로를 부르는 job 이 없다 — 검증 없이 출하된다"]
    violations: list[str] = []
    for job_id in publish_job_ids(workflow):
        if not (set(producers) & transitive_needs(workflow, job_id)):
            violations.append(f"{job_id}: `needs` 사슬에 마감 job 이 없다 — 검증 없이 출하된다")
    return violations


def caller_violations(workflow: dict[str, Any]) -> list[str]:
    """C14-R11-4 — 부르기만 한다(스텝 복제 금지)."""
    violations: list[str] = []
    for job_id in close_producer_job_ids(workflow):
        job = cast("dict[str, Any]", jobs(workflow)[job_id])
        if job.get("steps"):
            violations.append(f"{job_id}: 마감 워크플로를 부르면서 스텝을 함께 갖는다(복제의 시작)")
    return violations


def caller_shape_violations(workflow: dict[str, Any]) -> list[str]:
    """부르는 job 이 GitHub 의 스키마를 지키는가 — 허용 키 밖의 키(예: `runs-on`)는 실행 전에 거부된다."""
    violations: list[str] = []
    for job_id in close_producer_job_ids(workflow):
        job = cast("dict[str, Any]", jobs(workflow)[job_id])
        unsupported = sorted(set(job) - _SUPPORTED_CALLER_KEYS)
        if unsupported:
            violations.append(
                f"{job_id}: reusable workflow 를 부르는 job 에 쓸 수 없는 키다(GitHub 이 거부한다): {unsupported}"
            )
    return violations


def attempt_name_resolution_violations(workflow: dict[str, Any]) -> list[str]:
    """C14-R11-5 — 시도 이름이 **소유자의 글로브**에 맞고, 아티팩트 경로가 소유자의 규칙과 같다."""
    violations: list[str] = []
    prefix = attempt_prefix()
    workflow_env = cast("dict[str, Any]", workflow.get("env") or {})
    pattern = re.compile(r"--attempt\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
    for command in close_invocations(workflow):
        match = pattern.search(command)
        if match is None:
            violations.append(f"시도 이름을 넘기지 않는다: {command!r}")
            continue
        token = next(group for group in match.groups() if group)
        name = token
        shell_var = re.fullmatch(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", token)
        if shell_var is not None:
            resolved = workflow_env.get(shell_var.group(1))
            if not isinstance(resolved, str):
                violations.append(f"시도 이름이 변수인데 워크플로 env 에 값이 없다: {token}")
                continue
            name = resolved
        if not name.startswith(prefix):
            violations.append(
                f"시도 이름 {name!r} 이 보고서 글로브 {report_glob()!r} 에 맞지 않는다 — "
                "마감 검사가 '측정한 보고서가 없다'로 실패한다"
            )
        expected_artifact = cast("Callable[[str, Path], str]", getattr(_PROCEDURE, "_artifacts_output"))(
            name, REPO_ROOT
        )
        uploaded = json.dumps(workflow, ensure_ascii=False)
        if Path(expected_artifact).name not in uploaded:
            violations.append(
                f"아티팩트 경로가 소유자의 규칙과 다르다 — 올려야 할 파일: {Path(expected_artifact).name}"
            )
    return violations


def hygiene_violations(workflow: dict[str, Any]) -> list[str]:
    """C14-R11-6 — 전체 이력 체크아웃 · 실패를 삼키지 않는다."""
    violations: list[str] = []
    steps = [
        step
        for job in jobs(workflow).values()
        for step in cast("Sequence[dict[str, Any]]", (job or {}).get("steps") or [])
    ]
    checkouts = [step for step in steps if "actions/checkout" in str(step.get("uses") or "")]
    if not checkouts:
        violations.append("체크아웃 스텝이 없다")
    for step in checkouts:
        depth = (cast("dict[str, Any]", step.get("with") or {})).get("fetch-depth")
        if str(depth) not in {"0", "'0'", '"0"'}:
            violations.append(
                "체크아웃이 `fetch-depth: 0` 이 아니다 — 후보 커밋 객체가 없으면 "
                "`tree_fingerprint_of_commit` 이 잴 것이 없고 울타리 조항이 무력해진다"
            )
    for step in steps:
        for key in _SWALLOW_KEYS:
            if step.get(key) is True:
                violations.append(f"`{key}: true` 가 마감 경로에 있다 — 실패를 삼키면 판정이 없다: {step.get('name')}")
    return violations


# ---------------------------------------------------------------------------
# 실제 파일에 대한 조항
# ---------------------------------------------------------------------------


def test_r11_1_pipeline_runs_the_close_procedure() -> None:
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)
    violations = procedure_wiring_violations(workflow, manifest_gate_ids())
    assert not violations, " / ".join(violations)


def test_r11_2_close_workflow_is_callable_and_runs_on_its_own() -> None:
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)
    violations = self_run_violations(workflow)
    assert not violations, " / ".join(violations)


def test_r11_3_release_publish_is_blocked_without_the_close_job() -> None:
    workflow = load_workflow(_RELEASE_WORKFLOW)
    assert publish_job_ids(workflow), "전제 불성립 — 릴리스에서 publish job 을 찾지 못했다(동작으로 찾는다)"
    violations = publish_gate_violations(workflow)
    assert not violations, " / ".join(violations)


def test_r11_4_release_calls_the_owner_workflow_instead_of_copying_it() -> None:
    workflow = load_workflow(_RELEASE_WORKFLOW)
    assert close_producer_job_ids(workflow), f"릴리스가 {_GA_CLOSE_REFERENCE} 를 부르지 않는다"
    violations = caller_violations(workflow)
    assert not violations, " / ".join(violations)


def test_r11_5_attempt_name_and_artifact_path_match_the_owner() -> None:
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)
    violations = attempt_name_resolution_violations(workflow)
    assert not violations, " / ".join(violations)


def test_r11_4b_caller_job_uses_only_supported_keys() -> None:
    violations = caller_shape_violations(load_workflow(_RELEASE_WORKFLOW))
    assert not violations, " / ".join(violations)


def test_r11_6_full_history_and_no_swallowed_failures() -> None:
    violations = hygiene_violations(load_workflow(_GA_CLOSE_WORKFLOW))
    assert not violations, " / ".join(violations)


def test_r11_6_release_close_path_does_not_swallow_failures() -> None:
    """릴리스가 부르는 job 자체에도 실패 삼키기가 없어야 한다(호출지점 쪽 이빨)."""
    workflow = load_workflow(_RELEASE_WORKFLOW)
    for job_id in close_producer_job_ids(workflow):
        job = cast("dict[str, Any]", jobs(workflow)[job_id])
        assert job.get("continue-on-error") is not True, f"{job_id}: 실패를 삼킨다"
        conditional = str(job.get("if") or "")
        assert "always()" not in conditional, f"{job_id}: `always()` 로 실패를 우회한다: {conditional!r}"


# ---------------------------------------------------------------------------
# 이빨 — 배선을 **실제로** 풀어 보고 각 조항이 무는지 확인한다
# ---------------------------------------------------------------------------


def _mutated(workflow: dict[str, Any], mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    clone = copy.deepcopy(workflow)
    mutate(clone)
    return clone


def test_teeth_removing_publish_dependency_is_caught() -> None:
    """F-27 의 병(배선이 있는데 안 묻는다)을 파이프라인 수준에서 재현한다."""
    workflow = _mutated(load_workflow(_RELEASE_WORKFLOW), lambda w: None)
    producers = close_producer_job_ids(workflow)
    assert producers, "전제 불성립 — 마감 job 을 찾지 못했다"
    target = publish_job_ids(workflow)[0]

    def drop_needs(clone: dict[str, Any]) -> None:
        clone["jobs"][target]["needs"] = ["build"]

    planted = _mutated(workflow, drop_needs)
    violations = publish_gate_violations(planted)
    assert violations and target in violations[0], f"이빨 없음 — 의존을 끊었는데 통과했다: {violations}"
    assert publish_gate_violations(workflow) == [], "기준선이 깨졌다"


def test_teeth_indirect_dependency_is_not_enough_without_the_producer() -> None:
    """`needs` 사슬에 **다른** job 만 있으면 통과하면 안 된다(사슬을 봐야 한다)."""
    workflow = load_workflow(_RELEASE_WORKFLOW)
    target = publish_job_ids(workflow)[0]

    def reroute(clone: dict[str, Any]) -> None:
        clone["jobs"][target]["needs"] = ["dry-run-report"]

    assert publish_gate_violations(_mutated(workflow, reroute)), "이빨 없음 — 다른 job 만 의존해도 통과했다"


def test_teeth_dispatch_only_workflow_is_caught() -> None:
    """ "사람이 시작해야 한다"(R-11 그 자체)를 심는다."""
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)
    assert "schedule" in triggers(workflow) or "push" in triggers(workflow), "전제 불성립 — 스스로 도는 trigger 가 없다"

    def to_dispatch_only(clone: dict[str, Any]) -> None:
        # PyYAML 이 `on:` 을 불리언 True 로 읽는다 — 그 자리를 수동 실행 전용으로 바꾼다.
        on_key: Any = True
        clone[on_key] = {"workflow_dispatch": {}}
        clone.pop("on", None)

    violations = self_run_violations(_mutated(workflow, to_dispatch_only))
    assert any("schedule" in violation or "push" in violation for violation in violations), f"이빨 없음: {violations}"


def test_teeth_declaring_a_gate_list_in_the_workflow_is_caught() -> None:
    """게이트 목록을 옮겨 적으면(소유자가 둘이 되면) 물어야 한다 — 흔한 형태로 심는다."""
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)
    gate_ids = manifest_gate_ids()
    duplicate = "uv run scripts/ga_gate.py " + " ".join(f"--only {gate_id}" for gate_id in gate_ids[:2])
    planted = _mutated(
        workflow,
        lambda clone: clone["jobs"]["ga-close"]["steps"].append({"name": "duplicate scope", "run": duplicate}),
    )
    violations = procedure_wiring_violations(planted, gate_ids)
    assert violations and gate_ids[0] in violations[0], f"이빨 없음 — 게이트 목록을 옮겨 적어도 통과했다: {violations}"
    assert procedure_wiring_violations(workflow, gate_ids) == [], "기준선이 깨졌다"


def test_teeth_wrong_attempt_name_is_caught() -> None:
    """글로브를 벗어난 시도 이름(F-25 의 그 함정)을 심는다."""
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)

    def rename(clone: dict[str, Any]) -> None:
        clone["env"]["GA_CLOSE_ATTEMPT"] = "ci"

    planted = _mutated(workflow, rename)
    violations = attempt_name_resolution_violations(planted)
    assert violations and report_glob() in violations[0], f"이빨 없음: {violations}"


def test_teeth_shallow_checkout_is_caught() -> None:
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)

    def shallow(clone: dict[str, Any]) -> None:
        for step in clone["jobs"]["ga-close"]["steps"]:
            if "actions/checkout" in str(step.get("uses") or ""):
                step.setdefault("with", {})["fetch-depth"] = 1

    violations = hygiene_violations(_mutated(workflow, shallow))
    assert any("fetch-depth" in violation for violation in violations), f"이빨 없음: {violations}"


def test_teeth_continue_on_error_is_caught() -> None:
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)

    def swallow(clone: dict[str, Any]) -> None:
        for step in clone["jobs"]["ga-close"]["steps"]:
            if "run_attempt_close.py" in str(step.get("run") or ""):
                step["continue-on-error"] = True

    violations = hygiene_violations(_mutated(workflow, swallow))
    assert any("continue-on-error" in violation for violation in violations), f"이빨 없음: {violations}"


def test_teeth_unsupported_caller_key_is_caught() -> None:
    """`runs-on`·`steps` 같은 키를 부르는 job 에 넣으면 GitHub 이 실행 전에 거부한다."""
    workflow = load_workflow(_RELEASE_WORKFLOW)

    def add_runs_on(clone: dict[str, Any]) -> None:
        for job_id in close_producer_job_ids(clone):
            clone["jobs"][job_id]["runs-on"] = "ubuntu-latest"

    violations = caller_shape_violations(_mutated(workflow, add_runs_on))
    assert violations and "runs-on" in violations[0], f"이빨 없음: {violations}"


def test_teeth_copying_steps_into_the_caller_is_caught() -> None:
    """릴리스가 스텝을 복제하면(부름이 아니라 사본이면) 물어야 한다."""
    workflow = load_workflow(_RELEASE_WORKFLOW)

    def copy_steps(clone: dict[str, Any]) -> None:
        for job_id in close_producer_job_ids(clone):
            clone["jobs"][job_id]["steps"] = [{"name": "copy", "run": "uv run python scripts/run_attempt_close.py"}]

    violations = caller_violations(_mutated(workflow, copy_steps))
    assert violations, "이빨 없음 — 부름 위에 스텝을 얹어도 통과했다"


def test_teeth_gate_check_and_prefix_changes_are_planted_consistently() -> None:
    """소유자의 글로브를 바꾸면 파이프라인 이름도 따라와야 한다(규칙이 하나면 둘은 함께 움직인다)."""
    assert attempt_prefix() == "attempt-", f"글로브 접두사가 바뀌었다: {report_glob()}"
    workflow = load_workflow(_GA_CLOSE_WORKFLOW)
    name = cast("dict[str, Any]", (workflow.get("env") or {}))["GA_CLOSE_ATTEMPT"]
    assert isinstance(name, str) and name.startswith(attempt_prefix())


@pytest.mark.parametrize("key", ["workflow_call", "schedule"])
def test_required_triggers_are_declared(key: str) -> None:
    declared = triggers(load_workflow(_GA_CLOSE_WORKFLOW))
    assert key in declared, f"{key} 트리거가 없다 — R-11 의 종료 조건이 깨진다: {sorted(map(str, declared))}"


def test_all_workflows_parse() -> None:
    """이빨이 기대는 전제: 저장소의 모든 워크플로가 YAML 로 읽힌다."""
    paths = sorted(_WORKFLOW_DIR.glob("*.yml"))
    assert paths, "워크플로를 찾지 못했다"
    for path in paths:
        load_workflow(path)


def test_publish_actions_are_recognised_by_behaviour() -> None:
    """동작으로 찾는 규칙이 실제 릴리스에서 publish job 을 찾아낸다(이름 하드코딩 금지)."""
    found = publish_job_ids(load_workflow(_RELEASE_WORKFLOW))
    assert "publish-pypi" in found and "github-release" in found, f"찾지 못했다: {found}"
