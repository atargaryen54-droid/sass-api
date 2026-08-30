# SaaS Billing & Usage Management API

A production-oriented backend API for managing SaaS usage, clients, projects, pricing, billing, payments, refunds, and asynchronous processing.

The system is designed around a usage-based billing model where projects define billable event types and pricing rules, clients generate usage through API access, and usage events are processed asynchronously before being aggregated into invoices.

Beyond standard CRUD functionality, the project focuses on the engineering challenges that matter in a real multi-tenant SaaS backend: tenant isolation, idempotent event processing, billing accuracy, payment and refund state management, webhook handling, reconciliation with an external payment provider, and reliable background processing.

The application is built with FastAPI, PostgreSQL, Redis, Celery, SQLAlchemy, and Stripe, and is containerized with Docker. Its development workflow includes automated testing, Docker image builds and publishing through GitHub Actions, and a separate deployment pipeline that deploys tested images using immutable image tags.

The goal of this project is not simply to demonstrate API development, but to showcase the design and implementation of a backend system where correctness matters, particularly when handling money, asynchronous events, and data belonging to multiple tenants.

## Key Features

### Authentication & Multi-Tenant Architecture

* JWT-based authentication with access and refresh tokens.
* API key management for clients accessing project services.
* Strict tenant isolation across projects, clients, invoices, payments, pricing rules, and other resources.
* Cross-tenant resources are treated as non-existent, preventing accidental information disclosure.
* Ownership validation is enforced throughout the route and repository layers.

### Usage Tracking & Billing

* Usage-based billing through configurable event types and pricing rules.
* Asynchronous usage event processing using Celery and Redis.
* Idempotency protection to prevent duplicate usage events from being billed multiple times.
* Usage events are aggregated by client and event type to generate invoice line items.
* Support for daily, weekly, and monthly billing cycles.
* Protection against double billing by excluding usage events that have already been assigned to an invoice.
* Atomic billing operations ensure invoice creation and billing-date updates succeed or fail together.

### Payments & Refunds

* Stripe payment integration through a provider abstraction layer.
* Explicit state machines for invoice, payment, and refund lifecycles.
* Guards against invalid payment and refund operations.
* Support for payment retries when previous payment attempts fail.
* Partial and full refunds.
* Automatic cascading of fully refunded payments to update the associated payment and invoice status.
* Protection against refunding more than the original payment amount, including pending refund requests.

### Webhooks & Reconciliation

* Stripe webhook handling for payment and refund events.
* Webhook idempotency using processed-event tracking.
* Safe handling of duplicate webhook deliveries.
* Reconciliation jobs that recover missed payment or refund updates when webhook delivery is unavailable.
* Provider status checks synchronize external payment state with the local database.
* Batch reconciliation continues processing even when individual records fail.

### Background Processing & Scheduling

* Celery workers for asynchronous processing.
* Redis used as the message broker and task backend.
* Scheduled invoice generation through Celery Beat.
* Scheduled payment and refund reconciliation.
* Redis-based locking to prevent overlapping reconciliation jobs.
* Manual execution paths for critical background operations when asynchronous infrastructure is unavailable.

### Reliability & Data Integrity

* Explicit state-transition rules prevent invalid lifecycle changes.
* Same-state transitions are treated as safe no-ops, helping webhook and reconciliation processes coexist safely.
* Transaction rollback protection for failed billing and payment operations.
* Idempotent processing for asynchronous usage events and webhook deliveries.
* Database-backed safeguards against duplicate processing and inconsistent billing state.

### Testing

* Business-critical functionality tested against a real PostgreSQL test database.
* Comprehensive coverage of billing, state machines, payments, refunds, reconciliation, webhook handling, usage ingestion, and tenant isolation.
* External payment-provider interactions are mocked through the provider abstraction.
* Tests focus on correctness and high-risk business behavior rather than blanket CRUD endpoint coverage.
* The test suite identified and helped fix multiple real defects during development.

### Containerization & Delivery

