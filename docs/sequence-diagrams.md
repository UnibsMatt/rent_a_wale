# Sequence diagrams

## 1. User login

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (SPA)
    participant A as Backend API
    participant PG as PostgreSQL
    participant R as Redis

    B->>A: POST /api/v1/auth/login {email, password}
    A->>R: rate-limit check (ip + email bucket)
    A->>PG: SELECT user by email
    A->>A: bcrypt.verify(password, hashed_password)
    alt invalid credentials / inactive user
        A-->>B: 401 (uniform error, no user enumeration)
    else valid
        A->>PG: INSERT session (ip, user_agent)
        A->>PG: INSERT refresh_token (sha256 hash, expires 30d)
        A->>PG: INSERT audit_log (auth.login)
        A-->>B: 200 {access_token (JWT 15m, jti, role), refresh_token}
    end
    Note over B: access token in memory,<br/>refresh token for /auth/refresh rotation
```

## 2. Credit purchase

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as Backend API
    participant G as PaymentGateway (Fake today, Stripe later)
    participant PG as PostgreSQL

    B->>A: POST /api/v1/credits/purchase {amount, idempotency_key}
    A->>A: authorize (JWT), validate amount bounds
    A->>G: charge(user, amount)
    G-->>A: payment confirmed (reference)
    A->>PG: BEGIN
    A->>PG: SELECT credit_account FOR UPDATE
    A->>PG: INSERT credit_transaction (kind=purchase, +amount,<br/>idempotency_key, balance_after)
    A->>PG: UPDATE credit_account SET balance = balance + amount
    A->>PG: INSERT audit_log (credits.purchase)
    A->>PG: COMMIT
    A-->>B: 201 {transaction, new_balance}
    Note over A,PG: replay with the same idempotency_key<br/>returns the original transaction (unique index)
```

## 3. Deployment creation

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (wizard)
    participant A as Backend API
    participant PG as PostgreSQL
    participant Q as Redis/Celery
    participant W as Worker
    participant D as Docker Engine (SDK)

    B->>A: POST /api/v1/deployments/estimate {spec}
    A-->>B: {hourly, daily, monthly} from active pricing plan
    B->>A: POST /api/v1/deployments {spec}
    A->>A: validate spec (schema, image allowlist,<br/>compose security validator)
    A->>PG: check user quotas + host capacity snapshot
    A->>PG: SELECT credit_account FOR UPDATE<br/>require balance >= 1h estimated cost
    A->>PG: INSERT deployment (status=pending)<br/>INSERT deployment_event (created) [outbox]
    A->>Q: enqueue provision_deployment(id)
    A-->>B: 202 {deployment_id, status=pending}
    W->>PG: load deployment, set status=provisioning (+event)
    W->>D: pull image(s)
    W->>D: create network raw_dep_<id>, volumes
    W->>D: create containers (limits, labels,<br/>Traefik rule dep-<slug>.domain)
    W->>D: start in depends_on order, gate on healthchecks
    alt success
        W->>PG: status=running, started_at, public_url (+event running)
        Note over W,PG: billing consumer opens usage metering
    else failure
        W->>D: teardown partial resources
        W->>PG: status=failed, failure_reason (+event failed)
    end
    B->>A: GET /deployments/{id} (poll) / GET /logs?follow=1
```

## 4. Billing lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant S as Celery beat (scheduler)
    participant W as Worker
    participant PG as PostgreSQL
    participant D as Docker Engine

    loop every minute
        S->>W: billing_tick
        W->>PG: SELECT running deployments
        loop each running deployment
            W->>PG: BEGIN; SELECT credit_account FOR UPDATE
            W->>W: cost = minute_fraction(price_snapshot, cpu, mem, storage, services)
            alt balance >= cost
                W->>PG: INSERT usage_record (period unique) + debit transaction
                W->>PG: UPDATE balance; COMMIT
            else insufficient
                W->>PG: charge remainder to 0, event credit_exhausted; COMMIT
                W->>W: enqueue stop_deployment(id, reason=credit_exhausted)
            end
        end
    end
    loop every 2 minutes (reconciler)
        S->>W: reconcile_deployments
        W->>D: list containers with raw.managed=true
        W->>PG: compare against DB expectations
        W->>PG: dead container → status=failed, close billing (+event)
        W->>D: orphan container → stop & remove, audit log
    end
```

## 5. Shutdown on insufficient credits

```mermaid
sequenceDiagram
    autonumber
    participant W as Worker (billing_tick)
    participant PG as PostgreSQL
    participant Q as Redis/Celery
    participant W2 as Worker (lifecycle)
    participant D as Docker Engine
    participant B as Browser

    W->>PG: tick finds balance < minute cost
    W->>PG: debit remaining balance to 0
    W->>PG: deployment_event (credit_exhausted) [same tx]
    W->>Q: enqueue stop_deployment(id, reason=credit_exhausted)
    W2->>PG: status=stopping (+event)
    W2->>D: stop containers (SIGTERM, grace 10s)
    W2->>PG: status=credit_exhausted, stopped_at,<br/>close open usage period (+event stopped)
    W2->>PG: deployment_log ("stopped: credits exhausted")<br/>audit_log (system actor)
    B->>PG: dashboard poll shows status + reason,<br/>user can top up and restart
```
