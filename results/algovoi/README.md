# results/algovoi

AlgoVoi (chopmob-cloud) conformance results for `cross-extension-v0`.

## Role

AlgoVoi is the **signer and verifier** of the `cross-extension-v0` fixture, not a
settlement rail. Per [`vectors/v0/manifest.json`](../../vectors/v0/manifest.json)
`layer_type_provenance`, the composition envelope (composition_layers framework,
canonicaliser, verification recipe, JWS shape) and the `settlement` and
`reputation` layer types are AlgoVoi-authored; the artefacts are signed by
`did:web:api.algovoi.co.uk` (kid `d0481df4cbbda8e8aba86709419884ef`).

Settlement-rail verdicts (BLOCK / REVIEW / N/A) are reported by the rails that run
them — see [`results/a2a-se`](../a2a-se) (widrss / A2A-SE, #1576).

## Result

**5/5 JWS signatures verify** against the AlgoVoi production JWKS, over the
`rfc8785@0.1.4` canonical form the manifest declares. Re-verified live on
2026-06-17 against the as-published `vectors/v0` fixtures.

| Vector | attack_class | expected_verdict | jws_valid |
|---|---|---|---|
| escrow-double-release-001 | escrow_double_release | BLOCK | ✓ |
| refund-replay-001 | refund_replay | BLOCK | ✓ |
| dispute-amplification-001 | dispute_amplification | BLOCK | ✓ |
| synthetic-artifact-dispute-001 | synthetic_artifact_dispute | REVIEW | ✓ |
| mediator-grooming-001 | mediator_grooming | REVIEW | ✓ |

`escrow_double_release` and `refund_replay` map to BLOCK on the settlement rail,
matching the `results/a2a-se` conformance results. `dispute_amplification` is a
live Agent Trust Bench (ATB) category (three profiles).

## Reproduce

```
# public key: JWKS kid d0481df4cbbda8e8aba86709419884ef at
#   https://api.algovoi.co.uk/.well-known/jwks.json   (OKP / Ed25519)
# for each vectors/v0/*.json:
#   header.payload.signature = vector.jws         (compact JWS)
#   verify Ed25519(pubkey, ASCII(header + "." + payload), b64url_decode(signature))
```

All five verify. The signing base is the JCS (RFC 8785) canonical form; the JWS
header declares `alg=EdDSA`.

## Provenance

- Substrate: `draft-hopley-x402-settlement-attestation` and the AlgoVoi JCS
  conformance corpus (`chopmob-cloud/algovoi-jcs-conformance-vectors`).
- Signer: `did:web:api.algovoi.co.uk`.
- Thread: a2aproject/A2A Discussion #1832; settlement leg #1576.
