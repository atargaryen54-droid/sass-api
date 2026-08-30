# Testing Strategy

This document describes the testing strategy used by the SaaS API and the areas of the system the test suite is designed to protect.

The project does not treat test coverage as a goal by itself. Instead, testing effort is concentrated on areas where failures would have meaningful consequences: incorrect financial operations, corrupted application state, duplicate processing, or cross-tenant data exposure.

The test suite therefore focuses primarily on business rules, state transitions, asynchronous processing, external integration boundaries, and tenant isolation.

---

## Philosophy

The test suite deliberately does **not** aim for blanket coverage of every CRUD endpoint.

Coverage effort is concentrated on the surfaces where a bug actually costs something:

* money moving incorrectly
* duplicate billing or processing
* invalid lifecycle transitions
* corrupted financial state
* missed or incorrectly handled external events
* one tenant accessing another tenant's data

Simple CRUD flows with straightforward ownership checks and standard validation are not tested as isolated suites for every resource. These paths are exercised indirectly through fixtures and higher-level tests throughout the suite.

The philosophy is therefore:

> **Prioritize tests around business risk rather than maximizing a coverage percentage.**

The most heavily tested areas are:

* invoice generation and billing aggregation
* invoice, payment, and refund state machines
* payment and refund guards
* tenant isolation
* webhook idempotency
* asynchronous usage processing
* reconciliation and batch failure resilience

This approach keeps the suite focused on the parts of the system where a regression could cause the greatest damage.

---

## Test Environment

Tests run against a dedicated PostgreSQL test database rather than mocking the database layer.

Using a real database allows the suite to verify behavior involving:

* database constraints
* transactions and rollbacks
* unique constraints
* persistence behavior
* relationships between models
* tenant-scoped queries

The test schema is created using:

```python
Base.metadata.create_all()
```

This allows the test environment to create the required schema without requiring Alembic migrations to be executed before every test run.

The application uses a separate test database connection through `TEST_DATABASE_URL`, ensuring test data remains isolated from the development or production database.

External services are treated differently.

The real Stripe provider is mocked through the application's provider abstraction:

```text
PaymentProviderFactory
```

This means the test suite can simulate successful payments, failures, retries, refunds, and provider responses without making network calls to Stripe.

As a result, tests exercise the application's integration logic while remaining deterministic and independent of external network availability.

---

## Testing Approach

The project uses a combination of service-level and route-level testing.

### Service-Level Testing

Most business logic is tested directly through service methods.

This allows tests to focus on the behavior being verified without introducing unrelated HTTP concerns such as routing, authentication parsing, or request serialization.

For example, service-level tests are used for:

* invoice generation
* billing period calculations
* payment creation and retries
* refund calculations
* lifecycle state transitions
* reconciliation
* webhook handlers
* usage processing

This approach keeps tests focused and makes failures easier to diagnose.

### Route-Level Testing

Route-level tests are used where testing the complete request path provides additional value.

The primary example is tenant isolation.

A service-level ownership test could pass while a route accidentally fails to pass the authenticated user's identity into the repository layer.

For that reason, ownership tests exercise the full dependency chain:

```text
HTTP Request
      ↓
Authentication Dependency
      ↓
Route
      ↓
Repository / Service
      ↓
Database Query
```

This verifies that tenant isolation is enforced in the actual API wiring, not only in isolated business logic.

### External Provider Mocking

The Stripe payment provider is mocked through `PaymentProviderFactory.get`.

No test makes a real network call to Stripe.

Mocking occurs at the provider boundary rather than throughout the business logic. This allows the tests to simulate realistic provider responses while continuing to exercise the application's actual payment, refund, webhook, and reconciliation logic.

This approach makes failures deterministic and allows edge cases, such as provider exceptions or delayed status changes, to be tested reliably.

### Database Testing

The suite uses a real PostgreSQL test database rather than mocking repository behavior.

This is particularly important for this application because several important guarantees depend on database behavior, including:

* unique constraints for idempotency
* transaction rollbacks
* persistence of invoice relationships
* tenant-scoped queries
* aggregation queries
* financial state consistency

Testing against the real database provides stronger confidence that these behaviors work together as they do in the running application.

---

## Coverage Areas

### Tenant Isolation

Tenant isolation is tested at the route level to verify that ownership checks are correctly wired through the full request path.

The ownership test suite covers resources including:

* projects
* clients
* event types
* pricing rules
* invoices
* payments

Tests verify that:

* cross-tenant resource reads return `404`
* list endpoints do not expose another tenant's data
* cross-tenant mutations are rejected
* rejected mutations leave the real owner's data unchanged
* payment and refund operations cannot be performed against another tenant's financial resources

The API intentionally returns `404` rather than `403` for resources belonging to another tenant. A `403` response can reveal that a resource exists, while a `404` avoids confirming its existence to an unauthorized caller.

The suite also includes authentication rejection cases, including:

* missing authorization headers
* malformed tokens
* invalid authentication schemes
* empty bearer tokens

A corresponding sanity check verifies that users can successfully access their own resources. This prevents a false-positive situation where every request returns `404` and the isolation tests pass accidentally.

