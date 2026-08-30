# Deployment Guide

This document describes how the SaaS API is containerized, tested, packaged, and deployed using Docker, Docker Compose, GitHub Actions, and GitHub Container Registry.

The project is designed so that the same application image can run in development, testing, and production-style environments, with environment-specific configuration supplied externally.

---

## 1. Deployment Overview

The deployment pipeline consists of four major stages:

```text
Developer Push
      │
      ▼
GitHub Actions CI
      │
      ├── Run Test Suite
      │
      └── Build Docker Image
              │
              ▼
      GitHub Container Registry
              │
              ▼
GitHub Actions CD
              │
              ├── Pull Image
              ├── Start Services
              ├── Run Database Migrations
              └── Perform Health Check
```

The application itself consists of several services:

* FastAPI API
* PostgreSQL database
* Redis
* Celery worker
* Celery Beat scheduler

Docker Compose orchestrates these services.

---

# 2. Docker Architecture

The application uses a single Docker image for the API, Celery worker, and Celery Beat scheduler.

This is intentional.

All three services share the same application code and Python dependencies, but start with different commands.

```text
                    ┌─────────────────┐
                    │   Docker Image  │
                    │                 │
                    │   SaaS API App  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
         FastAPI API    Celery Worker   Celery Beat
```

The same image is therefore used with different startup commands.

### API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Celery Worker

```bash
celery -A app.core.celery_app worker --loglevel=info
```

### Celery Beat

```bash
celery -A app.core.celery_app beat --loglevel=info
```

This avoids maintaining separate Docker images for services that share the same codebase.

---

# 3. Docker Image

The application Docker image is built from the project `Dockerfile`.

The image performs the following steps:

1. Starts from Python 3.12 Slim.
2. Sets `/app` as the working directory.
3. Copies the dependency file.
4. Installs Python dependencies.
5. Copies the application source code.
6. Exposes port `8000`.
7. Starts the FastAPI application by default.

The API image can also be reused by the Celery worker and scheduler by overriding the default command through Docker Compose.

---

# 4. Development Environment

The development environment is managed using Docker Compose.

The development stack includes:

* PostgreSQL
* Redis
* FastAPI API
* Celery worker
* Celery Beat

The application services wait for PostgreSQL and Redis health checks before starting.

This prevents application services from attempting to connect before their dependencies are ready.

Example startup:

```bash
docker compose up -d
```

Check running services:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Stop the environment:

```bash
docker compose down
```

---

# 5. Production-Style Environment

The project also includes a production-oriented Docker Compose configuration.

The production configuration differs from development in an important way:

**the application image is pulled from GitHub Container Registry instead of being built locally.**

This simulates a real deployment workflow.

The deployment environment contains:

```text
FastAPI API
     │
     ├──────────────► PostgreSQL
     │
     ├──────────────► Redis
     │
     ├──────────────► Celery Worker
     │
     └──────────────► Celery Beat
```

Each service runs in the same Docker network and communicates using Docker service names.

For example:

```text
DATABASE_URL=postgresql://user:password@db:5432/database
```

The hostname is `db`, not `localhost`.

Inside Docker, `localhost` refers to the current container itself. Docker service names provide internal service discovery.

---

# 6. Environment Configuration

Sensitive configuration is not stored in the Docker image.

Instead, configuration is supplied through environment variables.

Examples include:

```text
DATABASE_URL
SECRET_KEY
ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS
REDIS_URL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

Production configuration is stored in an environment file that is excluded from version control.

For example:

```text
.env.production
```

This prevents secrets such as database passwords, JWT secrets, and Stripe credentials from being committed to the repository.

The Docker image therefore remains reusable across environments.

The same image can run with different:

* database connections
* Redis connections
* authentication secrets
* payment provider credentials
* deployment settings

This separation between application artifacts and environment configuration is a core deployment principle.

---

# 7. Persistent Data

PostgreSQL and Redis use Docker volumes.

```text
postgres_data
redis_data
```

Volumes allow data to survive container recreation.

For example, removing and recreating the PostgreSQL container does not automatically remove the database stored in its volume.

Different Docker Compose project names create separate resource namespaces.

For example:

```bash
docker compose -p saas-prod
```

creates resources with names similar to:

```text
saas-prod_postgres_data
saas-prod_redis_data
saas-prod_default
```

This allows development and production-style environments to coexist on the same Docker host without sharing containers or volumes.

---

# 8. Database Migrations

Database schema changes are managed with Alembic.

After the application services are running, migrations can be applied inside the API container.

Example:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic upgrade head
```