* Fully containerized application using Docker and Docker Compose.
* Separate API, Celery worker, Celery Beat, PostgreSQL, and Redis services.
* Service health checks and dependency management for reliable startup.
* Automated testing through GitHub Actions.
* Docker images automatically built and published to GitHub Container Registry.
* Separate CI and CD workflows ensure deployment uses tested application artifacts.
* Production configuration uses immutable Docker image tags for reproducible deployments.



## Architecture

The application follows a layered backend architecture designed to keep HTTP concerns, business logic, data access, and background processing clearly separated.

### System Overview

```text
                              ┌───────────────┐
                              │    Clients    │
                              │ Web / API     │
                              └───────┬───────┘
                                      │ HTTP
                                      ▼
                           ┌─────────────────────┐
                           │      FastAPI API    │
                           │                     │
                           │ Routes & Dependencies│
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │      Services       │
                           │  Business Logic     │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │    Repositories     │
                           │     Data Access     │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │    PostgreSQL       │
                           │     Database        │
                           └─────────────────────┘


        ┌─────────────────── Asynchronous Processing ───────────────────┐

 Usage Request                                                        Scheduled Jobs
       │                                                                    │
       ▼                                                                    ▼
┌──────────────┐                                                   ┌──────────────┐
│   FastAPI    │                                                   │ Celery Beat  │
└──────┬───────┘                                                   └──────┬───────┘
       │                                                                    │
       ▼                                                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              Redis                                       │
│                    Message Broker / Task Backend                         │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
                           ┌─────────────────────┐
                           │   Celery Worker     │
                           └──────────┬──────────┘
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                  Usage Processing  Billing   Reconciliation
                                      │
                                      ▼
                                 PostgreSQL


                           ┌─────────────────────┐
                           │       Stripe        │
                           │ Payment Provider    │
                           └──────────┬──────────┘
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                    Webhooks                 Reconciliation
                         │                         │
                         └────────────┬────────────┘
                                      ▼
                                Application State
```

### Application Layers

The synchronous application follows a clear separation of responsibilities:

```text
Routes → Services → Repositories → Database
```

#### Routes

The API layer handles HTTP concerns such as request parsing, authentication dependencies, validation, and response generation.

Routes remain intentionally thin and delegate business decisions to the service layer.

#### Services

Services contain the application's core business logic.

This includes operations such as:

* usage ingestion and billing
* invoice generation
* payment creation and retries
* refund processing
* webhook handling
* payment and refund reconciliation
* lifecycle state transitions

Keeping these rules outside the route layer makes the business logic easier to test independently from HTTP concerns.

#### Repositories

Repositories are responsible for database access and persistence.

They provide a dedicated layer for querying and modifying application data while keeping SQLAlchemy operations separate from business rules.

Tenant ownership checks are also consistently enforced when retrieving resources, helping prevent cross-tenant data access.

#### Database

PostgreSQL is the system's primary persistent datastore.

It stores the application's domain data, including users, projects, clients, pricing rules, usage events, invoices, payments, refunds, and processed webhook events.

Database transactions and constraints provide an additional layer of protection for operations where consistency is critical.

### Asynchronous Processing

Not every operation needs to complete during the HTTP request lifecycle.

Usage events are processed asynchronously to keep ingestion requests lightweight and to separate event acceptance from database processing.

The asynchronous workflow is:

```text
Usage Request
      ↓
FastAPI
      ↓
Celery Task Queued
      ↓
Redis
      ↓
Celery Worker
      ↓
Usage Event Persisted
```

Usage processing includes idempotency protection so duplicate event deliveries do not result in duplicate usage records or billing.

### Scheduled Operations

Celery Beat is responsible for scheduling recurring background operations.

The application currently uses scheduled tasks for:

* generating invoices for projects due for billing
* reconciling payment status with the payment provider
* reconciling refund status with the payment provider

Scheduled tasks are executed by Celery workers rather than inside the API process, keeping long-running background work separate from HTTP request handling.

Redis-based locking is used during reconciliation to prevent overlapping reconciliation jobs from processing the same workload simultaneously.

### Payment Provider Integration

The application integrates with Stripe through a payment provider abstraction.

Payment state can be updated through two complementary mechanisms:

1. **Webhooks**, which provide near-real-time updates from Stripe.
2. **Scheduled reconciliation**, which periodically checks the provider for payment or refund updates that may have been missed.

