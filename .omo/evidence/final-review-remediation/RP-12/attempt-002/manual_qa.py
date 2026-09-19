from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from antigravity_k.config import config as app_config
from antigravity_k.engine.audit_db import AuditDb
from antigravity_k.tools.egress_policy import EgressPolicyError
from antigravity_k.tools.media_gen_tools import _download_asset
from antigravity_k.tools.ssak_search_client import search
from antigravity_k.tools.system_tools import RunBashCommandTool


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rp12-manual-") as directory:
        root = Path(directory)

        database = AuditDb().init(str(root))
        database.insert(None, "safe", None, "tool", "{}")
        assert len(database.query_recent(kind="safe")) == 1
        assert database.query_recent(kind="' OR 1=1 --") == []
        database.close()
        print("PASS sql-bound-values: injection payload returned zero rows")

        with patch("antigravity_k.tools.egress_policy.urllib.request.urlopen") as raw_open:
            assert search("secret", base_url="file:///etc/passwd") == []
            raw_open.assert_not_called()
        print("PASS search-scheme: file URL rejected before urllib open")

        destination = root / "asset.bin"
        try:
            _download_asset("file:///etc/passwd", str(destination))
        except EgressPolicyError:
            pass
        else:
            raise AssertionError("media asset downloader accepted file URL")
        assert not destination.exists()
        print("PASS media-scheme: file URL rejected without destination write")

        sentinel = root / "raw-shell-ran"
        previous = app_config.security.sandbox_enabled
        app_config.security.sandbox_enabled = False
        try:
            result = RunBashCommandTool()._run_with_sandbox(f"touch {sentinel}")
        finally:
            app_config.security.sandbox_enabled = previous
        assert result.startswith("Error: run_bash_command requires an enabled OS sandbox")
        assert not sentinel.exists()
        print("PASS shell-boundary: disabled sandbox refused command without side effect")


if __name__ == "__main__":
    main()