The current migration state can be checked using:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic current
```

Available migration heads can be checked with:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic heads
```

A successful deployment should have the current migration revision matching the latest head.

---

# 9. Health Checks

The deployment uses health checks at multiple layers.

## PostgreSQL

PostgreSQL uses `pg_isready`.

The API, worker, and scheduler wait for the database to become healthy before starting.

## Redis

Redis uses:

```bash
redis-cli ping
```

The application services wait until Redis is healthy.

## API

The application exposes a health endpoint:

```text
/health
```

A successful response confirms that the FastAPI service is running and responding to requests.

Health checks are also used by the deployment workflow to verify that the application successfully started.

These checks serve different purposes.

Docker health checks verify that dependencies are ready.

The deployment health check verifies that the deployed application is actually responding.

Both are useful. One checks the foundation; the other checks whether the house is still standing. 🏠

---

# 10. Continuous Integration

Continuous Integration is handled through GitHub Actions.

The CI workflow runs when changes are pushed to:

```text
develop
main
```

and when pull requests target those branches.

The workflow performs the following steps:

1. Checks out the repository.
2. Sets up Python.
3. Installs dependencies.
4. Starts a PostgreSQL test service.
5. Runs the test suite.
6. Builds the Docker image.
7. Pushes the image to GitHub Container Registry when appropriate.

Pull requests run validation without publishing a production artifact.

Pushes to the configured branches can produce container images.

This separates code validation from artifact publication.

---

# 11. Test Environment in CI

The CI workflow creates an isolated PostgreSQL database for testing.

The test environment provides configuration such as:

```text
DATABASE_URL
TEST_DATABASE_URL
SECRET_KEY
ALGORITHM
REDIS_URL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

No real Stripe credentials are required.

The payment provider is mocked during testing, so the test suite does not make network calls to Stripe.

The test database is isolated from development and production-style environments.

This allows the full business-logic test suite to run safely during every CI validation cycle.

See [Testing](testing.md) for details about the testing strategy.

---

# 12. Container Image Publishing

Docker images are published to GitHub Container Registry.

Images are tagged using:

```text
latest
```

and the Git commit SHA:

```text
<commit-sha>
```

For example:

```text
ghcr.io/<repository>:latest
```

and:

```text
ghcr.io/<repository>:<commit-sha>
```

The SHA tag is particularly important for deployment.

It identifies an exact immutable version of the application.

Instead of deploying an ambiguous image such as:

```text
latest
```

the deployment can reference a specific build:

```text
IMAGE_TAG=<commit-sha>
```

The API, Celery worker, and Celery Beat scheduler all use the same image tag.

This guarantees that every application process runs the same version of the code.

---

# 13. Continuous Deployment

Continuous Deployment is handled separately from CI.

The deployment workflow runs only after the appropriate build pipeline succeeds.

The deployment process performs the following steps:

1. Uses the Docker image produced by CI.
2. Pulls the exact image version.
3. Starts the production-style Docker Compose stack.
4. Waits for dependent services.
5. Runs Alembic migrations.
6. Verifies the application health endpoint.

Conceptually:

```text
Successful CI
      │
      ▼
Published Container Image
      │
      ▼
CD Workflow
      │
      ▼
Pull Exact Image
      │
      ▼
Start Application Stack
      │
      ▼
Run Migrations
      │
      ▼
Health Check
      │
      ▼
Deployment Successful
```

The deployment workflow does not rebuild the application.

This is important.

The artifact tested and built by CI is the artifact deployed by CD.

That avoids the classic problem of:

> "The code passed CI, but production received a slightly different build."

CI builds it once.

CD deploys that exact build.

---

# 14. Image Tagging and Deployment Versions

The deployment uses an image tag supplied through the deployment environment.

For example:

```text
IMAGE_TAG=<commit-sha>
```

Docker Compose then references the image:

```yaml
image: ghcr.io/<repository>:${IMAGE_TAG}
```

This makes deployments reproducible.

A specific deployment can always be traced back to a specific Git commit.

For example:

```text
Git Commit
     │
     ▼
Docker Image SHA Tag
     │
     ▼
