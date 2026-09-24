"""CLI: validate vector JSON shape and JWS signatures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness.jws import (
    jwk_x_for_manifest,
    load_all_vectors,
    load_manifest,
    validate_vector_shape,
    verify_vector_jws,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate conformance vectors")
    parser.add_argument(
        "--vectors",
        type=Path,
        default=Path("vectors/v0"),
        help="Path to vector directory",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest(args.vectors)
    vectors = load_all_vectors(args.vectors)
    errors: list[str] = []

    if len(vectors) != len(manifest["vector_ids"]):
        errors.append(
            f"vector count mismatch: manifest={len(manifest['vector_ids'])} files={len(vectors)}"
        )

    for vector in vectors:
        vid = vector.get("vector_id", "<unknown>")
        shape_errors = validate_vector_shape(vector)
        for err in shape_errors:
            errors.append(f"{vid}: {err}")
        ok, detail = verify_vector_jws(vector, jwk_x=jwk_x_for_manifest(manifest))
        if not ok:
            errors.append(f"{vid}: jws verification failed: {detail}")
        else:
            print(f"OK {vid}")

    if errors:
        for err in errors:
            print(f"ERROR {err}", file=sys.stderr)
        return 1

    print(f"All {len(vectors)} vectors valid ({manifest['artefact_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
