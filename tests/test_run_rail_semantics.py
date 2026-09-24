"""Unsupported vectors are not a pass, and execution verifies the selected signature."""

from __future__ import annotations

import json
from pathlib import Path

from harness.jws import jwk_x_for_manifest, load_vector, verify_vector_jws
from harness.run_rail import main

ROOT = Path(__file__).resolve().parents[1]
ASSURANCE = ROOT / "vectors" / "assurance-v1"


def test_assurance_vectors_verify_with_manifest_key():
    manifest = json.loads((ASSURANCE / "manifest.json").read_text())
    vector = load_vector(ASSURANCE, "assurance-v1-delegation-widening-001")
    ok, detail = verify_vector_jws(vector, jwk_x=jwk_x_for_manifest(manifest))
    assert ok, detail


def test_unsupported_vector_is_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("RAIL_BASE_URL", "http://127.0.0.1:9")
    src = ASSURANCE
    dest = tmp_path / "vectors"
    dest.mkdir()
    manifest = json.loads((src / "manifest.json").read_text())
    manifest["vector_ids"] = ["assurance-v1-delegation-widening-001"]
    (dest / "manifest.json").write_text(json.dumps(manifest))
    (dest / "assurance-v1-delegation-widening-001.json").write_text(
        (src / "assurance-v1-delegation-widening-001.json").read_text()
    )
    assert main(["--vectors", str(dest)]) == 1