Deployment
```

This also makes rollback straightforward.

A previous working image tag can be deployed again if a newer release fails.

---

# 15. Deployment Success Criteria

A deployment is considered successful only after the following conditions are satisfied:

### Infrastructure

* PostgreSQL is running and healthy.
* Redis is running and healthy.

### Application Services

* FastAPI API container is running.
* Celery worker is running.
* Celery Beat is running.

### Database

* Alembic migrations successfully complete.
* The database revision matches the latest migration head.

### Application Health

The API health endpoint responds successfully.

For example:

```bash
curl http://localhost:8000/health
```

A successful response confirms that the deployed API is reachable.

---

# 16. Branch and Release Strategy

The project separates development work from production deployment.

A typical workflow is:

```text
Feature Branch
      │
      ▼
    develop
      │
      ▼
     main
      │
      ▼
 Production Deployment
```

### Feature Branches

Individual features or fixes can be developed independently.

### Develop

The `develop` branch acts as an integration branch where ongoing development work is combined and validated.

### Main

The `main` branch represents the release-ready version of the application.

Production deployment is tied to the release process rather than every pull request.

Pull requests validate code through CI, but they do not directly deploy the application.

This prevents an unmerged branch or review request from accidentally becoming production.

---

# 17. Running the Production-Style Stack

The production-style environment can be started using:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  up -d
```

Check service status:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  ps
```

View logs:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  logs -f
```

Stop the environment:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  down
```

Persistent volumes remain unless explicitly removed.

---

# 18. Future VPS Deployment

The current deployment architecture is intentionally designed so it can be moved to a VPS with relatively small changes.

The application services would remain largely the same:

* FastAPI
* PostgreSQL
* Redis
* Celery worker
* Celery Beat
* Docker Compose

The primary differences would be infrastructure-related:

```text
Local Machine
      │
      ▼
Docker Compose

        ↓ later

VPS
      │
      ▼
Docker Compose
      │
      ├── Reverse Proxy
      ├── Domain
      └── HTTPS Certificate
```

A future VPS deployment would typically add:

* a public server
* a domain name
* a reverse proxy such as Nginx or Caddy
* HTTPS certificates
* firewall configuration
* production backup strategy
* stronger secret management

The application container architecture and CI/CD artifact flow would remain applicable.

The main change is where the containers run, not how the application itself is packaged.

---

# 19. Current Scope

This project is intentionally built as a production-style portfolio system rather than a publicly operated commercial service.

The goal is to demonstrate practical software engineering skills across the full application lifecycle:

* backend architecture
* authentication and authorization
* multi-tenant isolation
* asynchronous processing
* billing logic
* payment integration
* webhook handling
* reconciliation
* idempotency
* testing
* Docker containerization
* database migrations
* CI/CD
* container image publishing
* production-style deployment

The system is therefore designed to demonstrate the engineering practices involved in deploying and operating a backend service without requiring the ongoing cost of maintaining public infrastructure.

---

# 20. Deployment Philosophy

The deployment setup follows one central principle:

> **Build once, test the important behavior, publish an immutable artifact, and deploy that exact artifact.**

The application is configured externally.

The container image is reusable.

Database schema changes are versioned.

Services wait for their dependencies.

Deployments are validated with health checks.

The result is a workflow that can run locally today and evolve into a VPS or cloud deployment later without requiring the application architecture to be rebuilt from scratch.
# Deployment Guide

This document describes how the SaaS API is containerized, tested, packaged, and deployed using Docker, Docker Compose, GitHub Actions, and GitHub Container Registry.

The project is designed so that the same application image can run in development, testing, and production-style environments, with environment-specific configuration supplied externally.

---

## 1. Deployment Overview

The deployment pipeline consists of four major stages:

```text
Developer Push
      │
      ▼
GitHub Actions CI
      │
      ├── Run Test Suite
      │
      └── Build Docker Image
              │
              ▼
      GitHub Container Registry
              │
              ▼
GitHub Actions CD
              │
              ├── Pull Image
              ├── Start Services
              ├── Run Database Migrations
              └── Perform Health Check
```

The application itself consists of several services:

* FastAPI API
* PostgreSQL database
* Redis
* Celery worker
* Celery Beat scheduler

Docker Compose orchestrates these services.

---

# 2. Docker Architecture

The application uses a single Docker image for the API, Celery worker, and Celery Beat scheduler.

This is intentional.

All three services share the same application code and Python dependencies, but start with different commands.

```text
                    ┌─────────────────┐
                    │   Docker Image  │
                    │                 │
                    │   SaaS API App  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
         FastAPI API    Celery Worker   Celery Beat
