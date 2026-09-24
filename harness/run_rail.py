"""Optional HTTP runner for settlement vectors against a live rail.

Usage:
    export RAIL_BASE_URL=https://exchange.a2a-settlement.org/api/v1
    export RAIL_REQUESTER_API_KEY=...
    python -m harness.run_rail --vectors vectors/v0

Exits 0 only when every selected vector has a runner and passes.
A vector without a runner is UNSUPPORTED and fails the process.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

from harness.jws import jwk_x_for_manifest, load_all_vectors, load_manifest, verify_vector_jws

SETTLEMENT_RUNNERS = {
    "escrow_double_release",
    "refund_replay",
    "premature_release",
    "sibling_over_budget",
}


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def run_escrow_double_release(client: httpx.Client, api_key: str, envelope: dict | None = None) -> tuple[bool, str]:
    """Create escrow, release twice; second release must be blocked."""
    reg = client.post(
        "/accounts/register",
        json={
            "bot_name": "ConfProvider",
            "developer_id": "conf",
            "developer_name": "Conf",
            "contact_email": "conf@test.dev",
            "skills": ["conformance"],
        },
    )
    if reg.status_code != 200:
        return False, f"provider register failed: {reg.status_code} {reg.text}"
    provider_id = reg.json()["account"]["id"]
    provider_key = reg.json()["api_key"]

    req = client.post(
        "/accounts/register",
        json={
            "bot_name": "ConfRequester",
            "developer_id": "conf",
            "developer_name": "Conf",
            "contact_email": "conf2@test.dev",
            "skills": ["conformance"],
        },
    )
    if req.status_code != 200:
        return False, f"requester register failed: {req.status_code} {req.text}"
    requester_key = req.json()["api_key"]

    escrow = client.post(
        "/exchange/escrow",
        headers=_headers(requester_key),
        json={"provider_id": provider_id, "amount": 10},
    )
    if escrow.status_code != 200:
        return False, f"escrow create failed: {escrow.status_code} {escrow.text}"
    escrow_id = escrow.json()["escrow_id"]

    first = client.post(
        "/exchange/release",
        headers=_headers(requester_key),
        json={"escrow_id": escrow_id},
    )
    if first.status_code != 200:
        return False, f"first release failed: {first.status_code} {first.text}"

    second = client.post(
        "/exchange/release",
        headers=_headers(requester_key),
        json={"escrow_id": escrow_id},
    )
    if second.status_code != 400:
        return False, f"expected 400 on double release, got {second.status_code}"
    if "already released" not in second.json().get("detail", "").lower():
        return False, f"unexpected detail: {second.json()}"
    return True, "PASS"


def run_refund_replay(client: httpx.Client, api_key: str, envelope: dict | None = None) -> tuple[bool, str]:
    """Refund terminal escrow twice; replay must be blocked."""
    reg = client.post(
        "/accounts/register",
        json={
            "bot_name": "ConfProvider2",
            "developer_id": "conf",
            "developer_name": "Conf",
            "contact_email": "conf3@test.dev",
            "skills": ["conformance"],
        },
    )
    if reg.status_code != 200:
        return False, f"provider register failed: {reg.status_code}"
    provider_id = reg.json()["account"]["id"]

    req = client.post(
        "/accounts/register",
        json={
            "bot_name": "ConfRequester2",
            "developer_id": "conf",
            "developer_name": "Conf",
            "contact_email": "conf4@test.dev",
            "skills": ["conformance"],
        },
    )
    if req.status_code != 200:
        return False, f"requester register failed: {req.status_code}"
    requester_key = req.json()["api_key"]

    amount = int((envelope or {}).get("amount") or 10)
    escrow = client.post(
        "/exchange/escrow",
        headers=_headers(requester_key),
        json={"provider_id": provider_id, "amount": amount},
    )
    if escrow.status_code not in (200, 201):
        return False, f"escrow create failed: {escrow.status_code} {escrow.text}"
    escrow_id = escrow.json()["escrow_id"]

    first_refund = client.post(
        "/exchange/refund",
        headers=_headers(requester_key),
        json={"escrow_id": escrow_id},
    )
    if first_refund.status_code not in (200, 201):
        return False, f"first refund failed: {first_refund.status_code} {first_refund.text}"
    replay = client.post(
        "/exchange/refund",
        headers=_headers(requester_key),
        json={"escrow_id": escrow_id},
    )
    if replay.status_code != 400:
        return False, f"expected 400 on refund replay, got {replay.status_code}"
    if "already refunded" not in replay.json().get("detail", "").lower():
        return False, f"unexpected detail: {replay.json()}"
    return True, "PASS"


def run_premature_release(client: httpx.Client, api_key: str, envelope: dict | None = None) -> tuple[bool, str]:
    """Release without a bound acceptance record must not move funds.

    Requires RAIL_OPERATOR_API_KEY for an account that can write obligation policy.
    The runner records balances before and after the rejected release.
    """
    del api_key
    env = envelope or {}
    operator_key = os.environ.get("RAIL_OPERATOR_API_KEY", "")
    if not operator_key:
        return False, "RAIL_OPERATOR_API_KEY is required for the premature-release vector"
    amount = int(env.get("amount") or 10)
    task_id = env.get("task_id") or "assurance-task"
    criteria = env.get("criteria_hash") or ("ab" * 32)

    def reg(name: str, email: str) -> tuple[bool, dict | str]:
        resp = client.post(
            "/accounts/register",
            json={
                "bot_name": name,
                "developer_id": "assurance",
                "developer_name": "Assurance",
                "contact_email": email,
                "skills": ["assurance"],
            },
        )
        if resp.status_code not in (200, 201):
            return False, f"register {name} failed: {resp.status_code} {resp.text}"
        return True, resp.json()

    ok, requester = reg("AssuranceRequester", "ar@test.dev")
    if not ok:
        return False, str(requester)
    ok, provider = reg("AssuranceProvider", "ap@test.dev")
    if not ok:
        return False, str(provider)
    ok, approver = reg("AssuranceApprover", "aa@test.dev")
    if not ok:
        return False, str(approver)

    budget = client.post(
        "/exchange/assurance/root-budgets",
        headers=_headers(operator_key),
        json={"principal_account_id": requester["account"]["id"], "limit_units": 1000},
    )
    if budget.status_code not in (200, 201):
        return False, f"root budget failed: {budget.status_code} {budget.text}"
    policy = client.post(
        "/exchange/assurance/policies",
        headers=_headers(operator_key),
        json={
            "principal_account_id": requester["account"]["id"],
            "task_id": task_id,
            "criteria_hash": criteria,
            "authorized_approver_id": approver["account"]["id"],
            "root_budget_id": budget.json()["root_budget_id"],
            "acceptance_required": True,
        },
    )
    if policy.status_code not in (200, 201):
        return False, f"policy failed: {policy.status_code} {policy.text}"
    bound = client.post(
        "/exchange/assurance/bind-account",
        headers=_headers(operator_key),
        json={"account_id": requester["account"]["id"], "policy_id": policy.json()["policy_id"]},
    )
    if bound.status_code not in (200, 201):
        return False, f"bind failed: {bound.status_code} {bound.text}"

    provider_before = client.get("/exchange/balance", headers=_headers(provider["api_key"]))
    if provider_before.status_code != 200:
        return False, f"provider balance before failed: {provider_before.status_code}"
    escrow = client.post(
        "/exchange/escrow",
        headers={**_headers(requester["api_key"]), "Idempotency-Key": "assurance-create"},
        json={"provider_id": provider["account"]["id"], "amount": amount, "task_id": task_id},
    )
    if escrow.status_code not in (200, 201):
        return False, f"escrow create failed: {escrow.status_code} {escrow.text}"
    escrow_id = escrow.json()["escrow_id"]
    release = client.post(
        "/exchange/release",
        headers={**_headers(requester["api_key"]), "Idempotency-Key": "assurance-release"},
        json={"escrow_id": escrow_id},
    )
    after = client.get("/exchange/balance", headers=_headers(provider["api_key"]))
    if release.status_code < 400:
        return False, f"premature release was not blocked: {release.status_code}"
    if after.status_code == 200 and after.json().get("available") != provider_before.json().get("available"):
        return False, "provider balance changed without acceptance"
    detail = client.get(f"/exchange/assurance/escrows/{escrow_id}", headers=_headers(requester["api_key"]))
    if detail.status_code == 200 and detail.json().get("status") == "released":
        return False, "escrow released without acceptance"
    return True, f"BLOCK status={release.status_code} escrow={escrow_id}"


def run_sibling_over_budget(client: httpx.Client, api_key: str, envelope: dict | None = None) -> tuple[bool, str]:
    """Two sibling holds must not exceed the locked root budget."""
    del api_key
    env = envelope or {}
    operator_key = os.environ.get("RAIL_OPERATOR_API_KEY", "")
    if not operator_key:
        return False, "UNSUPPORTED RAIL_OPERATOR_API_KEY is required; not a pass"
    amount = int(env.get("amount") or 10)
    limit_units = int(env.get("limit_units") or amount)
    task_id = env.get("task_id") or "assurance-budget"

    def reg(name: str) -> dict:
        resp = client.post(
            "/accounts/register",
            json={
                "bot_name": name,
                "developer_id": "assurance",
                "developer_name": "Assurance",
                "contact_email": f"{name}@test.dev",
                "skills": ["assurance"],
            },
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"register {name}: {resp.status_code} {resp.text}")
        return resp.json()

    try:
        requester = reg("BudgetRequester")
        sibling = reg("BudgetSibling")
        provider_a = reg("BudgetProviderA")
        provider_b = reg("BudgetProviderB")
        approver = reg("BudgetApprover")
    except RuntimeError as exc:
        return False, str(exc)
    criteria = "cd" * 32
    budget = client.post(
        "/exchange/assurance/root-budgets",
        headers=_headers(operator_key),
        json={"principal_account_id": requester["account"]["id"], "limit_units": limit_units},
    )
    if budget.status_code not in (200, 201):
        return False, f"root budget failed: {budget.status_code} {budget.text}"
    policy = client.post(
        "/exchange/assurance/policies",
        headers=_headers(operator_key),
        json={
            "principal_account_id": requester["account"]["id"],
            "task_id": task_id,
            "criteria_hash": criteria,
            "authorized_approver_id": approver["account"]["id"],
            "root_budget_id": budget.json()["root_budget_id"],
            "acceptance_required": False,
        },
    )
    if policy.status_code not in (200, 201):
        return False, f"policy failed: {policy.status_code} {policy.text}"
    for account_id in (requester["account"]["id"], sibling["account"]["id"]):
        bound = client.post(
            "/exchange/assurance/bind-account",
            headers=_headers(operator_key),
            json={"account_id": account_id, "policy_id": policy.json()["policy_id"]},
        )
        if bound.status_code not in (200, 201):
            return False, f"bind failed: {bound.status_code} {bound.text}"
    first = client.post(
        "/exchange/escrow",
        headers={**_headers(requester["api_key"]), "Idempotency-Key": "sib-a"},
        json={"provider_id": provider_a["account"]["id"], "amount": amount, "task_id": task_id},
    )
    if first.status_code not in (200, 201):
        return False, f"first hold failed: {first.status_code} {first.text}"
    second = client.post(
        "/exchange/escrow",
        headers={**_headers(sibling["api_key"]), "Idempotency-Key": "sib-b"},
        json={"provider_id": provider_b["account"]["id"], "amount": amount, "task_id": task_id},
    )
    if second.status_code < 400:
        return False, f"second hold was not blocked: {second.status_code}"
    return True, f"BLOCK second hold status={second.status_code}"


RUNNERS = {
    "escrow_double_release": run_escrow_double_release,
    "refund_replay": run_refund_replay,
    "premature_release": run_premature_release,
    "sibling_over_budget": run_sibling_over_budget,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run settlement vectors against a live rail")
    parser.add_argument(
        "--vectors",
        type=Path,
        default=Path("vectors/v0"),
        help="Path to vector directory",
    )
    args = parser.parse_args(argv)

    base_url = os.environ.get("RAIL_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("RAIL_REQUESTER_API_KEY", "")
    if not base_url:
        print("RAIL_BASE_URL not set — nothing to run", file=sys.stderr)
        return 1

    manifest = load_manifest(args.vectors)
    vectors = load_all_vectors(args.vectors)
    jwk_x = jwk_x_for_manifest(manifest)
    failures: list[str] = []
    skipped = 0

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for vector in vectors:
            ok_sig, sig_detail = verify_vector_jws(vector, jwk_x=jwk_x)
            if not ok_sig:
                print(f"FAIL {vector.get('vector_id')}: signature {sig_detail}")
                failures.append(vector.get("vector_id", "?"))
                continue
            attack = vector["attack_class"]
            envelope = vector.get("input_envelope") or {}
            if attack not in SETTLEMENT_RUNNERS:
                print(f"UNSUPPORTED {vector['vector_id']} ({attack}) — no HTTP runner")
                skipped += 1
                failures.append(vector["vector_id"])
                continue
            runner = RUNNERS[attack]
            ok, detail = runner(client, api_key, envelope=envelope)
            status = "PASS" if ok else "FAIL"
            print(f"{status} {vector['vector_id']}: {detail}")
            if not ok:
                failures.append(vector["vector_id"])

    print(f"\nartefact={manifest['artefact_id']} ran={len(vectors) - skipped} unsupported={skipped}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
