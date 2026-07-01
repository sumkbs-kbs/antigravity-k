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

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity_k.lora_pipeline")


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
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_training_format(self) -> dict[str, str]:
        """SFT(Supervised Fine-Tuning) 학습용 포맷으로 변환."""
        return {
            "instruction": self.user_request,
            "output": self.agent_output,
            "input": "",  # 추가 컨텍스트 (있으면)
        }

    def to_chat_format(self) -> dict[str, Any]:
        """ChatML 학습용 포맷으로 변환."""
        return {
            "messages": [
                {"role": "user", "content": self.user_request},
                {"role": "assistant", "content": self.agent_output},
            ],
        }


# ─── 메인 파이프라인 ─────────────────────────────────────────────────


class LoRAPipeline:
    """LoRA 파인튜닝 자동화 파이프라인.

    3단계 워크플로우:
    1. 수확 (Harvest): QualityGate A/B 등급 응답을 자동 저장
    2. 내보내기 (Export): JSONL 형태의 학습 데이터셋 생성
    3. 설정 생성 (Config): Unsloth/mlx-lm LoRA 학습 설정 자동 생성
    """

    # 수확 조건: 이 점수 이상만 수확
    HARVEST_THRESHOLD = 0.75  # B등급 이상 (score >= 0.6은 B, 0.75면 B+ 이상만)
    MAX_HARVEST_SIZE = 5000  # 최대 수확 건수

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
        self._harvest_dir = Path(harvest_dir)
        self._harvest_dir.mkdir(parents=True, exist_ok=True)
        self._min_score = min_score
        self._harvest_file = self._harvest_dir / "harvest.jsonl"
        self._entries: list[HarvestEntry] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """기존 수확 데이터를 로드합니다."""
        if not self._harvest_file.exists():
            return
        try:
            with open(self._harvest_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._entries.append(HarvestEntry(**data))
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
        metadata: dict[str, Any] | None = None,
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
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("[LoRA] 수확 데이터 저장 실패")

    # ─── 2단계: 내보내기 (Export) ─────────────────────────────────

    def export_dataset(
        self,
        output_path: str = "data/lora_dataset.jsonl",
        format: str = "chat",
        min_score: float | None = None,
        max_entries: int = 2000,
    ) -> dict[str, Any]:
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
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        stats = {
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
    ) -> dict[str, Any]:
        """LoRA/QLoRA 학습 설정을 자동 생성합니다.

        Args:
            base_model: 베이스 모델 (HuggingFace ID 또는 로컬 경로)
            dataset_path: 학습 데이터 경로
            output_dir: 학습 결과 저장 경로
            platform: "mlx" (Apple Silicon), "unsloth" (GPU), "auto" (자동 감지)

        Returns:
            생성된 설정 dict

        """
        import platform as plt

        if platform == "auto":
            platform = "mlx" if plt.system() == "Darwin" else "unsloth"

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
    def _mlx_lora_config(base_model: str, dataset_path: str, output_dir: str) -> dict[str, Any]:
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
    def _unsloth_config(base_model: str, dataset_path: str, output_dir: str) -> dict[str, Any]:
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

    # ─── 유틸리티 ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """수확 통계를 반환합니다."""
        if not self._entries:
            return {"total": 0, "message": "수확 데이터 없음"}

        scores = [e.quality_score for e in self._entries]
        task_types = {}
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
