"""Antigravity-K: MLX LoRA/QLoRA 파인튜닝 엔진.

=============================================
Apple Silicon 128GB Unified Memory에서 로컬 파인튜닝 실행.

사용법:
    # CLI
    python -m antigravity_k.finetune.trainer --config finetune_config.yaml

    # Python API
    from antigravity_k.finetune.trainer import FineTuneEngine
    engine = FineTuneEngine(config)
    engine.train()
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger("agk.finetune")


# ─── 설정 ────────────────────────────────────────────────────────────
@dataclass
class LoRAConfig:
    """LoRA 어댑터 하이퍼파라미터."""

    rank: int = 16  # LoRA rank (8, 16, 32, 64)
    alpha: float = 32.0  # LoRA alpha (보통 rank * 2)
    dropout: float = 0.05  # 드롭아웃 확률
    target_modules: list = field(
        default_factory=lambda: [
            "q_proj",
            "v_proj",
            "k_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )


@dataclass
class TrainingConfig:
    """학습 설정."""

    # 모델
    base_model: str = ""  # 베이스 모델 경로 (models/glm 등)
    output_dir: str = ""  # 어댑터 저장 경로

    # 데이터
    train_data: str = ""  # 학습 데이터 (JSONL 경로)
    valid_data: str = ""  # 검증 데이터 (JSONL 경로, 선택)

    # 학습 하이퍼파라미터
    num_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 1e-5
    warmup_steps: int = 100
    max_seq_length: int = 2048
    gradient_accumulation_steps: int = 4
    save_every: int = 100  # N 스텝마다 체크포인트 저장
    eval_every: int = 200  # N 스텝마다 검증

    # LoRA
    lora: LoRAConfig = field(default_factory=LoRAConfig)

    # 리소스
    use_quantized_training: bool = True  # QLoRA (4-bit base + LoRA)
    seed: int = 42


# ─── 데이터 준비 도구 ────────────────────────────────────────────────
class DatasetPreparer:
    """다양한 소스 데이터를 MLX 파인튜닝용 JSONL로 변환.

    지원 포맷:
        1. ChatML: {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}
        2. Instruction: {"instruction": "...", "input": "...", "output": "..."}
        3. QA: {"question": "...", "answer": "..."}
        4. Raw text: {"text": "..."}
    """

    SYSTEM_PROMPT = (
        "당신은 삼성중공업의 시니어 소프트웨어 엔지니어입니다. "
        "조선/해양 플랜트 도메인에 대한 깊은 이해를 바탕으로 "
        "정확하고 실용적인 기술 답변을 제공합니다."
    )

    @staticmethod
    def from_instruction(
        input_path: str,
        output_path: str,
        system_prompt: str | None = None,
    ) -> int:
        """Instruction 포맷 → ChatML JSONL 변환."""
        system = system_prompt or DatasetPreparer.SYSTEM_PROMPT
        count = 0

        with (
            open(input_path, encoding="utf-8") as fin,
            open(output_path, "w", encoding="utf-8") as fout,
        ):
            for line in fin:
                line = line.strip()
                if not line:
                    continue

                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("JSON 파싱 실패, 건너뜀: %s", line[:80])
                    continue

                # Instruction 포맷
                if "instruction" in item:
                    user_content = item["instruction"]
                    if item.get("input"):
                        user_content += f"\n\n입력:\n{item['input']}"
                    assistant_content = item.get("output", "")

                # QA 포맷
                elif "question" in item:
                    user_content = item["question"]
                    assistant_content = item.get("answer", "")

                # ChatML (그대로 통과)
                elif "messages" in item:
                    fout.write(json.dumps(item, ensure_ascii=False) + "\n")
                    count += 1
                    continue

                # Raw text
                elif "text" in item:
                    fout.write(json.dumps({"text": item["text"]}, ensure_ascii=False) + "\n")
                    count += 1
                    continue

                else:
                    logger.warning("알 수 없는 포맷, 건너뜀: %s", list(item.keys()))
                    continue

                chatml = {
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": assistant_content},
                    ],
                }
                fout.write(json.dumps(chatml, ensure_ascii=False) + "\n")
                count += 1

        logger.info("변환 완료: %s개 → %s", count, output_path)
        return count

    @staticmethod
    def from_code_files(
        source_dir: str,
        output_path: str,
        extensions: tuple = (".py", ".js", ".ts", ".dart", ".java"),
        min_lines: int = 10,
    ) -> int:
        """소스코드 파일 → 코드 이해/생성 학습 데이터로 변환."""
        count = 0

        with open(output_path, "w", encoding="utf-8") as fout:
            for root, _, files in os.walk(source_dir):
                for fname in files:
                    if not any(fname.endswith(ext) for ext in extensions):
                        continue

                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, encoding="utf-8", errors="ignore") as f:
                            code = f.read()
                    except Exception:
                        logger.exception("Unhandled exception")
                        continue

                    lines = code.strip().split("\n")
                    if len(lines) < min_lines:
                        continue

                    rel_path = os.path.relpath(fpath, source_dir)
                    ext = os.path.splitext(fname)[1]

                    chatml = {
                        "messages": [
                            {
                                "role": "system",
                                "content": "당신은 코드 분석 전문가입니다.",
                            },
                            {
                                "role": "user",
                                "content": f"다음 {ext} 파일을 분석하고 핵심 기능을 설명해주세요:\n\n파일: {rel_path}\n```{ext[1:]}\n{code[:3000]}\n```",  # noqa: E501
                            },
                            {
                                "role": "assistant",
                                "content": f"## {rel_path} 분석\n\n이 파일은 {len(lines)}줄의 {ext} 코드입니다.",
                            },
                        ],
                    }
                    fout.write(json.dumps(chatml, ensure_ascii=False) + "\n")
                    count += 1

        logger.info("코드 파일 변환: %s개 → %s", count, output_path)
        return count

    @staticmethod
    def split_dataset(
        input_path: str,
        train_ratio: float = 0.9,
        seed: int = 42,
    ) -> tuple:
        """데이터셋을 train/valid로 분할."""
        import random

        random.seed(seed)

        with open(input_path, encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]

        random.shuffle(lines)
        split_idx = int(len(lines) * train_ratio)

        train_path = input_path.replace(".jsonl", "_train.jsonl")
        valid_path = input_path.replace(".jsonl", "_valid.jsonl")

        with open(train_path, "w", encoding="utf-8") as f:
            f.writelines(lines[:split_idx])
        with open(valid_path, "w", encoding="utf-8") as f:
            f.writelines(lines[split_idx:])

        logger.info("분할 완료: train=%s, valid=%s", split_idx, len(lines) - split_idx)
        return train_path, valid_path


# ─── 파인튜닝 엔진 ──────────────────────────────────────────────────
class FineTuneEngine:
    """MLX LoRA 파인튜닝 엔진."""

    def __init__(self, config: TrainingConfig):
        """Initialize the FineTuneEngine.

        Args:
            config (TrainingConfig): TrainingConfig config.

        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 학습 상태
        self.current_step = 0
        self.current_epoch = 0
        self.best_val_loss = float("inf")
        self.training_log: list[str] = []

    def train(self) -> dict:
        """파인튜닝 실행."""
        import subprocess
        import sys

        logger.info("=" * 60)
        logger.info("Antigravity-K LoRA 파인튜닝 시작")
        logger.info("=" * 60)
        logger.info("  베이스 모델: %s", self.config.base_model)
        logger.info("  학습 데이터: %s", self.config.train_data)
        logger.info("  LoRA Rank:   %s", self.config.lora.rank)
        logger.info("  Epochs:      %s", self.config.num_epochs)
        logger.info("  Batch Size:  %s", self.config.batch_size)
        logger.info("  LR:          %s", self.config.learning_rate)
        logger.info("  출력 경로:   %s", self.output_dir)
        logger.info("=" * 60)

        start_time = time.time()

        # mlx_lm.lora CLI 호출
        cmd = [
            sys.executable,
            "-m",
            "mlx_lm.lora",
            "--model",
            self.config.base_model,
            "--data",
            str(Path(self.config.train_data).parent),
            "--train",
            "--adapter-path",
            str(self.output_dir / "adapters"),
            "--iters",
            str(self._calculate_total_iters()),
            "--batch-size",
            str(self.config.batch_size),
            "--learning-rate",
            str(self.config.learning_rate),
            "--lora-layers",
            str(self.config.lora.rank),
            "--save-every",
            str(self.config.save_every),
            "--seed",
            str(self.config.seed),
        ]

        if self.config.valid_data:
            cmd.extend(["--val-batches", "25"])

        logger.info("실행 명령: %s", " ".join(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # 실시간 로그 출력 + 수집
            assert process.stdout is not None
            for line in iter(process.stdout.readline, ""):
                line = line.rstrip()
                if line:
                    logger.info("  [MLX] %s", line)
                    self.training_log.append(line)

                    # 진행 상황 파싱
                    if "Iter" in line and "loss" in line:
                        self._parse_training_line(line)

            process.wait()

            elapsed = time.time() - start_time
            result = {
                "status": "success" if process.returncode == 0 else "failed",
                "return_code": process.returncode,
                "elapsed_seconds": round(elapsed, 1),
                "adapter_path": str(self.output_dir / "adapters"),
                "total_steps": self.current_step,
                "best_val_loss": (self.best_val_loss if self.best_val_loss < float("inf") else None),
            }

            if process.returncode == 0:
                logger.info("✓ 파인튜닝 완료! (%s초)", elapsed)
                self._save_training_info(result)
            else:
                logger.error("✗ 파인튜닝 실패 (exit code: %s)", process.returncode)

            return result

        except Exception as e:
            logger.exception("파인튜닝 오류")
            return {"status": "error", "error": str(e)}

    def merge_and_export(self, export_name: str | None = None) -> str:
        """LoRA 어댑터를 베이스 모델에 병합하여 독립 모델 생성."""
        import subprocess
        import sys

        adapter_path = self.output_dir / "adapters"
        name = export_name or f"finetuned-{int(time.time())}"
        export_path = Path(self.config.base_model).parent.parent / "finetuned" / name

        logger.info("모델 병합: %s → %s", adapter_path, export_path)

        cmd = [
            sys.executable,
            "-m",
            "mlx_lm.fuse",
            "--model",
            self.config.base_model,
            "--adapter-path",
            str(adapter_path),
            "--save-path",
            str(export_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("✓ 병합 완료: %s", export_path)

            # api_forwarder 자동 등록을 위한 메타데이터 저장
            meta = {
                "name": name,
                "base_model": self.config.base_model,
                "type": "finetuned",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "lora_config": asdict(self.config.lora),
            }
            meta_path = export_path / "agk_model_meta.json"
            export_path.mkdir(parents=True, exist_ok=True)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            return str(export_path)
        else:
            logger.error("병합 실패: %s", result.stderr)
            raise RuntimeError(result.stderr)

    def _calculate_total_iters(self) -> int:
        """전체 학습 스텝 수 계산."""
        try:
            with open(self.config.train_data) as f:
                num_samples = sum(1 for _ in f)
        except Exception:
            logger.exception("Unhandled exception")
            num_samples = 1000  # 기본값

        steps_per_epoch = max(
            1,
            num_samples // (self.config.batch_size * self.config.gradient_accumulation_steps),
        )
        return steps_per_epoch * self.config.num_epochs

    def _parse_training_line(self, line: str):
        """학습 로그에서 스텝/loss 파싱."""
        try:
            # 예: "Iter 100: train loss 2.345, ..."
            if "Iter" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "Iter":
                        step_str = parts[i + 1].rstrip(":")
                        self.current_step = int(step_str)
                    if p == "loss":
                        loss_val = float(parts[i + 1].rstrip(","))
                        if "val" in line.lower() and loss_val < self.best_val_loss:
                            self.best_val_loss = loss_val
        except (IndexError, ValueError):
            logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)

    def _save_training_info(self, result: dict):
        """학습 결과 메타데이터 저장."""
        info = {
            **result,
            "config": asdict(self.config),
            "training_log_lines": len(self.training_log),
        }
        info_path = self.output_dir / "training_info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        logger.info("학습 정보 저장: %s", info_path)


# ─── CLI 진입점 ──────────────────────────────────────────────────────
def main():
    """Run the main program."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Antigravity-K LoRA 파인튜닝")
    sub = parser.add_subparsers(dest="command", help="명령")

    # train
    train_p = sub.add_parser("train", help="파인튜닝 실행")
    train_p.add_argument("--model", required=True, help="베이스 모델 경로")
    train_p.add_argument("--data", required=True, help="학습 데이터 (JSONL)")
    train_p.add_argument("--output", default="./output/finetune", help="출력 경로")
    train_p.add_argument("--epochs", type=int, default=3)
    train_p.add_argument("--batch-size", type=int, default=4)
    train_p.add_argument("--lr", type=float, default=1e-5)
    train_p.add_argument("--lora-rank", type=int, default=16)

    # prepare
    prep_p = sub.add_parser("prepare", help="데이터 준비")
    prep_p.add_argument("--input", required=True, help="입력 데이터 경로")
    prep_p.add_argument("--output", required=True, help="출력 JSONL 경로")
    prep_p.add_argument("--format", choices=["instruction", "code"], default="instruction")
    prep_p.add_argument("--split", type=float, default=0.9, help="train/valid 비율")

    # merge
    merge_p = sub.add_parser("merge", help="어댑터 병합")
    merge_p.add_argument("--model", required=True, help="베이스 모델 경로")
    merge_p.add_argument("--adapter", required=True, help="어댑터 경로")
    merge_p.add_argument("--name", default=None, help="내보내기 이름")

    args = parser.parse_args()

    if args.command == "train":
        lora_cfg = LoRAConfig(rank=args.lora_rank)
        config = TrainingConfig(
            base_model=args.model,
            output_dir=args.output,
            train_data=args.data,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.lr,
            lora=lora_cfg,
        )
        engine = FineTuneEngine(config)
        result = engine.train()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "prepare":
        if args.format == "instruction":
            count = DatasetPreparer.from_instruction(args.input, args.output)
        elif args.format == "code":
            count = DatasetPreparer.from_code_files(args.input, args.output)
        else:
            print(f"알 수 없는 포맷: {args.format}")
            return

        print(f"✓ {count}개 샘플 변환 완료: {args.output}")

        if args.split < 1.0:
            train_path, valid_path = DatasetPreparer.split_dataset(args.output, args.split)
            print(f"✓ 분할 완료: {train_path}, {valid_path}")

    elif args.command == "merge":
        config = TrainingConfig(base_model=args.model, output_dir=os.path.dirname(args.adapter))
        engine = FineTuneEngine(config)
        export_path = engine.merge_and_export(args.name)
        print(f"✓ 병합 완료: {export_path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
