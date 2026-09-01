# API Documentation

## Overview

The SaaS API provides the backend for a usage-based billing platform. It allows users to create projects and clients, define billable events and pricing rules, ingest usage data asynchronously, generate invoices, process payments and refunds, and monitor billing activity.

The API is built with FastAPI and exposes interactive OpenAPI documentation when the application is running.

### Interactive Documentation

Once the application is running:

* Swagger UI: `/docs`
* ReDoc: `/redoc`
* OpenAPI schema: `/openapi.json`

These interfaces provide the complete machine-generated API specification, including request schemas, response schemas, validation rules, and available endpoints.

This document focuses on the API's architecture, authentication model, endpoint groups, and important behavioral rules.

---

## Authentication

Most management endpoints require JWT authentication.

Authenticated requests use the Bearer token scheme:

```http
Authorization: Bearer <access_token>
```

A user receives an access token and refresh token after logging in.

The general authentication flow is:

1. Register a user.
2. Log in with email and password.
3. Receive an access token and refresh token.
4. Use the access token for authenticated requests.
5. Use the refresh token to obtain a new token pair when necessary.
6. Log out to invalidate the active refresh token.

The application currently enforces a single active refresh-token session per user.

---

### API Authentication vs Client API Keys

The platform uses two different authentication concepts.

#### JWT Authentication

JWT access tokens authenticate platform users.

These users manage:

* Projects
* Clients
* Event types
* Pricing rules
* API keys
* Invoices
* Payments
* Refunds
* Dashboard information

JWT authentication represents the **owner or operator of the SaaS account**.

---

#### Client API Keys

API keys represent client credentials.

They are created and managed through authenticated management endpoints.

API keys support:

* Client identification
* API key rotation
* API key revocation
* Controlled access to client-facing functionality

API keys are associated with clients rather than directly with users.

This separation allows the platform owner to manage clients while clients can be identified independently through their credentials.

---

## Tenant Isolation

The API is designed as a multi-tenant system.

Users should only be able to access resources belonging to their own projects.

Ownership checks are enforced through repository queries that scope resources through the owning project and user.

Protected resources include:

* Projects
* Clients
* Event types
* Pricing rules
* Invoices
* Payments
* Refund operations
* API keys

When a user attempts to access another tenant's resource, the API returns `404 Not Found` rather than revealing that the resource exists.

This prevents unnecessary information disclosure.

For example:

```text
User A requests User B's invoice
        ↓
Invoice exists
        ↓
But does not belong to User A
        ↓
404 Not Found
```

The same principle applies to cross-tenant reads and mutations.

---

## Authentication Endpoints

### Register

```http
POST /auth/register
```

Creates a new platform user.

The request includes:

* Email
* Password
* Full name
* Company name
* Default currency
* Timezone

Passwords must be between 8 and 72 characters.

---

### Login

```http
POST /auth/login
```

Authenticates a user and returns:

* Access token
* Refresh token
* Token type

The access token is used for authenticated API requests.

---

### Refresh Token

```http
POST /auth/refresh
```

Uses a refresh token to obtain a new authentication token pair.

The refresh-token lifecycle is designed around a single active session model.

---

### Logout

```http
POST /auth/logout
```

Invalidates the active refresh token.

After logout, the invalidated refresh token can no longer be used to obtain new access tokens.

---

## Project Management

Projects represent the top-level billing configuration for a user's SaaS products or services.

Each project contains:

* A name
* A payment provider
* A billing frequency
* A next billing date

Supported billing frequencies include:

* Daily
* Weekly
* Monthly

Supported payment providers currently include:

* Stripe
* Chapa
* PayPal

The provider abstraction exists in the domain model, although the currently implemented payment integration is Stripe.

### Endpoints

```http
GET /projects
POST /projects

GET /projects/{project_external_id}
PATCH /projects/{project_external_id}
DELETE /projects/{project_external_id}
```

Projects are identified externally using `external_id` values rather than exposing internal database IDs.

---

## Client Management

Clients belong to projects.

A client represents an entity whose usage may be tracked and billed.

Each client includes:

* External ID
* Name
* Email

### Endpoints

