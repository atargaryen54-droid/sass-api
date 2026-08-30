# Architecture

## Overview

SaaS API is a containerized backend platform designed around usage-based billing. It provides the infrastructure needed to manage projects and clients, ingest usage events, calculate charges, generate invoices, process payments and refunds, and reconcile application state with external payment providers.

The system is designed as a set of clearly separated responsibilities rather than placing all application logic directly inside HTTP routes. Request handling, business rules, database access, asynchronous processing, scheduling, and third-party integrations are separated into distinct architectural layers.

At a high level, the system consists of:

* A FastAPI application serving the HTTP API
* PostgreSQL for persistent application data
* Redis as the Celery message broker
* Celery workers for asynchronous processing
* Celery Beat for scheduled operations
* A payment provider abstraction with Stripe as the currently implemented provider

The production environment runs these components as separate Docker containers while sharing the same versioned application image for the API, worker, and scheduler.

---

# 1. High-Level System Architecture

The system is composed of five primary services:

```text
                    ┌─────────────────────┐
                    │       Client        │
                    │ Dashboard / API App │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI API    │
                    │                     │
                    │ Routes → Services   │
                    │        → Repositories│
                    └──────┬────────┬─────┘
                           │        │
                ┌──────────┘        └──────────┐
                ▼                              ▼
       ┌─────────────────┐             ┌─────────────────┐
       │   PostgreSQL    │             │      Redis      │
       │                 │             │                 │
       │ Persistent Data │             │ Celery Broker   │
       └─────────────────┘             └────────┬────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              ▼                                   ▼
                        ┌──────────┐                        ┌──────────┐
                        │  Worker  │                        │   Beat   │
                        │          │                        │          │
                        │ Async    │                        │ Scheduled│
                        │ Tasks    │                        │ Operations│
                        └──────────┘                        └──────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Payment Provider │
                       │      Stripe      │
                       └──────────────────┘
```

Each component has a specific responsibility:

### FastAPI API

The API handles incoming HTTP requests, validates request data, performs authentication and authorization, and delegates application behavior to the appropriate service layer.

### PostgreSQL

PostgreSQL stores persistent application data, including users, projects, clients, API keys, usage events, invoices, payments, refunds, and processed webhook events.

### Redis

Redis acts as the message broker used by Celery to distribute asynchronous work.

### Celery Worker

Workers execute background tasks that should not block HTTP requests, including asynchronous usage-event processing.

### Celery Beat

Celery Beat schedules periodic operations such as billing-related jobs. Beat is responsible for scheduling tasks, while workers are responsible for executing them.

---

# 2. Application Layering

The application follows a layered architecture that separates HTTP concerns, business logic, and persistence.

```text
HTTP Request
     │
     ▼
Route / Dependency Layer
     │
     ▼
Service Layer
     │
     ▼
Repository Layer
     │
     ▼
Database
```

This separation keeps responsibilities explicit and prevents application logic from becoming tightly coupled to HTTP routes or database queries.

## API Layer

The API layer is responsible for:

* Handling HTTP requests and responses
* Request validation through Pydantic schemas
* Authentication dependencies
* Authorization and ownership boundaries
* Passing validated data to application services
* Serializing responses

Routes are intentionally kept relatively thin. Business rules should not depend on HTTP-specific concerns unless the behavior itself belongs to the transport layer.

## Service Layer

The service layer contains the application's business logic.

Examples include:

* Usage-event ingestion
* Invoice generation
* Billing-period calculation
* Payment creation and retries
* Refund validation
* Payment and refund reconciliation
* API key lifecycle management
* State-transition validation

This is where rules such as the following are enforced:

* Already-invoiced usage must not be billed again.
* A payment cannot be created for an invoice that is already paid or voided.
* Refunds cannot exceed the remaining refundable balance.
* Invalid state transitions must be rejected.
* Billing schedules should not advance when invoice generation fails.

Keeping these rules in services makes them independently testable without requiring every test to travel through HTTP routing and authentication.

## Repository Layer

Repositories are responsible for persistence and data access.

Their responsibilities include:

* Querying SQLAlchemy models
* Creating and updating database records
* Retrieving resources by external identifiers
* Applying ownership scopes where appropriate

Business rules are kept outside repositories. A repository should primarily answer questions about storing and retrieving data rather than deciding whether a business operation is valid.

---

# 3. Multi-Tenancy and Ownership

The application is structured around user-owned projects.

Projects act as the primary ownership boundary for resources associated with the platform.

