import json
from pathlib import Path

import pytest

from antigravity_k.engine.memory_provider import MemoryManager
from antigravity_k.engine.project_memory import ProjectMemoryProvider
from antigravity_k.engine.project_memory_keys import canonical_project_key


def _write_project_aliases(project_root: Path, aliases: dict[str, list[str]]) -> None:
    memory_dir = project_root / ".antigravity" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "project_aliases.json").write_text(
        json.dumps({"aliases": aliases}),
        encoding="utf-8",
    )


def test_project_decision_aliases_share_one_latest_value(tmp_path: Path) -> None:
    # Given: one project records the same database decision through two common keys.
    project_root = tmp_path / "project"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: db_engine=postgresql", "stored")

    # When: a later turn uses the canonical key with a new value.
    provider.sync_turn("프로젝트 결정: database=sqlite", "stored")

    # Then: recall exposes one canonical latest decision.
    recalled = provider.prefetch("database")
    assert recalled.count("[project:decision:database]") == 1
    assert "sqlite" in recalled
    assert "db_engine" not in recalled
    assert "postgresql" not in recalled


def test_legacy_project_aliases_migrate_by_observation_time(tmp_path: Path) -> None:
    # Given: an older store contains conflicting canonical and alias keys.
    project_root = tmp_path / "project"
    memory_dir = project_root / ".antigravity" / "memory"
    memory_dir.mkdir(parents=True)
    path = memory_dir / "project_facts.json"
    path.write_text(
        json.dumps(
            {
                "decision:database": {
                    "kind": "decision",
                    "value": "postgresql",
                    "observed_at": 1.0,
                },
                "decision:dbms": {
                    "kind": "decision",
                    "value": "sqlite",
                    "observed_at": 2.0,
                },
            },
        ),
        encoding="utf-8",
    )

    # When: a new provider loads the legacy store.
    provider = ProjectMemoryProvider(project_root)

    # Then: the latest record is persisted under the canonical key only.
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert provider.prefetch("database").endswith("[project:decision:database] sqlite")
    assert tuple(stored) == ("decision:database",)


def test_current_alias_correction_wins_before_turn_sync(tmp_path: Path) -> None:
    # Given: durable project memory contains an older canonical decision.
    project_root = tmp_path / "project"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: database=postgresql", "stored")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(provider)

    # When: the current request corrects it through a common alias.
    recalled = manager.prefetch_all("프로젝트 결정: dbms=sqlite")

    # Then: the model sees only the current canonical value before persistence.
    assert "[resolved:project:decision:database source=current_user scope=project] sqlite" in recalled
    assert "postgresql" not in recalled


def test_typed_metadata_uses_the_same_project_key_aliases(tmp_path: Path) -> None:
    # Given: typed metadata uses a package-manager alias.
    project_root = tmp_path / "project"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)

    # When: the structured turn is synchronized.
    provider.sync_turn(
        "record configuration",
        "stored",
        metadata={"project_memory_facts": {"decisions": {"pkg_manager": "uv"}}},
    )

    # Then: export exposes the canonical key used by normal turns.
    assert provider.export("project")[0]["key"] == "package_manager"


def test_project_key_canonicalization_preserves_kind_and_unknown_keys(tmp_path: Path) -> None:
    # Given: one alias is used for different fact kinds and one key is project-specific.
    project_root = tmp_path / "project"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: db=postgresql", "stored")
    provider.sync_turn("프로젝트 사실: db=managed", "stored")

    # When: project memory is recalled and an unknown key crosses the canonicalizer.
    recalled = provider.prefetch("database")
    custom_key = canonical_project_key("billing_database")

    # Then: decision/fact remain distinct and unknown keys are not guessed into an alias group.
    assert "[project:decision:database] postgresql" in recalled
    assert "[project:fact:database] managed" in recalled
    assert custom_key == "billing_database"


def test_authoritative_project_question_resolves_without_tools(tmp_path: Path) -> None:
    # Given: the project manager owns one canonical database decision.
    project_root = tmp_path / "project"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: dbms=sqlite", "stored")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(provider)

    # When: the user asks only for the remembered project decision.
    fact = manager.authoritative_project_fact_for_query(
        "현재 프로젝트에서 사용하기로 결정한 데이터베이스 이름만 답해줘.",
    )

    # Then: one typed authoritative fact is available for direct response routing.
    assert fact is not None
    assert fact.key == "project:decision:database"
    assert fact.value == "sqlite"


