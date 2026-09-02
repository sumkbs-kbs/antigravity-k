"""Antigravity-K: LoRA 파인튜닝 파이프라인.

========================================
QualityGate A등급 응답을 자동 수확하여 도메인 특화 LoRA 학습 데이터를 구축하고,
Unsloth/mlx-lm 기반 파인튜닝 설정을 자동 생성합니다.

핵심 아이디어:
  - 시스템이 스스로 "좋은 답변"을 수확하여 자가 개선 데이터셋을 구축
  - 별도의 라벨링 없이 QualityGate가 라벨러 역할을 담당
  - Apple Silicon 환경에서 mlx-lm LoRA, GPU 서버에서 Unsloth QLoRA 지원

사용법:
    pipeline = LoRAPipeline(quality_gate, harvest_dir="data/lora_harvest")
    pipeline.harvest(user_request, agent_output, quality_score)  # 자동 수확
    pipeline.export_dataset("data/lora_dataset.jsonl")           # 학습 데이터 내보내기
    pipeline.generate_config("mistral-small-24b")                # 학습 설정 생성
"""

from __future__ import annotations

import importlib.util
import json
import logging
import shlex
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TextIO, TypeAlias, cast, final

from antigravity_k.engine.provider_adapters.unsloth_platform_policy import default_training_platform, host_platform

logger = logging.getLogger("antigravity_k.lora_pipeline")

JsonObject: TypeAlias = dict[str, Any]  # pyright: ignore[reportExplicitAny]
NumericValue: TypeAlias = str | int | float | bool


# ─── 데이터 구조 ─────────────────────────────────────────────────────


@dataclass
class HarvestEntry:
    """수확된 고품질 응답 1건."""

    user_request: str
    agent_output: str
    quality_score: float
    quality_grade: str
    task_type: str
    model_used: str
    timestamp: float
    word_count: int = 0
    metadata: JsonObject = field(default_factory=dict)

    def to_training_format(self) -> dict[str, str]:
        """SFT(Supervised Fine-Tuning) 학습용 포맷으로 변환."""
        return {
            "instruction": self.user_request,
            "output": self.agent_output,
            "input": "",  # 추가 컨텍스트 (있으면)
        }

    def to_chat_format(self) -> JsonObject:
        """ChatML 학습용 포맷으로 변환."""
        return {
            "messages": [
                {"role": "user", "content": self.user_request},
                {"role": "assistant", "content": self.agent_output},
            ],
        }


# ─── DPO 선호쌍 ──────────────────────────────────────────────────────


@dataclass
class PreferencePair:
    """DPO(Direct Preference Optimization) 학습용 선호쌍 1건.

    chosen/rejected는 동일 프롬프트에 대한 두 응답이며,
    QualityGate 점수 또는 사용자 승인이 라벨 근거가 된다.

    source: 라벨 근거 출처 ("quality_gate" | "revision" | "human")
    """

    prompt: str
    chosen: str
    rejected: str
    chosen_score: float
    rejected_score: float
    source: str = "quality_gate"
    task_type: str = "general"
    timestamp: float = field(default_factory=time.time)

    def to_dpo_format(self) -> dict[str, str]:
        """TRL DPOTrainer 표준 포맷으로 변환."""
        return {
            "prompt": self.prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
        }


@dataclass
class TrainingRunResult:
    """학습 실행 결과."""

    success: bool
    exit_code: int | None = None
    elapsed_sec: float = 0.0
    log_tail: list[str] = field(default_factory=list)
    command: str = ""
    error: str = ""


def mlx_lm_available() -> bool:
    """mlx-lm 패키지 설치 여부."""
    return importlib.util.find_spec("mlx_lm") is not None


def _as_object(value: object) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def _as_float(value: object) -> float:
    return float(cast(NumericValue, value))


def _as_int(value: object) -> int:
    return int(cast(NumericValue, value))