```text
User
 │
 ├── Project A
 │    ├── Clients
 │    ├── Event Types
 │    ├── Pricing Rules
 │    ├── Usage Events
 │    └── Billing Records
 │
 └── Project B
      ├── Clients
      ├── Event Types
      ├── Pricing Rules
      ├── Usage Events
      └── Billing Records
```

Resources are scoped through project ownership to prevent one user from accessing another user's data.

For externally accessible resources, the API uses external identifiers rather than exposing internal database primary keys.

## Tenant Isolation

Repository queries involving tenant-owned resources are scoped through project ownership.

This prevents a request from retrieving a resource simply because its external identifier is known.

Cross-tenant resource access is treated as a missing resource and returns `404 Not Found` rather than `403 Forbidden`.

This approach avoids confirming the existence of resources belonging to another tenant.

Tenant isolation is tested at the route level because service-level tests alone cannot guarantee that ownership information is correctly passed through the full request chain.

---

# 4. Authentication and Access Model

The system uses two primary mechanisms for access.

## User Authentication

Users authenticate using JWT access tokens.

These tokens are used for management operations such as:

* Managing projects
* Managing clients
* Managing event types
* Managing pricing rules
* Managing API keys
* Viewing invoices and payments
* Creating payments and refunds

## API Keys

API keys are used for machine-to-machine access.

They are primarily intended for clients or applications reporting usage to the platform.

This creates a clear separation between human access and application access:

```text
Human / Dashboard Access
        │
        ▼
       JWT


Application / Service Access
        │
        ▼
      API Key
```

API keys support lifecycle operations including:

* Creation
* Listing
* Renaming
* Rotation
* Revocation

The API exposes only the information required to manage keys and avoids treating API keys as ordinary user authentication credentials.

---

# 5. Usage Ingestion Architecture

Usage events are processed asynchronously.

The request path validates the incoming event and queues it for background processing rather than synchronously persisting all work during the HTTP request.

```text
Client Application
        │
        │ Usage Event
        ▼
┌───────────────────┐
│  FastAPI Endpoint │
└─────────┬─────────┘
          │
          │ Validate
          ▼
┌───────────────────┐
│ UsageEventService │
└─────────┬─────────┘
          │
          │ Queue Task
          ▼
┌───────────────────┐
│      Redis        │
│ Celery Broker     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Celery Worker    │
└─────────┬─────────┘
          │
          │ Persist Event
          ▼
      PostgreSQL
```

The API responds with `202 Accepted` once the event has been accepted for asynchronous processing.

## Event Validation

Usage events are associated with registered event types.

Event codes are scoped to projects rather than treated as globally valid. A code registered for one project is not automatically valid for another.

## Idempotency

Usage ingestion supports idempotency to prevent duplicate events during retries or redelivery.

The idempotency key is scoped to the client rather than globally.

This means:

* Repeated delivery of the same event for the same client can be safely ignored.
* The same idempotency key used by a different client does not automatically represent a duplicate.

The worker performs persistence and handles duplicate delivery separately from genuinely unexpected failures.

Unexpected database errors are not silently treated as duplicates, allowing Celery's failure and retry behavior to operate correctly.

---

# 6. Billing Architecture

The billing system converts recorded usage into invoices.

The high-level flow is:

```text
Usage Events
     │
     ▼
Filter Unbilled Events
     │
     ▼
Group by Client and Event Type
     │
     ▼
Apply Pricing Rules
     │
     ▼
Create Invoice
     │
     ▼
Create Invoice Items
     │
     ▼
Associate Usage Events with Invoice
```

The billing engine aggregates usage by client and event type before calculating invoice line items.

Each line item represents the quantity of a particular event multiplied by its configured unit price.

## Double-Billing Prevention

Once usage events are included in an invoice, they are associated with that invoice.

Future billing runs exclude usage events that already have an invoice association.

This prevents the same usage from being invoiced multiple times.

## Billing Frequencies

Projects support configurable billing frequencies:

* Daily
* Weekly
* Monthly

The billing service determines whether a project is due for billing and calculates the appropriate billing period.

## Transactional Consistency

Invoice generation and billing schedule advancement are treated as part of the same logical operation.

If invoice generation fails:

* The invoice should not remain partially persisted.
* Usage events should not be partially committed as billed.
* The project's `next_billing_date` should not advance.

The billing operation therefore protects both invoice generation and schedule advancement from partial completion.

---

# 7. Background Processing and Scheduling

The application separates asynchronous execution from scheduling.

## Celery Worker

The worker executes queued background tasks.

Examples include:

* Processing usage events
* Other asynchronous application operations

## Celery Beat

Celery Beat schedules periodic tasks.

A simplified scheduled billing flow looks like:

