"""JWS verification for AlgoVoi cross-extension v0 vectors."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

# AlgoVoi JWKS kid d0481df4cbbda8e8aba86709419884ef
ALGOVOI_JWK_X = "GpEhVWMjUqIKDxcANFjaWqRY_BA0sK6NdwpUiouOkhI"


def b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def unsigned_vector(vector: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in vector.items() if k != "jws"}


def canonical_vector_bytes(vector: dict[str, Any]) -> bytes:
    """RFC8785-compatible canonical form (JCS subset: sorted keys, minimal separators)."""
    return json.dumps(unsigned_vector(vector), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def jwk_x_for_manifest(manifest: dict[str, Any]) -> str:
    """Use the artefact key. v0 stays on the AlgoVoi key when the manifest omits one."""
    return manifest.get("jwk_x") or ALGOVOI_JWK_X


def verify_vector_jws(vector: dict[str, Any], *, jwk_x: str = ALGOVOI_JWK_X) -> tuple[bool, str]:
    """Return (ok, detail) per artefact verification_recipe steps 1-6."""
    jws = vector.get("jws")
    if not jws:
        return False, "missing jws"

    parts = jws.split(".")
    if len(parts) != 3:
        return False, "malformed jws"

    header_b64, payload_b64, signature_b64 = parts
    payload_bytes = b64url_decode(payload_b64)
    canonical = canonical_vector_bytes(vector)
    if payload_bytes != canonical:
        return False, "payload bytes != canonical unsigned vector"

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        verify_key = VerifyKey(b64url_decode(jwk_x))
        verify_key.verify(signing_input, b64url_decode(signature_b64))
    except BadSignatureError:
        return False, "invalid Ed25519 signature"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)

    return True, "ok"


def load_manifest(vectors_dir: Path) -> dict[str, Any]:
    return json.loads((vectors_dir / "manifest.json").read_text(encoding="utf-8"))


def load_vector(vectors_dir: Path, vector_id: str) -> dict[str, Any]:
    path = vectors_dir / f"{vector_id}.json"
    if not path.exists():
        raise FileNotFoundError(vector_id)
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_vectors(vectors_dir: Path) -> list[dict[str, Any]]:
    manifest = load_manifest(vectors_dir)
    vectors = []
    for vector_id in manifest["vector_ids"]:
        vectors.append(load_vector(vectors_dir, vector_id))
    return vectors


def validate_vector_shape(vector: dict[str, Any]) -> list[str]:
    """Return list of shape errors (empty if valid)."""
    required = (
        "vector_id",
        "attack_class",
        "composition_layers",
        "input_envelope",
        "expected_verdict",
        "expected_error_code",
        "signer_did",
        "jws",
    )
    errors: list[str] = []
    for field in required:
        if field not in vector:
            errors.append(f"missing required field: {field}")
    if vector.get("expected_verdict") not in ("BLOCK", "REVIEW", "ALLOW"):
        errors.append(f"invalid expected_verdict: {vector.get('expected_verdict')}")
    if not isinstance(vector.get("composition_layers"), list):
        errors.append("composition_layers must be a list")
    if not isinstance(vector.get("input_envelope"), dict):
        errors.append("input_envelope must be an object")
    return errors
