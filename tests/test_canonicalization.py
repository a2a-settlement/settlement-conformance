"""Canonicalization conformance.

manifest.json declares `"canonicalizer": "rfc8785@0.1.4"`. These tests pin
the harness to that, so a vector signed by a conforming RFC 8785 signer
verifies here.

Every case below passes with rfc8785 and fails with the
`json.dumps(sort_keys=True, separators=(",", ":"))` approximation. The
current v0 vectors are unaffected either way, because they are pure ASCII
and carry amounts as strings rather than JSON numbers. The divergence
shows up on the first vector that is not, and it surfaces as
"payload bytes != canonical unsigned vector", which reads like a bad
signature rather than a canonicalizer mismatch.
"""

from __future__ import annotations

import json

import pytest

from harness.jws import canonical_vector_bytes


def canonical(obj: dict) -> bytes:
    # canonical_vector_bytes strips "jws"; nothing here uses that key.
    return canonical_vector_bytes(obj)


def approximation(obj: dict) -> bytes:
    """What the harness used before: not RFC 8785."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


@pytest.mark.parametrize(
    "obj,expected",
    [
        # RFC 8785 section 3.2.4: strings are serialized as UTF-8, not escaped.
        ({"note": "café"}, b'{"note":"caf\xc3\xa9"}'),
        ({"merchant": "München GmbH"}, b'{"merchant":"M\xc3\xbcnchen GmbH"}'),
        # RFC 8785 section 3.2.3: JSON number serialization (ECMAScript).
        ({"amount": 1e16}, b'{"amount":10000000000000000}'),
        ({"amount": -0.0}, b'{"amount":0}'),
    ],
)
def test_canonical_form_is_rfc8785(obj: dict, expected: bytes) -> None:
    assert canonical(obj) == expected
    assert approximation(obj) != expected, "case no longer distinguishes the two"


def test_property_names_sort_by_utf16_code_unit() -> None:
    """RFC 8785 section 3.2.3 sorts property names by UTF-16 code unit.

    U+1F600 is a surrogate pair (0xD83D 0xDE00) so it sorts before
    U+FFFD, which is the opposite of Python's default code point order.
    """
    out = canonical({"�": 1, "\U0001f600": 2}).decode("utf-8")
    assert out.index("\U0001f600") < out.index("�")


def test_existing_v0_vectors_are_unaffected() -> None:
    """The vendored vectors canonicalize identically under both.

    This is why the mismatch has not bitten yet, and it is worth keeping
    as a regression test: it shows the change is signature-preserving for
    everything currently in the corpus.
    """
    from pathlib import Path

    from harness.jws import load_all_vectors, unsigned_vector

    vectors_dir = Path(__file__).resolve().parent.parent / "vectors" / "v0"
    for vector in load_all_vectors(vectors_dir):
        assert canonical_vector_bytes(vector) == approximation(unsigned_vector(vector))
