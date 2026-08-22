"""
Tenant isolation tests.

There's no admin/shared-access model in this version of the app: every
resource is owned by exactly one user (directly for projects, transitively
through project -> client -> ... for everything else). These tests exist to
prove that boundary is actually enforced at the route level for every
resource type, not just in one repository method that happens to be copied
correctly everywhere else.

We deliberately go through the HTTP routes (not the services directly) so
we're proving the wired-up dependency chain (get_current_user -> user_id
threaded through the service -> repository join on Project.user_id) really
works end to end, not just that the service function would work if called
correctly.

Convention used throughout: cross-tenant reads/writes should 404, not 403.
A 403 would confirm the resource exists to an attacker; a 404 doesn't.
"""

from unittest.mock import patch

import pytest

from app.payment.schemas import PaymentIntentResult


# ---------------------------------------------------------------------------
# Helpers for building resources via the real API, under a given user's auth.
# ---------------------------------------------------------------------------

def create_project(client, headers, name="acme"):
    resp = client.post(
        "/projects",
        json={
            "name": name,
            "payment_provider": "stripe",
            "billing_frequency": "monthly",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def create_client_(client, headers, project_external_id, name="client", email=None):
    email = email or f"{name}@example.com"
    resp = client.post(
        "/clients",
        json={
            "project_external_id": project_external_id,
            "name": name,
            "email": email,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def create_event_type(client, headers, project_external_id, event_code="api_call"):
    resp = client.post(
        "/event_types",
        json={
            "project_external_id": project_external_id,
            "event_code": event_code,
            "event_name": event_code,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def create_pricing_rule(client, headers, event_type_external_id, price=1.5):
    resp = client.post(
        "/pricing_rules",
        json={
            "event_type_external_id": event_type_external_id,
            "price_per_unit": price,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def create_invoice_direct(db, project_external_id, client_external_id, event_type_external_id):
    """
    There's no route left that generates an invoice for an arbitrary period
    on demand (that manual route was removed once the worker + due-invoice
    trigger took over). For test setup we just need *an* invoice to exist,
    so we build one directly through the repository/ORM rather than trying
    to route around real billing logic here.
    """
    from app.models.project import Project
    from app.models.client import Client
    from app.models.event_type import EventType
    from app.repositories.invoice_repository import InvoiceRepository
    from datetime import datetime, timezone

    project = db.query(Project).filter(Project.external_id == project_external_id).first()
    client_row = db.query(Client).filter(Client.external_id == client_external_id).first()
    event_type = db.query(EventType).filter(EventType.external_id == event_type_external_id).first()

    invoice = InvoiceRepository.create_invoice(
        db=db,
        project_id=project.id,
        client_id=client_row.id,
        total_amount=15.0,
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        items=[
            {
                "event_type_id": event_type.id,
                "quantity": 10,
                "unit_price": 1.5,
                "total": 15.0,
            }
        ],
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def build_tenant(client, db, headers):
    """One full resource tree for a user: project -> client -> event_type
    -> pricing_rule -> invoice. Returns all the external ids a test might
    need to poke at."""
    project = create_project(client, headers)
    client_ = create_client_(client, headers, project["external_id"])
    event_type = create_event_type(client, headers, project["external_id"])
    pricing_rule = create_pricing_rule(client, headers, event_type["external_id"])
    invoice = create_invoice_direct(
        db, project["external_id"], client_["external_id"], event_type["external_id"]
    )

    return {
        "project_external_id": project["external_id"],
        "client_external_id": client_["external_id"],
        "event_type_external_id": event_type["external_id"],
        "pricing_rule_external_id": pricing_rule["external_id"],
        "invoice_external_id": invoice.external_id,
    }


FAKE_PAYMENT_RESULT = PaymentIntentResult(
    provider_payment_id="pi_fake_123",
    client_secret="secret_fake_123",
    status="requires_payment_method",
)


# ---------------------------------------------------------------------------
# Single-resource reads: B can never fetch A's resource by external_id.
# ---------------------------------------------------------------------------

class TestCrossTenantReadsAre404:

    def test_project(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.get(
            f"/projects/{tenant_a['project_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

    def test_client(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.get(
            f"/clients/{tenant_a['client_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

    def test_event_type(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.get(
            f"/event_types/{tenant_a['event_type_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

    def test_pricing_rule(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.get(
            f"/pricing_rules/{tenant_a['pricing_rule_external_id']}",
            headers=user_b["headers"],
        )
        assert resp.status_code == 404

    def test_invoice(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.get(
            f"/invoices/{tenant_a['invoice_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

    def test_payment(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        with patch(
            "app.payment.provider_factory.PaymentProviderFactory.get"
        ) as mock_get:
            mock_get.return_value.create_payment_intent.return_value = FAKE_PAYMENT_RESULT
            create_resp = client.post(
                f"/payments/{tenant_a['invoice_external_id']}", headers=user_a["headers"]
            )
        assert create_resp.status_code == 201, create_resp.text
        payment_external_id = create_resp.json()["payment_external_id"]

        # B has no route that gets a single payment by id, so we prove
        # isolation the way it actually matters here: B can't retry it,
        # and B can't see it in their own list (covered below). Retrying
        # goes through the same ownership-checked lookup as a get would.
        retry_resp = client.post(
            f"/payments/retry/{tenant_a['invoice_external_id']}", headers=user_b["headers"]
        )
        assert retry_resp.status_code == 404


# ---------------------------------------------------------------------------
# List endpoints: B's lists never contain A's resources.
# ---------------------------------------------------------------------------

class TestCrossTenantListsAreScoped:

    def test_projects(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])
        create_project(client, user_b["headers"], name="bees-own-project")

        resp = client.get("/projects", headers=user_b["headers"])
        assert resp.status_code == 200
        external_ids = {p["external_id"] for p in resp.json()}
        assert tenant_a["project_external_id"] not in external_ids

    def test_clients(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])
        project_b = create_project(client, user_b["headers"], name="bees-project")
        create_client_(client, user_b["headers"], project_b["external_id"], name="bees-client")

        resp = client.get("/clients", headers=user_b["headers"])
        assert resp.status_code == 200
        all_client_ids = {
            c["external_id"]
            for group in resp.json()
            for c in group["clients"]
        }
        assert tenant_a["client_external_id"] not in all_client_ids

    def test_invoices(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])
        tenant_b = build_tenant(client, db, user_b["headers"])

        resp = client.get("/invoices", headers=user_b["headers"])
        assert resp.status_code == 200
        body = resp.json()
        external_ids = {item["external_id"] for item in body["items"]}
        assert tenant_a["invoice_external_id"] not in external_ids
        assert tenant_b["invoice_external_id"] in external_ids

    def test_payments(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        with patch(
            "app.payment.provider_factory.PaymentProviderFactory.get"
        ) as mock_get:
            mock_get.return_value.create_payment_intent.return_value = FAKE_PAYMENT_RESULT
            client.post(f"/payments/{tenant_a['invoice_external_id']}", headers=user_a["headers"])

        resp = client.get("/payments", headers=user_b["headers"])
        assert resp.status_code == 200
        assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Mutations: B can't modify or delete A's resources.
# ---------------------------------------------------------------------------

class TestCrossTenantMutationsAre404:

    def test_patch_project(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.patch(
            f"/projects/{tenant_a['project_external_id']}",
            json={"name": "hijacked"},
            headers=user_b["headers"],
        )
        assert resp.status_code == 404

        # and it really is untouched
        check = client.get(
            f"/projects/{tenant_a['project_external_id']}", headers=user_a["headers"]
        )
        assert check.json()["name"] != "hijacked"

    def test_delete_client(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.delete(
            f"/clients/{tenant_a['client_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

        check = client.get(
            f"/clients/{tenant_a['client_external_id']}", headers=user_a["headers"]
        )
        assert check.status_code == 200

    def test_delete_project(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.delete(
            f"/projects/{tenant_a['project_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

        check = client.get(
            f"/projects/{tenant_a['project_external_id']}", headers=user_a["headers"]
        )
        assert check.status_code == 200


# ---------------------------------------------------------------------------
# Payment / refund flows crossing tenants.
# ---------------------------------------------------------------------------

class TestCrossTenantPaymentFlows:

    def test_cannot_create_payment_against_someone_elses_invoice(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.post(
            f"/payments/{tenant_a['invoice_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

    def test_cannot_refund_someone_elses_payment(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        with patch(
            "app.payment.provider_factory.PaymentProviderFactory.get"
        ) as mock_get:
            mock_get.return_value.create_payment_intent.return_value = FAKE_PAYMENT_RESULT
            create_resp = client.post(
                f"/payments/{tenant_a['invoice_external_id']}", headers=user_a["headers"]
            )
        assert create_resp.status_code == 201, create_resp.text
        payment_external_id = create_resp.json()["payment_external_id"]

        refund_resp = client.post(
            f"/payments/{payment_external_id}/refunds",
            json={},
            headers=user_b["headers"],
        )
        assert refund_resp.status_code == 404

    def test_cannot_retry_someone_elses_payment(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.post(
            f"/payments/retry/{tenant_a['invoice_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API keys: also transitively owned via client -> project -> user.
# ---------------------------------------------------------------------------

class TestCrossTenantApiKeys:

    def test_cannot_list_someone_elses_client_keys(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.get(
            f"/api-keys/{tenant_a['client_external_id']}", headers=user_b["headers"]
        )
        assert resp.status_code == 404

    def test_cannot_create_key_for_someone_elses_client(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        resp = client.post(
            "/api-keys",
            json={
                "client_external_id": tenant_a["client_external_id"],
                "name": "sneaky-key",
            },
            headers=user_b["headers"],
        )
        assert resp.status_code == 404

    def test_cannot_rotate_someone_elses_api_key(self, client, db, user_a, user_b):
        tenant_a = build_tenant(client, db, user_a["headers"])

        create_resp = client.post(
            "/api-keys",
            json={
                "client_external_id": tenant_a["client_external_id"],
                "name": "legit-key",
            },
            headers=user_a["headers"],
        )
        assert create_resp.status_code == 200, create_resp.text
        api_key_external_id = create_resp.json()["external_id"]

        rotate_resp = client.post(
            f"/api-keys/{api_key_external_id}/rotate",
            headers=user_b["headers"],
        )
        
        assert rotate_resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth edge cases: no token, garbage token, well-formed-but-unknown token.
# ---------------------------------------------------------------------------

class TestAuthRejection:

    def test_no_auth_header(self, client):
        resp = client.get("/projects")
        assert resp.status_code == 401

    def test_garbage_token(self, client):
        resp = client.get(
            "/projects", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    def test_wrong_scheme(self, client):
        resp = client.get(
            "/projects", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert resp.status_code == 401

    def test_empty_bearer(self, client):
        resp = client.get("/projects", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Sanity check: a user can always reach their own resources. If this fails,
# every 404 above is meaningless (we'd be 404ing on everything, not just
# cross-tenant access).
# ---------------------------------------------------------------------------

class TestSameTenantAccessStillWorks:

    def test_owner_can_read_their_own_resources(self, client, db, user_a):
        tenant_a = build_tenant(client, db, user_a["headers"])

        assert client.get(
            f"/projects/{tenant_a['project_external_id']}", headers=user_a["headers"]
        ).status_code == 200
        assert client.get(
            f"/clients/{tenant_a['client_external_id']}", headers=user_a["headers"]
        ).status_code == 200
        assert client.get(
            f"/event_types/{tenant_a['event_type_external_id']}", headers=user_a["headers"]
        ).status_code == 200
        assert client.get(
            f"/pricing_rules/{tenant_a['pricing_rule_external_id']}", headers=user_a["headers"]
        ).status_code == 200
        assert client.get(
            f"/invoices/{tenant_a['invoice_external_id']}", headers=user_a["headers"]
        ).status_code == 200