def test_project_mutation_request_does_not_use_memory_only_routing(tmp_path: Path) -> None:
    # Given: the project manager owns an existing database decision.
    project_root = tmp_path / "project"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: database=postgresql", "stored")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(provider)

    # When: the user asks to change implementation rather than recall the value.
    fact = manager.authoritative_project_fact_for_query("현재 프로젝트 데이터베이스를 SQLite로 바꿔줘")

    # Then: the normal agent/tool loop remains responsible for the request.
    assert fact is None


def test_project_switch_request_does_not_use_memory_only_routing(tmp_path: Path) -> None:
    # Given: the project manager owns an existing database decision.
    project_root = tmp_path / "project"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: database=postgresql", "stored")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(provider)

    # When: a current-state phrase is part of a migration request.
    fact = manager.authoritative_project_fact_for_query(
        "현재 프로젝트 데이터베이스를 SQLite로 전환하고 마이그레이션해줘",
    )

    # Then: presence of 'current' cannot misroute a mutation as memory recall.
    assert fact is None


def test_custom_project_aliases_share_one_latest_value(tmp_path: Path) -> None:
    # Given: project configuration maps two domain keys to the database decision.
    project_root = tmp_path / "project"
    _write_project_aliases(project_root, {"database": ["primary_db", "storage_backend"]})
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: primary_db=postgresql", "stored")

    # When: a later turn uses the second configured alias.
    provider.sync_turn("프로젝트 결정: storage_backend=sqlite", "stored")

    # Then: one canonical latest decision is recalled and exported.
    recalled = provider.prefetch("database")
    assert recalled.endswith("[project:decision:database] sqlite")
    assert provider.export("project")[0]["key"] == "database"


def test_custom_aliases_migrate_legacy_store_by_observation_time(tmp_path: Path) -> None:
    # Given: alias configuration and a legacy store contain two keys for one decision.
    project_root = tmp_path / "project"
    _write_project_aliases(project_root, {"database": ["primary_db"]})
    path = project_root / ".antigravity" / "memory" / "project_facts.json"
    path.write_text(
        json.dumps(
            {
                "decision:database": {
                    "kind": "decision",
                    "value": "postgresql",
                    "observed_at": 1.0,
                },
                "decision:primary_db": {
                    "kind": "decision",
                    "value": "sqlite",
                    "observed_at": 2.0,
                },
            },
        ),
        encoding="utf-8",
    )

    # When: a provider restarts with the project alias schema.
    provider = ProjectMemoryProvider(project_root)

    # Then: the persisted store contains only the latest canonical record.
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert provider.prefetch("database").endswith("[project:decision:database] sqlite")
    assert tuple(stored) == ("decision:database",)


def test_current_custom_alias_correction_wins_before_sync(tmp_path: Path) -> None:
    # Given: durable project memory contains the old canonical decision.
    project_root = tmp_path / "project"
    _write_project_aliases(project_root, {"database": ["primary_db"]})
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: database=postgresql", "stored")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(provider)

    # When: the current request corrects it through a configured alias.
    recalled = manager.prefetch_all("프로젝트 결정: primary_db=sqlite")

    # Then: only the current canonical value reaches the model before persistence.
    assert "[resolved:project:decision:database source=current_user scope=project] sqlite" in recalled
    assert "postgresql" not in recalled


def test_custom_alias_read_query_resolves_authoritative_fact(tmp_path: Path) -> None:
    # Given: a project config names its database decision primary_db.
    project_root = tmp_path / "project"
    _write_project_aliases(project_root, {"database": ["primary_db"]})
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: primary_db=sqlite", "stored")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(provider)

    # When: the user asks only for that project-specific key.
    fact = manager.authoritative_project_fact_for_query("현재 프로젝트 primary_db 결정이 뭐야?")

    # Then: direct response routing receives the canonical authoritative fact.
    assert fact is not None
    assert fact.key == "project:decision:database"
    assert fact.value == "sqlite"


