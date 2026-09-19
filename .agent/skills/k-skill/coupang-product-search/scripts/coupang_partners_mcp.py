#!/usr/bin/env python3
"""Bootstrap and run retention-corp/coupang_partners Coupang MCP tools.

The k-skill repo intentionally does not vendor the third-party implementation.
This wrapper keeps the skill pointed at the approved upstream repository, clones it
into a user cache when needed, and then delegates to its local MCP-compatible CLI.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
from collections.abc import Sequence

UPSTREAM_REPO_URL = "https://github.com/retention-corp/coupang_partners.git"
DEFAULT_MCP_ENDPOINT = "local://coupang-mcp"
DEFAULT_REPO_DIR = pathlib.Path(
    os.getenv("COUPANG_PARTNERS_REPO_DIR", "~/.cache/k-skill/coupang_partners")
).expanduser()
UPSTREAM_CLI = pathlib.Path("bin") / "coupang_mcp.py"


class BootstrapError(RuntimeError):
    """Raised when the upstream checkout cannot be prepared."""


class _ParsedArguments(argparse.Namespace):
    repo_dir: str
    no_clone: bool
    update: bool
    upstream_args: list[str]

    def __init__(
        self,
        *,
        repo_dir: str,
        no_clone: bool,
        update: bool,
        upstream_args: list[str],
    ) -> None:
        super().__init__(
            repo_dir=repo_dir,
            no_clone=no_clone,
            update=update,
            upstream_args=upstream_args,
        )
        self.repo_dir = repo_dir
        self.no_clone = no_clone
        self.update = update
        self.upstream_args = upstream_args


def parse_args(argv: Sequence[str] | None = None) -> _ParsedArguments:
    parser = argparse.ArgumentParser(
        description="Run the retention-corp/coupang_partners local Coupang MCP-compatible CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  coupang_partners_mcp.py tools\n"
            "  coupang_partners_mcp.py init\n"
            "  coupang_partners_mcp.py search 생수\n"
            "  coupang_partners_mcp.py budget 키보드 --max-price 100000\n"
            "\n"
            "Honored upstream environment variables (forwarded as-is):\n"
            "  COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY\n"
            "      Operator Coupang Partners API credentials. When set, upstream\n"
            "      uses the local HMAC-signed Coupang Partners path.\n"
            "  OPENCLAW_SHOPPING_CLIENT_ID\n"
            "      Allowlisted client id for the hosted fallback. upstream sends\n"
            "      openclaw-skill by default, which is the value currently on the\n"
            "      Retention Corp allowlist; k-skill does not override this.\n"
            "  OPENCLAW_SHOPPING_FORCE_HOSTED=1\n"
            "      Force the hosted fallback even when Coupang keys are present.\n"
            "  OPENCLAW_SHOPPING_BASE_URL\n"
            "      Override the hosted backend base URL. Default upstream target\n"
            "      is https://a.retn.kr and /v1/public/assist is the public entry.\n"
            "\n"
            "When both COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY are missing,\n"
            "upstream falls back to the hosted Retention Corp backend so this\n"
            "skill keeps working without Coupang Partners credentials."
        ),
    )
    _ = parser.add_argument(
        "--repo-dir",
        default=str(DEFAULT_REPO_DIR),
        help="Checkout directory for retention-corp/coupang_partners (default: %(default)s).",
    )
    _ = parser.add_argument(
        "--no-clone",
        action="store_true",
        help="Do not clone the upstream repository if it is missing; fail with setup guidance instead.",
    )
    _ = parser.add_argument(
        "--update",
        action="store_true",
        help="Run git pull --ff-only in an existing upstream checkout before delegating.",
    )
    _ = parser.add_argument(
        "upstream_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to bin/coupang_mcp.py, for example: tools, search 생수, rocket 에어팟.",
    )
    args = _ParsedArguments(
        repo_dir=str(DEFAULT_REPO_DIR),
        no_clone=False,
        update=False,
        upstream_args=[],
    )
    _ = parser.parse_args(argv, namespace=args)
    upstream_args = tuple(args.upstream_args)
    if upstream_args and upstream_args[0] == "--":
        upstream_args = upstream_args[1:]
    if not upstream_args:
        parser.error("missing upstream command; try: tools, init, search <keyword>, rocket <keyword>, budget <keyword>")
    args.upstream_args = list(upstream_args)
    return args


def upstream_cli_path(repo_dir: pathlib.Path) -> pathlib.Path:
    return repo_dir / UPSTREAM_CLI


def ensure_repo(repo_dir: pathlib.Path, *, clone: bool = True, update: bool = False) -> pathlib.Path:
    cli_path = upstream_cli_path(repo_dir)
    if cli_path.exists():
        if update:
            run_checked(
                ["git", "-C", str(repo_dir), "pull", "--ff-only"],
                "failed to update upstream checkout",
            )
        return cli_path

    if repo_dir.exists():
        guidance = f"(missing {UPSTREAM_CLI}). Recreate it with: git clone {UPSTREAM_REPO_URL} {repo_dir}"
        raise BootstrapError(f"{repo_dir} exists but does not look like retention-corp/coupang_partners {guidance}")

    if not clone:
        guidance = f"Create it with: git clone {UPSTREAM_REPO_URL} {repo_dir}"
        raise BootstrapError(f"Missing retention-corp/coupang_partners checkout at {repo_dir}. {guidance}")

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    run_checked(
        ["git", "clone", "--depth", "1", UPSTREAM_REPO_URL, str(repo_dir)],
        "failed to clone upstream checkout",
    )
    if not cli_path.exists():
        raise BootstrapError(f"Cloned {UPSTREAM_REPO_URL}, but {UPSTREAM_CLI} was not found in {repo_dir}")
    return cli_path


def run_checked(command: Sequence[str], context: str) -> None:
    try:
        _ = subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise BootstrapError(f"{context}: required executable not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise BootstrapError(f"{context}: {exc}") from exc


def build_command(cli_path: pathlib.Path, upstream_args: Sequence[str]) -> list[str]:
    return [sys.executable, str(cli_path), *upstream_args]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_dir = pathlib.Path(args.repo_dir).expanduser().resolve()

    try:
        cli_path = ensure_repo(repo_dir, clone=not args.no_clone, update=args.update)
    except BootstrapError as exc:
        print(f"coupang_partners_mcp.py: {exc}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    _ = env.setdefault("COUPANG_MCP_ENDPOINT", DEFAULT_MCP_ENDPOINT)
    completed = subprocess.run(build_command(cli_path, args.upstream_args), env=env)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
