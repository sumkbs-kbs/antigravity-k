"""Phase 58: lora_pipeline 커버리지 보강 — 예외/폴백/기타 분기.

Phase 25 이후 추가된 기능(레시피·문서 옵션·Unsloth 스크립트 저장·학습 실행)의
예외 경로와 폴백 분기를 잠가 90%+ 커버리지를 달성한다.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import final

from _pytest.monkeypatch import MonkeyPatch

from antigravity_k.engine.data_recipes import get_recipe
from antigravity_k.engine.lora_pipeline import HarvestEntry, LoRAPipeline


def _make_pipeline(tmp_path: Path) -> LoRAPipeline:
    return LoRAPipeline(harvest_dir=str(tmp_path / "harvest"), min_score=0.0)


@final
class _RaisingProc:
    """Popen 생성 시 OSError를 던지는 더블 — 시작 실패 경로용."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise OSError("spawn blocked by test")


@final
class _ChattyProc:
    """51줄 이상 흘려보내 tail.pop(0) 회전을 강제하는 더블."""

    returncode: int = 0

    def __init__(self) -> None:
        self.stdout: Iterator[str] = iter(f"line {i}\n" for i in range(1, 55))

    def __enter__(self) -> "_ChattyProc":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def wait(self) -> int:
        return 0

    def poll(self) -> int | None:
        return None


