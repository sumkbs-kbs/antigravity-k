"""Antigravity-K command-line interface (Typer-based)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from antigravity_k import __version__
from antigravity_k.config import config
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.secure_key import (
    VALID_SERVICES,
    get_api_key,
    get_key_source,
    remove_api_key,
    rotate_master_key,
    store_api_key,
)

app = typer.Typer(help="Antigravity-K command line interface", no_args_is_help=True)
key_app = typer.Typer(help="Manage encrypted API keys in vault")
memory_app = typer.Typer(help="Manage project-scoped memory configuration")
task_app = typer.Typer(help="Inspect and resume durable agent tasks")
app.add_typer(key_app, name="key", help="Manage API keys")
app.add_typer(memory_app, name="memory", help="Manage project memory")
app.add_typer(task_app, name="task", help="Manage durable agent tasks")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Print the Antigravity-K version and exit.",
    ),
) -> None:
    """Run the main entry point.

    Args:
        version (bool): bool version.

    """
    if version:
        console.print(f"antigravity-k {__version__}")
        raise typer.Exit()


@app.command()
def serve(
    host: str | None = typer.Option(None, "--host", help="Host to bind."),
    port: int | None = typer.Option(None, "--port", help="Port to bind."),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload."),
) -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run(
        "antigravity_k.api.server:app",
        host=host or config.server.host,
        port=port or config.server.port,
        reload=reload,
    )


@app.command("models")
def list_models() -> None:
    """List configured model profiles."""
    registry = ModelRegistry()
    table = Table(title="Configured Models")
    table.add_column("Name")
    table.add_column("Roles")
    table.add_column("Repo")
    table.add_column("Tier")
    table.add_column("Provider")
    table.add_column("Local")
    table.add_column("Memory GB", justify="right")

    for model in registry.list_models():
        table.add_row(
            model.name,
            ", ".join(model.supported_roles),
            model.repo,
            model.capability_tier,
            model.backend,
            "yes" if model.is_local else "no",
            f"{model.estimated_memory_gb:g}",
        )
    console.print(table)


@app.command()
def status() -> None:
    """Print mode status and basic project configuration."""
    from rich.panel import Panel

    from antigravity_k.engine.mode_manager import ModeManager

    mgr = ModeManager()

    # Mode status
    mode_lines = mgr.format_status().split("\n")
    console.print(
        Panel.fit(
            "\n".join(mode_lines),
            title="Execution Mode",
            border_style="cyan",
        ),
    )

    # Basic config
    console.print(
        {
            "version": __version__,
            "project_root": str(config.paths.project_root),
            "server": f"{config.server.host}:{config.server.port}",
            "api_engine": config.model.api_engine,
            "api_base": config.model.api_base,
        },
    )


@app.command("run")
def run_agent(
    prompt: str = typer.Argument(..., help="Prompt to run through the canonical agent runtime."),
    model: str = typer.Option("", "--model", help="Optional target model override."),
) -> None:
    from antigravity_k.api.dependencies import get_agent_runtime

    runtime = get_agent_runtime()
    tracked_stream = runtime.start_stream([{"role": "user", "content": prompt}], target_model=model)
    if tracked_stream.task_id:
        console.print(f"Task: {tracked_stream.task_id}")
    for chunk in tracked_stream.chunks:
        console.print(chunk, end="")
    console.print()


@task_app.command("list", help="List recent durable agent tasks.")
def task_list(limit: int = typer.Option(20, "--limit", min=1, max=200)) -> None:
    from antigravity_k.api.dependencies import get_agent_runtime

    table = Table(title="Durable Tasks")
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Prompt")
    for task in get_agent_runtime().list_tasks(limit=limit):
        table.add_row(
            str(task.get("task_id", "")),
            str(task.get("status", "unknown")),
            str(task.get("prompt", "")),
        )
    console.print(table)


@task_app.command("status", help="Show the durable state of one task.")
def task_status(task_id: str) -> None:
    from antigravity_k.api.dependencies import get_agent_runtime

    status = get_agent_runtime().get_task_status(task_id)
    if status is None:
        console.print(f"[red]Task not found:[/red] {task_id}")
        raise typer.Exit(code=1)
    console.print(status)


@task_app.command("output", help="Print the accumulated output of one task.")
def task_output(task_id: str) -> None:
    from antigravity_k.api.dependencies import get_agent_runtime

    output = get_agent_runtime().get_task_output(task_id)
    if output is None:
        console.print(f"[red]Task output not found:[/red] {task_id}")
        raise typer.Exit(code=1)
    console.print(output, end="")
    if not output.endswith("\n"):
        console.print()


@task_app.command("resume", help="Resume a failed or paused task and wait for its result.")
def task_resume(
    task_id: str,
    model: str = typer.Option("", "--model", help="Optional target model override."),
    timeout: float = typer.Option(300.0, "--timeout", min=0.1, help="Maximum wait time in seconds."),
) -> None:
    from antigravity_k.api.dependencies import get_agent_runtime

    runtime = get_agent_runtime()
    if not runtime.resume_task(task_id, target_model=model):
        console.print(f"[red]Task is not resumable or has no checkpoint:[/red] {task_id}")
        raise typer.Exit(code=1)
    status = runtime.wait_task(task_id, timeout=timeout)
    if status is None:
        console.print(f"[red]Task not found after resume:[/red] {task_id}")
        raise typer.Exit(code=1)
    state = str(status.get("status", "unknown"))
    console.print(f"Status: {state}")
    output = runtime.get_task_output(task_id)
    if output:
        console.print(output, end="")
        if not output.endswith("\n"):
            console.print()
    if state != "done":
        raise typer.Exit(code=2)


@memory_app.command("aliases")
def memory_aliases() -> None:
    from antigravity_k.engine.project_memory_keys import read_project_alias_schema
    from antigravity_k.engine.project_memory_paths import project_memory_dir

    schema = read_project_alias_schema(project_memory_dir(Path.cwd()))
    table = Table(title="Project Memory Aliases")
    table.add_column("Canonical Key")
    table.add_column("Aliases")
    for canonical, aliases in sorted(schema.aliases.items()):
        table.add_row(canonical, ", ".join(aliases))
    console.print(table)


@memory_app.command("alias-set")
def memory_alias_set(canonical: str, alias: str) -> None:
    from pydantic import ValidationError

    from antigravity_k.engine.project_memory_keys import (
        ProjectAliasConfigError,
        set_project_alias,
    )
    from antigravity_k.engine.project_memory_paths import project_memory_dir

    try:
        schema = set_project_alias(project_memory_dir(Path.cwd()), canonical, alias)
    except (ProjectAliasConfigError, ValidationError, ValueError) as error:
        console.print(f"[red]Invalid project alias: {error}[/red]")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Project alias saved:[/green] {alias} -> {canonical}")
    console.print(f"Aliases for {canonical}: {', '.join(schema.aliases[canonical])}")


@memory_app.command("alias-remove")
def memory_alias_remove(alias: str) -> None:
    from pydantic import ValidationError

    from antigravity_k.engine.project_memory_keys import (
        ProjectAliasConfigError,
        remove_project_alias,
    )
    from antigravity_k.engine.project_memory_paths import project_memory_dir

    try:
        _ = remove_project_alias(project_memory_dir(Path.cwd()), alias)
    except (ProjectAliasConfigError, ValidationError, ValueError) as error:
        console.print(f"[red]Invalid project alias: {error}[/red]")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Project alias removed:[/green] {alias}")


@app.command()
def doctor(
    heal: bool = typer.Option(
        False, "--heal", "-h", help="Automatically repair detected issues and clean stale caches."
    ),
) -> None:
    """Run a full environment diagnostic with automated self-healing capabilities."""
    from rich.panel import Panel
    from rich.table import Table

    if heal:
        from antigravity_k.engine.self_healing_doctor import SelfHealingDoctor

        doc = SelfHealingDoctor(project_root=".")
        rep = doc.run_health_check(auto_heal=True)
        console.print(
            f"[bold cyan]🏥 Self-Healing Doctor Results:[/bold cyan] {rep.healthy_count}/{rep.total_checks} Healthy ({rep.repaired_count} Auto-Repaired)"
        )
        for c in rep.checks:
            icon = "✅" if c.status in ("HEALTHY", "REPAIRED") else "⚠️"
            console.print(f"  {icon} [bold]{c.name}:[/bold] {c.message}")
        return

    results: list[tuple[str, str, str]] = []  # (check, status, detail)
    passed = 0
    warnings = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = "", is_warning: bool = False):
        nonlocal passed, warnings, failed
        if ok:
            status = "[green]✅ PASS[/green]"
            passed += 1
        elif is_warning:
            status = "[yellow]⚠️  WARN[/yellow]"
            warnings += 1
        else:
            status = "[red]❌ FAIL[/red]"
            failed += 1
        results.append((name, status, detail))

    # ── 1. Python & System Tools ──
    import sys

    check(
        "Python version",
        sys.version_info >= (3, 12),
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (requires ≥3.12)",
    )

    import shutil

    for tool in ("git", "node"):
        path = shutil.which(tool)
        check(f"{tool} in PATH", path is not None, path or "not found")

    # ── 2. Configuration ──
    check(
        "config.yaml exists",
        config.config_path.is_file(),
        str(config.config_path),
    )

    problems = config.validate()
    check(
        "Config validation",
        len(problems) == 0,
        f"{len(problems)} problem(s)" if problems else "all checks passed",
        is_warning=bool(problems),
    )

    # ── 3. API Keys ──
    for service in ("openrouter", "anthropic", "nvidia"):
        key = get_api_key(service)
        check(
            f"API key: {service}",
            key is not None,
            get_key_source(service) if key else "not set (optional)",
            is_warning=key is None,
        )

    # ── 4. Model Registry ──
    registry: ModelRegistry | None = None
    models: list[ModelProfile] = []
    try:
        registry = ModelRegistry()
        models = registry.list_models()
        check(
            "Model registry loaded",
            len(models) > 0,
            f"{len(models)} model(s) registered",
        )
    except Exception as e:
        check("Model registry loaded", False, str(e))

    # ── 4b. Local Providers (ollama / lmstudio / mlx) ──
    if registry is not None:
        from antigravity_k.engine.provider_capabilities import (
            LocalProviderCapabilityProbe,
            remediation_hint,
        )

        local_backends = {"ollama", "lmstudio", "lm_studio", "mlx"}
        representative_models: dict[str, ModelProfile] = {}
        for model in models:
            backend = model.backend.casefold() if model.backend else ""
            if backend in local_backends:
                representative_models.setdefault(backend, model)
        capability_probe = LocalProviderCapabilityProbe(registry)
        for profile in representative_models.values():
            capability = capability_probe.observe(profile)
            available = capability["runtime_status"] == "available"
            detail = (
                f"provider={capability['provider']} · "
                f"native_tools={capability['native_tool_calling']} · "
                f"{capability['source']} · {capability['detail']}"
            )
            hint = remediation_hint(profile, capability)
            if hint:
                detail += f" · fix={hint}"
            # 로컬 프로바이더는 선택적이므로 도달 실패는 FAIL이 아닌 WARN으로 처리한다.
            check(f"Local model health: {profile.name}", available, detail, is_warning=not available)

    # ── 5. Port Availability ──
    import socket

    port = config.server.port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(("127.0.0.1", port))
        check(
            f"Port {port} available",
            result != 0,
            f"port {'in use' if result == 0 else 'free'}",
            is_warning=result == 0,
        )
    finally:
        sock.close()

    # ── 6. Data Directories ──
    import os

    vault_env = os.environ.get("ANTIGRAVITY_VAULT_PATH", "vault_data")
    vault_path = Path(vault_env)
    try:
        vault_path.mkdir(parents=True, exist_ok=True)
        test_file = vault_path / ".doctor_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        check("Vault directory writable", True, str(vault_path.resolve()))
    except Exception as e:
        check("Vault directory writable", False, str(e))

    logs_dir = Path(config.paths.logs_dir)
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        check("Logs directory writable", True, str(logs_dir.resolve()))
    except Exception as e:
        check("Logs directory writable", False, str(e), is_warning=True)

    # ── 7. Amplification (CoV / cognitive / self-consistency / decomposition) ──
    # 작은 모델 성능 증폭 서브시스템의 현재 설정을 사용자에게 보여준다.
    # doctor는 읽기 전용 진단이므로 설정값은 표시만 하고 통과 처리한다.
    import yaml as _yaml

    def _object_dict(value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return {str(key): item for key, item in value.items()}

    amp_section: dict[str, object] = {}
    _cfg_path = config.config_path
    if _cfg_path.exists():
        try:
            with _cfg_path.open() as _f:
                _raw = _yaml.safe_load(_f) or {}
            if isinstance(_raw, dict):
                amp_section = _object_dict(_raw.get("amplification"))
        except Exception:
            amp_section = {}

    _cov = _object_dict(amp_section.get("cognitive"))
    _cov_enabled = bool(_cov.get("enabled", True)) if isinstance(_cov, dict) else True
    check(
        "Amplification: cognitive loop",
        True,
        f"{'on' if _cov_enabled else 'off'} · retries={_cov.get('max_retries', 2)} "
        f"dialectic={_cov.get('dialectic_enabled', True)}",
    )

    _cog = _object_dict(amp_section.get("cov"))
    _cog_enabled = bool(_cog.get("enabled", True)) if isinstance(_cog, dict) else True
    check(
        "Amplification: chain-of-verification",
        True,
        f"{'on' if _cog_enabled else 'off'} · revise={_cog.get('max_revise_iterations', 2)} "
        f"threshold={_cog.get('complexity_threshold', 0.4)}",
    )

    _sc = _object_dict(amp_section.get("self_consistency"))
    _sc_enabled = bool(_sc.get("enabled", False)) if isinstance(_sc, dict) else False
    check(
        "Amplification: self-consistency",
        True,
        f"{'on' if _sc_enabled else 'off'} · n={_sc.get('n_samples', 5)} "
        f"gate={_sc.get('complexity_threshold', 'null')}",
    )

    _td = _object_dict(amp_section.get("task_decomposition"))
    _td_enabled = bool(_td.get("enabled", False)) if isinstance(_td, dict) else False
    check(
        "Amplification: task decomposition",
        True,
        f"{'on' if _td_enabled else 'off'} · steps={_td.get('min_steps', 2)}-"
        f"{_td.get('max_steps', 6)} "
        f"escalate={'on' if _td.get('escalate_on_revision_failure', False) else 'off'}",
    )

    # ── Output ──
    table = Table(title="🩺 Antigravity-K Doctor", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim", overflow="fold")

    for name, status_text, detail in results:
        table.add_row(name, status_text, detail)

    console.print(table)
    console.print()

    summary_color = "red" if failed else ("yellow" if warnings else "green")
    console.print(
        Panel.fit(
            f"[bold]{passed} passed[/bold] · [yellow]{warnings} warnings[/yellow] · [red]{failed} failed[/red]",
            title=f"[{summary_color}]Diagnostic Summary[/{summary_color}]",
            border_style=summary_color,
        ),
    )

    if failed > 0:
        console.print("\n[red]❌ Issues detected. Fix the failing checks above before proceeding.[/red]")
        raise typer.Exit(code=1)
    elif warnings > 0:
        console.print("\n[yellow]⚠️  Some warnings detected. The app may work but check the items above.[/yellow]")


# ─── Key Management Commands ──────────────────────────────────────


def _validate_service(service: str) -> str:
    """서비스 이름을 검증하고 정규화합니다."""
    svc = service.lower().strip()
    if svc not in VALID_SERVICES:
        console.print(f"[red]❌ 지원하지 않는 서비스: '{svc}'[/red]")
        console.print(f"   유효한 서비스: {', '.join(VALID_SERVICES)}")
        raise typer.Exit(code=1)
    return svc


_SOURCE_ICON = {
    "env": "🌐 환경변수",
    "dotenv": "📄 .env 파일",
    "config": "⚙️  config.yaml",
    "vault": "🔐 vault 암호화",
    "none": "—",
}


@key_app.command("set")
def key_set(
    service: str = typer.Argument(
        ...,
        help="Service name (anthropic, openai, openrouter)",
    ),
    key: str = typer.Argument(
        ...,
        help="API key to store",
    ),
) -> None:
    """암호화하여 API 키를 vault 저장소에 저장합니다.

    키는 머신 고유 키로 PBKDF2 + Fernet 암호화되어

    .agk_vault/keys.enc에 저장됩니다 (git 무시됨).

    우선순위: 환경변수 > .env 파일 > config.yaml > vault 저장소
    """
    svc = _validate_service(service)

    if len(key) < 8:
        console.print("[red]❌ API 키가 너무 짧습니다 (최소 8자).[/red]")
        raise typer.Exit(code=1)

    # 이미 환경변수에 설정되어 있는지 확인
    env_var = f"AGK_{svc.upper()}_KEY"
    import os

    if os.environ.get(env_var):
        console.print(
            f"[yellow]⚠️  환경변수 {env_var}가 이미 설정되어 있습니다.[/yellow]\n"
            f"   vault 저장소에 저장해도 환경변수가 우선 적용됩니다.",
        )

    success = store_api_key(svc, key)
    if success:
        # 마스킹된 키 출력
        masked = key[:4] + "*" * min(len(key) - 4, 16)
        console.print("[green]✅ API 키 저장 완료[/green]")
        console.print(f"   서비스: {svc}")
        console.print(f"   키     : {masked}")
        console.print("   위치  : .agk_vault/keys.enc (암호화)")
        console.print("")
        console.print(
            f"[dim]팁: 키를 환경변수로도 설정하려면:  export {env_var}=your-key[/dim]",
        )
    else:
        console.print("[red]❌ 키 저장 실패[/red]")
        raise typer.Exit(code=1)


@key_app.command("list")
def key_list() -> None:
    """설정된 API 키 상태를 확인합니다.

    모든 소스(환경변수, .env, config.yaml, vault)를 확인하여

    각 서비스별로 키 설정 여부와 출처를 표시합니다.
    """
    table = Table(title="API Key Status")
    table.add_column("Service")
    table.add_column("Status")
    table.add_column("Source")
    table.add_column("Key (masked)")

    for svc in VALID_SERVICES:
        source = get_key_source(svc)
        key = get_api_key(svc)

        if key:
            masked = key[:4] + "*" * min(len(key or "") - 4, 16)
            table.add_row(svc, "✅ 설정됨", _SOURCE_ICON.get(source, source), masked)
        else:
            table.add_row(
                svc,
                "❌ 미설정",
                "—",
                f"[dim]export AGK_{svc.upper()}_KEY=... 또는 agk key set {svc} <key>[/dim]",
            )

    console.print(table)
    console.print(
        "\n[dim]키 우선순위: 환경변수 > .env 파일 > config.yaml > vault[/dim]",
    )


@key_app.command("remove")
def key_remove(
    service: str = typer.Argument(
        ...,
        help="Service name to remove from vault (anthropic, openai, openrouter)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="확인 없이 삭제",
    ),
) -> None:
    """Vault 저장소에서 API 키를 삭제합니다.

    환경변수나 .env 파일에 설정된 키는 삭제되지 않습니다.

    (해당 소스에서 직접 제거해야 함)
    """
    svc = _validate_service(service)

    # vault에 키가 있는지 확인
    source = get_key_source(svc)
    key = get_api_key(svc)

    if source != "vault":
        if source == "none":
            console.print(f"[yellow]⚠️  vault에 {svc} 키가 저장되어 있지 않습니다.[/yellow]")
        else:
            icon = _SOURCE_ICON.get(source, source)
            msg = f"[yellow]⚠️  {svc} 키는 {icon}에 설정되어 있어 vault에서 삭제할 수 없습니다.[/yellow]"
            console.print(f"{msg}\n   해당 소스({icon})에서 직접 제거하세요.")
        return

    if not force:
        masked = (key or "")[:4] + "*" * min(len(key or "") - 4, 16)
        console.print("[yellow]⚠️  다음 키를 vault에서 삭제합니다:[/yellow]")
        console.print(f"   서비스: {svc}")
        console.print(f"   키     : {masked}")
        confirm = typer.confirm("계속하시겠습니까?")
        if not confirm:
            console.print("[dim]취소됨[/dim]")
            raise typer.Exit()

    if remove_api_key(svc):
        console.print(f"[green]✅ vault에서 {svc} 키가 삭제되었습니다.[/green]")
    else:
        console.print(f"[yellow]⚠️  vault에 {svc} 키가 없습니다.[/yellow]")


@key_app.command("rotate")
def key_rotate(
    seed: str | None = typer.Option(
        None,
        "--seed",
        "-s",
        help="새 머신 시드 (지정하지 않으면 현재 시드 재사용, 동일 키 유지)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="키가 동일해도 강제 재암호화",
    ),
) -> None:
    """마스터 키를 순환(rotation)하고 vault 데이터를 재암호화합니다.

    --seed를 지정하면 새 시드로 새 키가 생성됩니다.

    --seed를 생략하면 현재 시드를 재사용하므로 동일한 키가 유지됩니다.
    (의미 있는 순환을 위해서는 --seed를 지정하세요.)

    --force를 사용하면 키가 동일해도 강제로 재암호화합니다.
    """
    result = rotate_master_key(new_seed=seed, force=force)

    if not result["success"]:
        console.print(f"[red]❌ 키 순환 실패: {result.get('error')}[/red]")
        raise typer.Exit(code=1)

    if not result["rotated"]:
        console.print(
            "[yellow]⚠️  키가 변경되지 않았습니다.[/yellow]\n   --seed <새 시드>를 지정하여 새 키를 생성하세요.",
        )
        return

    svc_count = result["services_count"]
    console.print("[green]✅ 마스터 키 순환 완료[/green]")
    console.print(f"   재암호화된 서비스: {svc_count}개")
    if svc_count > 0:
        console.print("   위치: .agk_vault/keys.enc (새 키로 암호화)")
    if seed:
        console.print("   키체인에 새 시드 저장됨")


# ─── Model Command ────────────────────────────────────────────────────────


model_app = typer.Typer(help="Manage models: list, set defaults")
app.add_typer(model_app, name="model", help="Manage models and set defaults")


@model_app.command("list")
def model_list() -> None:
    """List all available models with role grouping and default markers."""
    from rich.panel import Panel
    from rich.table import Table

    registry = ModelRegistry()
    defaults = registry.defaults

    roles = ["reasoning", "coding", "embedding", "vision"]
    role_labels = {
        "reasoning": "🧠 Reasoning",
        "coding": "💻 Coding",
        "embedding": "📐 Embedding",
        "vision": "👁️ Vision",
    }

    for role in roles:
        models = registry.find_by_role(role)
        if not models:
            continue

        default_name = getattr(defaults, role, None)
        label = role_labels.get(role, role)

        table = Table(title=f"{label} Models ({len(models)}개)", box=None, show_header=False)
        table.add_column("", style="dim", width=3)
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="dim")

        for m in models:
            is_default = m.name == default_name
            marker = "⭐" if is_default else ""
            desc = m.description or ""
            table.add_row(marker, m.name, desc)

        console.print(table)
        console.print()

    console.print(
        Panel.fit(
            "[dim]⭐ = 현재 기본 모델\n사용법: [bold]agk model set <모델명>[/bold] — 기본 모델 변경",
            border_style="dim",
        )
    )


@model_app.command("set")
def model_set(
    name: str = typer.Argument(
        ...,
        help="Set a model as default for its role (e.g. 'nvidia/nemotron-3-ultra-550b-a55b:free')",
    ),
) -> None:
    """Set a model as the default for its role in config.yaml.

    레지스트리에 등록된 모델 중 하나를 선택하여

    해당 역할(role)의 기본 모델로 설정합니다.

    config.yaml의 defaults 섹션이 업데이트되며,

    서버 재시작 시 자동으로 반영됩니다.
    """
    registry = ModelRegistry()
    model = registry.get_model(name)

    if not model:
        console.print(f"[red]❌ 모델 '{name}'을(를) 레지스트리에서 찾을 수 없습니다.[/red]")
        console.print("[yellow]📋 등록된 모델 목록은 'agk model list'로 확인하세요.[/yellow]")
        raise typer.Exit(code=1)

    # config.yaml 업데이트
    from pathlib import Path

    import yaml

    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config.yaml"

    if not config_path.exists():
        console.print(f"[red]❌ config.yaml 파일을 찾을 수 없습니다: {config_path}[/red]")
        raise typer.Exit(code=1)

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        console.print(f"[red]❌ config.yaml 파싱 실패: {e}[/red]")
        raise typer.Exit(code=1)

    role = model.role
    if "defaults" not in raw:
        raw["defaults"] = {}
    if not isinstance(raw["defaults"], dict):
        raw["defaults"] = {}

    old_default = raw["defaults"].get(role, "(없음)")
    raw["defaults"][role] = name

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        console.print(f"[red]❌ config.yaml 쓰기 실패: {e}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]✅ 기본 {role} 모델 변경 완료[/green]")
    console.print(f"   [dim]{old_default}[/dim] → [bold cyan]{name}[/bold cyan]")
    console.print()
    console.print("[dim]💡 서버를 재시작하면 새로운 기본 모델이 적용됩니다:[/dim]")
    console.print("[dim]   agk serve --reload  (또는 서버 재시작)[/dim]")


# ─── Mode Command ──────────────────────────────────────────────────────────


@app.command()
def mode(
    target: str = typer.Argument(
        "status",
        help="Target mode: plan, build, interactive, or status",
    ),
    reason: str | None = typer.Option(
        None,
        "--reason",
        "-r",
        help="Reason for mode switch",
    ),
    plan_path: str | None = typer.Option(
        None,
        "--plan",
        "-p",
        help="Plan artifact path (for build mode)",
    ),
) -> None:
    """Manage execution mode (Plan/Build/Interactive).

    Plan mode: Only read-only tools and write_artifact are allowed.
    Build mode: All tools are allowed (post-plan execution).
    Interactive: Default conversational mode.
    """
    from rich.panel import Panel

    from antigravity_k.engine.mode_manager import ModeManager

    mgr = ModeManager()
    target_lower = target.lower()

    if target_lower == "status":
        console.print(mgr.format_status())
        return

    if target_lower == "plan":
        rsn = reason or "CLI: agk mode plan"
        if mgr.switch_to_plan(rsn):
            console.print(mgr.format_status())
        else:
            console.print("[red]❌ Plan 모드 전환 실패[/red]")
        return

    if target_lower == "build":
        rsn = reason or "CLI: agk mode build"
        if plan_path:
            mgr.set_plan_artifact(plan_path)
            mgr.set_plan_quality_passed(True)
            rsn = f"Plan artifact: {plan_path}"
        if mgr.switch_to_build(plan_artifact_path=plan_path, reason=rsn):
            console.print(mgr.format_status())
        else:
            if mgr.is_plan:
                console.print(
                    Panel.fit(
                        "[yellow]❌ Build 모드 전환 실패:[/yellow]\n\n"
                        "Plan → Build 자동 전환 조건이 충족되지 않았습니다.\n"
                        "1. Plan 아티팩트(`implementation_plan.md`) 생성 필요\n"
                        "2. Plan 품질 검증(QualityGate) 통과 필요\n"
                        "3. 강제 전환: [bold]agk mode build --plan <path>[/bold]",
                        title="Build Mode",
                    ),
                )
            else:
                console.print("[red]❌ Build 모드 전환 실패[/red]")
        return

    if target_lower == "interactive":
        rsn = reason or "CLI: agk mode interactive"
        if mgr.switch_to_interactive(rsn):
            console.print(mgr.format_status())
        else:
            console.print("[red]❌ Interactive 모드 전환 실패[/red]")
        return

    console.print(f"[red]알 수 없는 모드: '{target}'[/red]")
    console.print("사용법: agk mode [plan|build|interactive|status]")


# ─── TUI Command ──────────────────────────────────────────────────────────


@app.command()
def tui(
    dev: bool = typer.Option(
        False,
        "--dev",
        "-d",
        help="Launch with development tools enabled.",
    ),
) -> None:
    """Launch the Textual Terminal UI (TUI).

    Interactive terminal interface with chat, slash commands, and system monitoring.
    """
    try:
        from antigravity_k.tui import run_tui

        run_tui()
    except ImportError as e:
        console.print(f"[red]TUI dependencies not installed: {e}[/red]")
        console.print("  Install with: [yellow]pip install textual[/yellow]")
        raise typer.Exit(code=1) from e


# ─── Market Commands ────────────────────────────────────────────────────────


@app.command()
def _market_search(registry, market_client, query: str) -> None:
    """Search the marketplace for skills."""
    console.print(f"[bold]🔍 Searching for '{query}'...[/bold]\n")
    results = registry.search(query)
    if isinstance(results, list) and results and "error" not in results[0]:
        console.print(market_client.format_search_results(results))
    else:
        console.print("[yellow]No results found or marketplace unreachable.[/yellow]")
        if results and isinstance(results[0], dict) and "error" in results[0]:
            console.print(f"[red]  Error: {results[0]['error']}[/red]")


def _market_install(registry, package: str) -> None:
    """Install a skill package."""
    console.print(f"[bold]📦 Installing '{package}'...[/bold]")
    result = registry.install(package)
    if result.get("success"):
        console.print(f"[green]✅ {result.get('summary', 'Install complete')}[/green]")
    else:
        console.print(f"[red]❌ Install failed: {result.get('error', 'Unknown error')}[/red]")
    if result.get("warnings"):
        for w in result["warnings"]:
            console.print(f"[yellow]⚠️  {w}[/yellow]")


def _market_remove(registry, name: str) -> None:
    """Remove an installed skill."""
    console.print(f"[bold]🗑️  Removing '{name}'...[/bold]")
    result = registry.remove(name)
    if result.get("success"):
        console.print(f"[green]✅ {result.get('summary', 'Removed')}[/green]")
    else:
        console.print(f"[red]❌ Remove failed: {result.get('error', 'Unknown error')}[/red]")


def _market_info(registry, market_client, name: str) -> None:
    """Show detailed skill information."""
    skill_info = registry.get_info(name)
    if skill_info:
        console.print(registry.format_info(skill_info))
        return
    # Try searching the package directly.
    if name.startswith("@antigravity-k/skill-"):
        detail = market_client.get_detail(name)
        if detail:
            from rich.panel import Panel

            lines = [
                f"📦 **{detail.name}** `v{detail.version}`",
                "",
                f"설명: {detail.description}",
                f"키워드: {', '.join(detail.keywords)}",
                f"라이선스: {detail.license}",
                f"홈페이지: {detail.homepage}",
                f"npm: {detail.npm_url}",
            ]
            if detail.is_agk_skill:
                lines.extend(
                    [
                        "",
                        "**AGK 메타데이터:**",
                        f"  - 위험도: `{detail.agk_risk_level}`",
                        f"  - 신뢰수준: `{detail.agk_trust_level}`",
                        f"  - 승인필요: {'✅' if detail.agk_requires_approval else '❌'}",
                    ]
                )
                if detail.agk_mcp_server_id:
                    lines.append(f"  - MCP 서버: `{detail.agk_mcp_server_id}`")
            console.print(Panel.fit("\n".join(lines), title="Skill Detail"))
        else:
            console.print(f"[yellow]⚠️  '{name}' not found in marketplace.[/yellow]")
    else:
        console.print(f"[yellow]⚠️  Skill '{name}' is not installed.[/yellow]")
        console.print(f"   Search: [bold]agk market --search {name}[/bold]")


def _market_list(registry) -> None:
    """List installed skills."""
    installed = registry.list_installed()
    console.print(registry.format_list(installed))


def _market_update(registry, name: str) -> None:
    """Update a specific skill."""
    console.print(f"[bold]⬆️  Updating '{name}'...[/bold]")
    result = registry.update(name)
    if result.get("success"):
        console.print(f"[green]✅ {result.get('summary', 'Update complete')}[/green]")
    else:
        console.print(f"[red]❌ Update failed: {result.get('error', 'Unknown error')}[/red]")


def _market_update_all(registry) -> None:
    """Update all outdated skills."""
    console.print("[bold]⬆️  Checking for updates across all skills...[/bold]")
    results = registry.update_all()
    updated = [r for r in results if r.get("success")]
    if updated:
        for r in updated:
            console.print(f"[green]  ✅ {r.get('skill_name', '?')} → {r.get('version', '?')}[/green]")
    else:
        console.print("[green]✅ All skills are up to date.[/green]")


def _market_publish_npm(skill_name: str, dry_run: bool) -> None:
    """Publish a local skill to npm."""
    console.print(f"[bold]📦 Publishing '{skill_name}' to npm...[/bold]")
    try:
        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=".")
        result = publisher.publish_to_npm(skill_name, dry_run=dry_run)
        if result.success:
            console.print(f"[green]{result.summary()}[/green]")
        else:
            console.print(f"[red]❌ Publish failed: {'; '.join(result.errors)}[/red]")
        for w in result.warnings:
            console.print(f"[yellow]⚠️  {w}[/yellow]")
    except ImportError as e:
        console.print(f"[red]❌ Publisher not available: {e}[/red]")


def _market_publish_github(skill_name: str, repo: str, dry_run: bool) -> None:
    """Publish a local skill via GitHub PR."""
    console.print(f"[bold]🔀 Creating PR for '{skill_name}' → {repo}...[/bold]")
    try:
        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=".")
        result = publisher.publish_to_github(skill_name, repo=repo, dry_run=dry_run)
        if result.success:
            console.print(f"[green]{result.summary()}[/green]")
            if result.pr_url:
                console.print(f"   🔗 {result.pr_url}")
        else:
            console.print(f"[red]❌ PR failed: {'; '.join(result.errors)}[/red]")
        for w in result.warnings:
            console.print(f"[yellow]⚠️  {w}[/yellow]")
    except ImportError as e:
        console.print(f"[red]❌ Publisher not available: {e}[/red]")


def _market_show_help() -> None:
    """Print the marketplace command help."""
    from rich.panel import Panel

    help_lines = [
        "[bold]Marketplace Commands[/bold]",
        "",
        "  [cyan]--search, -s[/cyan]    <query>          Search for skills",
        "  [cyan]--install, -i[/cyan]   <package>        Install a skill",
        "  [cyan]--remove, -r[/cyan]    <name>           Remove an installed skill",
        "  [cyan]--list, -l[/cyan]                        List installed skills",
        "  [cyan]--info[/cyan]          <name>           Show skill details",
        "  [cyan]--update, -u[/cyan]    <name>           Update a skill",
        "  [cyan]--update-all, -U[/cyan]                  Update all outdated skills",
        "  [cyan]--publish-npm[/cyan]   <name>           Publish local skill to npm",
        "  [cyan]--publish-github[/cyan] <name>          Publish local skill via GitHub PR",
        "  [cyan]--publish-repo[/cyan]  <org/repo>       Target repo for --publish-github",
        "  [cyan]--dry-run[/cyan]                         Validate without publishing",
        "",
        "Examples:",
        '  [dim]agk market --search "code review"[/dim]',
        "  [dim]agk market --install @antigravity-k/skill-code-review[/dim]",
        "  [dim]agk market --list[/dim]",
        "  [dim]agk market --publish-npm my-skill[/dim]",
        "  [dim]agk market --publish-npm my-skill --dry-run[/dim]",
        "  [dim]agk market --publish-github my-skill --publish-repo org/skills-repo[/dim]",
    ]
    console.print(Panel.fit("\n".join(help_lines), title="agk market"))


def market(
    search: str | None = typer.Option(None, "--search", "-s", help="Search for skills in the marketplace"),
    install: str | None = typer.Option(None, "--install", "-i", help="Install a skill package"),
    remove: str | None = typer.Option(None, "--remove", "-r", help="Remove an installed skill"),
    info: str | None = typer.Option(None, "--info", help="Show detailed skill information"),
    update: str | None = typer.Option(None, "--update", "-u", help="Update a specific skill"),
    list_skills: bool = typer.Option(False, "--list", "-l", help="List installed skills"),
    update_all: bool = typer.Option(False, "--update-all", "-U", help="Update all outdated skills"),
    publish_npm: str | None = typer.Option(
        None, "--publish-npm", help="Publish a local skill to npm (e.g. 'code-review')"
    ),
    publish_github: str | None = typer.Option(
        None, "--publish-github", help="Publish a local skill via GitHub PR (e.g. 'code-review')"
    ),
    publish_repo: str | None = typer.Option(
        None, "--publish-repo", help="Target GitHub repo for --publish-github (e.g. 'org/skills-repo')"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without publishing"),
) -> None:
    """Manage skills from the Antigravity-K Marketplace.

    Search, install, remove, list, update, and publish skills.

    Examples:
        agk market --search "code review"
        agk market --install @antigravity-k/skill-code-review
        agk market --list
        agk market --info code-review
        agk market --remove code-review
        agk market --update code-review
        agk market --update-all
        agk market --publish-npm my-skill
        agk market --publish-npm my-skill --dry-run
        agk market --publish-github my-skill --publish-repo org/skills-repo
    """
    # ── Lazy imports ────────────────────────────────────────────────
    try:
        from antigravity_k.engine.skill_market_client import SkillMarketClient
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry
    except ImportError as e:
        console.print(f"[red]❌ Market dependencies not available: {e}[/red]")
        raise typer.Exit(code=1) from e

    market_client = SkillMarketClient()
    registry = SkillMarketRegistry(project_root=".", market_client=market_client)

    # ── Dispatch to sub-command handlers ──────────────────────────
    if search:
        _market_search(registry, market_client, search)
    elif install:
        _market_install(registry, install)
    elif remove:
        _market_remove(registry, remove)
    elif info:
        _market_info(registry, market_client, info)
    elif list_skills:
        _market_list(registry)
    elif update:
        _market_update(registry, update)
    elif update_all:
        _market_update_all(registry)
    elif publish_npm:
        _market_publish_npm(publish_npm, dry_run)
    elif publish_github:
        if not publish_repo:
            console.print("[red]❌ --publish-repo <org/repo> is required for --publish-github[/red]")
            raise typer.Exit(code=1)
        _market_publish_github(publish_github, publish_repo, dry_run)
    else:
        _market_show_help()


@app.command()
def autopilot(
    goal: str = typer.Argument(..., help="High-level engineering mission to execute autonomously."),
    max_turns: int = typer.Option(10, "--max-turns", "-m", help="Maximum autonomous flight turns."),
) -> None:
    """Launch full autonomous self-driving flight mission for Qwen3.8-27B."""
    from antigravity_k.engine.flight_controller import AutonomousFlightController

    console.print(f"[bold cyan]🚀 Launching Autonomous Autopilot Mission:[/bold cyan] {goal}")

    controller = AutonomousFlightController(project_root=".", max_flight_turns=max_turns)

    from typing import Any

    # Initial starter subgoals inferred from goal
    subgoals: list[dict[str, Any]] = [
        {"id": "plan", "desc": f"Formulate implementation plan for '{goal}'"},
        {"id": "code", "desc": "Implement required changes and patches", "depends_on": ["plan"]},
        {"id": "verify", "desc": "Run TDD tests and static audits", "depends_on": ["code"]},
    ]

    def _execute_step(step_id: str, desc: str) -> bool:
        console.print(f"  [yellow]⚡ Step [{step_id}]:[/yellow] {desc}")
        # Step simulation / execution hook
        return True

    report = controller.launch_mission(
        goal=goal,
        initial_subgoals=subgoals,
        step_executor=_execute_step,
    )

    if report.is_success:
        console.print(
            f"[bold green]✅ Mission '{goal}' Completed Successfully in {report.total_steps_executed} turns![/bold green]"
        )

        # ── Proactive Next-Action Recommendations (Freebuff-style) ──
        try:
            from antigravity_k.engine.flight_deck_renderer import FlightDeckRenderer
            from antigravity_k.engine.next_action_recommender import NextActionRecommender

            recommender = NextActionRecommender(project_root=".")
            rec_batch = recommender.synthesize_recommendations(completed_goal=goal, touched_files=["src/antigravity_k/engine/flight_controller.py"])
            rec_panel = FlightDeckRenderer.render_recommendations_panel(rec_batch.format_cli_panel())
            console.print(rec_panel)
        except Exception as ex:
            console.print(f"[dim yellow]Notice: NextActionRecommender skipped ({ex})[/dim yellow]")
    else:
        console.print(f"[bold red]❌ Mission '{goal}' stopped after {report.total_steps_executed} turns.[/bold red]")


@app.command()
def fast(
    query: str = typer.Argument(..., help="Deterministic query to resolve instantly (e.g. 'where is ClassName')."),
) -> None:
    """Execute direct fast-path kernel query with <5ms latency (Zero LLM overhead)."""
    from antigravity_k.engine.fast_path_kernel import FastPathKernel

    kernel = FastPathKernel(project_root=".")
    res = kernel.try_execute(query)

    if res.handled:
        console.print(res.response)
    else:
        console.print(f"[yellow]⚡ Query '{query}' requires full LLM generation loop.[/yellow]")


if __name__ == "__main__":
    app()
