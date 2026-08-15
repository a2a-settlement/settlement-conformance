# Vector format (v0)

v0 adopts the AlgoVoi cross-extension envelope as the baseline. We are not inventing a parallel format — the composition framework, canonicalizer, and JWS shape are AlgoVoi-authored and already published at:

`https://api.algovoi.co.uk/.well-known/cross-extension/v0.json`

Vendored copies live under `vectors/v0/` with provenance in `manifest.json`.

## Artefact structure

Each vector file is a self-contained JSON object:

| Field | Required | Description |
|-------|----------|-------------|
| `vector_id` | yes | Stable identifier, e.g. `cross-ext-v0-escrow-double-release-001` |
| `attack_class` | yes | Machine name for the attack family |
| `composition_layers` | yes | Layer stack exercised (`settlement`, `reputation`, etc.) |
| `input_envelope` | yes | Attack payload — settlement core fields plus attack-specific extensions |
| `expected_verdict` | yes | `BLOCK` or `REVIEW` |
| `expected_error_code` | yes | AlgoVoi reference code (rails are not required to emit this literally) |
| `mediator_behavior` | no | Expected mediator action when verdict is REVIEW |
| `signer_did` | yes | DID of the vector author |
| `jws` | yes | Detached JWS over the unsigned vector |

The manifest (`vectors/v0/manifest.json`) carries artefact metadata: `schema_version`, `kid`, JWKS resolver URL, layer type registry, and the verification recipe.

## Verification recipe

Per AlgoVoi artefact `context.verification_recipe`:

1. Extract the `jws` field; the remaining object is the unsigned vector.
2. Compute RFC 8785 canonical JSON (`sort_keys=True`, minimal separators) over the unsigned vector.
3. Split `jws` on `.` into `[header_b64, payload_b64, signature_b64]`.
4. Confirm `base64url_decode(payload_b64)` equals the canonical bytes from step 2.
5. Resolve `signer_did` to the Ed25519 public key via JWKS (`kid: d0481df4cbbda8e8aba86709419884ef`).
6. Verify Ed25519 signature over `{header_b64}.{payload_b64}`.

Reference implementation: `harness/jws.py`. CI runs this on every PR touching `vectors/`.

## Settlement core fields

For vectors tagged `settlement_kind: a2a-se`, the settlement layer carries:

```
escrow_id, settlement_kind, mandate_hash, amount, currency, rail, chain
```

Attack-specific fields (`release_attempts`, `refund_authorization`, `dispute_history`, etc.) sit alongside the core in `input_envelope`.

A2A-SE typed attestations map the core minus `mandate_hash` — see [attestation-schemas.md](https://github.com/a2a-settlement/a2a-settlement/blob/main/docs/attestation-schemas.md) for the field mapping.

## Verdict adapter

Rails implement their own HTTP APIs and error surfaces. A conformance submission must document how observed behaviour maps to the vector's `expected_verdict`.

### Adapter pattern

```json
{
  "vector_id": "cross-ext-v0-escrow-double-release-001",
  "expected_verdict": "BLOCK",
  "observed": {
    "http_status": 400,
    "detail_substring": "already released"
  },
  "result": "PASS",
  "adapter_notes": "Second POST /exchange/release on terminal escrow returns 400"
}
```

### Mapping rules

| `expected_verdict` | Pass condition |
|--------------------|----------------|
| `BLOCK` | Attack rejected — no unsafe state transition, typically HTTP 4xx |
| `REVIEW` | Attack flagged for review — HTTP 4xx or explicit review/hold response; auto-approve is FAIL |

Rails that lack a REVIEW tier may map `REVIEW` vectors to `N/A` until the gate exists. Do not claim PASS on a gate you have not built.

### Error codes

`expected_error_code` values like `RELEASE_IDEMPOTENCY_VIOLATION` are reference labels from the AlgoVoi envelope. Match on behaviour (blocked release, blocked replay), not on string equality in response bodies.

## Contributing vectors

1. Fork, add `vectors/v0/<vector-id>.json`.
2. Include valid JWS per the verification recipe (or coordinate with maintainers for signing).
3. Update `vectors/v0/manifest.json` `vector_ids` list.
4. CI must pass JWS verification before merge.

Candidate categories for the next intake, once fixtures exist: `dispute_dos`, `reputation_manipulation`, `cascade_refund`, `skill_pricing_bait`.

## Results submission format

`results/<rail-id>/results.json`:

```json
{
  "rail_id": "a2a-se",
  "rail_url": "https://exchange.a2a-settlement.org",
  "artefact_id": "cross-extension-v0",
  "schema_version": "1.1",
  "tested_at": "2026-06-10T00:00:00Z",
  "commit": "<git-sha or deploy tag>",
  "vectors": [ ... ]
}
```

Each entry in `vectors` follows the adapter pattern above. Include a short `README.md` explaining how you ran the tests (in-process pytest, live HTTP, etc.).
