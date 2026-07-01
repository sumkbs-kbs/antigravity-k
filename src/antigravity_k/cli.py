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
    """Print basic project configuration."""
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
            masked = key[:4] + "*" * min(len(key) - 4, 16)
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
        masked = key[:4] + "*" * min(len(key) - 4, 16)
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


if __name__ == "__main__":
    app()