```

The same image is therefore used with different startup commands.

### API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Celery Worker

```bash
celery -A app.core.celery_app worker --loglevel=info
```

### Celery Beat

```bash
celery -A app.core.celery_app beat --loglevel=info
```

This avoids maintaining separate Docker images for services that share the same codebase.

---

# 3. Docker Image

The application Docker image is built from the project `Dockerfile`.

The image performs the following steps:

1. Starts from Python 3.12 Slim.
2. Sets `/app` as the working directory.
3. Copies the dependency file.
4. Installs Python dependencies.
5. Copies the application source code.
6. Exposes port `8000`.
7. Starts the FastAPI application by default.

The API image can also be reused by the Celery worker and scheduler by overriding the default command through Docker Compose.

---

# 4. Development Environment

The development environment is managed using Docker Compose.

The development stack includes:

* PostgreSQL
* Redis
* FastAPI API
* Celery worker
* Celery Beat

The application services wait for PostgreSQL and Redis health checks before starting.

This prevents application services from attempting to connect before their dependencies are ready.

Example startup:

```bash
docker compose up -d
```

Check running services:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Stop the environment:

```bash
docker compose down
```

---

# 5. Production-Style Environment

The project also includes a production-oriented Docker Compose configuration.

The production configuration differs from development in an important way:

**the application image is pulled from GitHub Container Registry instead of being built locally.**

This simulates a real deployment workflow.

The deployment environment contains:

```text
FastAPI API
     │
     ├──────────────► PostgreSQL
     │
     ├──────────────► Redis
     │
     ├──────────────► Celery Worker
     │
     └──────────────► Celery Beat
```

Each service runs in the same Docker network and communicates using Docker service names.

For example:

```text
DATABASE_URL=postgresql://user:password@db:5432/database
```

The hostname is `db`, not `localhost`.

Inside Docker, `localhost` refers to the current container itself. Docker service names provide internal service discovery.

---

# 6. Environment Configuration

Sensitive configuration is not stored in the Docker image.

Instead, configuration is supplied through environment variables.

Examples include:

```text
DATABASE_URL
SECRET_KEY
ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS
REDIS_URL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

Production configuration is stored in an environment file that is excluded from version control.

For example:

```text
.env.production
```

This prevents secrets such as database passwords, JWT secrets, and Stripe credentials from being committed to the repository.

The Docker image therefore remains reusable across environments.

The same image can run with different:

* database connections
* Redis connections
* authentication secrets
* payment provider credentials
* deployment settings

This separation between application artifacts and environment configuration is a core deployment principle.

---

# 7. Persistent Data

PostgreSQL and Redis use Docker volumes.

```text
postgres_data
redis_data
```

Volumes allow data to survive container recreation.

For example, removing and recreating the PostgreSQL container does not automatically remove the database stored in its volume.

Different Docker Compose project names create separate resource namespaces.

For example:

```bash
docker compose -p saas-prod
```

creates resources with names similar to:

```text
saas-prod_postgres_data
saas-prod_redis_data
saas-prod_default
```

This allows development and production-style environments to coexist on the same Docker host without sharing containers or volumes.

---

# 8. Database Migrations

Database schema changes are managed with Alembic.

After the application services are running, migrations can be applied inside the API container.

Example:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic upgrade head
```

The current migration state can be checked using:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic current
```

Available migration heads can be checked with:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic heads
```

A successful deployment should have the current migration revision matching the latest head.

---

# 9. Health Checks

The deployment uses health checks at multiple layers.

## PostgreSQL

PostgreSQL uses `pg_isready`.

The API, worker, and scheduler wait for the database to become healthy before starting.

## Redis

Redis uses:

```bash
redis-cli ping
```

The application services wait until Redis is healthy.

## API

The application exposes a health endpoint:

```text
/health
```

A successful response confirms that the FastAPI service is running and responding to requests.

Health checks are also used by the deployment workflow to verify that the application successfully started.

These checks serve different purposes.

Docker health checks verify that dependencies are ready.

The deployment health check verifies that the deployed application is actually responding.

Both are useful. One checks the foundation; the other checks whether the house is still standing. 🏠

---

# 10. Continuous Integration

Continuous Integration is handled through GitHub Actions.

The CI workflow runs when changes are pushed to:

```text
develop
main
```

and when pull requests target those branches.

The workflow performs the following steps:

1. Checks out the repository.
2. Sets up Python.
3. Installs dependencies.
4. Starts a PostgreSQL test service.
5. Runs the test suite.
6. Builds the Docker image.
7. Pushes the image to GitHub Container Registry when appropriate.

Pull requests run validation without publishing a production artifact.

Pushes to the configured branches can produce container images.

This separates code validation from artifact publication.

---

# 11. Test Environment in CI

The CI workflow creates an isolated PostgreSQL database for testing.

The test environment provides configuration such as:

```text
DATABASE_URL
TEST_DATABASE_URL
SECRET_KEY
ALGORITHM
REDIS_URL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