This provides a more resilient integration model than relying exclusively on webhook delivery.

### Reliability Design

Several design patterns are used throughout the system to protect data consistency:

* **Tenant isolation** prevents users from accessing another tenant's resources.
* **State machines** restrict invoices, payments, and refunds to valid lifecycle transitions.
* **Idempotency** protects asynchronous usage processing and webhook handling from duplicate delivery.
* **Transactions and rollbacks** protect multi-step billing and payment operations.
* **Reconciliation** provides recovery when external events are missed or delayed.
* **Distributed locking** prevents overlapping scheduled reconciliation jobs.

Together, these mechanisms focus on a central goal of the system: ensuring that operations involving money, usage, and tenant-owned data remain correct even when requests are duplicated, external systems fail, or background jobs encounter errors.

For a detailed discussion of architectural decisions, domain workflows, and design trade-offs, see [`docs/architecture.md`](docs/architecture.md).



## Technology Stack

### Backend

* **Python 3.12**
* **FastAPI** for building the REST API
* **Pydantic** and **Pydantic Settings** for data validation and configuration management
* **Uvicorn** as the ASGI server

### Database & Data Access

* **PostgreSQL** as the primary relational database
* **SQLAlchemy** as the ORM and database toolkit
* **Alembic** for database schema migrations

### Background Processing

* **Celery** for asynchronous and scheduled task execution
* **Celery Beat** for recurring scheduled jobs
* **Redis** as the Celery message broker and result backend

### Authentication & Security

* **JWT** authentication using `python-jose`
* **Passlib** and **bcrypt** for password hashing
* API keys for client-level access to project services

### Payments

* **Stripe** for payment processing
* Stripe webhooks for payment and refund status updates
* Provider abstraction layer to isolate payment-provider-specific logic from the core business domain

### Containerization & Infrastructure

* **Docker** for application containerization
* **Docker Compose** for orchestrating the API, workers, scheduler, PostgreSQL, and Redis services
* Docker health checks for service startup coordination

### Testing

* **Pytest** as the primary testing framework
* **pytest-asyncio** for asynchronous test support
* Real PostgreSQL database integration for business-critical tests
* Mocked payment-provider interactions to avoid external network dependencies

### CI/CD

* **GitHub Actions** for continuous integration and deployment workflows
* Automated test execution on pull requests and branch pushes
* **GitHub Container Registry (GHCR)** for publishing Docker images
* Immutable image tags based on Git commit SHAs for reproducible deployments

### Administration

* **SQLAdmin** for database administration and internal model management



## Getting Started

This project can be run locally using Docker and Docker Compose.

The local environment includes:

* FastAPI API
* PostgreSQL
* Redis
* Celery Worker
* Celery Beat

### Prerequisites

Make sure the following tools are installed:

* Git
* Docker
* Docker Compose

### Clone the Repository

```bash
git clone https://github.com/atargaryen54-droid/sass-api.git
cd sass-api
```

### Configure Environment Variables

Sensitive environment files are not committed to the repository.

The project provides example files that can be copied and customized for each environment.

#### Docker Development Environment

Create the Docker environment file:

```bash
cp .env.docker.example .env.docker
```

The Docker environment uses Docker Compose service names for internal communication:

```env
DATABASE_URL=postgresql://saas_user:saas_password@db:5432/saas_db
REDIS_URL=redis://cache:6379/0
```

> `.env.docker` is intentionally excluded from version control.

#### Local Development Environment

For running the application directly on the host machine, use `.env.example` as a starting point:

```bash
cp .env.example .env
```

The local configuration uses `localhost` for PostgreSQL and Redis connections.

### Start the Application

Build and start all services:

```bash
docker compose up --build
```

Or run them in the background:

```bash
docker compose up --build -d
```

This starts the following services:

* PostgreSQL
* Redis
* FastAPI API
* Celery Worker
* Celery Beat

The application services wait for PostgreSQL and Redis health checks before starting.

### Run Database Migrations

Apply the latest database migrations:

```bash
docker compose exec api alembic upgrade head
```

Verify the current migration revision:

