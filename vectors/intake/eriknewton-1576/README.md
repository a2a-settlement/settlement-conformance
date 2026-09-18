# Erik Newton #1576 intake candidates

These four files are unsigned, synthetic public examples proposed for the next
intake round in [A2A discussion #1576](https://github.com/a2aproject/A2A/discussions/1576).
They are scoped policy fixtures, not claims about universal rail behaviour and
not results from a rail run. No `PASS` result is asserted here.

Each fixture uses the v0 envelope fields that can be prepared before admission,
omitting `signer_did` and `jws`. The `input_envelope.attack_fixture` object makes
the policy or bound, pre-state, attempted operation, expected `BLOCK` or
`REVIEW` decision, failure oracle, and a minimal benign boundary control
explicit. The controls exercise the adjacent allowed case:

| Category | Attack boundary | Benign boundary control |
| --- | --- | --- |
| `dispute_dos` | Replaying one dispute idempotency key must not consume the scarce dispute budget. | A new dispute id and key consumes one remaining budget unit exactly once. |
| `reputation_manipulation` | Self and same-controller cluster feedback cannot raise weighted reputation; hold it for review. | One feedback item from an independent settled counterparty remains eligible for normal weighting. |
| `cascade_refund` | An overlapping child refund of `20.000000` cannot follow a parent credit of `25.000000` when only `15.000000` remains. | A disjoint `10.000000` child refund fits the remaining budget and may be credited once. |
| `skill_pricing_bait` | The same promised skill changing from `100.000000` to `165.000000` exceeds the `120.000000` authorization. | Capturing at the unchanged quoted `100.000000` price is allowed. |

The examples use `example.org`-style identifiers and deterministic synthetic
hashes only. They contain no private product details, credentials, signing
material, or canonical-admission claim.

Integral numeric values are written as JSON integers where applicable (for
example, the manipulated rating is `1`, rather than `1.0`) to remain stable
with the current harness serializer. Full RFC 8785 numeric normalization is a
separate upstream PR2 concern and is intentionally outside this fixture-only
contribution; the verifier is unchanged.

## Maintainer admission path

Maintainers should review the fixture semantics and adapt only if the proposed
policy test itself is wrong. To sign and admit a candidate, keep all proposed
semantic fields and values byte-for-byte unchanged, add the intended
`signer_did`, compute the v0 canonical unsigned payload, and add the generated
`jws`. The maintainer may then copy the signed object into `vectors/v0/` and
update the v0 manifest as part of the normal admission review. The candidate
files here must remain unsigned until that process occurs; the current verifier
is expected to reject them with `missing jws`.

These fixtures do not change the v0 manifest, verifier, signing harness, or
any signed v0 vector.
