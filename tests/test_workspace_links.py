"""Tests for workspace_links module."""

from antigravity_k.api.routes.workspace_links import _generate_links_for_path


class TestGenerateLinksForPath:
    def test_basic_structure(self):
        result = _generate_links_for_path("/home/user/project", "Main")
        assert result["name"] == "Main"
        assert result["path"] == "/home/user/project"
        assert "vscode" in result["links"]
        assert "jetbrains_intellij" in result["links"]
        assert "jetbrains_pycharm" in result["links"]
        assert "jetbrains_goland" in result["links"]
        assert "jetbrains_webstorm" in result["links"]

    def test_vscode_link(self):
        result = _generate_links_for_path("/my/project", "Test")
        assert result["links"]["vscode"] == "vscode://file/my/project"

    def test_jetbrains_link_contains_encoded_path(self):
        result = _generate_links_for_path("/path/with spaces", "Spaces")
        # path should be URL-encoded
        assert "%20" in result["links"]["jetbrains_intellij"]

    def test_jetbrains_link_has_project_param(self):
        result = _generate_links_for_path("/test", "T")
        assert "projectPath=" in result["links"]["jetbrains_intellij"]