No real Stripe credentials are required.

The payment provider is mocked during testing, so the test suite does not make network calls to Stripe.

The test database is isolated from development and production-style environments.

This allows the full business-logic test suite to run safely during every CI validation cycle.

See [Testing](testing.md) for details about the testing strategy.

---

# 12. Container Image Publishing

Docker images are published to GitHub Container Registry.

Images are tagged using:

```text
latest
```

and the Git commit SHA:

```text
<commit-sha>
```

For example:

```text
ghcr.io/<repository>:latest
```

and:

```text
ghcr.io/<repository>:<commit-sha>
```

The SHA tag is particularly important for deployment.

It identifies an exact immutable version of the application.

Instead of deploying an ambiguous image such as:

```text
latest
```

the deployment can reference a specific build:

```text
IMAGE_TAG=<commit-sha>
```

The API, Celery worker, and Celery Beat scheduler all use the same image tag.

This guarantees that every application process runs the same version of the code.

---

# 13. Continuous Deployment

Continuous Deployment is handled separately from CI.

The deployment workflow runs only after the appropriate build pipeline succeeds.

The deployment process performs the following steps:

1. Uses the Docker image produced by CI.
2. Pulls the exact image version.
3. Starts the production-style Docker Compose stack.
4. Waits for dependent services.
5. Runs Alembic migrations.
6. Verifies the application health endpoint.

Conceptually:

```text
Successful CI
      │
      ▼
Published Container Image
      │
      ▼
CD Workflow
      │
      ▼
Pull Exact Image
      │
      ▼
Start Application Stack
      │
      ▼
Run Migrations
      │
      ▼
Health Check
      │
      ▼
Deployment Successful
```

The deployment workflow does not rebuild the application.

This is important.

The artifact tested and built by CI is the artifact deployed by CD.

That avoids the classic problem of:

> "The code passed CI, but production received a slightly different build."

CI builds it once.

CD deploys that exact build.

---

# 14. Image Tagging and Deployment Versions

The deployment uses an image tag supplied through the deployment environment.

For example:

```text
IMAGE_TAG=<commit-sha>
```

Docker Compose then references the image:

```yaml
image: ghcr.io/<repository>:${IMAGE_TAG}
```

This makes deployments reproducible.

A specific deployment can always be traced back to a specific Git commit.

For example:

```text
Git Commit
     │
     ▼
Docker Image SHA Tag
     │
     ▼
Deployment
```

This also makes rollback straightforward.

A previous working image tag can be deployed again if a newer release fails.

---

# 15. Deployment Success Criteria

A deployment is considered successful only after the following conditions are satisfied:

### Infrastructure

* PostgreSQL is running and healthy.
* Redis is running and healthy.

### Application Services

* FastAPI API container is running.
* Celery worker is running.
* Celery Beat is running.

### Database

* Alembic migrations successfully complete.
* The database revision matches the latest migration head.

### Application Health

The API health endpoint responds successfully.

For example:

```bash
curl http://localhost:8000/health
```

A successful response confirms that the deployed API is reachable.

---

# 16. Branch and Release Strategy

The project separates development work from production deployment.

A typical workflow is:

```text
Feature Branch
      │
      ▼
    develop
      │
      ▼
     main
      │
      ▼
 Production Deployment
```

### Feature Branches

Individual features or fixes can be developed independently.

### Develop

The `develop` branch acts as an integration branch where ongoing development work is combined and validated.

### Main

The `main` branch represents the release-ready version of the application.

Production deployment is tied to the release process rather than every pull request.

Pull requests validate code through CI, but they do not directly deploy the application.

This prevents an unmerged branch or review request from accidentally becoming production.

---

# 17. Running the Production-Style Stack

The production-style environment can be started using:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  up -d
```

Check service status:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  ps
```

View logs:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  logs -f
```

Stop the environment:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  down
```

Persistent volumes remain unless explicitly removed.

---

# 18. Future VPS Deployment

The current deployment architecture is intentionally designed so it can be moved to a VPS with relatively small changes.

The application services would remain largely the same:

* FastAPI
* PostgreSQL
* Redis
* Celery worker
* Celery Beat
* Docker Compose

The primary differences would be infrastructure-related:

```text
Local Machine
      │
      ▼
Docker Compose

        ↓ later

VPS
      │
      ▼
Docker Compose
      │
      ├── Reverse Proxy
      ├── Domain
      └── HTTPS Certificate
```