```bash
docker compose exec api alembic current
```

### Verify the Application

Check the application's health endpoint:

```bash
curl http://localhost:8000/health
```

A successful response returns:

```json
{
  "status": "ok"
}
```

### API Documentation

FastAPI provides interactive API documentation automatically.

Once the application is running, open:

`http://localhost:8000/docs`

The interactive documentation allows you to explore available endpoints, inspect request and response schemas, and test API requests.

For a higher-level overview of the API and its workflows, see [`docs/api.md`](docs/api.md).



## Configuration

The application uses environment variables for configuration. Sensitive configuration files are excluded from version control.

Example environment files are provided as templates:

* `.env.example` for local development
* `.env.docker.example` for Docker Compose development
* `.env.test.example` for the test environment

### Application Configuration

| Variable                      | Description                                       |
| ----------------------------- | ------------------------------------------------- |
| `DATABASE_URL`                | PostgreSQL connection URL used by the application |
| `SECRET_KEY`                  | Secret used for JWT generation and validation     |
| `ALGORITHM`                   | JWT signing algorithm                             |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes                  |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh token lifetime in days                    |
| `REDIS_URL`                   | Redis connection URL used by Celery               |
| `STRIPE_SECRET_KEY`           | Stripe API secret key                             |
| `STRIPE_WEBHOOK_SECRET`       | Stripe webhook signing secret                     |

### Test Configuration

| Variable            | Description                                      |
| ------------------- | ------------------------------------------------ |
| `TEST_DATABASE_URL` | PostgreSQL connection URL used by the test suite |

> Never commit real secrets, production credentials, or environment-specific configuration files to the repository.



## Testing

The test suite focuses on **business-critical behavior rather than blanket CRUD coverage**.

Testing effort is concentrated on areas where failures could cause financial errors, corrupt application state, or expose one tenant's data to another.

### What Is Covered

The suite includes tests for:

* **Tenant isolation** and cross-user access protection
* **Invoice generation** and usage aggregation
* Invoice, payment, and refund **state machines**
* Payment creation and retry workflows
* Partial and full refund behavior
* Protection against over-refunding
* Payment and refund **reconciliation**
* Batch resilience when individual provider operations fail
* Stripe webhook routing and **idempotency**
* Asynchronous usage ingestion through Celery
* Usage-event idempotency and duplicate protection

Where appropriate, tests call services directly against a real PostgreSQL test database to validate business rules and transactional behavior.

HTTP-level tests are used where the full dependency chain matters, particularly for verifying that tenant ownership checks are correctly enforced from routes through repositories.

External payment-provider calls are mocked, so the test suite does not make real network requests to Stripe.

### Testing Philosophy

The goal is not to achieve coverage for its own sake.

Instead, the suite prioritizes behavior where a regression would be expensive:

* Incorrect billing
* Duplicate charges
* Invalid financial state transitions
* Cross-tenant data access
* Duplicate webhook processing
* Duplicate usage events
* Failed reconciliation batches

This approach keeps the suite focused on the parts of the system where correctness matters most.

### Running the Tests

The default test workflow runs the test suite inside the Docker environment.

#### 1. Configure the Test Environment

Create the test environment file:

```bash
cp .env.test.example .env.test
```

The default Docker configuration uses the PostgreSQL service hostname:

```env
TEST_DATABASE_URL=postgresql://saas_user:saas_password@db:5432/saas_db_test
```

#### 2. Create the Test Database

Start the application services:

```bash
docker compose up -d
```

Create the test database:

```bash
docker compose exec db createdb -U saas_user saas_db_test
```
If the database already exists, this step can be skipped.

#### 3. Run the Tests

Run the test suite inside the API container:

```bash
docker compose exec api pytest
```

#### Running Tests on the Host Machine

If you are running the application and PostgreSQL directly on your host machine rather than through Docker, update the database hostname in `.env.test` from `db` to `localhost`.

For example:

```env
TEST_DATABASE_URL=postgresql://saas_user:saas_password@localhost:5433/saas_db_test
```

Then run:

```bash
pytest
```


### Bugs Found Through Testing

Writing the test suite uncovered and helped fix several real bugs in the application, including:

