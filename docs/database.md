# Database design

PostgreSQL, normalized. All IDs are UUIDv4. All timestamps are `timestamptz` (UTC).
Money/credits are `NUMERIC(18,4)` — never floats.

## ER diagram

```mermaid
erDiagram
    users ||--o{ refresh_tokens : has
    users ||--o{ sessions : has
    users ||--|| credit_accounts : owns
    credit_accounts ||--o{ credit_transactions : records
    users ||--o{ deployments : owns
    deployments ||--o{ deployment_services : contains
    deployments ||--o{ deployment_events : emits
    deployments ||--o{ deployment_logs : writes
    deployments ||--o{ usage_records : accrues
    usage_records }o--|| pricing_plans : "priced by (snapshot)"
    users ||--o{ audit_logs : generates
    users ||--o{ compose_templates : submits
    deployments }o--o| compose_templates : "created from"

    users {
        uuid id PK
        citext email UK
        varchar hashed_password
        varchar role "user|admin"
        boolean is_active
        boolean is_email_verified
        varchar email_verification_token "nullable, hashed"
        varchar password_reset_token "nullable, hashed"
        timestamptz password_reset_expires_at
        timestamptz created_at
        timestamptz updated_at
    }

    sessions {
        uuid id PK
        uuid user_id FK
        varchar user_agent
        inet ip_address
        boolean revoked
        timestamptz created_at
        timestamptz last_used_at
    }

    refresh_tokens {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        varchar token_hash UK "sha256"
        uuid replaced_by "rotation chain"
        boolean revoked
        timestamptz expires_at
        timestamptz created_at
    }

    credit_accounts {
        uuid id PK
        uuid user_id FK "unique"
        numeric balance
        numeric max_cpu_quota
        numeric max_memory_mb_quota
        numeric max_storage_gb_quota
        int max_deployments_quota
        timestamptz updated_at
    }

    credit_transactions {
        uuid id PK
        uuid account_id FK
        varchar kind "purchase|usage|adjustment|refund"
        numeric amount "signed"
        numeric balance_after
        uuid deployment_id "nullable"
        varchar idempotency_key UK "nullable"
        jsonb metadata
        timestamptz created_at
    }

    pricing_plans {
        uuid id PK
        varchar name
        boolean is_active
        numeric base_cost_per_hour
        numeric cpu_cost_per_core_hour
        numeric memory_cost_per_gb_hour
        numeric storage_cost_per_gb_hour
        numeric service_cost_per_hour "per extra compose service"
        timestamptz created_at
    }

    deployments {
        uuid id PK
        uuid owner_id FK
        varchar name
        varchar slug UK "subdomain label"
        varchar kind "image|compose"
        varchar status "pending|provisioning|running|stopping|stopped|failed|deleting|deleted|credit_exhausted"
        varchar provider "docker"
        varchar node_id "future multi-VM"
        numeric cpu_cores
        int memory_mb
        int storage_gb
        jsonb spec "full validated spec"
        varchar public_url
        numeric estimated_hourly_cost
        varchar failure_reason
        timestamptz started_at
        timestamptz stopped_at
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at "soft delete"
    }

    deployment_services {
        uuid id PK
        uuid deployment_id FK
        varchar service_name
        varchar image
        varchar container_id
        varchar container_name "user{n}-{svc}"
        varchar status
        int restart_count
        boolean is_web "routed via Traefik"
        int internal_port
        timestamptz updated_at
    }

    deployment_events {
        uuid id PK
        uuid deployment_id FK
        varchar event_type "created|provisioning|running|stopped|failed|deleted|credit_exhausted"
        jsonb payload
        boolean dispatched "outbox flag"
        timestamptz created_at
    }

    deployment_logs {
        uuid id PK
        uuid deployment_id FK
        varchar source "system|billing|provider"
        varchar level
        text message
        timestamptz created_at
    }

    usage_records {
        uuid id PK
        uuid deployment_id FK
        timestamptz period_start
        timestamptz period_end
        numeric credits_charged
        jsonb price_snapshot "frozen plan values"
        timestamptz created_at
    }

    images {
        uuid id PK
        varchar pattern UK "repo[:tag] or repo/*"
        varchar mode "allow|block"
        varchar reason
        uuid created_by FK
        timestamptz created_at
    }

    compose_templates {
        uuid id PK
        uuid submitted_by FK
        varchar name
        text compose_yaml
        varchar status "pending|approved|rejected"
        uuid reviewed_by
        timestamptz created_at
    }

    audit_logs {
        uuid id PK
        uuid actor_id FK "nullable (system)"
        varchar action
        varchar resource_type
        varchar resource_id
        inet ip_address
        jsonb detail
        timestamptz created_at
    }

    host_metrics {
        uuid id PK
        numeric cpu_percent
        numeric memory_used_mb
        numeric memory_total_mb
        numeric disk_used_gb
        numeric disk_total_gb
        int running_containers
        timestamptz sampled_at
    }
```

## Invariants enforced in code + constraints

- `credit_transactions.balance_after` is always written under `SELECT … FOR UPDATE` of
  the account row; `CHECK (balance >= 0)` on `credit_accounts` is the last line of defense.
- `usage_records (deployment_id, period_start)` unique — the billing tick is idempotent.
- `deployments.slug` unique — it is the public subdomain label.
- Deployments are soft-deleted (`deleted_at`) so billing history keeps its FK integrity.
- `deployment_events` is a transactional outbox: rows are inserted with the state change
  and `dispatched=false`, then relayed to Celery; the relay marks `dispatched=true`.
```