A future VPS deployment would typically add:

* a public server
* a domain name
* a reverse proxy such as Nginx or Caddy
* HTTPS certificates
* firewall configuration
* production backup strategy
* stronger secret management

The application container architecture and CI/CD artifact flow would remain applicable.

The main change is where the containers run, not how the application itself is packaged.

---

# 19. Current Scope

This project is intentionally built as a production-style portfolio system rather than a publicly operated commercial service.

The goal is to demonstrate practical software engineering skills across the full application lifecycle:

* backend architecture
* authentication and authorization
* multi-tenant isolation
* asynchronous processing
* billing logic
* payment integration
* webhook handling
* reconciliation
* idempotency
* testing
* Docker containerization
* database migrations
* CI/CD
* container image publishing
* production-style deployment

The system is therefore designed to demonstrate the engineering practices involved in deploying and operating a backend service without requiring the ongoing cost of maintaining public infrastructure.

---

# 20. Deployment Philosophy

The deployment setup follows one central principle:

> **Build once, test the important behavior, publish an immutable artifact, and deploy that exact artifact.**

The application is configured externally.

The container image is reusable.

Database schema changes are versioned.

Services wait for their dependencies.

Deployments are validated with health checks.

The result is a workflow that can run locally today and evolve into a VPS or cloud deployment later without requiring the application architecture to be rebuilt from scratch.
# Deployment Guide

This document describes how the SaaS API is containerized, tested, packaged, and deployed using Docker, Docker Compose, GitHub Actions, and GitHub Container Registry.

The project is designed so that the same application image can run in development, testing, and production-style environments, with environment-specific configuration supplied externally.

---

## 1. Deployment Overview

The deployment pipeline consists of four major stages:

```text
Developer Push
      │
      ▼
GitHub Actions CI
      │
      ├── Run Test Suite
      │
      └── Build Docker Image
              │
              ▼
      GitHub Container Registry
              │
              ▼
GitHub Actions CD
              │
              ├── Pull Image
              ├── Start Services
              ├── Run Database Migrations
              └── Perform Health Check
```

The application itself consists of several services:

* FastAPI API
* PostgreSQL database
* Redis
* Celery worker
* Celery Beat scheduler

Docker Compose orchestrates these services.

---

# 2. Docker Architecture

The application uses a single Docker image for the API, Celery worker, and Celery Beat scheduler.

This is intentional.

All three services share the same application code and Python dependencies, but start with different commands.

```text
                    ┌─────────────────┐
                    │   Docker Image  │
                    │                 │
                    │   SaaS API App  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
         FastAPI API    Celery Worker   Celery Beat
```

The same image is therefore used with different startup commands.

### API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Celery Worker

```bash
celery -A app.core.celery_app worker --loglevel=info
```

### Celery Beat

```bash
celery -A app.core.celery_app beat --loglevel=info
```

This avoids maintaining separate Docker images for services that share the same codebase.

---

# 3. Docker Image

The application Docker image is built from the project `Dockerfile`.

The image performs the following steps:

1. Starts from Python 3.12 Slim.
2. Sets `/app` as the working directory.
3. Copies the dependency file.
4. Installs Python dependencies.
5. Copies the application source code.
6. Exposes port `8000`.
7. Starts the FastAPI application by default.

The API image can also be reused by the Celery worker and scheduler by overriding the default command through Docker Compose.

---

# 4. Development Environment

The development environment is managed using Docker Compose.

The development stack includes:

* PostgreSQL
* Redis
* FastAPI API
* Celery worker
* Celery Beat

The application services wait for PostgreSQL and Redis health checks before starting.

This prevents application services from attempting to connect before their dependencies are ready.

Example startup:

```bash
docker compose up -d
```

Check running services:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Stop the environment:

```bash
docker compose down
```

---

# 5. Production-Style Environment

The project also includes a production-oriented Docker Compose configuration.

The production configuration differs from development in an important way:

**the application image is pulled from GitHub Container Registry instead of being built locally.**

This simulates a real deployment workflow.

The deployment environment contains:

```text
FastAPI API
     │
     ├──────────────► PostgreSQL
     │
     ├──────────────► Redis
     │
     ├──────────────► Celery Worker
     │
     └──────────────► Celery Beat
```

Each service runs in the same Docker network and communicates using Docker service names.

For example:

```text
DATABASE_URL=postgresql://user:password@db:5432/database
```

The hostname is `db`, not `localhost`.