```http
POST /clients
GET /clients

GET /clients/{client_external_id}
PATCH /clients/{client_external_id}
DELETE /clients/{client_external_id}
```

The client list endpoint can optionally filter by project:

```text
GET /clients?project_external_id=<project_id>
```

---

## Event Types

Event types define the kinds of usage events that can be tracked for a project.

Examples might include:

```text
api_request
video_processed
storage_gb
report_generated
```

Each event type belongs to a specific project.

An event code is therefore scoped to its project rather than being globally shared across the entire system.

### Endpoints

```http
POST /event_types
GET /event_types

GET /event_types/{event_type_external_id}
PATCH /event_types/{event_type_external_id}
DELETE /event_types/{event_type_external_id}
```

Listing event types requires a project identifier:

```text
GET /event_types?project_external_id=<project_id>
```

---

## Pricing Rules

Pricing rules define how tracked usage is converted into billable amounts.

A pricing rule associates an event type with a price per unit.

Conceptually:

```text
Usage Event
     ↓
Event Type
     ↓
Pricing Rule
     ↓
Price Per Unit
     ↓
Invoice Item
```

For example:

```text
Event: video_processed
Quantity: 10
Price per unit: $0.50

Total: $5.00
```

### Endpoints

```http
POST /pricing_rules
GET /pricing_rules

GET /pricing_rules/{pricing_rule_external_id}
PATCH /pricing_rules/{pricing_rule_external_id}
DELETE /pricing_rules/{pricing_rule_external_id}
```

Pricing rules can be listed by project.

---

## API Key Management

API keys are associated with clients and can be managed by authenticated platform users.

The API supports:

* Creating keys
* Listing keys
* Renaming keys
* Revoking keys
* Rotating keys

### Create API Key

```http
POST /api-keys
```

The request identifies the client and provides a name for the key.

The key itself should be treated as a credential and stored securely by the receiving client.

---

### List Client API Keys

```http
GET /api-keys/{client_external_id}
```

Returns API keys associated with a client.

Responses expose metadata such as:

* External ID
* Name
* Key prefix
* Revocation status

The full secret value is not returned as ordinary key metadata.

---

### Rename API Key

```http
PATCH /api-keys/{api_key_external_id}
```

Updates the human-readable name of an API key.

---

### Revoke API Key

```http
POST /api-keys/{api_key_external_id}/revoke
```

Revokes an API key.

Revocation metadata includes information such as:

* Revocation status
* Revocation timestamp
* Revoking user

---

### Rotate API Key

```http
POST /api-keys/{api_key_external_id}/rotate
```

Rotates an existing API key.

Key rotation allows credentials to be replaced without requiring the client relationship itself to be recreated.

---

## Usage Tracking

Usage events represent billable activity generated by clients.

The API accepts usage data and processes it asynchronously.

### Track Usage

```http
POST /usage-events
```

The request includes:

* Event code
* Quantity
* Optional metadata

Example conceptual payload:

```json
{
  "event_code": "video_processed",
  "quantity": 5,
  "metadata": {
    "resolution": "1080p"
  }
}
```

---

### Asynchronous Processing

Usage ingestion does not synchronously write the final usage record during the request.

Instead:

```text
API Request
    ↓
Validate Event Type
    ↓
Queue Celery Task
    ↓
Return 202 Accepted
    ↓
Worker Processes Event
    ↓
Usage Event Stored
```

This keeps the request path lightweight and allows background workers to handle persistence.

---

### Idempotency

The endpoint accepts an optional `Idempotency-Key` header.

```http
Idempotency-Key: <unique_key>
```

Idempotency protects against duplicate usage events caused by retries or redelivery.

The uniqueness scope is client-specific.

This means:

```text
Client A + key-123
```

and:

```text
Client B + key-123
```

are treated independently.

A duplicate key for the same client does not create another usage event.

---

## Invoice Management

Invoices are generated from accumulated usage events.

The billing engine:

1. Selects usage events within a billing period.
2. Groups usage by client and event type.
3. Applies pricing rules.
4. Creates invoice items.
5. Calculates totals.
6. Associates billed usage events with the generated invoice.

Already invoiced usage events are excluded from future invoice generation.

This prevents the same usage event from being billed twice.

