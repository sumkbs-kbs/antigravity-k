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
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias, cast

ChatMessage: TypeAlias = dict[str, str]
ChatMLRecord: TypeAlias = dict[str, list[ChatMessage]]
DatasetEntry: TypeAlias = Mapping[str, object]


def _conversation_messages(entry: DatasetEntry) -> list[Mapping[str, object]]:
    raw_messages = entry.get("conversations", [])
    if not isinstance(raw_messages, list):
        return []
    messages: list[Mapping[str, object]] = []
    for message in cast(list[object], raw_messages):
        if isinstance(message, Mapping):
            messages.append(cast(Mapping[str, object], message))
    return messages


def convert_to_chatml(entry: DatasetEntry) -> ChatMLRecord:
    """원본 Hermes 데이터셋 포맷을 ChatML로 변환"""
    chatml: list[ChatMessage] = []
    for msg in _conversation_messages(entry):
        raw_role = msg.get("from", "user")
        role = raw_role if isinstance(raw_role, str) else "user"
        if role == "human":
            role = "user"
        elif role == "gpt":
            role = "assistant"

        raw_value = msg.get("value", "")
        value = raw_value if isinstance(raw_value, str) else str(raw_value)
        # 시스템 프롬프트 등 기타 처리 가능
        chatml.append({"role": role, "content": value})

    return {"messages": chatml}


def _parse_paths(parser: argparse.ArgumentParser) -> tuple[Path, Path]:
    args = parser.parse_args()
    raw_input = getattr(args, "input", None)
    raw_output = getattr(args, "output", None)
    if not isinstance(raw_input, str) or not isinstance(raw_output, str):
        raise ValueError("--input and --output must be string paths")
    return Path(raw_input), Path(raw_output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Hermes Agent dataset to ChatML")
    _ = parser.add_argument("--input", type=str, required=True, help="Input JSON file path")
    _ = parser.add_argument("--output", type=str, required=True, help="Output JSONL file path")
    input_path, output_path = _parse_paths(parser)

    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist.")
        return

    print(f"Loading data from {input_path}...")
    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = cast(object, json.load(f))
    if not isinstance(raw_data, list):
        raise ValueError("Input JSON must contain a list of records")
    data: list[DatasetEntry] = [
        cast(DatasetEntry, entry)
        for entry in cast(list[object], raw_data)
        if isinstance(entry, Mapping)
    ]

    print(f"Converting {len(data)} records...")

    converted_count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in data:
            try:
                chatml_entry = convert_to_chatml(entry)
                _ = f.write(json.dumps(chatml_entry, ensure_ascii=False) + "\n")
                converted_count += 1
            except Exception as e:
                print(f"Skipping entry due to error: {e}")

    print(f"Successfully converted {converted_count} records to {output_path}")


if __name__ == "__main__":
    main()