Inside Docker, `localhost` refers to the current container itself. Docker service names provide internal service discovery.

---

# 6. Environment Configuration

Sensitive configuration is not stored in the Docker image.

Instead, configuration is supplied through environment variables.

Examples include:

```text
DATABASE_URL
SECRET_KEY
ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS
REDIS_URL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

Production configuration is stored in an environment file that is excluded from version control.

For example:

```text
.env.production
```

This prevents secrets such as database passwords, JWT secrets, and Stripe credentials from being committed to the repository.

The Docker image therefore remains reusable across environments.

The same image can run with different:

* database connections
* Redis connections
* authentication secrets
* payment provider credentials
* deployment settings

This separation between application artifacts and environment configuration is a core deployment principle.

---

# 7. Persistent Data

PostgreSQL and Redis use Docker volumes.

```text
postgres_data
redis_data
```

Volumes allow data to survive container recreation.

For example, removing and recreating the PostgreSQL container does not automatically remove the database stored in its volume.

Different Docker Compose project names create separate resource namespaces.

For example:

```bash
docker compose -p saas-prod
```

creates resources with names similar to:

```text
saas-prod_postgres_data
saas-prod_redis_data
saas-prod_default
```

This allows development and production-style environments to coexist on the same Docker host without sharing containers or volumes.

---

# 8. Database Migrations

Database schema changes are managed with Alembic.

After the application services are running, migrations can be applied inside the API container.

Example:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic upgrade head
```

The current migration state can be checked using:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic current
```

Available migration heads can be checked with:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  exec api alembic heads
```

A successful deployment should have the current migration revision matching the latest head.

---

# 9. Health Checks

The deployment uses health checks at multiple layers.

## PostgreSQL

PostgreSQL uses `pg_isready`.

The API, worker, and scheduler wait for the database to become healthy before starting.

## Redis

Redis uses:

```bash
redis-cli ping
```

The application services wait until Redis is healthy.

## API

The application exposes a health endpoint:

```text
/health
```

A successful response confirms that the FastAPI service is running and responding to requests.

Health checks are also used by the deployment workflow to verify that the application successfully started.

These checks serve different purposes.

Docker health checks verify that dependencies are ready.

The deployment health check verifies that the deployed application is actually responding.

Both are useful. One checks the foundation; the other checks whether the house is still standing. 🏠

---

# 10. Continuous Integration

Continuous Integration is handled through GitHub Actions.

The CI workflow runs when changes are pushed to:

```text
develop
main
```

and when pull requests target those branches.

The workflow performs the following steps:

1. Checks out the repository.
2. Sets up Python.
3. Installs dependencies.
4. Starts a PostgreSQL test service.
5. Runs the test suite.
6. Builds the Docker image.
7. Pushes the image to GitHub Container Registry when appropriate.

Pull requests run validation without publishing a production artifact.

Pushes to the configured branches can produce container images.

This separates code validation from artifact publication.

---

# 11. Test Environment in CI

The CI workflow creates an isolated PostgreSQL database for testing.

The test environment provides configuration such as:

```text
DATABASE_URL
TEST_DATABASE_URL
SECRET_KEY
ALGORITHM
REDIS_URL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

No real Stripe credentials are required.

The payment provider is mocked during testing, so the test suite does not make network calls to Stripe.

The test database is isolated from development and production-style environments.

This allows the full business-logic test suite to run safely during every CI validation cycle.

See [Testing](testing.md) for details about the testing strategy.

---

# 12. Container Image Publishing

Docker images are published to GitHub Container Registry.

Images are tagged using:

```text
latest
```

and the Git commit SHA:

```text
<commit-sha>
```

For example:

```text
ghcr.io/<repository>:latest
```

and:

```text
ghcr.io/<repository>:<commit-sha>
```

The SHA tag is particularly important for deployment.

It identifies an exact immutable version of the application.

Instead of deploying an ambiguous image such as:

```text
latest
```

the deployment can reference a specific build:

```text
IMAGE_TAG=<commit-sha>
```

The API, Celery worker, and Celery Beat scheduler all use the same image tag.

This guarantees that every application process runs the same version of the code.

---

# 13. Continuous Deployment

Continuous Deployment is handled separately from CI.

The deployment workflow runs only after the appropriate build pipeline succeeds.

The deployment process performs the following steps:

1. Uses the Docker image produced by CI.
2. Pulls the exact image version.
3. Starts the production-style Docker Compose stack.
4. Waits for dependent services.
5. Runs Alembic migrations.
6. Verifies the application health endpoint.

Conceptually:

```text
Successful CI
      │
      ▼
