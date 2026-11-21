"""Tests for the deterministic parts of the evaluation code (no LLM, no network)."""

from evaluation.report import stage
from evaluation.retrieval_check import first_hit_rank
from evaluation.score_deterministic import abstained


def test_first_hit_rank_finds_first_expected():
    assert first_hit_rank(["a", "b", "c"], {"c", "b"}) == 2


def test_first_hit_rank_none_when_absent():
    assert first_hit_rank(["a", "b"], {"z"}) is None


def test_abstained_handles_curly_apostrophe():
    assert abstained("I don\u2019t have enough information to answer this.")
    assert not abstained("Apple had about 166,000 employees.")


def _golden(route="sec", chunks=("c1",)):
    return {"expected_route": route, "expected_chunk_ids": list(chunks)}


def _answer(route="sec", sources=("c1",), text="An answer."):
    return {"route": route, "source_ids": list(sources), "answer": text}


def test_stage_blames_routing_first():
    # Wrong route AND missing chunk: routing is the earliest failure, so it is blamed
    assert stage(_golden(), _answer(route="news", sources=()), cov=0.0) == "routing"


def test_stage_retrieval_when_route_right_but_chunk_missing():
    assert stage(_golden(), _answer(sources=("other",)), cov=0.0) == "retrieval"


def test_stage_incomplete_and_ok():
    assert stage(_golden(), _answer(), cov=0.5) == "incomplete"
    assert stage(_golden(), _answer(), cov=1.0) == "ok"
    