"""Firebase emulator integration tests.

These exercise the *real* FirestoreRepository adapter, the real Firestore
security rules, and real emulator-issued ID tokens through the FastAPI app in
`AUTH_MODE=firebase`. Nothing here uses the in-memory repository or demo auth.

Skipped unless the emulator suite is running and these env vars are set:

    FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
    FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
    FIREBASE_PROJECT_ID=demo-retail-procurement

Start the suite with:  docker run ... procurement-emulators:local
(see firebase/Dockerfile.emulators). No real project or credential is used.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

FIRESTORE_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")
AUTH_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST")
PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "demo-retail-procurement")

pytestmark = pytest.mark.skipif(
    not (FIRESTORE_HOST and AUTH_HOST),
    reason="Firebase emulators not configured (set FIRESTORE_EMULATOR_HOST and FIREBASE_AUTH_EMULATOR_HOST)",
)

FIRESTORE_REST = f"http://{FIRESTORE_HOST}/v1/projects/{PROJECT_ID}/databases/(default)/documents"
AUTH_REST = f"http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1"
FAKE_API_KEY = "emulator-key"  # the Auth emulator accepts any key


# ---------------------------------------------------------------------------
# Emulator helpers
# ---------------------------------------------------------------------------


def _create_user(email: str, password: str, claims: dict | None = None) -> dict:
    """Create an emulator user, optionally with role claims, and return tokens."""
    signup = httpx.post(
        f"{AUTH_REST}/accounts:signUp",
        params={"key": FAKE_API_KEY},
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=20,
    )
    signup.raise_for_status()
    body = signup.json()

    if claims:
        from firebase_admin import auth as fb_auth

        from app.core.firebase_app import ensure_firebase_app

        ensure_firebase_app()
        fb_auth.set_custom_user_claims(body["localId"], claims)
        # Claims only land in a freshly minted token.
        signin = httpx.post(
            f"{AUTH_REST}/accounts:signInWithPassword",
            params={"key": FAKE_API_KEY},
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=20,
        )
        signin.raise_for_status()
        body = signin.json()

    return body


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="module")
def manager_token() -> str:
    user = _create_user(_unique("manager") + "@example.com", "Passw0rd!", {"role": "owner_manager"})
    return user["idToken"]


@pytest.fixture(scope="module")
def viewer_token() -> str:
    user = _create_user(_unique("viewer") + "@example.com", "Passw0rd!", {"role": "viewer"})
    return user["idToken"]


@pytest.fixture(scope="module")
def no_role_token() -> str:
    user = _create_user(_unique("norole") + "@example.com", "Passw0rd!")
    return user["idToken"]


@pytest.fixture(scope="module")
def firestore_repo():
    from app.data.firestore_repository import FirestoreRepository

    return FirestoreRepository()


@pytest.fixture(scope="module")
def firebase_client(firestore_repo):
    """FastAPI app wired to AUTH_MODE=firebase and the Firestore repository.

    The repository is injected through `repo_dep` rather than via the
    REPOSITORY_BACKEND env var: `Settings` evaluates its `os.getenv` defaults at
    module import, so setting that variable after import has no effect. In a
    container the variable is present before the process starts, so the deployed
    path is unaffected — but a test must inject explicitly.
    """
    from app.api.routes import repo_dep
    from app.core.config import Settings, get_settings
    from app.data.bootstrap import bootstrap_sample_data
    from app.main import app

    def _settings() -> Settings:
        return Settings(
            auth_mode="firebase",
            repository_backend="firestore",
            firebase_project_id=PROJECT_ID,
        )

    bootstrap_sample_data(firestore_repo)

    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[repo_dep] = lambda: firestore_repo
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(repo_dep, None)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Part 13 — Firestore repository adapter
# ---------------------------------------------------------------------------


PROCUREMENT_COLLECTIONS = [
    ("suppliers", "supplier_id"),
    ("supplier_quotes", "quote_id"),
    ("supplier_performance", "performance_id"),
    ("agent_recommendations", "recommendation_id"),
    ("approval_log", "approval_id"),
    ("purchase_orders", "po_id"),
    ("goods_receipts", "receipt_id"),
    ("invoices", "invoice_id"),
    ("system_events", "event_id"),
    ("agent_outputs", "output_id"),
    ("agent_state", "state_id"),
    ("agent_runs", "run_id"),
    ("outcomes", "outcome_id"),
]


@pytest.mark.parametrize("collection,key", PROCUREMENT_COLLECTIONS)
def test_adapter_create_read_update_delete(firestore_repo, collection, key):
    doc_id = _unique("t")
    record = {key: doc_id, "product_id": "SKU-100", "qty": 10}

    firestore_repo.upsert(collection, record, key)
    fetched = firestore_repo.get(collection, doc_id, key)
    assert fetched is not None, f"{collection} write was not readable"
    assert fetched["qty"] == 10

    firestore_repo.upsert(collection, {**record, "qty": 25}, key)
    assert firestore_repo.get(collection, doc_id, key)["qty"] == 25

    assert any(r.get(key) == doc_id for r in firestore_repo.list(collection))

    firestore_repo.delete(collection, doc_id, key)
    assert firestore_repo.get(collection, doc_id, key) is None


def test_adapter_queries_by_non_id_field(firestore_repo):
    doc_id = _unique("q")
    marker = _unique("marker")
    firestore_repo.upsert("supplier_quotes", {"quote_id": doc_id, "supplier_id": marker, "unit_cost": 9.5}, "quote_id")
    try:
        found = firestore_repo.get("supplier_quotes", marker, "supplier_id")
        assert found is not None
        assert found["quote_id"] == doc_id
    finally:
        firestore_repo.delete("supplier_quotes", doc_id, "quote_id")


def test_adapter_data_persists_across_new_connections(firestore_repo):
    """A second adapter instance must see the first one's writes."""
    from app.data.firestore_repository import FirestoreRepository

    doc_id = _unique("persist")
    firestore_repo.upsert("suppliers", {"supplier_id": doc_id, "name": "Persistence Check"}, "supplier_id")
    try:
        reconnected = FirestoreRepository()
        again = reconnected.get("suppliers", doc_id, "supplier_id")
        assert again is not None
        assert again["name"] == "Persistence Check"
    finally:
        firestore_repo.delete("suppliers", doc_id, "supplier_id")