* A Stripe payment failure handler incorrectly reading values from a dictionary using `getattr()`, causing provider failure messages to be lost.
* A refund calculation that originally didn't consider pending refunds when guarding for refunds not to exceed payment amount.
* A Celery usage-processing task that treated all database integrity errors as duplicate events, potentially hiding legitimate data failures.

These issues were identified through business-logic tests designed to validate realistic workflows and edge cases rather than simply checking whether code executed without errors.

For a detailed breakdown of the testing strategy and individual test suites, see [`docs/testing.md`](docs/testing.md).



## Background Processing

Some operations in VoltMetric are intentionally separated from the request-response cycle to keep API requests fast and to make long-running or retryable work more resilient.

The application uses **Celery** for asynchronous processing and **Celery Beat** for scheduled tasks, with **Redis** acting as the message broker and distributed lock provider.

### Usage Event Processing

Usage events are accepted through the API but are not written directly to the database during the request.

Instead, the ingestion flow is:

```text
Client Request
      │
      ▼
Validate API Key and Event Type
      │
      ▼
Validate Project Ownership and Event Code
      │
      ▼
Queue Celery Task
      │
      ▼
Return Response
      │
      ▼
Celery Worker Processes Event
      │
      ▼
Persist UsageEvent
```

This keeps usage ingestion lightweight and allows event processing to happen independently of the API request lifecycle.

Each event includes an **idempotency key** to protect against duplicate delivery. The worker safely ignores duplicate events while allowing the same idempotency key to be used by different clients where appropriate.

Unexpected processing failures are not silently swallowed. The task rolls back the database transaction and raises the error so Celery can treat the execution as a failed task.

---

### Scheduled Billing

Celery Beat periodically triggers the billing scheduler.

The scheduler identifies projects whose `next_billing_date` has been reached and processes each project independently.

```text
Celery Beat
      │
      ▼
Find Projects Due for Billing
      │
      ▼
Process Each Project Independently
      │
      ├── Generate Invoice
      │
      ├── Aggregate Unbilled Usage
      │
      ├── Create Invoice Items
      │
      └── Advance Billing Date
```

Each project is processed using its own database session. This prevents a failure while billing one project from stopping the rest of the billing batch.

Billing operations are designed to be atomic. If invoice generation fails, the transaction is rolled back so that partially generated invoices and incorrectly advanced billing dates are not persisted.

---

### Payment and Refund Reconciliation

Payment providers can occasionally leave the local application state temporarily out of sync with the provider's state.

A scheduled reconciliation task periodically checks eligible payments and refunds against the configured payment provider.

The reconciliation process:

* Checks only payments and refunds that require reconciliation.
* Retrieves the latest provider status.
* Updates local records when the provider state has changed.
* Records failure information where applicable.
* Continues processing the batch even if an individual provider request fails.

A Redis distributed lock prevents multiple reconciliation workers from processing the same reconciliation cycle simultaneously.

```text
Scheduled Task
      │
      ▼
Acquire Redis Lock
      │
      ├── Lock Unavailable → Skip Cycle
      │
      ▼
Reconcile Payments
      │
      ▼
Reconcile Refunds
      │
      ▼
Release Lock
```

This provides an additional layer of resilience alongside webhook processing. Webhooks handle provider events as they arrive, while reconciliation acts as a safety net for events that may be delayed, missed, or temporarily fail to process.

---

### Worker Architecture

The production environment runs the application as separate services:

```text
                ┌──────────────┐
                │   FastAPI    │
                │     API      │
                └──────┬───────┘
                       │
                       ▼
                  ┌────────┐
                  │ Redis  │
                  └───┬────┘
                      │
              ┌───────▼────────┐
              │ Celery Worker  │
              └───────┬────────┘
                      │
                      ▼
                 ┌─────────┐
                 │PostgreSQL│
                 └─────────┘

              ┌────────────────┐
              │  Celery Beat   │
              └───────┬────────┘
                      │
                      ▼
                Scheduled Tasks
```

Separating the API, worker, and scheduler into independent containers allows each component to operate according to its own responsibility while sharing the same application codebase and infrastructure.



## CI/CD Pipeline

