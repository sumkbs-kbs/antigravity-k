"""Tests for AgentArchive (agent_archive.py)."""

import tempfile
from pathlib import Path

import pytest

from antigravity_k.engine.agent_archive import AgentArchive, AgentVariant


@pytest.fixture
def archive():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield AgentArchive(archive_dir=tmpdir)


@pytest.fixture
def variant():
    return AgentVariant(
        variant_id="v1",
        generation=0,
        parent_id="",
        system_prompt_hash="abc123",
        system_prompt_snippet="You are a helpful assistant",
        benchmark_score=0.85,
        mutation_type="prompt",
        mutation_description="Initial prompt",
        improvement_delta=0.0,
    )


class TestAgentVariant:
    def test_to_dict(self):
        v = AgentVariant(variant_id="v1", generation=0)
        d = v.to_dict()
        assert d["variant_id"] == "v1"
        assert d["generation"] == 0

    def test_from_dict(self):
        data = {"variant_id": "v1", "generation": 1, "benchmark_score": 0.9}
        v = AgentVariant.from_dict(data)
        assert v.variant_id == "v1"
        assert v.generation == 1
        assert v.benchmark_score == 0.9

    def test_from_dict_filters_unknown_fields(self):
        data = {"variant_id": "v1", "generation": 0, "unknown_field": "ignored"}
        v = AgentVariant.from_dict(data)
        assert not hasattr(v, "unknown_field")


class TestAgentArchive:
    def test_init_creates_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir) / "subdir"
            AgentArchive(archive_dir=str(archive_dir))
            assert archive_dir.exists()

    def test_archive_first_variant(self, archive, variant):
        assert archive.archive(variant) is True
        assert archive.get("v1") is not None

    def test_archive_rejects_worse_variant(self, archive, variant):
        archive.archive(variant)
        worse = AgentVariant(
            variant_id="v2",
            generation=1,
            parent_id="v1",
            benchmark_score=0.5,
            improvement_delta=0.0,
            mutation_type="prompt",
        )
        assert archive.archive(worse) is False

    def test_archive_accepts_improved_variant(self, archive, variant):
        archive.archive(variant)
        better = AgentVariant(
            variant_id="v2",
            generation=1,
            parent_id="v1",
            benchmark_score=0.95,
            improvement_delta=0.1,
            mutation_type="prompt",
            mutation_description="Improved",
        )
        assert archive.archive(better) is True

    def test_get_nonexistent(self, archive):
        assert archive.get("nonexistent") is None

    def test_get_best(self, archive, variant):
        archive.archive(variant)
        better = AgentVariant(variant_id="v2", generation=1, benchmark_score=0.95, mutation_type="sampling")
        archive.archive(better)
        best = archive.get_best()
        assert best is not None
        assert best.variant_id == "v2"

    def test_get_best_empty(self, archive):
        assert archive.get_best() is None

    def test_get_latest(self, archive, variant):
        archive.archive(variant)
        v2 = AgentVariant(variant_id="v2", generation=1, benchmark_score=0.9, mutation_type="code")
        archive.archive(v2)
        latest = archive.get_latest()
        assert latest is not None
        assert latest.variant_id == "v2"

    def test_advance_generation(self, archive):
        assert archive.advance_generation() == 1
        assert archive.advance_generation() == 2

    def test_lineage(self, archive, variant):
        archive.archive(variant)
        v2 = AgentVariant(variant_id="v2", generation=1, parent_id="v1", benchmark_score=0.9, mutation_type="sampling")
        archive.archive(v2)
        chain = archive.lineage("v2")
        assert len(chain) == 2
        assert chain[0].variant_id == "v2"
        assert chain[1].variant_id == "v1"

    def test_lineage_missing(self, archive):
        chain = archive.lineage("nonexistent")
        assert chain == []

    def test_lineage_markdown_no_variant(self, archive):
        md = archive.lineage_markdown("")
        assert "비어" in md

    def test_lineage_markdown_with_variant(self, archive, variant):
        archive.archive(variant)
        md = archive.lineage_markdown("v1")
        assert "v1" in md
        assert "Gen" in md

    def test_crossover(self, archive, variant):
        archive.archive(variant)
        v2 = AgentVariant(
            variant_id="v2",
            generation=1,
            benchmark_score=0.9,
            mutation_type="sampling",
            few_shot_examples=["example1"],
            sampling_profiles={"creative": {"temp": 0.8}},
        )
        archive.archive(v2)
        child = archive.crossover("v1", "v2")
        assert child is not None
        assert child.mutation_type == "crossover"
        assert "v1" in child.parent_id
        assert "v2" in child.parent_id

    def test_crossover_missing_parent(self, archive):
        assert archive.crossover("nonexistent", "v2") is None

    def test_stats_empty(self, archive):
        stats = archive.stats()
        assert stats["total"] == 0

    def test_stats_with_data(self, archive, variant):
        archive.archive(variant)
        stats = archive.stats()
        assert stats["total"] >= 1
        assert stats["active"] >= 1
        assert "best_score" in stats

    def test_max_archive_size_enforced(self, archive):
        for i in range(60):
            v = AgentVariant(
                variant_id=f"v{i}",
                generation=i,
                benchmark_score=0.5 + (i * 0.01),
                mutation_type="prompt",
            )
            archive.archive(v)
        assert len([x for x in archive._variants if not x.retired]) <= archive.MAX_ARCHIVE_SIZE