---

### Billing and Invoice Generation

The billing engine is one of the most heavily tested parts of the application.

`InvoiceService.generate_invoices` is responsible for converting raw usage events into invoices and invoice line items.

Tests verify:

* correct aggregation by client
* correct aggregation by event type within a client
* usage events already associated with an invoice are excluded
* events outside the requested billing period are excluded
* missing pricing rules fall back to a `0.00` unit price rather than crashing
* an empty billing period produces no invoice
* generated usage events are associated with the resulting invoice

Double-billing protection is verified by running invoice generation twice and confirming that the second execution does not bill the same usage events again.

`InvoiceService.generate_project_billing` is tested separately because it is responsible for project-level billing period calculations and updating `next_billing_date`.

Billing frequencies are tested across:

* daily
* weekly
* monthly

The suite also verifies atomicity.

If invoice generation fails partway through the operation:

* no partially generated invoice should remain
* `next_billing_date` must not advance

This ensures that billing generation and billing schedule updates succeed or fail together.

Invalid or corrupted billing frequency values are also tested to ensure they do not leave the project in a partially updated state.

---

### Invoice State Machine

Invoice lifecycle transitions are tested through `InvoiceStatusService`.

The suite verifies:

* every allowed transition
* disallowed transitions
* same-status transitions as safe no-ops

State-machine tests ensure that invoice lifecycle rules are enforced consistently and cannot be bypassed by arbitrary status changes.

---

### Payment Lifecycle

Payments are tested both as a state machine and as part of the payment workflow.

`PaymentStatusService` verifies:

* valid lifecycle transitions
* invalid lifecycle transitions
* same-status no-ops

This includes transitions that may appear superficially reasonable but would violate the application's lifecycle rules, such as moving a completed payment back into a pending state.

Payment creation tests verify that:

* payments cannot be created for `VOIDED` invoices
* payments cannot be created for already `PAID` invoices
* rejected payment attempts do not leave orphan payment records
* provider failures mark the payment as `FAILED`
* provider failure reasons are persisted
* provider failures are re-raised so the caller knows the operation failed
* successful payment creation stores the provider payment identifier
* successful creation advances the invoice from `GENERATED` to `PENDING`
* retry-style operations do not attempt invalid duplicate invoice transitions
* unknown invoices are rejected

Payment retry behavior is tested independently.

The suite verifies rejection when:

* the invoice is not in `PENDING`
* the most recent payment is not `FAILED`
* no previous payment attempt exists
* the most recent payment is `CANCELLED`

Each guard condition is tested independently so failures clearly identify which business rule regressed.

---

### Refund Lifecycle

Refund lifecycle transitions are tested through `RefundStatusService`.

The suite verifies:

* allowed transitions
* disallowed transitions
* the `FAILED → PENDING` retry path
* same-status no-ops

Refund creation tests verify that:

* refunds can only be created for successful payments
* already fully refunded payments cannot be refunded again
* omitted refund amounts default to the remaining refundable balance
* the remaining balance is recalculated after partial refunds
* refund requests exceeding the remaining balance are rejected
* zero or negative refund amounts are rejected
* requests for exactly the remaining balance succeed
* provider failures roll back cleanly

The application also protects against overlapping refund requests.

Both completed and in-flight refunds are considered when calculating the remaining refundable balance. This prevents multiple refund requests from independently passing validation while collectively exceeding the original payment amount.

---

### Full Refund Cascading

The payment service contains logic for detecting when a payment has been fully refunded.

Tests verify that:

* partial refunds do not change the payment or invoice to `REFUNDED`
* an exact full refund transitions both payment and invoice appropriately
* refund totals greater than or equal to the payment amount trigger the full-refund cascade
* `PENDING` and `FAILED` refunds do not count as completed refunds
* multiple successful partial refunds correctly accumulate toward the full payment amount

This verifies that the application evaluates the total refund history rather than only inspecting the most recent refund.

---

### Reconciliation

Reconciliation periodically checks the payment provider for updates that may not have been reflected through webhook processing.

The most important property tested in reconciliation is batch resilience:

> A failure while reconciling one payment or refund must not stop the rest of the batch.

Tests simulate batches where one provider request fails while other records still reconcile successfully.

The suite verifies that:

* payment reconciliation does not stop after one provider failure
* refund reconciliation does not stop after one provider failure
* only relevant payment statuses are sent to the provider
* only pending refunds are reconciled
* out-of-scope records do not trigger provider calls
* provider status changes are applied correctly
* failed payments capture provider failure reasons
* matching provider and local statuses are treated as no-ops
* successful full refunds cascade to payment and invoice state
* partial successful refunds do not prematurely trigger the full-refund cascade
* empty reconciliation queues do not call the provider

Provider responses are simulated using controlled test helpers that can return different responses or raise exceptions for specific provider identifiers.

This allows realistic mixed-success batches to be tested without making network calls.

---

### Webhook Processing

Webhook processing is tested with a strong focus on idempotency and safe event handling.

The application tracks processed webhook events using the provider event identifier.

Tests verify that an already processed event:

* exits before its handler executes
* does not perform duplicate state transitions
* does not create duplicate processed-event records