The project uses separate **Continuous Integration (CI)** and **Continuous Deployment (CD)** workflows to validate code changes, produce deployable artifacts, and deploy validated versions of the application.

The pipeline follows a simple principle:

> **CI validates the code and produces the artifact. CD deploys the validated artifact.**

This separation ensures that production deployments use an image that has already passed the test suite rather than rebuilding application code during deployment.

### Continuous Integration

The CI workflow runs automatically for pushes and pull requests involving the `develop` and `main` branches.

The behavior differs depending on how the workflow is triggered:

* **Pull requests** run the test suite to validate proposed changes before merging.
* **Pushes to `develop`** run the test suite and build and publish a Docker image.
* **Pushes to `main`** run the same validation and image build process, producing the artifact used for production deployment.

The CI pipeline performs the following steps:

```text
Code Change
     │
     ▼
Set Up Test Environment
     │
     ▼
Run Test Suite
     │
     ▼
Build Docker Image
     │
     ▼
Publish Image to GitHub Container Registry
```

Tests run against an isolated PostgreSQL service configured specifically for the CI environment. Application configuration and secrets required for testing are supplied through GitHub Actions environment variables rather than relying on local environment files.

The Docker image is only published after the test suite succeeds. This prevents unvalidated application versions from becoming deployment artifacts.

Images are published to the **GitHub Container Registry (GHCR)** and tagged with both:

* `latest`
* The Git commit SHA

The commit SHA tag provides an immutable reference to the exact application version that produced the image, allowing deployments to be traced directly back to a specific source revision.

The CI workflow therefore establishes a clear pipeline:

> **Test the code → Build the artifact → Publish the artifact**

The published image can then be consumed by the deployment workflow without rebuilding the application.

### Container Image Strategy

Docker images are tagged using both `latest` and the Git commit SHA.

The `latest` tag provides a convenient reference to the newest published image, while the commit SHA identifies the exact version of the application built from a specific source revision.

Production deployments use the **commit SHA tag** rather than relying on `latest`. This makes deployments reproducible and provides a direct link between the running application and the source code that produced it.

Using immutable image tags also makes rollback straightforward: a previous deployment can be restored by deploying the corresponding commit SHA.

```text
Source Commit
      │
      ▼
Docker Image
      │
      ├── latest
      │
      └── <commit-sha>  ← Production deployment
```

### Continuous Deployment

The Continuous Deployment workflow deploys the Docker image produced by the CI pipeline rather than rebuilding the application during deployment.

CD runs only after the corresponding CI workflow has completed successfully. This ensures that the deployment process consumes a validated image that has already passed the test suite.

The deployment flow is:

```text id="q8x2vr"
Merge to main
      │
      ▼
Continuous Integration
      │
      ├── Run Tests
      └── Build + Publish Docker Image
                │
                ▼
       Validated Container Artifact
                │
                ▼
      Continuous Deployment
                │
                ▼
     Deploy SHA-Tagged Image
                │
                ▼
       Apply Database Migrations
                │
                ▼
        Verify Application Health
```

The deployment workflow uses the commit SHA associated with the validated build, ensuring that the version being deployed is the exact version produced by CI.

The production stack runs as separate containers for:

* **FastAPI API**
* **Celery worker**
* **Celery Beat scheduler**
* **PostgreSQL**
* **Redis**

The API, worker, and scheduler all use the same published application image while running different commands according to their responsibilities.

### Deployment-Ready Architecture

The application has been prepared to run in a production-style environment using a dedicated Docker Compose configuration and runtime environment variables.

Production configuration is kept separate from the application image. Sensitive values such as database credentials, application secrets, Stripe credentials, and Redis configuration are supplied at runtime rather than being baked into the container image.

The production deployment configuration also includes:

* Persistent Docker volumes for PostgreSQL and Redis data
* Database and Redis health checks
* Service dependency checks before starting application services
* Automatic container restart policies
* Separate API, worker, and scheduler processes
* SHA-based container image versioning
* Database migrations executed as part of the deployment process
* Application health verification after deployment

This follows a **build once, configure at runtime** approach: the same application image can be used across environments while environment-specific configuration is supplied separately.

