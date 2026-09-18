"""Consistency checks for the unsigned #1576 intake candidates."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from harness.jws import verify_vector_jws


INTAKE_DIR = (
    Path(__file__).resolve().parent.parent
    / "vectors"
    / "intake"
    / "eriknewton-1576"
)

EXPECTED = {
    "cross-ext-v0-intake-dispute-dos-001": {
        "attack_class": "dispute_dos",
        "expected_verdict": "BLOCK",
        "expected_error_code": "DUPLICATE_DISPUTE_IDEMPOTENCY_REPLAY",
    },
    "cross-ext-v0-intake-reputation-manipulation-001": {
        "attack_class": "reputation_manipulation",
        "expected_verdict": "REVIEW",
        "expected_error_code": "REPUTATION_INDEPENDENCE_VIOLATION",
    },
    "cross-ext-v0-intake-cascade-refund-001": {
        "attack_class": "cascade_refund",
        "expected_verdict": "BLOCK",
        "expected_error_code": "REFUND_SCOPE_OVERLAP_OR_BUDGET_EXCEEDED",
    },
    "cross-ext-v0-intake-skill-pricing-bait-001": {
        "attack_class": "skill_pricing_bait",
        "expected_verdict": "BLOCK",
        "expected_error_code": "SKILL_PRICE_EXCEEDS_AUTHORIZATION",
    },
}

TOP_LEVEL_FIELDS = {
    "vector_id",
    "attack_class",
    "composition_layers",
    "input_envelope",
    "expected_verdict",
    "expected_error_code",
    "mediator_behavior",
}

CORE_ENVELOPE_FIELDS = {
    "escrow_id",
    "settlement_kind",
    "mandate_hash",
    "amount",
    "currency",
    "rail",
    "chain",
    "attack_fixture",
}


@pytest.fixture(scope="module")
def candidates() -> list[dict]:
    paths = sorted(INTAKE_DIR.glob("*.json"))
    assert {path.stem for path in paths} == {
        "dispute-dos-001",
        "reputation-manipulation-001",
        "cascade-refund-001",
        "skill-pricing-bait-001",
    }
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def test_candidates_have_expected_categories_and_unsigned_shape(candidates: list[dict]) -> None:
    assert {candidate["vector_id"]: {
        "attack_class": candidate["attack_class"],
        "expected_verdict": candidate["expected_verdict"],
        "expected_error_code": candidate["expected_error_code"],
    } for candidate in candidates} == EXPECTED
    for candidate in candidates:
        assert set(candidate) == TOP_LEVEL_FIELDS
        assert candidate["expected_verdict"] in {"BLOCK", "REVIEW"}
        assert candidate["input_envelope"]["settlement_kind"] == "a2a-se"
        assert set(candidate["input_envelope"]) == CORE_ENVELOPE_FIELDS
        assert not _contains_signing_field(candidate)


def test_each_policy_fixture_has_expected_outcome_and_failure_oracle(
    candidates: list[dict],
) -> None:
    for candidate in candidates:
        fixture = candidate["input_envelope"]["attack_fixture"]
        assert set(fixture) == {
            "policy",
            "pre_state",
            "attempted_operation",
            "expected_outcome",
            "failure_oracle",
            "boundary_control",
        }
        assert fixture["expected_outcome"]["verdict"] == candidate["expected_verdict"]
        assert fixture["expected_outcome"]["error_code"] == candidate["expected_error_code"]
        assert fixture["policy"]
        assert fixture["pre_state"]
        assert fixture["attempted_operation"]
        assert fixture["failure_oracle"]["must_hold"]
        assert fixture["boundary_control"]["expected_behavior"]


def test_each_category_keeps_its_distinguishing_policy_and_control(
    candidates: list[dict],
) -> None:
    by_category = {candidate["attack_class"]: candidate for candidate in candidates}

    dispute = by_category["dispute_dos"]["input_envelope"]["attack_fixture"]
    dispute_attempt = dispute["attempted_operation"]
    existing_dispute = dispute["pre_state"]["disputes"][0]
    dispute_control = dispute["boundary_control"]
    assert dispute["policy"]["duplicate_idempotency_replay_consumes_budget"] is False
    assert dispute_attempt["replays"] > 1
    assert dispute_attempt["dispute_id"] == existing_dispute["dispute_id"]
    assert dispute_attempt["idempotency_key"] == existing_dispute["idempotency_key"]
    assert dispute["policy"]["max_new_disputes"] - len(dispute["pre_state"]["disputes"]) == dispute["pre_state"]["dispute_budget_remaining"]
    assert dispute["pre_state"]["dispute_budget_remaining"] > 0
    assert dispute_control["dispute_id"] != existing_dispute["dispute_id"]
    assert dispute_control["idempotency_key"] != existing_dispute["idempotency_key"]
    assert dispute_control["precondition"]

    reputation = by_category["reputation_manipulation"]["input_envelope"]["attack_fixture"]
    reputation_attempt = reputation["attempted_operation"]
    reputation_pre_state = reputation["pre_state"]
    reputation_cluster = set(reputation_pre_state["known_controller_cluster"])
    feedback_authors = {entry["reviewer_did"] for entry in reputation_attempt["feedback"]}
    reputation_control = reputation["boundary_control"]
    assert reputation["policy"]["independent_counterparty_required"] is True
    assert reputation["expected_outcome"]["verdict"] == "REVIEW"
    assert reputation_attempt["subject_agent_did"] in feedback_authors
    assert feedback_authors <= reputation_cluster
    assert reputation_control["reviewer_did"] not in reputation_cluster
    eligible = reputation_pre_state["eligible_independent_counterparties"][0]
    assert eligible["reviewer_did"] == reputation_control["reviewer_did"]
    assert eligible["settled_escrow_id"] == reputation_attempt["feedback"][0]["settled_escrow_id"]
    assert eligible["prior_feedback"] is False
    assert eligible["controller_differs_from_subject"] is True

    refund = by_category["cascade_refund"]["input_envelope"]["attack_fixture"]
    refund_pre_state = refund["pre_state"]
    refund_attempt = refund["attempted_operation"]
    credited_parent = refund_pre_state["refunds_credited"][0]
    refund_control = refund["boundary_control"]
    budget_total = Decimal(refund["policy"]["refund_budget"])
    budget_used = Decimal(refund_pre_state["refund_budget_used"])
    budget_remaining = Decimal(refund_pre_state["refund_budget_remaining"])
    assert refund["policy"]["parent_child_overlap_forbidden"] is True
    assert Decimal(refund_pre_state["refund_budget_total"]) == budget_total
    assert budget_used + budget_remaining == budget_total
    assert Decimal(refund_attempt["amount"]) > budget_remaining
    assert refund_attempt["parent_refund_id"] == credited_parent["refund_id"]
    assert refund_attempt["scope"] == credited_parent["scope"]
    assert Decimal(refund_control["amount"]) <= budget_remaining
    assert refund_control["scope"] != credited_parent["scope"]

    pricing = by_category["skill_pricing_bait"]["input_envelope"]["attack_fixture"]
    pricing_pre_state = pricing["pre_state"]
    pricing_attempt = pricing["attempted_operation"]
    pricing_control = pricing["boundary_control"]
    for key in ("skill_id", "skill_version", "promised_skill"):
        assert pricing_pre_state[key] == pricing_attempt[key] == pricing_control[key]
    max_authorized = Decimal(pricing["policy"]["max_authorized_price"])
    assert Decimal(pricing_attempt["actual_price"]) > max_authorized
    assert Decimal(pricing_control["actual_price"]) == Decimal(pricing_control["quoted_price"])
    assert Decimal(pricing_control["actual_price"]) <= max_authorized


@pytest.mark.parametrize("expected_category", sorted(item["attack_class"] for item in EXPECTED.values()))
def test_current_verifier_rejects_unsigned_candidate(
    candidates: list[dict], expected_category: str
) -> None:
    candidate = next(item for item in candidates if item["attack_class"] == expected_category)
    ok, detail = verify_vector_jws(candidate)
    assert not ok
    assert detail == "missing jws"


def _contains_signing_field(value: object) -> bool:
    """Reject signing material anywhere in an unsigned candidate fixture."""
    forbidden = {"signer_did", "jws", "signature", "kid", "jwk", "public_key"}
    if isinstance(value, dict):
        return any(key in forbidden or _contains_signing_field(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_signing_field(child) for child in value)
    return False
