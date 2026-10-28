"""Validate results submissions match vector catalogue."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.jws import load_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = REPO_ROOT / "vectors" / "v0"
RESULTS_PATHS = (
    pytest.param(("a2a-se", REPO_ROOT / "results" / "a2a-se" / "results.json"), id="a2a-se"),
    pytest.param(("algovoi", REPO_ROOT / "results" / "algovoi" / "results.json"), id="algovoi"),
)


@pytest.fixture(scope="module", params=RESULTS_PATHS)
def results(request):
    rail_id, path = request.param
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["rail_id"] == rail_id
    return payload


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(VECTORS_DIR)


def test_results_cover_all_vectors(results, manifest):
    result_ids = {v["vector_id"] for v in results["vectors"]}
    assert result_ids == set(manifest["vector_ids"])


def test_results_have_valid_verdicts(results):
    for entry in results["vectors"]:
        assert entry["expected_verdict"] in ("BLOCK", "REVIEW")
        assert entry["result"] in ("PASS", "FAIL", "N/A")
        if entry["result"] == "N/A":
            assert "reason" in entry
        if entry["result"] == "PASS":
            if results["rail_id"] == "a2a-se":
                assert "observed" in entry
            else:
                assert entry.get("jws_valid") is True
                assert "notes" in entry