### Moving to a VPS

The project has not been deployed to a public VPS because its current goal is to serve as a portfolio and production-readiness demonstration rather than a public SaaS product.

However, the current deployment architecture is intentionally designed so that moving to a VPS would require relatively small infrastructure changes rather than changes to the application architecture.

The core application stack and Docker images would remain unchanged. The main changes would include:

* Provisioning a VPS and installing Docker and Docker Compose
* Copying the production Docker Compose configuration to the server
* Providing production environment variables and secrets on the server
* Configuring a reverse proxy such as Nginx or Caddy
* Adding HTTPS certificates
* Connecting a domain name to the server
* Restricting publicly exposed ports so that only the application entry point is externally accessible

The application would continue using the same SHA-tagged container images from GitHub Container Registry, allowing the server to pull and run the exact artifacts produced by CI.

This means the current system is **deployment-ready**, with the remaining work primarily involving hosting infrastructure, networking, and production server configuration.

### Deployment Validation

A successful container startup does not necessarily mean that an application has been deployed successfully.

For example, an API container may start correctly while the application cannot connect to the database, required database tables may not yet exist, or a configuration error may prevent important functionality from working.

For this reason, deployment validation is performed in multiple stages.

```text
Infrastructure Started
        │
        ▼
Database and Redis Healthy
        │
        ▼
Application Services Running
        │
        ▼
Database Migrations Applied
        │
        ▼
API Health Check
        │
        ▼
Deployment Successful
```

The production stack first waits for PostgreSQL and Redis health checks before starting the application services.

Once the infrastructure is available, the deployment process starts the API, Celery worker, and Celery Beat scheduler.

Database migrations are then applied using Alembic to ensure that the database schema matches the version of the application being deployed.

Finally, the deployment verifies the API through its health endpoint.

The deployment is considered successful only when:

* PostgreSQL is healthy and accepting connections
* Redis is healthy and available
* The API container is running
* The Celery worker is running
* The Celery Beat scheduler is running
* Database migrations complete successfully
* The API health endpoint returns a successful response

This layered validation approach helps catch failures that container startup checks alone cannot detect.

In other words, the deployment pipeline verifies more than whether Docker successfully started a process. It verifies that the infrastructure is available, the application services can start against that infrastructure, the database schema is ready, and the API itself is responding successfully.

### Production Configuration

The production Docker image does not contain environment-specific secrets or configuration.

Instead, the application follows a **build once, configure at runtime** approach.

The same container image can be used across different environments, while configuration is supplied separately through environment variables.

Production configuration includes values such as:

* Database connection details
* Application secret key
* JWT configuration
* Redis connection details
* Stripe API credentials
* Stripe webhook secrets

Sensitive configuration is not committed to the repository or baked into the Docker image.

Environment-specific values are supplied separately through the production environment and deployment configuration. This allows the same immutable application artifact to run with different configuration in development, testing, and production environments.

The separation between application artifacts and configuration provides several benefits:

* Secrets can be changed without rebuilding the application image
* The same tested image can be promoted between environments
* Environment-specific infrastructure details remain outside the application code
* Sensitive credentials are not stored in source control
* Deployments remain reproducible because application versions and configuration are managed independently

The production Docker Compose configuration defines the services and infrastructure required to run the application, while runtime environment variables provide the configuration required by those services.

This separation allows the deployment architecture to remain portable. Moving the application from the local production-like environment to a VPS would primarily involve changing the hosting infrastructure and production configuration rather than rebuilding or redesigning the application itself.



## API Documentation

The API is documented at two levels.

**FastAPI provides the interface documentation**, including available endpoints, request schemas, response schemas, and interactive testing.

**Project documentation explains the system**, focusing on the workflows and architectural decisions behind the API.

### Interactive API Documentation

When the application is running, FastAPI provides automatically generated interactive documentation:

* **Swagger UI:** `/docs`
* **ReDoc:** `/redoc`

For example, when running locally:

```text
http://localhost:8000/docs
http://localhost:8000/redoc
```

These interfaces are generated directly from the application's routes and Pydantic schemas, helping ensure that the API reference stays synchronized with the implementation.

