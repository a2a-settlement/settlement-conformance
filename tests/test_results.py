"""Validate results submissions match the signed vector catalogue.

Every submission under `results/` is checked, not just one hard-coded
rail, and each entry is cross-checked against the signed vector it claims
to report on. Without the cross-check a submission can silently restate a
vector's `expected_verdict` (downgrading BLOCK to REVIEW, for example) and
still validate, which makes the scoreboard unreliable in exactly the way
the README's verdict table is meant to prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.jws import load_all_vectors, load_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = REPO_ROOT / "vectors" / "v0"
RESULTS_DIR = REPO_ROOT / "results"

VALID_RESULTS = ("PASS", "FAIL", "N/A")


def results_files() -> list[Path]:
    if not RESULTS_DIR.is_dir():
        return []
    return sorted(RESULTS_DIR.glob("*/results.json"))


def results_ids() -> list[str]:
    return [p.parent.name for p in results_files()]


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(VECTORS_DIR)


@pytest.fixture(scope="module")
def vectors_by_id():
    return {v["vector_id"]: v for v in load_all_vectors(VECTORS_DIR)}


def test_at_least_one_submission_present():
    assert results_files(), "no results/<rail-id>/results.json found"


@pytest.mark.parametrize("path", results_files(), ids=results_ids())
def test_submission_covers_all_vectors(path: Path, manifest):
    results = json.loads(path.read_text(encoding="utf-8"))
    result_ids = {v["vector_id"] for v in results["vectors"]}
    assert result_ids == set(manifest["vector_ids"]), (
        f"{path.parent.name}: submission does not cover the catalogue exactly"
    )


@pytest.mark.parametrize("path", results_files(), ids=results_ids())
def test_submission_entries_are_well_formed(path: Path, vectors_by_id):
    results = json.loads(path.read_text(encoding="utf-8"))
    rail = path.parent.name

    for entry in results["vectors"]:
        vector_id = entry["vector_id"]
        assert vector_id in vectors_by_id, (
            f"{rail}: unknown vector_id {vector_id!r}, not in the signed catalogue"
        )

        # The signed vector is authoritative for what was expected.
        signed_verdict = vectors_by_id[vector_id]["expected_verdict"]
        assert entry["expected_verdict"] == signed_verdict, (
            f"{rail}/{vector_id}: reports expected_verdict "
            f"{entry['expected_verdict']!r} but the signed vector says "
            f"{signed_verdict!r}"
        )

        assert entry["result"] in VALID_RESULTS, (
            f"{rail}/{vector_id}: invalid result {entry['result']!r}"
        )

        if entry["result"] == "N/A":
            reason = entry.get("reason")
            assert isinstance(reason, str) and reason.strip(), (
                f"{rail}/{vector_id}: N/A requires a non-empty reason"
            )

        if entry["result"] in ("PASS", "FAIL"):
            observed = entry.get("observed")
            assert isinstance(observed, dict) and observed, (
                f"{rail}/{vector_id}: {entry['result']} requires a non-empty "
                f"'observed' object recording what the rail actually did"
            )
