import time

import pytest

from antigravity_k.engine.memory_contracts import MemoryFact, MemoryFactAuthority
from antigravity_k.engine.memory_importance import _HALF_LIFE_DAYS, _RECENCY_WEIGHT, rank_facts, score_fact


def _fact(
    key: str,
    authority: MemoryFactAuthority = MemoryFactAuthority.PROJECT_DECISION,
    value: str = "postgresql",
    observed_at: float | None = None,
) -> MemoryFact:
    return MemoryFact(
        key=key,
        value=value,
        source="test",
        scope="project",
        authority=authority,
        observed_at=time.time() if observed_at is None else observed_at,
    )


def test_higher_authority_scores_higher() -> None:
    now = time.time()
    low = _fact("low", MemoryFactAuthority.INFERRED_PREFERENCE, observed_at=now)
    high = _fact("high", MemoryFactAuthority.CURRENT_USER, observed_at=now)
    assert score_fact(high, now=now) > score_fact(low, now=now)


def test_older_fact_scores_lower() -> None:
    now = time.time()
    fresh = _fact("fresh", observed_at=now)
    old = _fact("old", observed_at=now - 90 * 86400)
    assert score_fact(fresh, now=now) > score_fact(old, now=now)


def test_longer_value_scores_higher() -> None:
    now = time.time()
    terse = _fact("terse", value="sqlite", observed_at=now)
    verbose = _fact("verbose", value="postgresql with pgvector for similarity search", observed_at=now)
    assert score_fact(verbose, now=now) > score_fact(terse, now=now)


def test_recency_halves_at_half_life() -> None:
    now = time.time()
    fact = _fact("decay", observed_at=now)
    fresh_score = score_fact(fact, now=now)
    half_score = score_fact(fact, now=now + _HALF_LIFE_DAYS * 86400)
    assert fresh_score - half_score == pytest.approx(_RECENCY_WEIGHT / 2, abs=1e-6)


def test_score_deterministic_with_fixed_now() -> None:
    now = time.time()
    fact = _fact("fixed", observed_at=now - 3600)
    assert score_fact(fact, now=now) == score_fact(fact, now=now)


def test_rank_facts_sorts_descending() -> None:
    now = time.time()
    facts = [
        _fact("a", MemoryFactAuthority.INFERRED_PREFERENCE, observed_at=now),
        _fact("b", MemoryFactAuthority.CURRENT_USER, observed_at=now),
        _fact("c", MemoryFactAuthority.PROJECT_DECISION, observed_at=now),
    ]
    ranked = rank_facts(facts, now=now)
    assert [fact.key for fact, _ in ranked] == ["b", "c", "a"]
    assert ranked[0][1] > ranked[1][1] > ranked[2][1]


def test_rank_facts_top_k() -> None:
    now = time.time()
    facts = [_fact(f"k{i}", observed_at=now) for i in range(5)]
    assert len(rank_facts(facts, now=now, top_k=2)) == 2


def test_rank_facts_empty() -> None:
    assert rank_facts([]) == []