```text
Celery Beat
     │
     │ Schedule Task
     ▼
Celery Worker
     │
     ▼
Billing Service
     │
     ▼
Find Projects Due for Billing
     │
     ▼
Generate Invoices
```

The distinction is intentional:

> Celery Beat schedules work. Celery workers execute work.

Separating these responsibilities allows scheduled operations and asynchronous processing to run independently.

---

# 8. Payment Architecture

Payments are designed around a provider abstraction.

The application business logic does not directly depend on Stripe-specific behavior throughout the payment domain.

```text
Payment Service
       │
       ▼
Payment Provider Factory
       │
       ▼
┌─────────────────────┐
│ Payment Provider    │
│ Interface           │
└──────────┬──────────┘
           │
           ▼
         Stripe
```

The payment provider abstraction allows the application to separate payment-domain behavior from provider-specific implementation details.

The application's payment-provider model includes support for providers such as:

* Stripe
* Chapa
* PayPal

Stripe is the currently implemented integration.

The abstraction allows additional providers to be implemented without requiring the payment lifecycle itself to become tightly coupled to a single provider.

---

# 9. Payment Lifecycle

Payments move through explicitly controlled states.

A simplified lifecycle is:

```text
CREATED
   │
   ▼
INITIATED
   │
   ▼
PROCESSING
   │
   ├──────────────► SUCCEEDED
   │                     │
   │                     ▼
   │                  REFUNDED
   │
   ├──────────────► FAILED
   │
   └──────────────► CANCELLED
```

The application uses dedicated status services to control valid and invalid transitions.

The same architectural pattern is applied to:

* Invoices
* Payments
* Refunds

This prevents arbitrary state changes from being scattered throughout the application.

Instead, lifecycle rules are centralized and independently testable.

For example, a transition that is valid in one state may be explicitly rejected in another.

Same-status transitions are treated as safe no-ops where appropriate.

---

# 10. Refund Architecture

Refunds are created against successful payments.

Before creating a refund, the application validates:

* The payment is eligible for refunding.
* The requested amount is positive.
* The requested amount does not exceed the remaining refundable balance.
* The payment has not already been fully refunded.

If no refund amount is specified, the remaining refundable balance is used.

## Remaining Refundable Balance

The remaining refundable amount accounts for both completed refunds and in-flight pending refunds.

Including pending refunds prevents multiple concurrent refund requests from independently passing validation and collectively exceeding the original payment amount.

## Full Refund Cascade

When successful refunds fully cover a payment:

```text
Refund SUCCEEDED
        │
        ▼
Payment → REFUNDED
        │
        ▼
Invoice → REFUNDED
```

Partial refunds do not trigger the full cascade until the cumulative successful refund amount reaches the payment amount.

---

# 11. Webhook Architecture

The application receives payment-provider events through webhooks.

For Stripe, the flow is:

```text
Stripe
   │
   │ Webhook Event
   ▼
/webhooks/stripe
   │
   ▼
Route Event
   │
   ▼
Check Processed Events
   │
   ├── Already Processed → Ignore
   │
   ▼
Event Handler
   │
   ▼
Update Payment / Refund State
   │
   ▼
Record Processed Event
```

## Webhook Idempotency

Payment providers can retry webhook delivery.

To prevent repeated delivery from applying the same state changes multiple times, processed event identifiers are recorded.

If an event has already been processed, processing stops before the event handler is executed.

## Unknown Events

Unhandled event types are intentionally not marked as successfully processed.

This prevents an unsupported event from being permanently swallowed.

If support for that event is later added, the provider can continue delivering it rather than the application incorrectly claiming that it was already handled.

---

# 12. Reconciliation Architecture

Webhooks provide one source of payment status updates, but the application also supports reconciliation with the payment provider.

Reconciliation compares locally stored records with the provider's current state.

```text
Database Records
       │
       ▼
Find Reconciliation Candidates
       │
       ▼
Payment Provider
       │
       ▼
Retrieve Provider State
       │
       ▼
Apply Valid State Transition
```

Only records in states requiring reconciliation are considered.

Records already in final or irrelevant states are not unnecessarily sent to the provider.

## Batch Resilience

Each record in a reconciliation batch is handled independently.

A failure while reconciling one payment or refund does not stop the remainder of the batch.

For example:

```text
Payment A → Updated Successfully
Payment B → Provider Error
Payment C → Updated Successfully
```

The failure of Payment B does not prevent Payment C from being reconciled.

This behavior is particularly important for scheduled or batch-based operations where a single provider failure should not halt all unrelated records.

---

# 13. Database Architecture

PostgreSQL is used for persistent application data.

The database stores entities including:

