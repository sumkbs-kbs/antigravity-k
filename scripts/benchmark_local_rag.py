from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from pydantic import TypeAdapter

from antigravity_k.engine.rag_indexer import RAGIndexer
from antigravity_k.engine.rag_quality import (
    RAGJSON,
    RAGGoldenCase,
    RAGSearchProvider,
    audit_rag_fixture,
    run_rag_benchmark,
)
from antigravity_k.engine.vector_store import VectorStore

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


@dataclass
class BenchmarkOptions:
    project_root: Path = Path(".")
    fixture: Path = Path("tests/fixtures/rag_quality_cases.json")
    output: Path = Path("data/benchmarks/local-rag-quality.json")
    k: int = 5
    subdirs: list[str] | None = None


def _load_cases(path: Path) -> tuple[RAGGoldenCase, ...]:
    payload = TypeAdapter(list[dict[str, RAGJSON]]).validate_json(path.read_bytes())
    cases: list[RAGGoldenCase] = []
    for item in payload:
        cases.append(RAGGoldenCase.from_dict(item))
    return tuple(cases)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic local-RAG retrieval benchmark")
    _ = parser.add_argument("--project-root", type=Path)
    _ = parser.add_argument("--fixture", type=Path)
    _ = parser.add_argument("--output", type=Path)
    _ = parser.add_argument("--k", type=int)
    _ = parser.add_argument(
        "--subdir",
        dest="subdirs",
        action="append",
        help="Project subdirectory to index; repeat for multiple scopes (defaults to src/antigravity_k/engine)",
    )
    args = BenchmarkOptions()
    _ = parser.parse_args(namespace=args)
    cases = _load_cases(args.fixture)
    subdirs = args.subdirs or ["src/antigravity_k/engine"]
    serialized_subdirs: list[JSONValue] = []
    serialized_subdirs.extend(subdirs)
    with TemporaryDirectory(prefix="agk-rag-benchmark-") as vector_dir:
        with VectorStore(vector_dir, collection_name="local_rag_quality") as store:
            indexer = RAGIndexer(str(args.project_root.resolve()), vector_store=store)
            indexed_chunks = indexer.index_project(subdirs=subdirs)
            report = run_rag_benchmark(cast(RAGSearchProvider, cast(object, indexer)), cases, k=args.k)
    fixture_audit: list[JSONValue] = [item.to_dict() for item in audit_rag_fixture(args.project_root.resolve(), cases)]
    artifact: dict[str, JSONValue] = {
        "project_root": str(args.project_root.resolve()),
        "fixture": str(args.fixture),
        "indexed_chunks": indexed_chunks,
        "k": args.k,
        "subdirs": serialized_subdirs,
        "fixture_audit": fixture_audit,
        **report.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _ = args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
