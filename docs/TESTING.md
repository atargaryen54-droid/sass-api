# Test Suite Documentation

## Philosophy

This suite deliberately does **not** aim for blanket coverage of every CRUD
endpoint. Coverage effort is concentrated on the surfaces where a bug
actually costs something: money moving incorrectly, state getting
corrupted, or one tenant seeing another tenant's data. Simple
create/read/update/delete flows with a single ownership check and a 404
guard are not tested file-by-file here — they're low-risk, low-complexity,
and a bug in one is cheap to catch by hand.

Concretely, that means:

- **Tested exhaustively:** every state machine (`Invoice`, `Payment`,
  `Refund`), the billing aggregation engine, payment/refund guards,
  webhook idempotency, reconciliation's batch-resilience, and tenant
  isolation.
- **Not tested here:** `clients`, `projects`, `event_types`,
  `pricing_rules`, `api_keys`, `auth` as standalone CRUD suites — these
  are exercised indirectly as fixture setup throughout every other file,
  which already proves the basic paths work.

Where relevant, tests call services directly against the real test
database rather than going through HTTP + auth + routing. The exception is
`test_ownership.py`, which exists specifically to prove the *wired-up*
route-to-repository dependency chain enforces tenant isolation — a
service-level test could pass there while a route forgot to pass
`current_user.id` through, which is exactly the class of bug that test
file exists to catch.

The real Stripe provider is mocked everywhere via
`PaymentProviderFactory.get` — nothing in this suite makes a network call.

---

## `test_ownership.py` — tenant isolation

**Why this file exists:** every "get by external_id" repository method
joins through to `Project.user_id` to scope results to the requesting
user. That pattern is consistent today, but it's exactly the kind of thing
that's easy to silently break in one method later — a copy-pasted
repository function that forgets the join wouldn't fail loudly, it would
just leak data. This file exists to make that regression fail a test
instead of getting discovered in production.

Covers, per resource type (project, client, event_type, pricing_rule,
invoice, payment): cross-tenant reads return `404` (not `403` — the
distinction matters, since a `403` confirms the resource exists to an
attacker and a `404` doesn't); list endpoints never leak another tenant's
rows; cross-tenant mutations (`PATCH`/`DELETE`) are rejected and leave the
real owner's data untouched; payment/refund creation against another
tenant's invoice/payment is rejected; and a battery of auth-rejection
cases (missing header, garbage token, wrong scheme, empty bearer).

Also includes one "sanity check" test confirming a user *can* reach their
own resources — without it, every 404 above would be meaningless, since a
suite that 404s on everything would pass by accident.

---

## `test_invoices.py` — the billing engine

Three things are tested here:

**`InvoiceService.generate_invoices`** — the aggregation logic that turns
raw usage events into invoice line items. Covers: correct aggregation by
client and by event type within a client; already-invoiced events
(`invoice_id` set) are excluded so a second run never double-bills;
events outside the requested period are excluded; a missing pricing rule
falls back to a `0.00` unit price instead of crashing; an empty result
when there's nothing to bill; and — the one that matters most — events
actually get marked with the new `invoice_id` after generation, proven by
running generation twice and confirming the second run bills nothing.

**`InvoiceService.generate_project_billing`** — period math and
`next_billing_date` rollover, parametrized across DAILY/WEEKLY/MONTHLY.
Includes two atomicity tests: if invoice creation fails partway through,
`next_billing_date` must **not** have advanced and no invoice should
exist — proving the rollback protects both halves of the operation
together, not just one. Same pattern for an unsupported/corrupted
`billing_frequency` value.

**`InvoiceStatusService`** — the full allowed/disallowed transition
matrix, plus same-status-is-a-no-op. No DB needed for these; they mutate
a plain Python attribute.

---

## `test_payments.py` — the payment lifecycle

**`PaymentStatusService`** — same state-machine treatment as invoices:
every allowed edge, a deliberately long list of disallowed edges
(including ones that look "almost fine," like `PAID → PENDING`), and
same-status no-ops.

**`create_payment`** — blocked when the invoice is `VOIDED`/`PAID`, with
no orphan payment row left behind; a provider exception flips the payment
to `FAILED` with `failure_reason` set and still re-raises (so the caller
knows it failed); success sets `INITIATED`, stores
`provider_payment_id`, and advances the invoice `GENERATED → PENDING`; a
retry-style call against an already-`PENDING` invoice doesn't try to
re-transition it; unknown invoice → 404.

**`retry_payment`** — the happy path, plus four separate rejection tests
(invoice not `PENDING`, last payment not `FAILED`, no payment attempts
yet, last payment `CANCELLED`) written as individual tests rather than one
combined case, so a failure points at exactly which guard condition
regressed.

**`mark_refunded_if_fully_refunded`** — partial refund leaves payment and
invoice alone; an exact full refund cascades both to `REFUNDED`; a refund
total that overshoots the payment amount still triggers the cascade
(`>=`, not `==`); non-`SUCCEEDED` refunds (`PENDING`, `FAILED`) don't
count toward the sum even when their nominal amounts alone would clear
the threshold; and multiple partial `SUCCEEDED` refunds that sum to the
full amount correctly trigger the cascade, proving it's a running total
and not just a check against the latest refund.

---

## `test_refunds.py`

**`RefundStatusService`** — full transition matrix, including the
`FAILED → PENDING` retry path, and same-status no-ops.

**`create_refund`** — rejects non-`SUCCEEDED` payments and already-fully-
refunded ones; no `requested_amount` defaults to the full remaining
balance, correctly recalculated after a prior partial refund; a request
over the remaining balance is rejected with nothing persisted; zero/
negative amounts rejected; a request for exactly the remaining balance
succeeds; a provider failure rolls back cleanly.

One test, `test_pending_refund_is_not_counted_against_remaining_balance`,
was written to document a gap that existed at the time: `remaining_amount`
was calculated by summing only `SUCCEEDED` refunds, so two refund
requests landing while an earlier one was still `PENDING` could both pass
the guard independently. **This has since been fixed** (the calculation
now also subtracts in-flight `PENDING` refunds), and the test was updated
to assert the corrected behavior — a second refund request that would
push the total over the payment amount is now rejected even while an
earlier refund is still pending.

---

## `test_reconciliation.py`

The single most important property in this file is the
`try/except/continue` inside each reconciliation loop: **one payment or
refund failing to reconcile must not stop the rest of the batch.** That's
tested directly — a batch of three payments where the middle one's
provider call raises still leaves the other two correctly updated, and
`reconcile_payments`/`reconcile_refunds` themselves don't raise.

Also covers: only `INITIATED`/`PROCESSING` payments (and only `PENDING`
refunds) are ever looked at — confirmed by asserting the provider is
never even called for out-of-scope rows, not just that they're
unaffected; a status change from the provider is applied; `FAILED`
results capture `failure_reason`; a matching status is a true no-op; a
fully-covering `SUCCEEDED` refund cascades to payment + invoice; a
*partial* `SUCCEEDED` refund correctly does not cascade yet; and an empty
queue never touches the provider at all.

A small `provider_returning()` test helper maps provider IDs to canned
responses (or exceptions), which is what makes it possible to have one
specific row in a batch fail while the others succeed under the same
mocked provider instance.

---

## `test_webhooks.py`

**Idempotency & routing** — an already-processed event (by `event["id"]`)
short-circuits *before* any handler runs, verified by mocking the handler
and asserting it's never called, not just by checking the outcome. An
unrecognized event type doesn't raise and — deliberately — doesn't get
written to `ProcessedWebhookRepository` either, so Stripe will keep
redelivering it until the app actually knows how to handle it, rather
than the event being silently swallowed forever.

**Per-handler coverage** (`payment_intent.succeeded/failed/canceled`,
`refund.updated`): correct state transition, `ProcessedWebhook` record
written, and a safe no-op when the referenced payment/refund doesn't
exist in our DB. `handle_payment_succeeded` is additionally tested for
idempotency when the payment's already `SUCCEEDED` (no exception, no
duplicate processed-record write). `handle_refund_updated`'s `succeeded`
path is tested for the full cascade to payment + invoice, and an
unrecognized refund status (neither `succeeded`/`failed`/`cancelled`) is
confirmed to leave the refund untouched and unmarked — same
redelivery-safe reasoning as the top-level unhandled-event-type case.