* Users
* Projects
* Clients
* API keys
* Event types
* Pricing rules
* Usage events
* Invoices
* Invoice items
* Payments
* Refunds
* Processed webhook events

## Schema Management

Database schema changes are managed using Alembic migrations.

Application code and database schema are versioned independently through migration revisions.

Production deployments apply migrations before the updated application services begin operating against the new schema.

This prevents application code from expecting database structures that do not yet exist.

## Persistent Storage

The production PostgreSQL container uses a Docker volume for persistent data.

Recreating an application container does not automatically remove the database data stored in the volume.

Redis also uses persistent storage through a Docker volume.

---

# 14. Deployment Architecture

The production environment is containerized with Docker Compose.

The stack consists of:

```text
Docker Compose
│
├── PostgreSQL
├── Redis
├── FastAPI API
├── Celery Worker
└── Celery Beat
```

The API, worker, and Beat services use the same versioned application image.

They differ only in the command executed inside the container.

For example:

```text
Same Application Image
        │
        ├── FastAPI API Command
        │
        ├── Celery Worker Command
        │
        └── Celery Beat Command
```

Using the same immutable image version ensures that the API and background processes run compatible application code.

---

# 15. CI/CD Architecture

The deployment pipeline separates validation, artifact creation, and production deployment.

```text
Developer
    │
    ▼
Push to develop
    │
    ▼
CI Pipeline
├── Run Tests
└── Build Docker Image
    │
    ▼
GitHub Container Registry
    │
    ▼
Merge to main
    │
    ▼
CD Pipeline
├── Pull Exact Image Version
├── Apply Database Migrations
├── Start Production Services
└── Verify Health
```

## Continuous Integration

The CI pipeline is responsible for:

* Running the automated test suite
* Building the Docker image after successful validation
* Publishing the image to GitHub Container Registry

Pull requests run validation without automatically creating a production deployment artifact.

## Continuous Deployment

The CD pipeline deploys a previously built image rather than rebuilding application code during deployment.

Images are identified using immutable commit SHA tags.

For example:

```text
ghcr.io/<repository>:<commit-sha>
```

This ensures the deployed application is the exact artifact produced by the successful CI workflow.

## Deployment Verification

The deployment process includes service health checks after application services are started.

Database and Redis dependencies also expose health checks through Docker Compose.

These checks serve different responsibilities:

* Compose health checks control service startup dependencies.
* Deployment verification confirms the application stack is operational after deployment.

For detailed deployment instructions, see [deployment.md](deployment.md).

---

# 16. Testing and Architectural Boundaries

The testing strategy follows the architecture of the application.

Business rules are primarily tested at the service level, while route-level tests are used where HTTP wiring, authentication, and dependency propagation are important.

The test suite focuses heavily on:

* Tenant isolation
* Financial correctness
* State transitions
* Idempotency
* Transactional behavior
* Batch resilience

External payment-provider behavior is mocked during testing, preventing the test suite from making real network calls.

The application uses a real PostgreSQL test database for persistence-related tests rather than replacing database behavior with in-memory mocks.

This provides stronger confidence in:

* Transactions
* Constraints
* Query behavior
* Ownership scoping
* Persistence semantics

For the complete testing philosophy and coverage rationale, see [testing.md](testing.md).

---

# 17. Architectural Principles

The system is guided by several core architectural principles.

## Separation of Concerns

HTTP handling, business logic, persistence, background processing, and external integrations are separated into distinct responsibilities.

## Tenant Isolation

Resources are scoped through ownership boundaries, with cross-tenant access prevented at the data-access level and verified through route-level integration tests.

## Idempotency

Usage ingestion and webhook processing are designed to tolerate retries without duplicating effects.

## Explicit State Transitions

Invoice, payment, and refund lifecycles are controlled through dedicated status services rather than arbitrary status assignments.

## Transactional Consistency

Billing operations are designed to avoid partially completed invoice generation and scheduling updates.

## Asynchronous Processing

Operations that do not need to block an HTTP response are delegated to background workers.

## Provider Abstraction

Payment-domain logic is separated from provider-specific implementations.

## Immutable Deployments

Production services run the exact versioned Docker image produced by the CI pipeline.

---

# Conclusion

The architecture is designed around keeping complex business behavior explicit and isolated.

The system separates request handling from business rules, persistence from domain behavior, and asynchronous work from synchronous API operations. Financial operations are protected by explicit state transitions and transactional behavior, while tenant ownership and idempotency provide safeguards against common SaaS and distributed-system failures.

The result is a backend architecture intended not only to expose API endpoints, but to manage the operational complexity behind usage-based billing, asynchronous processing, payments, refunds, and multi-tenant data safely and predictably.
