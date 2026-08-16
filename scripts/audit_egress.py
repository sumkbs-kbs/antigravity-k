from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from typing import cast, final, override
from urllib.parse import urlsplit

_EGRESS_PREFIXES = (
    "httpx.",
    "requests.",
    "urllib.request.urlopen",
    "urllib.urlopen",
    "urlopen",
    "aiohttp.ClientSession",
    "urllib3.PoolManager",
    "safe_urlopen",
)


@dataclass(frozen=True)
class EgressCall:
    file: str
    line: int
    column: int
    function: str
    target: str
    category: str
    policy: str
    endpoint: str


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _literal_strings(node: ast.AST) -> list[str]:
    return [child.value for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str)]


def _is_egress_target(target: str) -> bool:
    return any(target == prefix.rstrip(".") or target.startswith(prefix) for prefix in _EGRESS_PREFIXES)


def _safe_endpoint(value: str) -> tuple[str, str]:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return "", "configured_endpoint"

    host = parts.hostname.lower()
    try:
        address = ip_address(host)
    except ValueError:
        address = None

    if host == "localhost" or host.endswith(".localhost") or address and address.is_loopback:
        category = "local_endpoint"
    elif address and (address.is_private or address.is_link_local or address.is_reserved):
        category = "private_endpoint"
    else:
        category = "public_endpoint"

    port = f":{parts.port}" if parts.port else ""
    host_text = f"[{host}]" if ":" in host else host
    endpoint = f"{parts.scheme}://{host_text}{port}{parts.path}"
    return endpoint, category


def _classify(target: str, strings: list[str], *, guarded: bool = False) -> tuple[str, str, str]:
    if guarded or target == "safe_urlopen":
        return "guarded_endpoint", "shared-runtime-egress-policy", ""
    for value in strings:
        endpoint, category = _safe_endpoint(value)
        if endpoint:
            policy = {
                "local_endpoint": "local-only",
                "private_endpoint": "blocked-unless-explicitly-reviewed",
                "public_endpoint": "public-egress-policy",
            }[category]
            return category, policy, endpoint
    return "configured_endpoint", "provider-or-connector-review", ""


@final
class _EgressVisitor(ast.NodeVisitor):
    def __init__(self, relative_file: str) -> None:
        self.relative_file = relative_file
        self.function_stack: list[str] = []
        self.calls: list[EgressCall] = []

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        _ = self.function_stack.pop()

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        target = _qualified_name(node.func)
        if _is_egress_target(target):
            guarded = target == "safe_urlopen" or (
                target.startswith("httpx.")
                and any(
                    isinstance(child, ast.Name)
                    and child.id in {"validate_httpx_request", "validate_httpx_request_async"}
                    for child in ast.walk(node)
                )
            )
            if self.relative_file.endswith("egress_policy.py") and target.startswith("urllib.request.urlopen"):
                guarded = True
            category, policy, endpoint = _classify(target, _literal_strings(node), guarded=guarded)
            self.calls.append(
                EgressCall(
                    file=self.relative_file,
                    line=node.lineno,
                    column=node.col_offset,
                    function=".".join(self.function_stack) or "<module>",
                    target=target,
                    category=category,
                    policy=policy,
                    endpoint=endpoint,
                )
            )
        self.generic_visit(node)


def audit_tree(root: Path) -> list[EgressCall]:
    calls: list[EgressCall] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        visitor = _EgressVisitor(path.relative_to(root.parent).as_posix())
        visitor.visit(tree)
        calls.extend(visitor.calls)
    return calls


def build_report(root: Path, calls: list[EgressCall]) -> dict[str, object]:
    summary = Counter(call.category for call in calls)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "files_scanned": len({call.file for call in calls}),
        "egress_call_count": len(calls),
        "summary": dict(sorted(summary.items())),
        "entries": [asdict(call) for call in calls],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory Python egress call sites without making network requests.")
    _ = parser.add_argument("--root", type=Path, default=Path("src/antigravity_k"))
    _ = parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = cast(Path, args.root).resolve()
    report = build_report(root, audit_tree(root))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    output = cast(Path | None, args.output)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        _ = output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    status = main()
    if status:
        raise SystemExit(status)
