# settlement-conformance

Adversarial conformance track for settlement-capable A2A extensions.

Neutral home for signed attack vectors, rail result submissions, and a reference verification harness. Started from the [#1576](https://github.com/a2aproject/A2A/discussions/1576) thread — the goal is a shared test corpus any settlement rail can run against and report back on honestly.

## Scope

Vectors cover settlement-layer attacks and cross-extension compositions:

- **escrow_double_release** — second payout on a terminal escrow
- **refund_replay** — replayed or cross-bound refund authorization
- **dispute_amplification** — concurrent dispute flooding
- **synthetic_artifact_dispute** — evidence hash mismatch in disputes
- **mediator_grooming** — reputation velocity anomalies

v0 adopts the AlgoVoi cross-extension envelope (schema_version 1.1, JWS-signed). See [docs/vector-format.md](docs/vector-format.md).

## Governance

| Role | GitHub | Status |
|------|--------|--------|
| Chair | [@widrss](https://github.com/widrss) | active |
| Maintainer (invited) | [@chopmob-cloud](https://github.com/chopmob-cloud) | pending acceptance |

Chair runs the track day-to-day: vector intake, result review, release tagging. Maintainers can merge vectors and results PRs. Invites go out at repo creation — if either declines, chair keeps the seat open until someone else steps up.

New vectors: PR to `vectors/v0/` (or `vectors/v1/` when we cut the next generation). JWS must verify in CI.

## How a rail participates

1. **Run** the vectors your rail owns. For `settlement_kind: a2a-se`, that's the two settlement vectors in v0; others may be N/A until you implement the gate.
2. **Map** rail behaviour to verdicts. Rails won't emit AlgoVoi's literal `expected_error_code` strings — use a verdict adapter (HTTP status + detail substring, or your own error taxonomy). Document the mapping in your results README.
3. **Submit** a PR adding `results/<rail-id>/results.json` + short prose README. Partial results are fine — N/A with a reason is better than silence.

### Verdict semantics

| Vector field | Meaning |
|--------------|---------|
| `expected_verdict: BLOCK` | Rail must reject the attack (no funds moved, no unsafe state transition) |
| `expected_verdict: REVIEW` | Rail should flag for human/mediator review rather than auto-approve |

| Result | Meaning |
|--------|---------|
| `PASS` | Rail behaviour matches expected verdict |
| `FAIL` | Rail accepted the attack or returned wrong verdict class |
| `N/A` | Vector not applicable to this rail yet — include `reason` |

## Layout

```
vectors/v0/          Signed attack vectors (one JSON file per vector + manifest)
results/<rail-id>/   Per-rail conformance submissions
harness/             Reference JWS verification + optional HTTP rail runner
docs/                Format specs and contribution notes
```

## Quick start

```bash
# Verify all v0 vector signatures
pip install -r harness/requirements.txt
python -m pytest tests/ -v

# Optional: run settlement vectors against a live rail
export RAIL_BASE_URL=https://exchange.a2a-settlement.org/api/v1
export RAIL_API_KEY=...
python -m harness.run_rail --vectors vectors/v0
```

## Current results

| Rail | Vectors run | PASS | N/A | Last updated |
|------|-------------|------|-----|--------------|
| [a2a-se](results/a2a-se/) | 5 | 2 | 3 | 2026-06-10 |

## Related work

- A2A-SE exchange conformance run: [a2a-settlement/docs/conformance-results.md](https://github.com/a2a-settlement/a2a-settlement/blob/main/docs/conformance-results.md)
- AlgoVoi cross-extension artefact: `https://api.algovoi.co.uk/.well-known/cross-extension/v0.json`
- Discussion home: [a2aproject/A2A#1576](https://github.com/a2aproject/A2A/discussions/1576)
