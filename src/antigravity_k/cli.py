"""Cli module."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from antigravity_k import __version__
from antigravity_k.config import config
from antigravity_k.engine.model_registry import ModelRegistry
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
app.add_typer(key_app, name="key", help="Manage API keys")
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
    table.add_column("Role")
    table.add_column("Repo")
    table.add_column("Memory GB", justify="right")

    for model in registry.list_models():
        table.add_row(
            model.name,
            model.role,
            model.repo,
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
            "[dim]⭐ = 현재 기본 모델\n" "사용법: [bold]agk model set <모델명>[/bold] — 기본 모델 변경",
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

    # ── Search ───────────────────────────────────────────────────
    if search:
        console.print(f"[bold]🔍 Searching for '{search}'...[/bold]\n")
        results = registry.search(search)
        if isinstance(results, list) and results and "error" not in results[0]:
            console.print(market_client.format_search_results(results))
        else:
            console.print("[yellow]No results found or marketplace unreachable.[/yellow]")
            if results and isinstance(results[0], dict) and "error" in results[0]:
                console.print(f"[red]  Error: {results[0]['error']}[/red]")
        return

    # ── Install ───────────────────────────────────────────────────
    if install:
        console.print(f"[bold]📦 Installing '{install}'...[/bold]")
        result = registry.install(install)
        if result.get("success"):
            console.print(f"[green]✅ {result.get('summary', 'Install complete')}[/green]")
        else:
            console.print(f"[red]❌ Install failed: {result.get('error', 'Unknown error')}[/red]")
        if result.get("warnings"):
            for w in result["warnings"]:
                console.print(f"[yellow]⚠️  {w}[/yellow]")
        return

    # ── Remove ────────────────────────────────────────────────────
    if remove:
        console.print(f"[bold]🗑️  Removing '{remove}'...[/bold]")
        result = registry.remove(remove)
        if result.get("success"):
            console.print(f"[green]✅ {result.get('summary', 'Removed')}[/green]")
        else:
            console.print(f"[red]❌ Remove failed: {result.get('error', 'Unknown error')}[/red]")
        return

    # ── Info ──────────────────────────────────────────────────────
    if info:
        skill_info = registry.get_info(info)
        if skill_info:
            console.print(registry.format_info(skill_info))
        else:
            # Try searching the package directly
            if info.startswith("@antigravity-k/skill-"):
                detail = market_client.get_detail(info)
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
                    console.print(f"[yellow]⚠️  '{info}' not found in marketplace.[/yellow]")
            else:
                console.print(f"[yellow]⚠️  Skill '{info}' is not installed.[/yellow]")
                console.print(f"   Search: [bold]agk market --search {info}[/bold]")
        return

    # ── List ──────────────────────────────────────────────────────
    if list_skills:
        installed = registry.list_installed()
        console.print(registry.format_list(installed))
        return

    # ── Update ────────────────────────────────────────────────────
    if update:
        console.print(f"[bold]⬆️  Updating '{update}'...[/bold]")
        result = registry.update(update)
        if result.get("success"):
            console.print(f"[green]✅ {result.get('summary', 'Update complete')}[/green]")
        else:
            console.print(f"[red]❌ Update failed: {result.get('error', 'Unknown error')}[/red]")
        return

    # ── Update All ────────────────────────────────────────────────
    if update_all:
        console.print("[bold]⬆️  Checking for updates across all skills...[/bold]")
        results = registry.update_all()
        updated = [r for r in results if r.get("success")]
        if updated:
            for r in updated:
                console.print(f"[green]  ✅ {r.get('skill_name', '?')} → {r.get('version', '?')}[/green]")
        else:
            console.print("[green]✅ All skills are up to date.[/green]")
        return

    # ── Publish to npm ────────────────────────────────────────────
    if publish_npm:
        console.print(f"[bold]📦 Publishing '{publish_npm}' to npm...[/bold]")
        try:
            from antigravity_k.engine.skill_publisher import SkillPublisher

            publisher = SkillPublisher(project_root=".")
            result = publisher.publish_to_npm(publish_npm, dry_run=dry_run)
            if result.success:
                console.print(f"[green]{result.summary()}[/green]")
            else:
                console.print(f"[red]❌ Publish failed: {'; '.join(result.errors)}[/red]")
            for w in result.warnings:
                console.print(f"[yellow]⚠️  {w}[/yellow]")
        except ImportError as e:
            console.print(f"[red]❌ Publisher not available: {e}[/red]")
        return

    # ── Publish to GitHub PR ───────────────────────────────────────
    if publish_github:
        if not publish_repo:
            console.print("[red]❌ --publish-repo <org/repo> is required for --publish-github[/red]")
            raise typer.Exit(code=1)
        console.print(f"[bold]🔀 Creating PR for '{publish_github}' → {publish_repo}...[/bold]")
        try:
            from antigravity_k.engine.skill_publisher import SkillPublisher

            publisher = SkillPublisher(project_root=".")
            result = publisher.publish_to_github(publish_github, repo=publish_repo, dry_run=dry_run)
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
        return

    # ── No option → show help ─────────────────────────────────────
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


if __name__ == "__main__":
    app()