def test_adapter_upsert_merges_rather_than_replacing(firestore_repo):
    doc_id = _unique("merge")
    firestore_repo.upsert("suppliers", {"supplier_id": doc_id, "name": "Merge Co", "status": "ACTIVE"}, "supplier_id")
    try:
        firestore_repo.upsert("suppliers", {"supplier_id": doc_id, "status": "INACTIVE"}, "supplier_id")
        row = firestore_repo.get("suppliers", doc_id, "supplier_id")
        assert row["status"] == "INACTIVE"
        assert row["name"] == "Merge Co", "merge=True must preserve untouched fields"
    finally:
        firestore_repo.delete("suppliers", doc_id, "supplier_id")


def test_adapter_missing_document_returns_none(firestore_repo):
    assert firestore_repo.get("suppliers", _unique("absent"), "supplier_id") is None


def test_adapter_upsert_without_key_raises(firestore_repo):
    with pytest.raises(ValueError):
        firestore_repo.upsert("suppliers", {"name": "no key"}, "supplier_id")


# ---------------------------------------------------------------------------
# Part 14 — Firestore security rules (enforced on client-style REST access;
# the Admin SDK deliberately bypasses rules, so these go over REST).
# ---------------------------------------------------------------------------


def _rest_read(path: str, token: str | None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.get(f"{FIRESTORE_REST}/{path}", headers=headers, timeout=20)


def _rest_write(path: str, token: str | None, value: str = "x"):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.patch(
        f"{FIRESTORE_REST}/{path}",
        headers=headers,
        json={"fields": {"probe": {"stringValue": value}}},
        timeout=20,
    )


# Operational collection used as the rules probe. R1 screens malformed
# supplier documents, so a probe doc here cannot break the agents; it is
# deleted after each test regardless.
PROBE_COLLECTION = "suppliers"


def _rest_delete(path: str, token: str):
    return httpx.delete(f"{FIRESTORE_REST}/{path}", headers={"Authorization": f"Bearer {token}"}, timeout=20)


def test_rules_deny_unauthenticated_read():
    response = _rest_read(f"{PROBE_COLLECTION}/{_unique('rules')}", token=None)
    assert response.status_code in (401, 403), f"unauthenticated read should be denied, got {response.status_code}"


def test_rules_deny_unauthenticated_write():
    response = _rest_write(f"{PROBE_COLLECTION}/{_unique('rules')}", token=None)
    assert response.status_code in (401, 403), f"unauthenticated write should be denied, got {response.status_code}"


def test_rules_deny_authenticated_user_without_role_claim(no_role_token):
    """Signed in is not sufficient — procurementRole() requires a role claim."""
    response = _rest_write(f"{PROBE_COLLECTION}/{_unique('rules')}", token=no_role_token)
    assert response.status_code == 403


def test_rules_deny_unauthorized_role(viewer_token):
    response = _rest_write(f"{PROBE_COLLECTION}/{_unique('rules')}", token=viewer_token)
    assert response.status_code == 403


def test_rules_allow_procurement_manager_write_then_read(manager_token):
    path = f"{PROBE_COLLECTION}/{_unique('rules')}"
    try:
        write = _rest_write(path, token=manager_token, value="allowed")
        assert write.status_code == 200, write.text
        read = _rest_read(path, token=manager_token)
        assert read.status_code == 200
        assert read.json()["fields"]["probe"]["stringValue"] == "allowed"
    finally:
        _rest_delete(path, token=manager_token)


PROTECTED_FOR_CLIENTS = [
    "agent_outputs", "agent_state", "agent_runs", "system_events",
    "approval_log", "outcomes", "agent_recommendations",
]


@pytest.mark.parametrize("collection", PROTECTED_FOR_CLIENTS)
def test_rules_protected_collection_rejects_even_manager_writes(manager_token, collection):
    """The shared exchange/governance layer is backend-only.

    This is the rule the whole architecture depends on: a manager can read
    these collections but must go through the backend API to change anything.
    A catch-all `allow write` would silently defeat it — hence none exists.
    """
    response = _rest_write(f"{collection}/{_unique('rules')}", token=manager_token)
    assert response.status_code == 403, f"{collection} accepted a direct client write from a manager"


@pytest.mark.parametrize("collection", PROTECTED_FOR_CLIENTS)
def test_rules_protected_collection_readable_by_manager(manager_token, collection):
    response = _rest_read(f"{collection}/{_unique('rules')}", token=manager_token)
    # 404 = rule allowed the read, document simply doesn't exist. 403 = denied.
    assert response.status_code == 404, f"{collection} should be readable by a manager, got {response.status_code}"


@pytest.mark.parametrize("collection", ["products", "inventory_snapshots", "inventory_movements"])
def test_rules_shared_context_is_read_only_for_procurement(manager_token, collection):
    assert _rest_write(f"{collection}/{_unique('rules')}", token=manager_token).status_code == 403
    assert _rest_read(f"{collection}/{_unique('rules')}", token=manager_token).status_code == 404


def test_rules_unlisted_collection_is_denied_by_default(manager_token):
    """No catch-all: a collection the rules do not name is closed to everyone."""
    assert _rest_write(f"not_a_real_collection/{_unique('x')}", token=manager_token).status_code == 403
    assert _rest_read(f"not_a_real_collection/{_unique('x')}", token=manager_token).status_code == 403


def test_rules_protect_sensitive_collections_from_unauthorized_role(viewer_token):
    """Audit and approval history must not be writable by a non-procurement role."""
    for collection in ("system_events", "approval_log", "agent_recommendations", "agent_outputs", "agent_state", "agent_runs", "outcomes"):
        response = _rest_write(f"{collection}/{_unique('rules')}", token=viewer_token)
        assert response.status_code == 403, f"{collection} accepted a write from role=viewer"


# ---------------------------------------------------------------------------
# Part 15 — Firebase Auth emulator, verified by the backend
# ---------------------------------------------------------------------------


def test_backend_accepts_emulator_issued_token(firebase_client, manager_token):
    response = firebase_client.get("/api/v1/me", headers=_auth(manager_token))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "owner_manager"
    assert body["uid"]


def test_backend_rejects_missing_token(firebase_client):
    assert firebase_client.get("/api/v1/me").status_code == 401


def test_backend_rejects_malformed_token(firebase_client):
    assert firebase_client.get("/api/v1/me", headers=_auth("not-a-jwt")).status_code == 401


def test_backend_rejects_non_bearer_scheme(firebase_client, manager_token):
    response = firebase_client.get("/api/v1/me", headers={"Authorization": f"Basic {manager_token}"})
    assert response.status_code == 401


def test_backend_ignores_demo_header_when_auth_mode_is_firebase(firebase_client):
    response = firebase_client.get("/api/v1/me", headers={"X-Demo-User": "attacker@example.com"})
    assert response.status_code == 401


def test_role_claim_propagates_from_emulator_token(firebase_client, viewer_token):
    response = firebase_client.get("/api/v1/me", headers=_auth(viewer_token))
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


# ---------------------------------------------------------------------------
# Part 16 — Governance under real Firebase auth
# ---------------------------------------------------------------------------


def test_unauthenticated_caller_cannot_generate_recommendation(firebase_client):
    assert firebase_client.post("/api/v1/procurement/recommend/SKU-100").status_code == 401


def test_unauthorized_role_cannot_generate_recommendation(firebase_client, viewer_token):
    response = firebase_client.post("/api/v1/procurement/recommend/SKU-100", headers=_auth(viewer_token))
    assert response.status_code == 403


def test_governance_lifecycle_under_firebase_auth(firebase_client, manager_token, viewer_token):
    created = firebase_client.post("/api/v1/procurement/recommend/SKU-100", headers=_auth(manager_token))
    assert created.status_code == 200
    rec = created.json()
    assert rec["agent_id"] == "R4"
    assert rec["status"] == "READY_FOR_REVIEW"
    rec_id = rec["recommendation_id"]

    # 4. cannot execute before approval
    early = firebase_client.post(f"/api/v1/recommendations/{rec_id}/execute", headers=_auth(manager_token))
    assert early.status_code == 409

    # 2. unauthorized role cannot approve
    denied = firebase_client.post(
        f"/api/v1/recommendations/{rec_id}/decision",
        headers=_auth(viewer_token),
        json={"decision": "APPROVED", "reason": "should not be permitted"},
    )
    assert denied.status_code == 403

    # 3. authorized manager can approve
    approved = firebase_client.post(
        f"/api/v1/recommendations/{rec_id}/decision",
        headers=_auth(manager_token),
        json={"decision": "APPROVED", "reason": "emulator governance test"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["reviewed_by"]

    # 6. approved recommendation creates one PO
    first = firebase_client.post(f"/api/v1/recommendations/{rec_id}/execute", headers=_auth(manager_token))
    assert first.status_code == 200
    po_id = first.json()["po_id"]

    # 7. duplicate execution stays idempotent
    second = firebase_client.post(f"/api/v1/recommendations/{rec_id}/execute", headers=_auth(manager_token))
    assert second.status_code == 200
    assert second.json()["po_id"] == po_id

    orders = firebase_client.get("/api/v1/data/purchase_orders", headers=_auth(manager_token)).json()
    assert len([po for po in orders if po.get("recommendation_id") == rec_id]) == 1


def test_rejected_recommendation_cannot_execute_under_firebase_auth(firebase_client, manager_token):
    rec = firebase_client.post("/api/v1/procurement/recommend/SKU-100", headers=_auth(manager_token)).json()
    rec_id = rec["recommendation_id"]

    rejected = firebase_client.post(
        f"/api/v1/recommendations/{rec_id}/decision",
        headers=_auth(manager_token),
        json={"decision": "REJECTED", "reason": "not required"},
    )
    assert rejected.status_code == 200

    blocked = firebase_client.post(f"/api/v1/recommendations/{rec_id}/execute", headers=_auth(manager_token))
    assert blocked.status_code == 409


# ---------------------------------------------------------------------------
# Part 18 — Procurement lifecycle persisted in Firestore
# ---------------------------------------------------------------------------


def test_full_lifecycle_persists_records_in_firestore(firebase_client, firestore_repo, manager_token):
    rec = firebase_client.post("/api/v1/procurement/recommend/SKU-100", headers=_auth(manager_token)).json()
    rec_id = rec["recommendation_id"]

    firebase_client.post(
        f"/api/v1/recommendations/{rec_id}/decision",
        headers=_auth(manager_token),
        json={"decision": "APPROVED", "reason": "lifecycle test"},
    )
    po = firebase_client.post(f"/api/v1/recommendations/{rec_id}/execute", headers=_auth(manager_token)).json()
    po_id = po["po_id"]

    # Every artefact must be readable straight from Firestore, not just the API.
    stored_rec = firestore_repo.get("agent_recommendations", rec_id, "recommendation_id")
    assert stored_rec is not None
    assert stored_rec["status"] == "EXECUTED"
    assert stored_rec["reviewed_by"]
    assert stored_rec["reviewed_at"]

    stored_po = firestore_repo.get("purchase_orders", po_id, "po_id")
    assert stored_po is not None
    assert stored_po["recommendation_id"] == rec_id

    approvals = [a for a in firestore_repo.list("approval_log") if a.get("recommendation_id") == rec_id]
    assert approvals, "approval must be journalled in Firestore"
    assert approvals[0]["decision"] == "APPROVED"

    audits = [a for a in firestore_repo.list("system_events") if a.get("entity_id") in {rec_id, po_id}]
    assert audits, "system events must be persisted in Firestore"
    assert all(a.get("actor_id") for a in audits)
    assert all(a.get("created_at") for a in audits)
    assert all(a.get("event_id") for a in audits)


def test_reconciliation_against_firestore(firebase_client, firestore_repo, manager_token):
    clean = firebase_client.post("/api/v1/procurement/reconcile/PO-DEMO-001", headers=_auth(manager_token))
    assert clean.status_code == 200
    assert clean.json()["action"]["match_status"] == "MATCH"

    mismatch = firebase_client.post("/api/v1/procurement/reconcile/PO-DEMO-002", headers=_auth(manager_token))
    assert mismatch.status_code == 200
    body = mismatch.json()
    assert body["action"]["match_status"] == "MISMATCH"
    assert "UNDER_DELIVERY" in body["action"]["exception_types"]

    # R5 output is evidence: persisted in agent_outputs, never as a review item.
    assert firestore_repo.get("agent_outputs", body["output_id"], "output_id"), "R5 result must be persisted in Firestore"
    assert firestore_repo.get("agent_recommendations", body["output_id"], "recommendation_id") is None
    # The derived human action is what lands in agent_recommendations.
    assert firestore_repo.get("agent_recommendations", body["action_recommendation_id"], "recommendation_id")


# ---------------------------------------------------------------------------
# Part 17 — Storage emulator
#
# Storage is genuinely used: services/storage.py::archive_import uploads CSV
# import evidence when FIREBASE_STORAGE_BUCKET is set, and returns checksum-only
# metadata when it is not.
# ---------------------------------------------------------------------------

STORAGE_HOST = os.getenv("FIREBASE_STORAGE_EMULATOR_HOST")
EMULATOR_BUCKET = f"{PROJECT_ID}.appspot.com"

storage_emulator = pytest.mark.skipif(
    not STORAGE_HOST,
    reason="Storage emulator not configured (set FIREBASE_STORAGE_EMULATOR_HOST)",
)


def test_archive_import_without_bucket_returns_checksum_only():
    """The documented local/demo path: no bucket configured, no upload attempted."""
    from app.services import storage as storage_service

    payload = b"supplier_id,name\nSUP-001,Ubuntu\n"
    result = storage_service.archive_import(payload, "suppliers.csv", "demo:manager")
    assert result["storage_uri"] is None
    assert result["sha256"]
    assert result["bytes"] == len(payload)
    assert "storage_error" not in result


@storage_emulator
def test_archive_import_uploads_to_storage_emulator(monkeypatch):
    from app.core.config import Settings
    from app.services import storage as storage_service

    monkeypatch.setenv("STORAGE_EMULATOR_HOST", f"http://{STORAGE_HOST}")

    def _settings() -> Settings:
        return Settings(firebase_project_id=PROJECT_ID, firebase_storage_bucket=EMULATOR_BUCKET)

    monkeypatch.setattr(storage_service, "get_settings", _settings)

    payload = b"quote_id,supplier_id,unit_cost\nQ-1,SUP-001,18.90\n"
    result = storage_service.archive_import(payload, "supplier_quotes.csv", "demo:manager")

    assert "storage_error" not in result, f"upload failed: {result.get('storage_error')}"
    assert result["storage_uri"], "a configured bucket must produce a storage_uri"
    assert result["storage_uri"].startswith(f"gs://{EMULATOR_BUCKET}/procurement-imports/")
    assert result["sha256"]


@storage_emulator
def test_uploaded_object_is_readable_with_metadata(monkeypatch):
    from firebase_admin import storage as fb_storage

    from app.core.config import Settings
    from app.core.firebase_app import ensure_firebase_app
    from app.services import storage as storage_service

    monkeypatch.setenv("STORAGE_EMULATOR_HOST", f"http://{STORAGE_HOST}")

    def _settings() -> Settings:
        return Settings(firebase_project_id=PROJECT_ID, firebase_storage_bucket=EMULATOR_BUCKET)

    monkeypatch.setattr(storage_service, "get_settings", _settings)

    payload = b"receipt_id,po_id,qty_received\nGR-9,PO-DEMO-001,260\n"
    result = storage_service.archive_import(payload, "goods_receipts.csv", "demo:manager")
    assert "storage_error" not in result, result.get("storage_error")

    ensure_firebase_app(_settings())
    path = result["storage_uri"].split(f"{EMULATOR_BUCKET}/", 1)[1]
    blob = fb_storage.bucket(EMULATOR_BUCKET).blob(path)
    blob.reload()

    assert blob.download_as_bytes() == payload, "archived evidence must round-trip byte-identically"
    assert blob.metadata["sha256"] == result["sha256"]
    assert blob.metadata["actor_id"] == "demo:manager"


@storage_emulator
def test_storage_rules_deny_unauthenticated_access():
    """storage.rules scopes procurement-imports/{userId} to that user only."""
    url = f"http://{STORAGE_HOST}/v0/b/{EMULATOR_BUCKET}/o/{'procurement-imports%2Fsomeone%2Fsecret.csv'}"
    response = httpx.get(url, timeout=20)
    assert response.status_code in (401, 403, 404), f"expected denial, got {response.status_code}"


@storage_emulator
def test_storage_rules_deny_access_to_another_users_folder(manager_token):
    """A signed-in user must not read another user's import folder."""
    url = f"http://{STORAGE_HOST}/v0/b/{EMULATOR_BUCKET}/o/{'procurement-imports%2Fdifferent-uid%2Fother.csv'}"
    response = httpx.get(url, headers=_auth(manager_token), timeout=20)
    assert response.status_code in (401, 403, 404), f"expected denial, got {response.status_code}"


# ---------------------------------------------------------------------------
# Malformed-document resilience, against real Firestore
#
# This is where the defect originally surfaced: Firestore enforces no schema, so
# a privileged direct write can store a supplier document that never passed the
# API's Pydantic validation.
# ---------------------------------------------------------------------------


def test_malformed_supplier_in_firestore_does_not_break_recommendation(
    firebase_client, firestore_repo, manager_token
):
    incomplete_id = _unique("SUP-NONAME")
    firestore_repo.upsert("suppliers", {"supplier_id": incomplete_id, "status": "ACTIVE"}, "supplier_id")
    firestore_repo.db.collection("suppliers").document(_unique("no-id")).set({"name": "Ghost Co", "status": "ACTIVE"})

    try:
        response = firebase_client.post("/api/v1/procurement/recommend/SKU-100", headers=_auth(manager_token))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["agent_id"] == "R4"
        assert body["status"] == "READY_FOR_REVIEW", "valid suppliers must still yield a recommendation"
        assert body["action"]["supplier_id"] in {"SUP-001", "SUP-002", "SUP-003"}
    finally:
        firestore_repo.delete("suppliers", incomplete_id, "supplier_id")
        for doc in firestore_repo.db.collection("suppliers").stream():
            data = doc.to_dict() or {}
            if not str(data.get("supplier_id", "")).strip():
                doc.reference.delete()


def test_malformed_supplier_in_firestore_is_reported_by_r1(firebase_client, firestore_repo, manager_token):
    bad_id = _unique("SUP-BADSTATUS")
    firestore_repo.upsert(
        "suppliers", {"supplier_id": bad_id, "name": "Bad Status Co", "status": "NOT_A_STATUS"}, "supplier_id"
    )
    try:
        response = firebase_client.post(
            "/api/v1/agents/R1/run",
            headers=_auth(manager_token),
            json={"entity_type": "product", "entity_id": "SKU-100", "payload": {"requested_qty": 260}},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert any(g.startswith("malformed_suppliers_excluded") for g in body["guardrails"])
        assert body["action"]["ranked_suppliers"], "valid suppliers must still rank"
    finally:
        firestore_repo.delete("suppliers", bad_id, "supplier_id")


# ---------------------------------------------------------------------------
# Phase 25 — DATABASE-READY END-TO-END on the shared architecture
#
# Every step reads back from Firestore, not from the API response, so this
# proves what actually landed in the shared collections.
# ---------------------------------------------------------------------------


def test_shared_architecture_end_to_end_trace(firebase_client, firestore_repo, manager_token):
    from app.contracts.shared import state_id
    from app.data.output_repository import OutputRepository
    from app.services import events as ev

    outputs = OutputRepository(firestore_repo)
    H = _auth(manager_token)

    # 1–5. Shared operational data + upstream contracts are seeded by the fixture.
    for agent, out_type in (("D4", "DemandForecast"), ("I1", "InventoryPosition"), ("I2", "ReorderNeed"), ("I3", "SafetyStockTarget")):
        env = outputs.get_latest_output(out_type, "SKU-100")
        assert env and env.agent_id == agent, f"{out_type} must be in agent_state as {agent}"
        assert firestore_repo.get("agent_outputs", env.output_id, "output_id"), f"{out_type} must be in agent_outputs"
    upstream_ids = {outputs.get_latest_output(t, "SKU-100").output_id for t in ("DemandForecast", "ReorderNeed", "SafetyStockTarget")}

    # 6–13. R1 → R2 → R3 → R4 through the real coordinator over HTTP.
    r4 = firebase_client.post("/api/v1/procurement/recommend/SKU-100", headers=H).json()
    assert r4["agent_id"] == "R4" and r4["action_type"] == "PurchaseRecommendation"
    rec_id, r4_out = r4["recommendation_id"], r4["output_id"]

    # 7/9/11. R1/R2/R3 published to agent_outputs + agent_state.
    assert firestore_repo.get("agent_state", state_id("R1", "SupplierComparison", "SKU-100"), "state_id")
    chosen = r4["action"]["supplier_id"]
    assert firestore_repo.get("agent_state", state_id("R2", "SupplierReliabilityScore", chosen), "state_id")
    assert firestore_repo.get("agent_state", state_id("R3", "LeadTimeRisk", chosen), "state_id")

    # 13. PurchaseRecommendation in all three places.
    assert firestore_repo.get("agent_outputs", r4_out, "output_id")
    assert firestore_repo.get("agent_state", state_id("R4", "PurchaseRecommendation", "SKU-100"), "state_id")["output_id"] == r4_out
    rec = firestore_repo.get("agent_recommendations", rec_id, "recommendation_id")
    assert rec and rec["source_output_id"] == r4_out and rec["status"] == "READY_FOR_REVIEW"

    # 14. purchase.recommendation.created event.
    evs = firestore_repo.list("system_events")
    assert any(e["event_type"] == ev.EVENT_PURCHASE_RECOMMENDATION_CREATED and e["payload"].get("recommendation_id") == rec_id for e in evs)

    # 15–16. Approve through the approval service; approval_log written.
    assert firebase_client.post(f"/api/v1/recommendations/{rec_id}/decision", headers=H, json={"decision": "APPROVED", "reason": "e2e"}).status_code == 200
    log = [a for a in firestore_repo.list("approval_log") if a["recommendation_id"] == rec_id]
    assert len(log) == 1 and log[0]["decision"] == "APPROVED" and log[0]["reviewer"]

    # 17–18. Execute → purchase_orders.
    po = firebase_client.post(f"/api/v1/recommendations/{rec_id}/execute", headers=H).json()
    po_id = po["po_id"]
    assert firestore_repo.get("purchase_orders", po_id, "po_id")["recommendation_id"] == rec_id
    assert firestore_repo.get("agent_recommendations", rec_id, "recommendation_id")["status"] == "EXECUTED"

    # 19–20. Goods receipt + invoice through the API (events emitted).
    receipt = {"receipt_id": f"GR-{po_id}", "po_id": po_id, "supplier_id": po["supplier_id"], "product_id": "SKU-100",
               "qty_received": po["qty"], "qty_defective": 0, "received_at": po["promised_date"] + "T10:00:00Z"}
    invoice = {"invoice_id": f"INV-{po_id}", "invoice_number": f"N-{po_id}", "po_id": po_id, "supplier_id": po["supplier_id"],
               "product_id": "SKU-100", "qty_invoiced": po["qty"], "unit_cost": po["unit_cost"], "tax_amount": 0,
               "currency": "ZAR", "invoiced_at": po["promised_date"] + "T12:00:00Z"}
    assert firebase_client.put("/api/v1/data/goods_receipts", headers=H, json=receipt).status_code == 200
    assert firebase_client.put("/api/v1/data/invoices", headers=H, json=invoice).status_code == 200
    evs = firestore_repo.list("system_events")
    assert any(e["event_type"] == ev.EVENT_GOODS_RECEIPT_RECORDED and e["entity_id"] == po_id for e in evs)
    assert any(e["event_type"] == ev.EVENT_INVOICE_RECEIVED and e["entity_id"] == po_id for e in evs)

    # 21–22. R5 reconciliation published.
    r5 = firebase_client.post(f"/api/v1/procurement/reconcile/{po_id}", headers=H).json()
    assert r5["action"]["match_status"] == "MATCH"
    assert firestore_repo.get("agent_outputs", r5["output_id"], "output_id")
    assert firestore_repo.get("agent_state", state_id("R5", "ProcurementException", po_id), "state_id")["output_id"] == r5["output_id"]

    # 23. Close → supplier_performance + outcomes feedback.
    close = firebase_client.post(f"/api/v1/procurement/close/{po_id}/{r5['recommendation_id']}", headers=H)
    assert close.status_code == 200, close.text
    perf = [p for p in firestore_repo.list("supplier_performance") if p["po_id"] == po_id]
    assert len(perf) == 1
    outcome = firestore_repo.get("outcomes", f"OUT-{po_id}", "outcome_id")
    assert outcome and outcome["performance_id"] == perf[0]["performance_id"]
    assert outcome["recommendation_id"] == rec_id and outcome["reconciliation_status"] == "MATCH"

    # 24. System events for the whole lifecycle.
    types = {e["event_type"] for e in firestore_repo.list("system_events") if e["entity_id"] in {po_id, "SKU-100", rec_id, po["supplier_id"]}}
    for required in (ev.EVENT_PURCHASE_RECOMMENDATION_CREATED, ev.EVENT_RECOMMENDATION_APPROVED,
                     ev.EVENT_OUTCOME_RECORDED, ev.EVENT_PURCHASE_ORDER_CREATED,
                     ev.EVENT_RECONCILIATION_COMPLETED, ev.EVENT_PURCHASE_ORDER_CLOSED, ev.EVENT_SUPPLIER_PERFORMANCE_UPDATED):
        assert required in types, f"missing system event {required}"

    # 25. agent_runs for every agent in the chain, all succeeded.
    runs = firestore_repo.list("agent_runs")
    assert {r["agent_id"] for r in runs if r["status"] == "SUCCEEDED"} >= {"R1", "R2", "R3", "R4", "R5"}
    r4_run = firestore_repo.get("agent_runs", r4["run_id"], "run_id")
    assert r4_run["output_id"] == r4_out and r4_run["completed_at"]

    # 26. Reconstruct the full trace from persisted records only.
    r4_record = firestore_repo.get("agent_outputs", r4_out, "output_id")
    assert upstream_ids <= set(r4_record["input_refs"]), "R4 must reference the exact upstream output ids"
    for ref in r4_record["input_refs"]:
        if ref.startswith(("REC-", "I2-", "I3-", "D4-")):
            assert firestore_repo.get("agent_outputs", ref, "output_id"), f"unresolvable input ref {ref}"
    assert firestore_repo.get("agent_runs", r4_record["run_id"], "run_id")["agent_id"] == "R4"

    # 27. R2 re-evaluation now sees the new outcome via supplier_performance.
    scorecard = firebase_client.get(f"/api/v1/suppliers/{po['supplier_id']}/scorecard", headers=H).json()
    assert scorecard["reliability"]["sample_size"] >= 1

    # 28. Evidence/action split holds in Firestore: R1–R3 raised no approval
    #     records; R4 did; the clean R5 result did not.
    recs = firestore_repo.list("agent_recommendations")
    assert not [r for r in recs if r["agent_id"] in {"R1", "R2", "R3"}], "R1–R3 must never create approval records"
    assert any(r["recommendation_id"] == rec_id and r["agent_id"] == "R4" for r in recs)
    assert not [r for r in recs if r.get("source_output_id") == r5["output_id"]], "a clean MATCH raises no review action"
    assert r5.get("action_recommendation_id") is None

    # 29. system_events holds triggers only — no bookkeeping copies.
    all_types = {e["event_type"] for e in firestore_repo.list("system_events")}
    assert not any(t.startswith(("data.", "demo.", "job.")) for t in all_types), all_types
    assert "audit_events" not in {c.id for c in firestore_repo.db.collections()}

    # 30. The audit history is composed on read from the canonical sources.
    history = firebase_client.get("/api/v1/audit", params={"entity_id": po_id}, headers=H).json()
    sources = {h["source"] for h in history}
    assert {"agent_outputs", "system_events", "outcomes"} <= sources, sources
    full = firebase_client.get("/api/v1/audit", headers=H).json()
    assert {"agent_runs", "agent_outputs", "agent_recommendations", "approval_log", "system_events", "outcomes"} <= {h["source"] for h in full}


def test_shared_r5_mismatch_raises_review_action_in_firestore(firebase_client, firestore_repo, manager_token):
    H = _auth(manager_token)
    r5 = firebase_client.post("/api/v1/procurement/reconcile/PO-DEMO-002", headers=H).json()
    assert r5["action"]["match_status"] == "MISMATCH"

    # Evidence published; not a review item.
    assert firestore_repo.get("agent_outputs", r5["output_id"], "output_id")
    assert firestore_repo.get("agent_recommendations", r5["output_id"], "recommendation_id") is None
    # Separate human action, linked by source_output_id.
    review_id = r5["action_recommendation_id"]
    review = firestore_repo.get("agent_recommendations", review_id, "recommendation_id")
    assert review and review["action_type"] == "ReconciliationReview"
    assert review["source_output_id"] == r5["output_id"] and review["status"] == "READY_FOR_REVIEW"
    # Trigger fired.
    assert any(e["event_type"] == "procurement.exception.created" and e["payload"]["output_id"] == r5["output_id"]
               for e in firestore_repo.list("system_events"))
    # Closure gated on the action, not the evidence.
    blocked = firebase_client.post(f"/api/v1/procurement/close/PO-DEMO-002/{r5['output_id']}", headers=H)
    assert blocked.status_code == 409
    assert firebase_client.post(f"/api/v1/recommendations/{review_id}/decision", headers=H,
                                json={"decision": "APPROVED", "reason": "accepted"}).status_code == 200
    closed = firebase_client.post(f"/api/v1/procurement/close/PO-DEMO-002/{r5['output_id']}", headers=H)
    assert closed.status_code == 200, closed.text
    assert closed.json()["outcome"]["exception_count"] == 5
    # Reset so other tests see the demo PO open again.
    po = firestore_repo.get("purchase_orders", "PO-DEMO-002", "po_id")
    po["status"] = "OPEN"
    firestore_repo.upsert("purchase_orders", po, "po_id")


def test_shared_retry_same_output_published_twice_in_firestore(firebase_client, firestore_repo, manager_token):
    from app.contracts.models import AgentResult, RiskLevel
    from app.data.output_repository import OutputRepository

    oid = _unique("REC-retry")
    res = AgentResult(
        recommendation_id=oid, output_id=oid, run_id=_unique("RUN"), agent_id="R1",
        entity_type="product", entity_id=_unique("SKU"), action_type="SupplierComparison",
        action={"ranked_suppliers": []}, rationale=["x"], evidence_refs=[], confidence=0.5,
        risk_level=RiskLevel.LOW, requires_approval=False, model_or_rule_version="1.0.0-r1",
    )
    outputs = OutputRepository(firestore_repo)
    outputs.publish(res)
    outputs.publish(res)
    matches = [o for o in firestore_repo.list("agent_outputs") if o["output_id"] == oid]
    assert len(matches) == 1
    for o in matches:
        firestore_repo.delete("agent_outputs", o["output_id"], "output_id")


# ---------------------------------------------------------------------------
# Part 19 — Failure behavior
# ---------------------------------------------------------------------------


def test_missing_document_is_a_404_not_a_crash(firebase_client, manager_token):
    response = firebase_client.post(
        "/api/v1/recommendations/REC-does-not-exist/decision",
        headers=_auth(manager_token),
        json={"decision": "APPROVED", "reason": "x"},
    )
    assert response.status_code == 404


def test_reconcile_unknown_po_fails_safely(firebase_client, manager_token):
    """Missing evidence must yield a non-actionable result, not a fabricated match.

    The documented contract is a safe DRAFT with INSUFFICIENT_EVIDENCE rather
    than an HTTP error, so assert the contract itself.
    """
    response = firebase_client.post("/api/v1/procurement/reconcile/PO-NOT-REAL", headers=_auth(manager_token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT", "a non-actionable result must not be approvable"
    assert body["action"]["match_status"] == "INSUFFICIENT_EVIDENCE"
    assert body["confidence"] == 0.0
    assert body["rationale"], "the reason for refusing must be explained"


def test_invalid_decision_payload_is_rejected(firebase_client, manager_token):
    rec = firebase_client.post("/api/v1/procurement/recommend/SKU-100", headers=_auth(manager_token)).json()
    response = firebase_client.post(
        f"/api/v1/recommendations/{rec['recommendation_id']}/decision",
        headers=_auth(manager_token),
        json={"decision": "NOT_A_REAL_DECISION"},
    )
    assert response.status_code == 422


def test_firestore_unavailable_surfaces_as_error_not_silent_success():
    """A write against an unreachable Firestore must raise, never silently succeed."""
    from app.data.firestore_repository import FirestoreRepository

    live = os.environ.get("FIRESTORE_EMULATOR_HOST")
    try:
        # Port 1 is closed; the client picks the host up from the environment.
        os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:1"
        from google.cloud import firestore as gcf

        broken = FirestoreRepository.__new__(FirestoreRepository)
        broken.db = gcf.Client(project=PROJECT_ID)

        with pytest.raises(Exception):
            broken.upsert("suppliers", {"supplier_id": _unique("dead"), "name": "unreachable"}, "supplier_id")
    finally:
        if live:
            os.environ["FIRESTORE_EMULATOR_HOST"] = live
        else:
            os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
