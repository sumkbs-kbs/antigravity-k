"""Unit tests for LoRAPipeline DPO preference-pair builder (Unsloth gap closer)."""

from antigravity_k.engine.lora_pipeline import LoRAPipeline, PreferencePair


def _make_pipeline(tmp_path):
    return LoRAPipeline(harvest_dir=str(tmp_path / "harvest"), min_score=0.0)


class TestRecordPair:
    def test_records_valid_pair(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        ok = pipe.record_pair(
            prompt="버그 고쳐줘",
            chosen="고친 코드",
            rejected="안 고친 코드",
            chosen_score=0.9,
            rejected_score=0.4,
        )
        assert ok is True
        assert len(pipe._pairs) == 1

    def test_rejects_inverted_scores(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        assert pipe.record_pair("p", "c", "r", chosen_score=0.4, rejected_score=0.4) is False
        assert pipe.record_pair("p", "c", "r", chosen_score=0.3, rejected_score=0.5) is False

    def test_persistence_across_instances(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        pipe.record_pair("p", "chosen-text", "rejected-text", 0.8, 0.2)
        reloaded = LoRAPipeline(harvest_dir=str(tmp_path / "harvest"))
        assert len(reloaded._pairs) == 1
        assert reloaded._pairs[0].chosen == "chosen-text"


class TestBuildPreferencePairs:
    def test_extracts_pairs_from_scored_harvest(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        pipe.harvest("같은 질문", "좋은 답변", quality_score=0.95, task_type="coding")
        pipe.harvest("같은 질문", "나쁜 답변", quality_score=0.40, task_type="coding")
        added = pipe.build_preference_pairs(min_score_gap=0.15)
        assert added == 1
        pair = pipe._pairs[0]
        assert pair.chosen == "좋은 답변"
        assert pair.rejected == "나쁜 답변"
        assert pair.source == "quality_gate"

    def test_skips_small_gap(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        pipe.harvest("q", "a1", quality_score=0.80)
        pipe.harvest("q", "a2", quality_score=0.75)
        assert pipe.build_preference_pairs(min_score_gap=0.15) == 0

    def test_skips_single_entries(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        pipe.harvest("q", "only", quality_score=0.9)
        assert pipe.build_preference_pairs() == 0


class TestExportDpo:
    def test_exports_trl_format(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        pipe.record_pair("prompt-1", "good", "bad", 0.9, 0.3)
        stats = pipe.export_dpo_dataset(output_path=str(tmp_path / "dpo.jsonl"))
        assert stats["exported"] == 1
        content = (tmp_path / "dpo.jsonl").read_text(encoding="utf-8").strip()
        record = __import__("json").loads(content)
        assert set(record.keys()) == {"prompt", "chosen", "rejected"}
        assert record["chosen"] == "good"

    def test_empty_export(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        stats = pipe.export_dpo_dataset(output_path=str(tmp_path / "dpo.jsonl"))
        assert stats["exported"] == 0
        assert stats["total_pairs"] == 0


class TestDpoConfigGeneration:
    def test_mlx_platform_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "antigravity_k.engine.lora_pipeline.default_training_platform",
            lambda _host: "mlx",
        )
        pipe = _make_pipeline(tmp_path)
        config = pipe.generate_dpo_config(
            base_model="mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
            output_dir=str(tmp_path / "out"),
        )
        assert config["platform"] == "mlx"
        assert "--fine-tune-type dora" in config["command"]
        assert (tmp_path / "out" / "dpo_config.json").exists()

    def test_unsloth_platform_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "antigravity_k.engine.lora_pipeline.default_training_platform",
            lambda _host: "unsloth",
        )
        pipe = _make_pipeline(tmp_path)
        config = pipe.generate_dpo_config(output_dir=str(tmp_path / "out2"))
        assert config["platform"] == "unsloth"
        assert "DPOTrainer" in config["script"]
        assert "beta=0.1" in config["script"]


def test_preference_pair_to_dpo_format():
    pair = PreferencePair(
        prompt="p",
        chosen="c",
        rejected="r",
        chosen_score=0.9,
        rejected_score=0.2,
    )
    assert pair.to_dpo_format() == {"prompt": "p", "chosen": "c", "rejected": "r"}


class TestRunTraining:
    def test_missing_mlx_lm_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: False)
        pipe = _make_pipeline(tmp_path)
        res = pipe.run_training({"platform": "mlx", "command": "python -m mlx_lm.lora --train"})
        assert res.success is False
        assert "mlx-lm" in res.error

    def test_unsloth_platform_persists_script_and_fails_gracefully(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        out_dir = tmp_path / "gpu_out"
        res = pipe.run_training(
            {
                "platform": "unsloth",
                "output_dir": str(out_dir),
                "script": "from unsloth import FastLanguageModel\n",
            }
        )
        assert res.success is False
        assert (out_dir / "train_sft.py").exists()

    def test_unsloth_dpo_script_naming(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        out_dir = tmp_path / "gpu_out2"
        pipe.run_training(
            {
                "platform": "unsloth",
                "output_dir": str(out_dir),
                "script": "from trl import DPOTrainer\ntrainer.train()\n",
            }
        )
        assert (out_dir / "train_dpo.py").exists()

    def test_mlx_run_streams_logs_and_reports_success(self, tmp_path, monkeypatch):
        class FakeProc:
            returncode = 0

            def __init__(self):
                self.stdout = iter(["iter 1: loss=2.0\n", "iter 2: loss=1.5\n"])

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def wait(self):
                return 0

            def poll(self):
                return None

        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.subprocess.Popen", lambda *a, **k: FakeProc())
        pipe = _make_pipeline(tmp_path)
        logs: list[str] = []
        res = pipe.run_training(
            {"platform": "mlx", "command": "python -m mlx_lm.lora --train"},
            on_log=logs.append,
        )
        assert res.success is True
        assert len(logs) == 2
        assert res.log_tail[-1] == "iter 2: loss=1.5"

    def test_mlx_run_failure_captures_exit_code(self, tmp_path, monkeypatch):
        class FailingProc:
            returncode = 1

            def __init__(self):
                self.stdout = iter(["error: OOM\n"])

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def wait(self):
                return 1

            def poll(self):
                return None

        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.subprocess.Popen", lambda *a, **k: FailingProc())
        pipe = _make_pipeline(tmp_path)
        res = pipe.run_training({"platform": "mlx", "command": "python -m mlx_lm.lora"})
        assert res.success is False
        assert res.exit_code == 1
        assert any("OOM" in line for line in res.log_tail)

    def test_empty_command_rejected(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        res = pipe.run_training({"platform": "mlx"})
        assert res.success is False
        assert "command" in res.error
