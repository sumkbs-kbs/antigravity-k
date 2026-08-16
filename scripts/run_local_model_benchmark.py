from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from statistics import fmean, pstdev

_GROUNDING_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}


def _build_grounding_prompt(case) -> str:
    question = case.question.strip() or "Restate only the factual claim supported by the evidence."
    citation_ids = ", ".join(f"[citation:{source.source_id}]" for source in case.sources)
    evidence = []
    for source in case.sources:
        evidence.append(
            "\n".join(
                (
                    f"{source.title} ({source.source_id})",
                    "[untrusted_web_content]",
                    source.text,
                    "[/untrusted_web_content]",
                ),
            ).strip(),
        )
    return (
        "Return JSON only with one key named answer. Answer in one concise sentence using only the evidence. "
        "Do not explain reasoning. If sources disagree, explicitly state the conflict. "
        f"End the sentence with one or more exact citation markers from this list: {citation_ids}. "
        "Never use a placeholder citation or any other citation format.\n\n"
        f"Question:\n{question}\n\nEvidence:\n{chr(10).join(evidence)}"
    )


def _extract_grounding_answer(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    answer = payload.get("answer") if isinstance(payload, dict) else None
    return answer if isinstance(answer, str) else raw


def _generate_grounding_responses(manager, model: str, cases) -> dict[str, str]:
    responses = {}
    for case in cases:
        raw_response = manager.generate(
            _build_grounding_prompt(case),
            model,
            max_tokens=256,
            temperature=0.0,
            min_p=0.0,
            repeat_penalty=1.0,
            task_type="SEARCH",
            response_format=_GROUNDING_RESPONSE_SCHEMA,
        )
        responses[case.case_id] = _extract_grounding_answer(raw_response)
    return responses


def _collect_live_search_contexts(cases, force_refresh: bool = False):
    import anyio

    from antigravity_k.tools.search_quality_evaluator import citation_sources_from_context
    from antigravity_k.tools.web_search_engine import WebSearchEngine

    async def collect():
        engine = WebSearchEngine(max_results=3)
        records = []
        try:
            for case in cases:
                query = case.query.strip() or case.question.strip()
                response = await engine.search(
                    query,
                    use_cache=not force_refresh,
                    force_refresh=force_refresh,
                )
                context = engine.format_for_llm(response)
                sources = citation_sources_from_context(context)
                records.append(
                    {
                        "case": case,
                        "sources": sources,
                        "search": {
                            "query": query,
                            "engine": response.engine,
                            "result_count": len(response.results),
                            "search_time_ms": response.search_time_ms,
                            "cache_mode": "refresh" if force_refresh else "cache_allowed",
                            "retrieved": [
                                {
                                    "source_id": result.source_id,
                                    "title": result.title,
                                    "url": result.url,
                                    "snippet": result.snippet,
                                }
                                for result in response.results
                            ],
                        },
                    },
                )
        finally:
            await engine.close()
        return records

    return anyio.run(collect)


def _run_live_search_grounding(manager, model: str, cases, force_refresh: bool = False):
    from antigravity_k.tools.claim_grounding_benchmark import evaluate_live_grounding_case

    generated_responses = {}
    results = []
    search_records = []
    for record in _collect_live_search_contexts(cases, force_refresh=force_refresh):
        case = record["case"]
        sources = tuple(record["sources"])
        response = _generate_grounding_responses(manager, model, (replace(case, sources=sources),))[case.case_id]
        generated_responses[case.case_id] = response
        results.append(evaluate_live_grounding_case(case, response, sources))
        search_records.append(record["search"])
    return results, generated_responses, search_records


def _summarize_grounding_runs(runs):
    all_results = [result for run in runs for result in run]
    by_case = {}
    for result in all_results:
        by_case.setdefault(result.case_id, []).append(result)
    return {
        "repeat_count": len(runs),
        "result_count": len(all_results),
        "pass_rate": round(sum(result.passed for result in all_results) / len(all_results), 3) if all_results else 0.0,
        "all_pass_run_rate": round(
            sum(bool(run) and all(result.passed for result in run) for run in runs) / len(runs),
            3,
        )
        if runs
        else 0.0,
        "by_case": {
            case_id: {
                "repeat_count": len(results),
                "passed_count": sum(result.passed for result in results),
                "pass_rate": round(sum(result.passed for result in results) / len(results), 3),
            }
            for case_id, results in sorted(by_case.items())
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.6:latest")
    parser.add_argument("--suite", default="simple")
    parser.add_argument("--output", type=Path, default=Path("data/benchmarks/local-model.json"))
    parser.add_argument("--grounding-fixture", type=Path, default=Path("tests/fixtures/claim_grounding_cases.json"))
    parser.add_argument("--grounding-responses", type=Path, default=None)
    parser.add_argument(
        "--grounding-live",
        action="store_true",
        help="Generate grounding responses with the selected local model before evaluating them",
    )
    parser.add_argument(
        "--grounding-live-search",
        action="store_true",
        help="Search live providers, then generate and strictly evaluate a grounded local response",
    )
    parser.add_argument(
        "--grounding-live-search-refresh",
        action="store_true",
        help="Force a provider refresh for every grounding repeat instead of allowing the search cache",
    )
    parser.add_argument("--grounding-repeats", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=1)
    return parser.parse_args()


def _is_excellent(result) -> bool:
    # For verified_code cases, execution is the ground truth: a verified result is
    # excellent regardless of prose quality, so a terse-but-correct answer does not
    # misrepresent the model's functional capability to the routing calibration.
    if getattr(result, "verified", False):
        return True
    return result.quality_grade == "excellent"


def _summarize_repeats(reports):
    all_results = [result for report in reports for result in report.results]
    if not all_results:
        return {
            "repeat_count": len(reports),
            "result_count": 0,
            "mean_benchmark_score": 0.0,
            "benchmark_score_stddev": 0.0,
            "excellent_rate": 0.0,
            "all_excellent_run_rate": 0.0,
            "runs": [],
            "by_case": {},
        }

    run_summaries = []
    all_excellent_runs = 0
    for index, report in enumerate(reports, start=1):
        results = report.results
        excellent = sum(_is_excellent(result) for result in results)
        if results and excellent == len(results):
            all_excellent_runs += 1
        run_summaries.append(
            {
                "repeat": index,
                "benchmark_score": round(fmean(result.benchmark_score for result in results), 3) if results else 0.0,
                "quality_score": round(fmean(result.quality_score for result in results), 3) if results else 0.0,
                "excellent_rate": round(excellent / len(results), 3) if results else 0.0,
                "retry_count": sum(result.quality_revision_count for result in results),
                "error_count": sum(bool(result.error) for result in results),
            },
        )

    by_case = {}
    case_results = {}
    for result in all_results:
        case_results.setdefault(result.case_id, []).append(result)
    for case_id, results in sorted(case_results.items()):
        scores = [result.benchmark_score for result in results]
        by_case[case_id] = {
            "repeat_count": len(results),
            "mean_benchmark_score": round(fmean(scores), 3),
            "min_benchmark_score": round(min(scores), 3),
            "benchmark_score_stddev": round(pstdev(scores), 3),
            "excellent_rate": round(sum(_is_excellent(result) for result in results) / len(results), 3),
            "grades": {
                grade: sum(result.quality_grade == grade for result in results)
                for grade in ("excellent", "good", "retry", "fail")
            },
        }

    scores = [result.benchmark_score for result in all_results]
    return {
        "repeat_count": len(reports),
        "result_count": len(all_results),
        "mean_benchmark_score": round(fmean(scores), 3),
        "benchmark_score_stddev": round(pstdev(scores), 3),
        "min_benchmark_score": round(min(scores), 3),
        "excellent_rate": round(sum(_is_excellent(result) for result in all_results) / len(all_results), 3),
        "all_excellent_run_rate": round(all_excellent_runs / len(reports), 3) if reports else 0.0,
        "runs": run_summaries,
        "by_case": by_case,
    }


def main() -> int:
    from antigravity_k.engine.benchmark_harness import BenchmarkHarness
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    args = _parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
    if args.grounding_repeats < 1:
        raise SystemExit("--grounding-repeats must be at least 1")
    manager = ModelManager(ModelRegistry())
    history_path = args.output.with_suffix(".history.json")
    harness = BenchmarkHarness(model_manager=manager, db_path=history_path)
    reports = [harness.run_suite(args.suite, targets=[args.model]) for _ in range(args.repeats)]
    report = reports[-1]
    payload = {
        "schema_version": 2,
        "model": args.model,
        "suite": report.suite_name,
        "repeats": args.repeats,
        "started_at": reports[0].started_at,
        "finished_at": reports[-1].finished_at,
        "duration_s": round(sum(item.duration_s for item in reports), 2),
        "results": [result.to_dict() for result in report.results],
        "stability": _summarize_repeats(reports),
        "runs": [
            {
                "repeat": index,
                "started_at": item.started_at,
                "finished_at": item.finished_at,
                "duration_s": round(item.duration_s, 2),
                "results": [result.to_dict() for result in item.results],
            }
            for index, item in enumerate(reports, start=1)
        ],
    }
    grounding_failed = False
    grounding_modes = sum(
        bool(value) for value in (args.grounding_live, args.grounding_live_search, args.grounding_responses)
    )
    if grounding_modes > 1:
        raise SystemExit("grounding modes are mutually exclusive")
    if grounding_modes:
        from antigravity_k.tools.claim_grounding_benchmark import (
            load_claim_grounding_cases,
            load_claim_responses,
            run_claim_grounding_benchmark,
        )

        grounding_cases = load_claim_grounding_cases(args.grounding_fixture)
        grounding_runs = []
        grounding_run_payloads = []
        for repeat in range(1, args.grounding_repeats + 1):
            search_records = None
            if args.grounding_live_search:
                grounding_results, generated_responses, search_records = _run_live_search_grounding(
                    manager,
                    args.model,
                    grounding_cases,
                    force_refresh=args.grounding_live_search_refresh,
                )
            else:
                generated_responses = (
                    _generate_grounding_responses(manager, args.model, grounding_cases) if args.grounding_live else None
                )
                grounding_responses = generated_responses or load_claim_responses(args.grounding_responses)
                grounding_results = run_claim_grounding_benchmark(grounding_cases, grounding_responses)
            grounding_runs.append(grounding_results)
            run_payload = {
                "repeat": repeat,
                "generated_responses": generated_responses,
                "results": [result.to_dict() for result in grounding_results],
            }
            if search_records is not None:
                run_payload["search"] = search_records
            grounding_run_payloads.append(run_payload)
        grounding_results = grounding_runs[-1]
        grounding_failed = any(not result.passed for run in grounding_runs for result in run)
        payload["grounding"] = {
            "mode": "live_search"
            if args.grounding_live_search
            else ("live_model" if args.grounding_live else "response_file"),
            "model": args.model if (args.grounding_live or args.grounding_live_search) else None,
            "fixture": str(args.grounding_fixture),
            "responses": str(args.grounding_responses),
            "repeat_count": args.grounding_repeats,
            "case_count": len(grounding_results),
            "failed_count": sum(not result.passed for result in grounding_results),
            "generated_responses": grounding_run_payloads[-1]["generated_responses"],
            "stability": _summarize_grounding_runs(grounding_runs),
            "runs": grounding_run_payloads,
            "results": [result.to_dict() for result in grounding_results],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if all(not result.error for item in reports for result in item.results) and not grounding_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