Two real bugs were found and fixed while writing this file:

1. **`handle_payment_failed`** read the failure message with
   `getattr(payment_intent, "last_payment_error", None)` — but
   `payment_intent` is a plain dict, and `getattr()` doesn't perform dict
   key lookup. `last_error` was always `None`, so `failure_reason` always
   fell back to the generic `"Payment failed"` string regardless of what
   Stripe actually sent. Fixed to use `.get(...)`, matching the pattern
   already correctly used in `handle_refund_updated`.
2. The pending-refund gap described above under `test_refunds.py`.

Both were caught specifically *because* the tests were written to assert
realistic payloads and exact values rather than just "doesn't crash" —
a good illustration of why business-logic tests earn their keep beyond
raw coverage percentage.

---

## `test_usage.py` — usage ingestion

**`UsageEventService.ingest_event`** — 404 for an unregistered
`event_code`; that scoping is per-project, not global (a code registered
under a *different* project also 404s here); a valid event enqueues
`process_usage_event.delay` with exactly the expected payload; and
`ingest_event` itself never writes a `UsageEvent` row synchronously —
that's the worker's job, not the request path's.

**`process_usage_event`** (the Celery task, called directly rather than
through the broker — Celery tasks remain plain callables outside it)
covers: a real row gets written with the correct fields, including
metadata; a duplicate `idempotency_key` for the same client is silently
ignored on redelivery; the same `idempotency_key` for a *different*
client is **not** deduped, since the unique constraint is scoped
per-client, not global; and a genuinely unexpected (non-duplicate) error
rolls back and re-raises so Celery's retry mechanism actually sees it
failed.

One infrastructure note for future changes to this file: the task opens
its own DB session via `SessionLocal()` rather than accepting one as a
parameter, so left alone it talks to the real/dev database instead of the
test database every fixture here lives in. `TestProcessUsageEventTask`
has an autouse fixture that patches `app.tasks.usage_tasks.SessionLocal`
to the test engine for its tests — any new test calling this task
directly needs to stay inside that class (or get the same treatment) or
it'll silently hit the wrong database.

**A bug was found and fixed here too:** the task's `except` clause
originally caught `IntegrityError` broadly, so *any* integrity violation
— not just the intended duplicate-`idempotency_key` case — was silently
swallowed and logged as "duplicate ignored." A foreign-key violation
(e.g. a stale `event_type_id`) would have disappeared with no error and
no row written, which could mask a real data problem as routine
deduping. This has since been fixed to isolate the specific
unique-constraint violation from other integrity errors. The test that
documented the old (buggy) behavior has been removed, since it no longer
reflects reality and correct dedup behavior is already covered by the
duplicate-`idempotency_key` tests above.

That's three real bugs found and fixed across this test-writing pass —
the `getattr`-on-a-dict issue and the pending-refund gap noted earlier,
plus this one.