Published Container Image
      │
      ▼
CD Workflow
      │
      ▼
Pull Exact Image
      │
      ▼
Start Application Stack
      │
      ▼
Run Migrations
      │
      ▼
Health Check
      │
      ▼
Deployment Successful
```

The deployment workflow does not rebuild the application.

This is important.

The artifact tested and built by CI is the artifact deployed by CD.

That avoids the classic problem of:

> "The code passed CI, but production received a slightly different build."

CI builds it once.

CD deploys that exact build.

---

# 14. Image Tagging and Deployment Versions

The deployment uses an image tag supplied through the deployment environment.

For example:

```text
IMAGE_TAG=<commit-sha>
```

Docker Compose then references the image:

```yaml
image: ghcr.io/<repository>:${IMAGE_TAG}
```

This makes deployments reproducible.

A specific deployment can always be traced back to a specific Git commit.

For example:

```text
Git Commit
     │
     ▼
Docker Image SHA Tag
     │
     ▼
Deployment
```

This also makes rollback straightforward.

A previous working image tag can be deployed again if a newer release fails.

---

# 15. Deployment Success Criteria

A deployment is considered successful only after the following conditions are satisfied:

### Infrastructure

* PostgreSQL is running and healthy.
* Redis is running and healthy.

### Application Services

* FastAPI API container is running.
* Celery worker is running.
* Celery Beat is running.

### Database

* Alembic migrations successfully complete.
* The database revision matches the latest migration head.

### Application Health

The API health endpoint responds successfully.

For example:

```bash
curl http://localhost:8000/health
```

A successful response confirms that the deployed API is reachable.

---

# 16. Branch and Release Strategy

The project separates development work from production deployment.

A typical workflow is:

```text
Feature Branch
      │
      ▼
    develop
      │
      ▼
     main
      │
      ▼
 Production Deployment
```

### Feature Branches

Individual features or fixes can be developed independently.

### Develop

The `develop` branch acts as an integration branch where ongoing development work is combined and validated.

### Main

The `main` branch represents the release-ready version of the application.

Production deployment is tied to the release process rather than every pull request.

Pull requests validate code through CI, but they do not directly deploy the application.

This prevents an unmerged branch or review request from accidentally becoming production.

---

# 17. Running the Production-Style Stack

The production-style environment can be started using:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  up -d
```

Check service status:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  ps
```

View logs:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  logs -f
```

Stop the environment:

```bash
docker compose \
  -p saas-prod \
  --env-file .env.production \
  -f docker-compose.prod.yml \
  down
```

Persistent volumes remain unless explicitly removed.

---

# 18. Future VPS Deployment

The current deployment architecture is intentionally designed so it can be moved to a VPS with relatively small changes.

The application services would remain largely the same:

* FastAPI
* PostgreSQL
* Redis
* Celery worker
* Celery Beat
* Docker Compose

The primary differences would be infrastructure-related:

```text
Local Machine
      │
      ▼
Docker Compose

        ↓ later

VPS
      │
      ▼
Docker Compose
      │
      ├── Reverse Proxy
      ├── Domain
      └── HTTPS Certificate
```

A future VPS deployment would typically add:

* a public server
* a domain name
* a reverse proxy such as Nginx or Caddy
* HTTPS certificates
* firewall configuration
* production backup strategy
* stronger secret management

The application container architecture and CI/CD artifact flow would remain applicable.

The main change is where the containers run, not how the application itself is packaged.

---

# 19. Current Scope

This project is intentionally built as a production-style portfolio system rather than a publicly operated commercial service.

The goal is to demonstrate practical software engineering skills across the full application lifecycle:

* backend architecture
* authentication and authorization
* multi-tenant isolation
* asynchronous processing
* billing logic
* payment integration
* webhook handling
* reconciliation
* idempotency
* testing
* Docker containerization
* database migrations
* CI/CD
* container image publishing
* production-style deployment

The system is therefore designed to demonstrate the engineering practices involved in deploying and operating a backend service without requiring the ongoing cost of maintaining public infrastructure.

---

# 20. Deployment Philosophy

The deployment setup follows one central principle:

> **Build once, test the important behavior, publish an immutable artifact, and deploy that exact artifact.**

The application is configured externally.

The container image is reusable.

Database schema changes are versioned.

Services wait for their dependencies.

Deployments are validated with health checks.

The result is a workflow that can run locally today and evolve into a VPS or cloud deployment later without requiring the application architecture to be rebuilt from scratch.