def test_custom_alias_schema_isolated_per_project(tmp_path: Path) -> None:
    # Given: two projects assign the same alias to different canonical decisions.
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    _write_project_aliases(project_a, {"database": ["primary_store"]})
    _write_project_aliases(project_b, {"cache_backend": ["primary_store"]})
    provider_a = ProjectMemoryProvider(project_a)
    provider_b = ProjectMemoryProvider(project_b)

    # When: both projects persist a decision through their local alias.
    provider_a.sync_turn("프로젝트 결정: primary_store=postgresql", "stored")
    provider_b.sync_turn("프로젝트 결정: primary_store=redis", "stored")

    # Then: each project exposes only its own canonical meaning.
    assert "[project:decision:database] postgresql" in provider_a.prefetch("store")
    assert "cache_backend" not in provider_a.prefetch("store")
    assert "[project:decision:cache_backend] redis" in provider_b.prefetch("store")
    assert "database" not in provider_b.prefetch("store")


@pytest.mark.parametrize(
    "aliases",
    (
        {"database": ["primary_store"], "cache_backend": ["primary_store"]},
        {"cache_backend": ["db"]},
        {"cache_backend": ["database"]},
        {"primary_store": ["cache_backend"], "cache_backend": ["other_store"]},
    ),
)
def test_invalid_custom_alias_schema_fails_closed(tmp_path: Path, aliases: dict[str, list[str]]) -> None:
    # Given: a project alias schema is ambiguous or attempts to redefine a built-in key.
    project_root = tmp_path / "project"
    _write_project_aliases(project_root, aliases)

    # When / Then: provider startup rejects the unsafe schema.
    with pytest.raises(ValueError, match="alias"):
        ProjectMemoryProvider(project_root)


def test_malformed_custom_alias_schema_fails_closed(tmp_path: Path) -> None:
    # Given: the project alias file is not valid JSON.
    project_root = tmp_path / "project"
    memory_dir = project_root / ".antigravity" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "project_aliases.json").write_text("{not-json", encoding="utf-8")

    # When / Then: provider startup reports the invalid boundary instead of ignoring it.
    with pytest.raises(ValueError, match="alias"):
        ProjectMemoryProvider(project_root)


def test_custom_alias_file_rejects_symlink_escape(tmp_path: Path) -> None:
    # Given: the project alias file redirects to configuration outside the workspace.
    project_root = tmp_path / "project"
    outside = tmp_path / "outside-aliases.json"
    memory_dir = project_root / ".antigravity" / "memory"
    memory_dir.mkdir(parents=True)
    outside.write_text(json.dumps({"aliases": {"database": ["primary_db"]}}), encoding="utf-8")
    (memory_dir / "project_aliases.json").symlink_to(outside)

    # When / Then: provider startup rejects the escaped configuration boundary.
    with pytest.raises(ValueError, match="alias"):
        ProjectMemoryProvider(project_root)


def test_project_purge_preserves_alias_configuration(tmp_path: Path) -> None:
    # Given: project memory uses an operator alias and contains one decision.
    project_root = tmp_path / "project"
    _write_project_aliases(project_root, {"database": ["primary_db"]})
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: primary_db=postgresql", "stored")

    # When: the project memory value is purged.
    deleted = provider.clear("project")

    # Then: data is gone but a restarted provider still applies the project configuration.
    restarted = ProjectMemoryProvider(project_root)
    restarted.sync_turn("프로젝트 결정: primary_db=sqlite", "stored")
    assert deleted == 1
    assert restarted.prefetch("database").endswith("[project:decision:database] sqlite")


def test_typed_metadata_uses_custom_project_aliases(tmp_path: Path) -> None:
    # Given: project configuration defines an alias used by structured metadata.
    project_root = tmp_path / "project"
    _write_project_aliases(project_root, {"database": ["primary_db"]})
    provider = ProjectMemoryProvider(project_root)

    # When: the typed turn stores a decision through that alias.
    provider.sync_turn(
        "record configuration",
        "stored",
        metadata={"project_memory_facts": {"decisions": {"primary_db": "sqlite"}}},
    )

    # Then: export uses the same canonical key as normal-turn storage.
    assert provider.export("project")[0]["key"] == "database"