---

### Invoice Endpoints

```http
GET /invoices
POST /invoices

GET /invoices/{invoice_external_id}
```

---

### List Invoices

```http
GET /invoices
```

Supports pagination.

Parameters include:

```text
page
page_size
project_ext_id
client_ext_id
status
period_start
period_end
```

The maximum page size is 100.

---

### Generate Due Invoices

```http
POST /invoices
```

This endpoint manually triggers generation of invoices for projects whose billing schedules are due.

This operation currently acts across the system rather than belonging to a single user's project.

For that reason, it should not be treated as an ordinary tenant-facing action.

The intended production design is for this capability to become an administrative or privileged operation.

In a future role-based authorization model, access to system-wide operations such as invoice generation should be restricted to authorized administrative users.

---

## Invoice Status Lifecycle

Invoices use a controlled status lifecycle.

Available statuses are:

```text
generated
pending
paid
voided
refunded
```

State transitions are validated by a dedicated status service rather than allowing arbitrary status updates.

This prevents invalid transitions from silently corrupting billing state.

For example, a paid invoice should not casually return to a pending state because someone felt adventurous at 2 AM.

The test suite covers both allowed and disallowed transitions.

---

## Payment Management

Payments are associated with invoices.

The payment flow integrates with an external payment provider through a provider abstraction.

The currently implemented provider integration is Stripe.

### Create Payment

```http
POST /payments/{invoice_external_id}
```

Creates a payment attempt for an invoice.

A successful creation returns:

* Payment external ID
* Provider client secret

The client secret can then be used by the frontend payment flow.

---

### Retry Payment

```http
POST /payments/retry/{invoice_external_id}
```

Allows a failed payment attempt to be retried when the invoice and previous payment state permit it.

Retry guards prevent invalid retry scenarios.

---

### List Payments

```http
GET /payments
```

Supports pagination and filtering by:

```text
page
page_size
project_ext_id
client_ext_id
status
period_start
period_end
```

---

## Payment Status Lifecycle

Payments use controlled state transitions.

Available statuses include:

```text
created
initiated
processing
succeeded
failed
cancelled
refunded
```

Transitions are validated by the payment status service.

The system prevents invalid transitions such as arbitrary movement from terminal states back into active processing states.

---

## Refund Management

Refunds are created against successful payments.

### Create Refund

```http
POST /payments/{payment_external_id}/refunds
```

A refund request may include:

* Amount
* Optional reason

If no amount is supplied, the remaining refundable balance is used.

The system validates that:

* The payment succeeded.
* The requested amount is positive.
* The payment is not already fully refunded.
* The requested amount does not exceed the remaining refundable balance.

Pending refunds are also considered when calculating the remaining refundable balance.

This prevents multiple concurrent refund requests from collectively exceeding the original payment amount.

---

## Refund Status Lifecycle

Refunds use controlled states.

The lifecycle supports statuses such as:

```text
pending
succeeded
failed
cancelled
```

The state service validates allowed transitions, including retry scenarios.

A fully completed refund may cascade updates to:

```text
Refund
   ↓
Payment
   ↓
Invoice
```

When successful refunds collectively cover the full payment amount, the payment and associated invoice can transition to `REFUNDED`.

---

## Payment Reconciliation

```http
POST /payments
```

The reconciliation endpoint checks payment states against the configured provider.

The reconciliation process examines payments requiring attention and updates local state when the provider reports a change.

The reconciliation service is designed to be batch-resilient.

Conceptually:

```text
Payment A ✓
Payment B ✗
Payment C ✓
```

A failure while reconciling Payment B should not prevent Payment C from being processed.

Each reconciliation item is handled independently so one provider error does not terminate the entire batch.

Like manual invoice generation, this endpoint currently operates at a system-wide level.

It is therefore better suited to administrative access or internal automation in a future authorization model.

---

## Stripe Webhooks

```http
POST /webhooks/stripe
```

Stripe webhooks provide asynchronous updates from the payment provider.

Supported events include payment and refund lifecycle updates.

Examples include:

```text
payment_intent.succeeded
payment_intent.payment_failed
payment_intent.canceled
refund.updated
```