### API Capabilities

The API is organized around several core areas:

* **Authentication**
  User authentication using access and refresh tokens.

* **Projects and Clients**
  Management of projects and the clients associated with them.

* **Event Types and Pricing**
  Definition of billable events and their pricing configuration.

* **API Keys and Usage Tracking**
  API-key-based usage ingestion with asynchronous event processing.

* **Billing and Invoicing**
  Aggregation of usage events into invoices based on configured pricing rules and billing periods.

* **Payments and Refunds**
  Payment processing and refund handling through a payment provider abstraction.

* **Webhooks and Reconciliation**
  Provider events and scheduled reconciliation keep local payment and refund state synchronized with external providers.

### Authentication

User-facing resources are protected using JWT-based authentication.

After logging in, the client receives credentials used to access protected endpoints. Access tokens are short-lived, while refresh tokens are used to obtain new access credentials when appropriate.

The system also uses API keys for client usage ingestion, separating user authentication from machine-to-machine usage reporting.

### Further API Documentation

For a deeper explanation of the major API workflows and how the different parts of the system interact, see:

* [`API Guide`](docs/api.md)

The API guide focuses on workflows such as authentication, API-key usage, asynchronous usage ingestion, billing, payments, refunds, webhooks, and reconciliation rather than duplicating the endpoint reference generated automatically by FastAPI.



## Future Improvements

The current implementation focuses on building a reliable foundation for usage-based billing, asynchronous processing, payment workflows, and deployment automation. Several areas have been identified for future development as the platform evolves.

### Billing and Financial Features

Future versions could expand the billing engine with more advanced pricing and financial capabilities, including:

* Subscription and recurring billing
* Annual and custom billing cycles
* Coupons and discounts
* Taxes
* Usage tiers and volume-based pricing
* Minimum charges
* Multi-currency support
* Improved currency handling for currencies with different smallest-unit representations
* Decimal-based money handling throughout the application
* Expanded invoice lifecycle management, including cancellation and voiding workflows

Financial records could also be further strengthened by snapshotting relevant billing information on invoice items, ensuring historical invoices remain unchanged even when event definitions or pricing configuration change later.

### Payment Provider Expansion

The payment layer is designed around a provider abstraction, allowing future versions to support additional payment providers and payment methods.

Potential improvements include:

* Integration with additional providers such as Payoneer/Chapa
* Support for multiple payment providers
* Project-level payment provider configuration
* Saved payment methods
* Automatic payment methods
* Improved handling of abandoned or expired payment attempts

A future provider configuration model could allow projects to manage their own enabled payment providers and provider-specific credentials.

### Platform and Multi-Tenancy

The platform could evolve from the current user-owned resource model into a broader organizational platform.

Possible improvements include:

* Organizations and companies
* Teams
* Roles and permissions
* Separation of user, personnel, and company concepts
* Customer-facing management portals
* Expanded account and profile management
* Multi-device session management

These improvements would provide a foundation for more complex business structures and collaborative use of the platform.

### API Key and Security Management

API keys already support the core usage ingestion workflow, but their lifecycle management can be expanded further.

Future improvements include:

* API key versioning
* Advanced key rotation strategies
* `last_used_at` tracking
* Revocation reasons
* Tracking who revoked a key
* Improved visibility into key lifecycle and usage
* More centralized ownership and authorization checks

Additional session and authentication improvements could also include stronger multi-device login management and account security workflows.

### Analytics and Reporting

Because the platform already collects usage, billing, payment, and client data, future versions could build analytical capabilities on top of the existing system.

Potential features include:

* Revenue analytics
* Usage trends
* Client-level analytics
* Forecasting
* Advanced financial reporting

These capabilities could eventually provide users with greater visibility into how their services are being consumed and monetized.

### Developer Experience and Platform Evolution

Future development could also focus on making the platform easier to integrate with and extend.

Potential improvements include:

* API versioning
* Client SDKs
* Expanded filtering and querying capabilities
* Additional management endpoints
* Improved developer tooling and integration workflows

The goal of these improvements is not simply to add features, but to evolve the platform while preserving the separation of responsibilities and architectural boundaries established in the current implementation.



## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