class TestHarvestEdges:
    def test_below_threshold_rejected(self, tmp_path: Path) -> None:
        pipe = LoRAPipeline(harvest_dir=str(tmp_path / "h"), min_score=0.9)
        assert pipe.harvest("q", "a", quality_score=0.5) is False

    def test_max_harvest_size_rejects(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        monkeypatch.setattr(LoRAPipeline, "MAX_HARVEST_SIZE", 2, raising=False)
        assert pipe.harvest("q1", "a1", quality_score=0.5) is True
        assert pipe.harvest("q2", "a2", quality_score=0.5) is True
        assert pipe.harvest("q3", "a3", quality_score=0.5) is False
        assert pipe.stats()["total"] == 2

    def test_exact_duplicate_rejected(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        assert pipe.harvest("same question", "identical answer body", quality_score=0.5) is True
        assert pipe.harvest("same question", "identical answer body", quality_score=0.5) is False

    def test_corrupt_harvest_file_tolerated(self, tmp_path: Path) -> None:
        hdir = tmp_path / "h2"
        hdir.mkdir()
        (hdir / "harvest.jsonl").write_text('{broken json\n{"ok": true}\n', encoding="utf-8")
        pipe = LoRAPipeline(harvest_dir=str(hdir), min_score=0.0)  # 예외가 조용히 흡수된다
        assert pipe.stats()["total"] == 0

    def test_unwritable_harvest_file_keeps_entry(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        real_open = open

        def broken_open(file: object, *args: object, **kwargs: object) -> object:
            if str(file).endswith("harvest.jsonl"):
                raise OSError("disk full")
            return real_open(file, *args, **kwargs)  # type: ignore[arg-type]

        import builtins

        monkeypatch.setattr(builtins, "open", broken_open)
        assert pipe.harvest("q", "a", quality_score=0.5) is True  # 메모리엔 남는다
        assert pipe.stats()["total"] == 1

    def test_load_skips_blank_lines(self, tmp_path: Path) -> None:
        hdir = tmp_path / "h3"
        hdir.mkdir()
        entry = HarvestEntry(
            user_request="q",
            agent_output="a",
            quality_score=0.5,
            quality_grade="",
            task_type="general",
            model_used="",
            timestamp=0.0,
            word_count=1,
            metadata={},
        )
        # 로더는 전체 필드를 요구한다 — 부분 레코드는 줄 단위가 아니라
        # 로드 전체를 중단시킨다 (문서화된 동작). 완전 레코드로 검증.
        payload = json.dumps(asdict(entry))
        (hdir / "harvest.jsonl").write_text("\n\n" + payload + "\n", encoding="utf-8")
        pipe = LoRAPipeline(harvest_dir=str(hdir), min_score=0.0)
        assert pipe.stats()["total"] == 1  # 빈 줄은 건너뛰고 유효 줄만 로드


class TestExportFormats:
    def test_instruction_format_export(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        _ = pipe.harvest("q1", "answer one", quality_score=0.5)
        out = tmp_path / "export.jsonl"
        stats = pipe.export_dataset(str(out), format="instruction")
        assert stats["format"] == "instruction"
        record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert record["instruction"] == "q1"
        assert record["output"] == "answer one"

    def test_export_empty_harvest(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        out = tmp_path / "empty.jsonl"
        stats = pipe.export_dataset(str(out))
        assert stats["exported"] == 0
        assert stats["avg_score"] == 0


class TestGenerateConfig:
    def test_unsloth_platform_config(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        config = pipe.generate_config(
            base_model="org/model",
            dataset_path="data/ds.jsonl",
            output_dir=str(tmp_path / "cfg"),
            platform="unsloth",
        )
        assert config["platform"] == "unsloth"
        assert (tmp_path / "cfg" / "lora_config.json").exists()


class TestRunTrainingCoverage:
    def test_popen_failure_returns_error(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.subprocess.Popen", _RaisingProc)
        pipe = _make_pipeline(tmp_path)
        res = pipe.run_training({"platform": "mlx", "command": "python -m mlx_lm.lora"})
        assert res.success is False
        assert "프로세스 시작 실패" in res.error

    def test_log_tail_rotates_beyond_50_lines(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.subprocess.Popen", lambda *a, **k: _ChattyProc())
        pipe = _make_pipeline(tmp_path)
        logs: list[str] = []
        res = pipe.run_training(
            {"platform": "mlx", "command": "python -m mlx_lm.lora"},
            on_log=logs.append,
        )
        assert res.success is True
        assert len(logs) == 54  # 콜백은 전부 받는다
        assert len(res.log_tail) == 50  # tail은 50으로 회전
        assert res.log_tail[0] == "line 5"  # 앞 4줄은 pop 됨
        assert res.log_tail[-1] == "line 54"

    def test_unsloth_script_write_failure_returns_none(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr(
            "antigravity_k.engine.lora_pipeline.Path.write_text",
            lambda *a, **k: (_ for _ in ()).throw(OSError("read-only fs")),
        )
        pipe = _make_pipeline(tmp_path)
        res = pipe.run_training({"platform": "unsloth", "output_dir": str(tmp_path / "out"), "script": "x = 1\n"})
        assert res.success is False
        assert "None" in res.error  # 스크립트 저장 실패가 결과에 반영됨


class TestPairsEdges:
    def test_corrupt_pairs_file_tolerated(self, tmp_path: Path) -> None:
        hdir = tmp_path / "h4"
        hdir.mkdir()
        (hdir / "pairs.jsonl").write_text("not json at all\n", encoding="utf-8")
        pipe = LoRAPipeline(harvest_dir=str(hdir), min_score=0.0)
        assert pipe.pairs == []

    def test_unwritable_pairs_file_keeps_pair(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        real_open = open

        def broken_open(file: object, *args: object, **kwargs: object) -> object:
            if str(file).endswith("pairs.jsonl"):
                raise OSError("disk full")
            return real_open(file, *args, **kwargs)  # type: ignore[arg-type]

        import builtins

        monkeypatch.setattr(builtins, "open", broken_open)
        ok = pipe.record_pair("p", "c", "r", chosen_score=0.9, rejected_score=0.4)
        assert ok is True
        assert len(pipe.pairs) == 1

    def test_identical_outputs_skip_pair_building(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        _ = pipe.harvest("dup", "same output text", quality_score=0.9)
        _ = pipe.harvest("dup", "same output text", quality_score=0.2)
        # 중복 정책상 두 번째 harvest가 거부되므로 그룹에 1건 — 쌍 없음
        assert pipe.build_preference_pairs() == 0


class TestStatsAndClear:
    def test_stats_empty_and_filled(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        assert pipe.stats() == {"total": 0, "message": "수확 데이터 없음"}
        _ = pipe.harvest("q1", "a1", quality_score=0.5, task_type="coding")
        _ = pipe.harvest("q2", "a2", quality_score=0.7, task_type="coding")
        stats = pipe.stats()
        assert stats["total"] == 2
        assert stats["by_task_type"] == {"coding": 2}
        assert stats["avg_score"] == 0.6

    def test_clear_removes_file(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        _ = pipe.harvest("q", "a", quality_score=0.5)
        assert pipe.stats()["total"] == 1
        pipe.clear()
        assert pipe.stats()["total"] == 0


class TestApplyRecipeOverrides:
    def test_user_overrides_win_over_recipe(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        # 소스 없이 harvest 경로 사용 — 데이터 없이도 config 병합 로직만 검증
        monkeypatch.setattr(
            "antigravity_k.engine.data_recipes.load_records_from_source",
            lambda *_a, **_k: [],
        )
        pipe = _make_pipeline(tmp_path)
        recipe = get_recipe("chat-sft")
        result = pipe.apply_recipe(
            recipe_name="chat-sft",
            base_model="org/model",
            output_dir=str(tmp_path / "recipe-out"),
            source="",
            hyperparameter_overrides={"epochs": 7, "custom_flag": "on"},
        )
        config = result["config"]
        assert isinstance(config, dict)
        hyper = config["hyperparameters"]
        assert isinstance(hyper, dict)
        assert hyper["epochs"] == 7  # 사용자 지정이 레시피 기본을 이긴다
        assert hyper["custom_flag"] == "on"
        assert result["sufficient"] is False  # 레코드 0건 — min_records 미달
        assert result["recipe"] == recipe.name


class TestFuseAndOllamaServe:
    def test_resolve_local_model_path_existing_dir(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "my_local_model"
        model_dir.mkdir()
        resolved = LoRAPipeline.resolve_local_model_path(str(model_dir))
        assert resolved == str(model_dir.resolve())

    def test_resolve_local_model_path_hf_cache(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        fake_cache = tmp_path / ".cache" / "huggingface" / "hub" / "models--test--model" / "snapshots"
        snap1 = fake_cache / "snap1"
        snap2 = fake_cache / "snap2"
        snap1.mkdir(parents=True)
        snap2.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        resolved = LoRAPipeline.resolve_local_model_path("test/model")
        assert resolved in (str(snap1.resolve()), str(snap2.resolve()))

    def test_resolve_local_model_path_fallback(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert LoRAPipeline.resolve_local_model_path("unknown/remote-model") == "unknown/remote-model"

    def test_fuse_adapter_missing_mlx_lm(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: False)
        res = pipe.fuse_adapter("base", str(tmp_path / "ad"), str(tmp_path / "merged"))
        assert res.success is False
        assert "mlx-lm 미설치" in res.error

    def test_fuse_adapter_missing_adapter_dir(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        res = pipe.fuse_adapter("base", str(tmp_path / "nonexistent_adapters"), str(tmp_path / "merged"))
        assert res.success is False
        assert "어댑터 경로를 찾을 수 없습니다" in res.error

    def test_fuse_adapter_success(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        adapter_dir = tmp_path / "adapters"
        adapter_dir.mkdir()
        merged_dir = tmp_path / "merged"
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        import subprocess

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _ChattyProc())
        logs: list[str] = []
        res = pipe.fuse_adapter("base", str(adapter_dir), str(merged_dir), de_quantize=True, on_log=logs.append)
        assert res.success is True
        assert res.exit_code == 0
        assert "--de-quantize" in res.command
        assert len(logs) > 50

    def test_create_modelfile(self, tmp_path: Path) -> None:
        out_mf = tmp_path / "Modelfile"
        mf = LoRAPipeline.create_modelfile(
            model_path="/path/to/model.gguf",
            output_path=out_mf,
            system_prompt="You are Ssak-Ai.",
            stop_tokens=["<|endoftext|>"],
        )
        assert mf.exists()
        content = mf.read_text(encoding="utf-8")
        assert "FROM /path/to/model.gguf" in content
        assert 'SYSTEM """You are Ssak-Ai."""' in content
        assert 'PARAMETER stop "<|endoftext|>"' in content

    def test_register_ollama_missing_modelfile(self, tmp_path: Path) -> None:
        pipe = _make_pipeline(tmp_path)
        res = pipe.register_ollama("test:model", tmp_path / "missing_Modelfile")
        assert res["success"] is False
        assert "Modelfile을 찾을 수 없습니다" in str(res["error"])

    def test_register_ollama_no_binary(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        mf = tmp_path / "Modelfile"
        mf.write_text("FROM foo\n", encoding="utf-8")
        import shutil

        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        res = pipe.register_ollama("test:model", mf)
        assert res["success"] is False
        assert "ollama CLI" in str(res["error"])

    def test_register_ollama_success(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        mf = tmp_path / "Modelfile"
        mf.write_text("FROM foo\n", encoding="utf-8")
        import shutil
        import subprocess

        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/ollama")
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _ChattyProc())
        res = pipe.register_ollama("test:model", mf)
        assert res["success"] is True
        assert res["model_name"] == "test:model"

    def test_fuse_and_register_ollama_e2e_flow(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        pipe = _make_pipeline(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        adapter_dir = tmp_path / "adapters"
        adapter_dir.mkdir()
        from antigravity_k.engine.lora_pipeline import TrainingRunResult

        monkeypatch.setattr(
            pipe,
            "fuse_adapter",
            lambda **k: TrainingRunResult(success=True, exit_code=0),
        )
        monkeypatch.setattr(
            pipe,
            "register_ollama",
            lambda model_name, modelfile_path, on_log=None: {"success": True, "model_name": model_name, "error": ""},
        )
        result = pipe.fuse_and_register_ollama(
            base_model="base-model",
            adapter_path=adapter_dir,
            output_dir=out_dir,
            ollama_model_name="ssak:test",
            skip_fuse=True,
        )
        assert result["success"] is True
        assert result["ollama_model_name"] == "ssak:test"
        assert Path(result["modelfile_path"]).exists()