Webhook handlers update local payment and refund state based on provider events.

---

### Webhook Idempotency

Payment providers may deliver the same webhook more than once.

The application tracks processed webhook event IDs.

The flow is:

```text
Webhook Received
       ↓
Already Processed?
   ↙           ↘
 Yes            No
  ↓              ↓
Ignore        Process Event
                  ↓
             Mark Processed
```

This prevents duplicate webhook delivery from producing duplicate state changes.

Unknown event types are intentionally not marked as processed.

This allows the provider to redeliver the event if support for that event type is added later.

---

## Dashboard

### Summary

```http
POST /dashboard/summary
```

Returns high-level account information, including:

* Total clients
* Total projects
* Active API keys
* Pending invoices
* Paid invoices
* Failed payments
* Revenue for the current month
* Usage events recorded today

The endpoint requires JWT authentication.

---

## Health and Operational Endpoints

### Health Check

```http
GET /health
```

Provides a basic application health response.

This endpoint is intended for infrastructure monitoring and deployment verification.

It can be used by deployment systems to confirm that the application process is running and responding.

---

### Database Check

```http
GET /db-check
```

Performs a database connectivity check.

The endpoint currently reports whether the application can successfully connect to the database.

Because the response exposes only a simple connectivity result and no database data, it does not currently require authentication.

In a more hardened production environment, operational endpoints should still be reviewed based on infrastructure requirements and exposure.

---

## Current User

### Get Current User

```http
GET /me
```

Returns information about the currently authenticated user.

Requires a valid Bearer access token.

---

## Pagination

Invoice and payment listing endpoints support pagination.

The common parameters are:

```text
page
page_size
```

The response includes:

```json
{
  "page": 1,
  "page_size": 10,
  "total": 42,
  "pages": 5,
  "items": []
}
```

The maximum supported page size is 100.

---

## Error Handling

FastAPI automatically validates request data against the API schemas.

Validation failures return:

```http
422 Unprocessable Entity
```

Authentication failures and ownership violations are handled according to the authentication and tenant-isolation rules.

Typical responses include:

```text
401 Unauthorized
404 Not Found
422 Unprocessable Entity
```

Cross-tenant resources intentionally return `404 Not Found` to avoid revealing the existence of another tenant's data.

---

## External IDs

The API generally exposes resources through externally generated identifiers rather than internal database primary keys.

Examples include:

```text
project_external_id
client_external_id
invoice_external_id
payment_external_id
api_key_external_id
```

This keeps internal database identifiers separate from the public API contract.

---

## OpenAPI Documentation

FastAPI automatically generates the OpenAPI schema from the application's routes and Pydantic models.

The generated documentation should be considered the authoritative reference for:

* Exact request schemas
* Response schemas
* Required fields
* Optional fields
* Validation constraints
* Query parameters
* Endpoint availability

When running the application locally:

```text
/docs
```

provides an interactive Swagger UI where requests can be tested directly.

```text
/redoc
```

provides an alternative documentation interface.

```text
/openapi.json
```

provides the machine-readable OpenAPI specification.

This document complements those interfaces by explaining the architectural and business rules behind the endpoints.

---

## API Design Notes

Several parts of the API are intentionally separated between tenant-facing operations and system-level operations.

Most resource management follows this pattern:

```text
Authenticated User
        ↓
Owns Projects
        ↓
Projects Own Resources
        ↓
Repository Scopes Queries
        ↓
Tenant Isolation
```

System-wide operations such as:

* Manual invoice generation
* Payment reconciliation

currently exist as unrestricted operational endpoints.

This was a pragmatic implementation decision during development.

The recommended future direction is to introduce role-based authorization and restrict these operations to administrative users or internal scheduled services.

---

## Future Improvements

Potential future API improvements include:

* Role-based access control
* Administrative authorization for system-wide operations
* Additional payment-provider implementations
* API versioning
* Rate limiting
* More granular API-key permissions
* Structured audit logging
* Scheduled reconciliation and billing workflows
* Public deployment of the interactive API documentation
* Monitoring and observability endpoints
* More granular health checks for dependencies

The current architecture is designed so these improvements can be added without fundamentally changing the core billing and payment domain.
