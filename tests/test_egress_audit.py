from pathlib import Path

from scripts.audit_egress import audit_tree, build_report


def test_audit_tree_classifies_local_public_and_configured_endpoints(tmp_path: Path):
    source = tmp_path / "sample.py"
    _ = source.write_text(
        (
            "import httpx\n"
            "from urllib.request import urlopen\n"
            "from antigravity_k.tools.egress_policy import safe_urlopen\n"
            "\n"
            "def fetch(endpoint):\n"
            "    httpx.get(endpoint)\n"
            '    httpx.get("http://localhost:8080/health")\n'
            '    urlopen("https://example.com/path?token=secret")\n'
            '    safe_urlopen("http://localhost:11434/api/tags")\n'
        ),
        encoding="utf-8",
    )

    calls = audit_tree(tmp_path)
    report = build_report(tmp_path, calls)

    assert len(calls) == 4
    assert report["egress_call_count"] == 4
    assert {call.category for call in calls} == {
        "configured_endpoint",
        "guarded_endpoint",
        "local_endpoint",
        "public_endpoint",
    }
    public_call = next(call for call in calls if call.category == "public_endpoint")
    assert public_call.endpoint == "https://example.com/path"
    assert "secret" not in public_call.endpoint