def _harvest_entry(data: Mapping[str, object]) -> HarvestEntry:
    return HarvestEntry(
        user_request=str(data["user_request"]),
        agent_output=str(data["agent_output"]),
        quality_score=_as_float(data["quality_score"]),
        quality_grade=str(data["quality_grade"]),
        task_type=str(data["task_type"]),
        model_used=str(data["model_used"]),
        timestamp=_as_float(data["timestamp"]),
        word_count=_as_int(data.get("word_count", 0)),
        metadata=_as_object(data.get("metadata", {})),
    )


def _preference_pair(data: Mapping[str, object]) -> PreferencePair:
    return PreferencePair(
        prompt=str(data["prompt"]),
        chosen=str(data["chosen"]),
        rejected=str(data["rejected"]),
        chosen_score=_as_float(data["chosen_score"]),
        rejected_score=_as_float(data["rejected_score"]),
        source=str(data.get("source", "quality_gate")),
        task_type=str(data.get("task_type", "general")),
        timestamp=_as_float(data.get("timestamp", time.time())),
    )


# ─── 메인 파이프라인 ─────────────────────────────────────────────────


@final
class LoRAPipeline:
    """LoRA 파인튜닝 자동화 파이프라인.

    3단계 워크플로우:
    1. 수확 (Harvest): QualityGate A/B 등급 응답을 자동 저장
    2. 내보내기 (Export): JSONL 형태의 학습 데이터셋 생성
    3. 설정 생성 (Config): Unsloth/mlx-lm LoRA 학습 설정 자동 생성
    """

    # 수확 조건: 이 점수 이상만 수확
    HARVEST_THRESHOLD: float = 0.75  # B등급 이상 (score >= 0.6은 B, 0.75면 B+ 이상만)
    MAX_HARVEST_SIZE: int = 5000  # 최대 수확 건수

    def __init__(
        self,
        harvest_dir: str = "data/lora_harvest",
        min_score: float = 0.75,
    ):
        """Initialize the LoRAPipeline.

        Args:
            harvest_dir (str): str harvest dir.
            min_score (float): float min score.

        """
        self._harvest_dir: Path = Path(harvest_dir)
        self._harvest_dir.mkdir(parents=True, exist_ok=True)
        self._min_score: float = min_score
        self._harvest_file: Path = self._harvest_dir / "harvest.jsonl"
        self._pairs_file: Path = self._harvest_dir / "pairs.jsonl"
        self._entries: list[HarvestEntry] = []
        self._pairs: list[PreferencePair] = []
        self._load_existing()
        self._load_pairs()

    @property
    def pairs(self) -> list[PreferencePair]:
        return list(self._pairs)

    def _load_existing(self) -> None:
        """기존 수확 데이터를 로드합니다."""
        if not self._harvest_file.exists():
            return
        try:
            with open(self._harvest_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = _as_object(cast(object, json.loads(line)))
                        self._entries.append(_harvest_entry(data))
            logger.info("[LoRA] %s개 기존 수확 데이터 로드", len(self._entries))
        except Exception:
            logger.exception("[LoRA] 기존 수확 데이터 로드 실패")

    # ─── 1단계: 수확 (Harvest) ────────────────────────────────────

    def harvest(
        self,
        user_request: str,
        agent_output: str,
        quality_score: float,
        quality_grade: str = "",
        task_type: str = "general",
        model_used: str = "",
        metadata: JsonObject | None = None,
    ) -> bool:
        """고품질 응답을 자동 수확합니다.

        QualityGate 평가 후 호출하면, 일정 점수 이상의 응답만 자동 저장됩니다.

        Returns:
            True if harvested, False if below threshold

        """
        if quality_score < self._min_score:
            return False

        if len(self._entries) >= self.MAX_HARVEST_SIZE:
            logger.warning("[LoRA] 최대 수확 건수 도달, 수확 스킵")
            return False

        # 중복 방지: 동일 요청 + 동일 응답(앞 200자)
        for existing in self._entries[-100:]:  # 최근 100개만 검사
            if existing.user_request == user_request and existing.agent_output[:200] == agent_output[:200]:
                return False

        entry = HarvestEntry(
            user_request=user_request,
            agent_output=agent_output,
            quality_score=quality_score,
            quality_grade=quality_grade,
            task_type=task_type,
            model_used=model_used,
            timestamp=time.time(),
            word_count=len(agent_output.split()),
            metadata=metadata or {},
        )

        self._entries.append(entry)
        self._append_to_file(entry)

        logger.info(
            "[LoRA] 수확 완료: %s (%s) — %s... (총 %s건)",
            quality_grade,
            quality_score,
            user_request[:50],
            len(self._entries),
        )
        return True

    def _append_to_file(self, entry: HarvestEntry) -> None:
        """수확 데이터를 파일에 추가합니다 (append mode)."""
        try:
            with open(self._harvest_file, "a", encoding="utf-8") as f:
                _ = f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("[LoRA] 수확 데이터 저장 실패")

    # ─── 2단계: 내보내기 (Export) ─────────────────────────────────

    def export_dataset(
        self,
        output_path: str = "data/lora_dataset.jsonl",
        format: str = "chat",
        min_score: float | None = None,
        max_entries: int = 2000,
    ) -> JsonObject:
        """수확 데이터를 학습용 JSONL로 내보냅니다.

        Args:
            output_path: 출력 파일 경로
            format: "chat" (ChatML) 또는 "instruction" (Alpaca)
            min_score: 최소 점수 필터 (None이면 self._min_score)
            max_entries: 최대 내보내기 건수

        Returns:
            내보내기 통계

        """
        threshold = min_score or self._min_score
        filtered = [e for e in self._entries if e.quality_score >= threshold]

        # 점수 높은 순으로 정렬 후 상위 N개
        filtered.sort(key=lambda e: e.quality_score, reverse=True)
        selected = filtered[:max_entries]

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            for entry in selected:
                if format == "chat":
                    record = entry.to_chat_format()
                else:
                    record = entry.to_training_format()
                _ = f.write(json.dumps(record, ensure_ascii=False) + "\n")

        stats: JsonObject = {
            "total_harvested": len(self._entries),
            "exported": len(selected),
            "min_score_filter": threshold,
            "output_path": str(output),
            "format": format,
            "avg_score": (sum(e.quality_score for e in selected) / len(selected) if selected else 0),
            "avg_word_count": (sum(e.word_count for e in selected) / len(selected) if selected else 0),
        }
        logger.info("[LoRA] 데이터셋 내보내기 완료: %s건 → %s", len(selected), output)
        return stats

    # ─── 3단계: 학습 설정 생성 (Config) ───────────────────────────

    def generate_config(
        self,
        base_model: str = "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        dataset_path: str = "data/lora_dataset.jsonl",
        output_dir: str = "data/lora_output",
        platform: str = "auto",
    ) -> JsonObject:
        """LoRA/QLoRA 학습 설정을 자동 생성합니다.

        Args:
            base_model: 베이스 모델 (HuggingFace ID 또는 로컬 경로)
            dataset_path: 학습 데이터 경로
            output_dir: 학습 결과 저장 경로
            platform: "mlx" (Apple Silicon), "unsloth" (GPU), "auto" (자동 감지)

        Returns:
            생성된 설정 dict

        """
        if platform == "auto":
            platform = default_training_platform(host_platform())

        if platform == "mlx":
            config = self._mlx_lora_config(base_model, dataset_path, output_dir)
        else:
            config = self._unsloth_config(base_model, dataset_path, output_dir)

        # 설정 파일 저장
        config_path = Path(output_dir) / "lora_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logger.info("[LoRA] 학습 설정 생성: %s (platform: %s)", config_path, platform)
        return config

    @staticmethod
    def _mlx_lora_config(base_model: str, dataset_path: str, output_dir: str) -> JsonObject:
        """Apple Silicon mlx-lm LoRA 설정."""
        return {
            "platform": "mlx",
            "command": (
                f"python -m mlx_lm.lora "
                f"--model {base_model} "
                f"--train "
                f"--data {dataset_path} "
                f"--adapter-path {output_dir}/adapters "
                f"--iters 600 "
                f"--batch-size 4 "
                f"--lora-layers 16 "
                f"--learning-rate 1e-5"
            ),
            "base_model": base_model,
            "dataset": dataset_path,
            "output_dir": output_dir,
            "hyperparameters": {
                "lora_rank": 16,
                "lora_alpha": 32,
                "learning_rate": 1e-5,
                "batch_size": 4,
                "iterations": 600,
                "lora_layers": 16,
            },
            "merge_command": (
                f"python -m mlx_lm.fuse "
                f"--model {base_model} "
                f"--adapter-path {output_dir}/adapters "
                f"--save-path {output_dir}/merged"
            ),
            "notes": [
                "Apple Silicon M4 Max 환경에 최적화",
                "mlx-lm 설치: pip install mlx-lm",
                "학습 후 merged 모델을 Ollama에 등록하여 사용",
            ],
        }

    @staticmethod
    def _unsloth_config(base_model: str, dataset_path: str, output_dir: str) -> JsonObject:
        """GPU 서버 Unsloth QLoRA 설정."""
        return {
            "platform": "unsloth",
            "script": f"""
from unsloth import FastLanguageModel

import torch

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{base_model}",
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset

dataset = load_dataset("json", data_files="{dataset_path}", split="train")

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=4096,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=60,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        output_dir="{output_dir}",
    ),
)
trainer.train()
model.save_pretrained("{output_dir}/lora_model")
""",
            "base_model": base_model,
            "dataset": dataset_path,
            "output_dir": output_dir,
            "hyperparameters": {
                "lora_rank": 16,
                "lora_alpha": 32,
                "learning_rate": 2e-4,
                "batch_size": 2,
                "gradient_accumulation_steps": 4,
                "max_steps": 60,
                "max_seq_length": 4096,
                "load_in_4bit": True,
            },
            "notes": [
                "Unsloth 설치: pip install unsloth",
                "CUDA GPU 필수 (24GB+ VRAM 권장)",
                "학습 완료 후 GGUF 변환하여 Ollama에 등록",
            ],
        }

    # ─── DPO 선호쌍 (Unsloth 격차 해소) ────────────────────────────

    def _load_pairs(self) -> None:
        """기존 선호쌍 데이터를 로드합니다."""
        if not self._pairs_file.exists():
            return
        try:
            with open(self._pairs_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = _as_object(cast(object, json.loads(line)))
                        self._pairs.append(_preference_pair(data))
            logger.info("[LoRA] %s개 기존 선호쌍 로드", len(self._pairs))
        except Exception:
            logger.exception("[LoRA] 기존 선호쌍 로드 실패")

    def record_pair(
        self,
        prompt: str,
        chosen: str,
        rejected: str,
        chosen_score: float,
        rejected_score: float,
        source: str = "quality_gate",
        task_type: str = "general",
    ) -> bool:
        """선호쌍을 직접 기록합니다.

        revision 흐름(재생성 전 답=rejected, 후 답=chosen)이나 사용자 승인에서 호출.

        Returns:
            True if recorded, False if scores are inverted or equal
        """
        if chosen_score <= rejected_score:
            return False
        pair = PreferencePair(
            prompt=prompt,
            chosen=chosen,
            rejected=rejected,
            chosen_score=chosen_score,
            rejected_score=rejected_score,
            source=source,
            task_type=task_type,
        )
        self._pairs.append(pair)
        try:
            with open(self._pairs_file, "a", encoding="utf-8") as f:
                _ = f.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("[LoRA] 선호쌍 저장 실패")
        return True

    def build_preference_pairs(
        self,
        min_score_gap: float = 0.15,
    ) -> int:
        """수확 데이터에서 동일 프롬프트 그룹별로 선호쌍을 자동 추출합니다.

        같은 user_request에 대해 점수 차이가 min_score_gap 이상인 응답 쌍이
        있으면 (최고점=chosen, 최저점=rejected) 페어를 생성합니다.
        QualityGate가 암묵적 라벨러 역할을 하는 자가 개선 경로입니다.

        Returns:
            새로 추가된 페어 수
        """
        groups: dict[str, list[HarvestEntry]] = {}
        for e in self._entries:
            groups.setdefault(e.user_request, []).append(e)

        added = 0
        for prompt, entries in groups.items():
            if len(entries) < 2:
                continue
            best = max(entries, key=lambda e: e.quality_score)
            worst = min(entries, key=lambda e: e.quality_score)
            if best.quality_score - worst.quality_score < min_score_gap:
                continue
            if best.agent_output == worst.agent_output:
                continue
            if self.record_pair(
                prompt=prompt,
                chosen=best.agent_output,
                rejected=worst.agent_output,
                chosen_score=best.quality_score,
                rejected_score=worst.quality_score,
                source="quality_gate",
                task_type=best.task_type,
            ):
                added += 1

        logger.info("[LoRA] 수확 데이터에서 선호쌍 %s건 추출", added)
        return added

    def export_dpo_dataset(
        self,
        output_path: str = "data/dpo_dataset.jsonl",
        max_pairs: int = 2000,
    ) -> JsonObject:
        """선호쌍을 TRL DPOTrainer 호환 JSONL로 내보냅니다."""
        selected = sorted(self._pairs, key=lambda p: p.chosen_score - p.rejected_score, reverse=True)
        selected = selected[:max_pairs]

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            for pair in selected:
                _ = f.write(json.dumps(pair.to_dpo_format(), ensure_ascii=False) + "\n")

        stats: JsonObject = {
            "total_pairs": len(self._pairs),
            "exported": len(selected),
            "output_path": str(output),
            "avg_score_gap": (
                sum(p.chosen_score - p.rejected_score for p in selected) / len(selected) if selected else 0
            ),
        }
        logger.info("[LoRA] DPO 데이터셋 내보내기 완료: %s건 → %s", len(selected), output)
        return stats

    def generate_dpo_config(
        self,
        base_model: str = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
        dataset_path: str = "data/dpo_dataset.jsonl",
        output_dir: str = "data/dpo_output",
        platform: str = "auto",
    ) -> JsonObject:
        """DPO 학습 설정을 생성합니다 (mlx-lm / Unsloth).

        SFT로 정렬된 베이스 위에 선호 정렬을 얹는 2단계 훈련의 2단계 설정.
        """
        if platform == "auto":
            platform = default_training_platform(host_platform())

        config_path = Path(output_dir) / "dpo_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if platform == "mlx":
            config: JsonObject = {
                "platform": "mlx",
                "command": (
                    f"python -m mlx_lm.lora "
                    f"--model {base_model} "
                    f"--train "
                    f"--fine-tune-type dora "
                    f"--data {dataset_path} "
                    f"--adapter-path {output_dir}/adapters "
                    f"--iters 400 "
                    f"--batch-size 2 "
                    f"--learning-rate 1e-6"
                ),
                "notes": [
                    "mlx-lm DPO는 chat 포맷 프롬프트-응답 쌍을 요구하므로",
                    "export 시 chosen/rejected를 assistant 턴으로 감싸야 할 수 있습니다.",
                    "학습 전 mlx-lm 최신 버전 문서의 DPO 데이터 형식을 확인하세요.",
                ],
            }
        else:
            config = {
                "platform": "unsloth",
                "script": f"""
from unsloth import FastLanguageModel
from trl import DPOTrainer, DPOConfig
from datasets import load_dataset

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{base_model}",
    max_seq_length=4096,
    load_in_4bit=True,
)

dataset = load_dataset("json", data_files="{dataset_path}", split="train")
trainer = DPOTrainer(
    model=model,
    train_dataset=dataset,
    tokenizer=tokenizer,
    args=DPOConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=120,
        learning_rate=5e-6,
        beta=0.1,
        logging_steps=1,
        output_dir="{output_dir}",
    ),
)
trainer.train()
model.save_pretrained("{output_dir}/dpo_model")
""",
                "notes": [
                    "Unsloth DPOTrainer은 CUDA GPU 필수 (24GB+ 권장)",
                    "SFT 어댑터 위에 실행하는 것을 권장 (2단계 정렬)",
                ],
            }

        config["base_model"] = base_model
        config["dataset"] = dataset_path
        config["output_dir"] = output_dir
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logger.info("[LoRA] DPO 학습 설정 생성: %s (platform: %s)", config_path, platform)
        return config

    # ─── 학습 실행 (Unsloth 격차: 설정 생성 → 실제 실행) ──────────

    def run_training(
        self,
        config: Mapping[str, object],
        on_log: Callable[[str], None] | None = None,
        timeout_sec: float | None = None,
    ) -> TrainingRunResult:
        """생성된 mlx-lm 학습 설정을 실제로 실행합니다.

        platform이 "mlx"면 command를 파싱해 서브프로세스로 실행하고
        로그를 on_log 콜백으로 스트리밍합니다. "unsloth"는 CUDA GPU가 필요해
        스크립트를 디스크에 저장한 뒤 안내 에러와 함께 실패 결과를 반환합니다.
        """
        started = time.monotonic()
        _ = timeout_sec
        platform = str(config.get("platform", ""))

        if platform == "unsloth":
            script_path = self._persist_unsloth_script(config)
            return TrainingRunResult(
                success=False,
                error=(f"Unsloth 학습은 CUDA GPU 호스트에서 실행하세요. 스크립트 저장됨: {script_path}"),
                elapsed_sec=time.monotonic() - started,
            )

        command = str(config.get("command", ""))
        if not command:
            return TrainingRunResult(success=False, error="config에 command가 없습니다", elapsed_sec=0.0)

        if not mlx_lm_available():
            return TrainingRunResult(
                success=False,
                error="mlx-lm 미설치 — `uv sync --extra mlx` 또는 `pip install mlx-lm` 후 재시도",
                elapsed_sec=time.monotonic() - started,
            )

        argv = shlex.split(command)
        tail: list[str] = []
        try:
            proc: subprocess.Popen[str] = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            return TrainingRunResult(
                success=False,
                error=f"프로세스 시작 실패: {exc}",
                command=command,
                elapsed_sec=time.monotonic() - started,
            )

        assert proc.stdout is not None
        stdout: TextIO = cast(TextIO, proc.stdout)
        with proc:
            for raw_line in stdout:
                line = raw_line.rstrip()
                tail.append(line)
                if len(tail) > 50:
                    _ = tail.pop(0)
                if on_log is not None:
                    on_log(line)

        exit_code = proc.wait() if proc.poll() is None else proc.returncode
        return TrainingRunResult(
            success=exit_code == 0,
            exit_code=exit_code,
            elapsed_sec=time.monotonic() - started,
            log_tail=tail,
            command=command,
        )

    @staticmethod
    def _persist_unsloth_script(config: Mapping[str, object]) -> Path | None:
        """Unsloth 학습 스크립트를 output_dir에 저장한다 (GPU 호스트 이전용)."""
        output_dir = Path(str(config.get("output_dir", "data/lora_output")))
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / ("train_dpo.py" if "DPOTrainer" in str(config.get("script", "")) else "train_sft.py")
        try:
            _ = script_path.write_text(str(config.get("script", "")), encoding="utf-8")
        except Exception:
            logger.exception("[LoRA] Unsloth 스크립트 저장 실패")
            return None
        logger.info("[LoRA] Unsloth 스크립트 저장: %s", script_path)
        return script_path

    # ─── 유틸리티 ─────────────────────────────────────────────────

    def stats(self) -> JsonObject:
        """수확 통계를 반환합니다."""
        if not self._entries:
            return {"total": 0, "message": "수확 데이터 없음"}

        scores = [e.quality_score for e in self._entries]
        task_types: dict[str, int] = {}
        for e in self._entries:
            task_types[e.task_type] = task_types.get(e.task_type, 0) + 1

        return {
            "total": len(self._entries),
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "by_task_type": task_types,
            "harvest_dir": str(self._harvest_dir),
        }

    def clear(self) -> None:
        """수확 데이터를 초기화합니다."""
        self._entries.clear()
        if self._harvest_file.exists():
            self._harvest_file.unlink()
        logger.info("[LoRA] 수확 데이터 초기화")


"""Antigravity-K LoRA Pipeline — Self-improving training data harvester."""
