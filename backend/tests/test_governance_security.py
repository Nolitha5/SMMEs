"""Authorization boundary and governance-enforcement tests.

Scope note: Firebase *token issuance* is never exercised here. Only the
application's own handling of the token is under test; the firebase-admin
verification call is stubbed where it is reached. End-to-end Firebase
Authentication remains an integration-environment validation item.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import UserPrincipal, current_user, require_manager
from app.core.config import Settings, get_settings
from app.main import app


def _firebase_settings() -> Settings:
    return Settings(auth_mode="firebase")


# --------------------------------------------------------------------------
# Authentication boundary
# --------------------------------------------------------------------------


def test_firebase_mode_rejects_missing_authorization_header():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(current_user(authorization=None, x_demo_user=None, settings=_firebase_settings()))
    assert exc.value.status_code == 401


def test_firebase_mode_rejects_non_bearer_authorization_header():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(current_user(authorization="Basic abc123", x_demo_user=None, settings=_firebase_settings()))
    assert exc.value.status_code == 401


def test_firebase_mode_ignores_demo_header_spoofing():
    """A caller must not be able to downgrade to demo auth by sending X-Demo-User."""
    with pytest.raises(HTTPException) as exc:
        asyncio.run(current_user(authorization=None, x_demo_user="attacker@example.com", settings=_firebase_settings()))
    assert exc.value.status_code == 401


def test_firebase_mode_maps_invalid_token_to_401(monkeypatch):
    """Real _verify_firebase_token error mapping, with the Firebase SDK stubbed."""
    firebase_admin = pytest.importorskip("firebase_admin")
    from firebase_admin import auth as fb_auth

    monkeypatch.setattr(firebase_admin, "_apps", {"stub": object()}, raising=False)

    def _reject(_token):
        raise ValueError("token expired")

    monkeypatch.setattr(fb_auth, "verify_id_token", _reject)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(current_user(authorization="Bearer not-a-real-token", x_demo_user=None, settings=_firebase_settings()))
    assert exc.value.status_code == 401
    assert "Invalid Firebase token" in exc.value.detail


def test_demo_mode_bypasses_authentication_by_design():
    """Documents the intended local-development behaviour.

    AUTH_MODE=demo grants owner_manager to every caller with no credential.
    It is a development-only profile and must never be enabled outside local use.
    """
    principal = asyncio.run(current_user(authorization=None, x_demo_user="dev@example.com", settings=Settings(auth_mode="demo")))
    assert principal.role == "owner_manager"
    assert principal.email == "dev@example.com"
    assert principal.uid.startswith("demo:")


# --------------------------------------------------------------------------
# Role boundary
# --------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["owner_manager", "admin", "procurement_manager"])
def test_require_manager_allows_procurement_roles(role):
    user = UserPrincipal(uid="u1", email="m@example.com", role=role)
    assert require_manager(user) is user


@pytest.mark.parametrize("role", ["viewer", "clerk", "", "supplier"])
def test_require_manager_rejects_unauthorized_roles(role):
    user = UserPrincipal(uid="u2", email="v@example.com", role=role)
    with pytest.raises(HTTPException) as exc:
        require_manager(user)
    assert exc.value.status_code == 403


def test_protected_route_enforces_authentication_in_firebase_mode():
    """HTTP-level proof that a write route is closed without a bearer token."""
    app.dependency_overrides[get_settings] = _firebase_settings
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/procurement/recommend/SKU-100")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_settings, None)


# --------------------------------------------------------------------------
# Governance: approval must precede execution
# --------------------------------------------------------------------------


def _generate_recommendation(client) -> dict:
    response = client.post("/api/v1/procurement/recommend/SKU-100")
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "R4"
    assert body["status"] == "READY_FOR_REVIEW"
    return body


def test_recommendation_cannot_execute_before_approval():
    with TestClient(app) as client:
        rec = _generate_recommendation(client)
        response = client.post(f"/api/v1/recommendations/{rec['recommendation_id']}/execute")
        assert response.status_code == 409
        assert "APPROVED" in response.json()["detail"]

        orders = client.get("/api/v1/data/purchase_orders").json()
        assert not [po for po in orders if po.get("recommendation_id") == rec["recommendation_id"]]


def test_rejected_recommendation_cannot_execute():
    with TestClient(app) as client:
        rec = _generate_recommendation(client)
        rejected = client.post(
            f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
            json={"decision": "REJECTED", "reason": "budget freeze"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"

        response = client.post(f"/api/v1/recommendations/{rec['recommendation_id']}/execute")
        assert response.status_code == 409


def test_rejected_recommendation_cannot_be_re_decided():
    with TestClient(app) as client:
        rec = _generate_recommendation(client)
        client.post(
            f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
            json={"decision": "REJECTED", "reason": "not needed"},
        )
        retry = client.post(
            f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
            json={"decision": "APPROVED", "reason": "changed my mind"},
        )
        assert retry.status_code == 409


def test_duplicate_execution_does_not_create_duplicate_purchase_order():
    with TestClient(app) as client:
        rec = _generate_recommendation(client)
        client.post(
            f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
            json={"decision": "APPROVED", "reason": "approved for test"},
        )

        first = client.post(f"/api/v1/recommendations/{rec['recommendation_id']}/execute")
        second = client.post(f"/api/v1/recommendations/{rec['recommendation_id']}/execute")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["po_id"] == second.json()["po_id"]

        orders = client.get("/api/v1/data/purchase_orders").json()
        matching = [po for po in orders if po.get("recommendation_id") == rec["recommendation_id"]]
        assert len(matching) == 1


def test_non_r4_recommendation_cannot_create_purchase_order():
    from app.governance.policies import can_execute

    ok, reason = can_execute({"status": "APPROVED", "agent_id": "R5"})
    assert ok is False
    assert "R4" in reason


# --------------------------------------------------------------------------
# Governance: auditability
# --------------------------------------------------------------------------


def test_modification_preserves_original_and_is_auditable():
    with TestClient(app) as client:
        rec = _generate_recommendation(client)
        original_qty = rec["action"]["qty"]

        modified = client.post(
            f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
            json={
                "decision": "MODIFIED",
                "reason": "reduced to fit budget",
                "modified_action": {"qty": original_qty - 10},
            },
        )
        assert modified.status_code == 200
        body = modified.json()
        assert body["status"] == "MODIFIED"
        assert body["action"]["qty"] == original_qty - 10
        # Untouched fields survive the merge rather than being replaced wholesale.
        assert body["action"]["supplier_id"] == rec["action"]["supplier_id"]

        # The Blueprint names the trigger per decision, so a MODIFIED decision
        # surfaces as `recommendation.modified` on the system_events stream and
        # is also reconstructed into the composed audit history.
        history = client.get("/api/v1/audit").json()
        decisions = [
            e for e in history
            if e["event_type"] == "recommendation.modified" and e["entity_id"] == rec["recommendation_id"]
        ]
        assert decisions, "modification must be auditable"
        from_events = [d for d in decisions if d["source"] == "system_events"]
        assert from_events, "a consumer must be able to subscribe to the modification trigger"
        payload = from_events[0]["payload"]
        assert payload["decision"] == "MODIFIED"
        assert payload["modified_action"] == {"qty": original_qty - 10}
        assert payload["reason"] == "reduced to fit budget"


def test_execution_audit_records_actor_and_timestamp():
    with TestClient(app) as client:
        rec = _generate_recommendation(client)
        client.post(
            f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
            json={"decision": "APPROVED", "reason": "approved for test"},
        )
        created = client.post(f"/api/v1/recommendations/{rec['recommendation_id']}/execute")
        po_id = created.json()["po_id"]

        events = client.get("/api/v1/audit").json()
        creation = [e for e in events if e["event_type"] == "purchase_order.created" and e["entity_id"] == po_id]
        assert creation, "PO creation must be audited"
        event = creation[0]
        assert event["actor_id"]
        assert event["created_at"]


def test_approval_records_reviewer_identity_and_decision_time():
    with TestClient(app) as client:
        rec = _generate_recommendation(client)
        approved = client.post(
            f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
            json={"decision": "APPROVED", "reason": "within budget"},
        ).json()

        assert approved["reviewed_by"]
        assert approved["reviewed_at"]
        assert approved["review_reason"] == "within budget"
