#!/usr/bin/env python3
"""Hermes Agent Reasoning Traces 데이터셋 변환기
==================================================
허깅페이스의 `lambda/hermes-agent-reasoning-traces` 데이터셋을
Ollama / mlx-lm 파인튜닝용 ChatML 형식으로 변환합니다.

Usage:
    python scripts/prepare_hermes_dataset.py --input raw_data.json --output train.jsonl
"""

import argparse
import json
from pathlib import Path


def convert_to_chatml(entry):
    """원본 Hermes 데이터셋 포맷을 ChatML로 변환"""
    chatml = []
    for msg in entry.get("conversations", []):
        role = msg.get("from", "user")
        if role == "human":
            role = "user"
        elif role == "gpt":
            role = "assistant"

        value = msg.get("value", "")
        # 시스템 프롬프트 등 기타 처리 가능
        chatml.append({"role": role, "content": value})

    return {"messages": chatml}


def main():
    parser = argparse.ArgumentParser(description="Convert Hermes Agent dataset to ChatML")
    parser.add_argument("--input", type=str, required=True, help="Input JSON file path")
    parser.add_argument("--output", type=str, required=True, help="Output JSONL file path")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist.")
        return

    print(f"Loading data from {input_path}...")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Converting {len(data)} records...")

    converted_count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in data:
            try:
                chatml_entry = convert_to_chatml(entry)
                f.write(json.dumps(chatml_entry, ensure_ascii=False) + "\n")
                converted_count += 1
            except Exception as e:
                print(f"Skipping entry due to error: {e}")

    print(f"Successfully converted {converted_count} records to {output_path}")


if __name__ == "__main__":
    main()