The handler itself is mocked in idempotency tests to confirm that duplicate events are rejected before any business logic runs.

Unknown webhook event types are intentionally not marked as processed.

This allows the provider to redeliver the event if support for that event type is added later, rather than permanently swallowing an event the application does not yet understand.

Individual handlers are tested for:

* `payment_intent.succeeded`
* `payment_intent.failed`
* `payment_intent.canceled`
* `refund.updated`

Tests verify:

* correct lifecycle transitions
* processed webhook records are written
* missing local payment or refund records are handled safely
* repeated successful events remain idempotent
* successful full refunds trigger the appropriate cascade
* partial refunds do not trigger premature full-refund behavior
* unrecognized refund statuses leave the refund unchanged and unmarked

This ensures unsupported or unknown events remain safely eligible for future redelivery.

---

### Usage Processing

Usage ingestion is intentionally asynchronous.

The request path validates the incoming usage event and queues background processing rather than immediately writing the event to the database.

Tests verify that:

* an unknown event code returns `404`
* event codes are scoped to their project
* an event code registered under another project cannot be used
* valid usage requests enqueue the expected Celery task payload
* ingestion itself does not synchronously persist a `UsageEvent`

The Celery usage-processing task is tested directly as a callable.

Tests verify that:

* valid events are persisted with the expected fields
* metadata is stored correctly
* duplicate idempotency keys for the same client are ignored
* the same idempotency key can be used by different clients
* unexpected processing failures roll back and re-raise

The idempotency constraint is intentionally scoped per client rather than globally.

This prevents duplicate processing for the same client while allowing unrelated clients to use the same idempotency key.

Because the Celery task creates its own database session through `SessionLocal()`, tests patch that dependency to use the test database.

This ensures task tests do not accidentally connect to the development database.

---

## Bugs Found Through Testing

Writing the test suite uncovered several real implementation bugs.

### Incorrect Dictionary Access in Webhook Handling

A payment failure webhook handler attempted to retrieve Stripe error information using `getattr()`.

The webhook payload was a dictionary, meaning attribute access did not retrieve the provider's error field.

As a result, the real failure reason was discarded and the application always fell back to a generic error message.

The implementation was corrected to use dictionary key access through `.get()`.

---

### Pending Refund Overlap

The remaining refundable balance was originally calculated using only successfully completed refunds.

This allowed a potential race where multiple refund requests could pass validation while earlier refund requests were still pending.

The calculation was updated to account for in-flight pending refunds as well, preventing requests from collectively exceeding the original payment amount.

---

### Overly Broad Integrity Error Handling

The asynchronous usage-processing task originally treated every `IntegrityError` as a duplicate usage event.

This meant unrelated database integrity failures, such as foreign-key violations, could be silently swallowed and incorrectly logged as routine duplicate delivery.

The implementation was updated to identify the specific unique-constraint violation associated with duplicate idempotency keys.

Other integrity errors are now rolled back and re-raised so Celery can recognize the task as failed.

---

These bugs demonstrate an important purpose of the test suite beyond increasing coverage metrics:

> Tests are used to challenge assumptions about business logic and realistic failure scenarios.

The issues above were discovered because the tests asserted specific business outcomes and realistic provider behavior rather than simply verifying that code executed without raising exceptions.

---

## What Is Intentionally Not Covered

The suite does not maintain separate exhaustive CRUD test files for every resource.

Resources such as:

* clients
* projects
* event types
* pricing rules
* API keys
* authentication

are exercised indirectly throughout fixture setup and higher-level tests.

This is an intentional trade-off.

The project prioritizes testing areas where failures could result in:

* financial errors
* duplicate billing
* invalid state transitions
* tenant data exposure
* lost asynchronous work
* incorrect external integration behavior

Simple CRUD paths with low business complexity are comparatively inexpensive to validate manually and provide less value per additional test.

The goal is not maximum test count or blanket endpoint coverage.

The goal is confidence in the application's highest-risk behavior.

---

## Running the Test Suite

The default workflow runs tests inside the Docker environment.

### 1. Configure the Test Environment

Create the test environment file:

```bash
cp .env.test.example .env.test
```

The Docker configuration uses the PostgreSQL service hostname:

```env
TEST_DATABASE_URL=postgresql://saas_user:saas_password@db:5432/saas_db_test
```

### 2. Start the Application Services

```bash
docker compose up -d
```

### 3. Create the Test Database

```bash
docker compose exec db createdb -U saas_user saas_db_test
```

If the test database already exists, this step can be skipped.

### 4. Run the Tests

Run the test suite inside the API container:

```bash
docker compose exec api pytest
```

The test schema is created automatically by the test configuration using:

```python
Base.metadata.create_all()
```

No Alembic migration step is required before running the test suite.

### Running Tests on the Host Machine

If the application and PostgreSQL are running directly on the host machine rather than through Docker, update the database hostname in `.env.test`.

Change:

```text
db
```

to:

```text
localhost
```

For example:

```env
TEST_DATABASE_URL=postgresql://saas_user:saas_password@localhost:5433/saas_db_test
```

Then run:

```bash
pytest
```
