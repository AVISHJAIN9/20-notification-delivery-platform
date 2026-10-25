# Step 6: System Architecture & Scaling

## High-Level Architecture Overview

OmniPost is designed around decoupled, asynchronous pipeline stages where ingestion, business rule evaluation, queuing, and provider dispatch are separated by explicit state barriers.

```mermaid
flowchart TD
    subgraph Ingestion ["Ingestion & Gateway"]
        Client["Microservice / Console"] -->|HTTP POST| Gateway["FastAPI API (Port 8200)"]
        Gateway -->|Verify Key & Tenant| Auth["Security Auth (security/auth.py)"]
        Gateway -->|Validate & Deduplicate| Core["Core Engine (core/engine.py)"]
    end

    subgraph Evaluation ["Evaluation & Personalization"]
        Core -->|Opt-Out & Quiet Hours| Pref["Preference Engine (preferences/routing.py)"]
        Core -->|Interpolate Variables| Tmpl["Template Engine (templates/engine.py)"]
    end

    subgraph QueueLayer ["Priority Queue & Lease Engine"]
        Pref -->|URGENT / HIGH / NORMAL / LOW| QStore["Queue Store (models/store.py)"]
        QStore -->|Atomic Lease Dequeue| Worker["Dispatcher Worker (queues/dispatcher.py)"]
    end

    subgraph ProviderLayer ["Provider Routing & Resilience"]
        Worker -->|Rate Limit Check| Bucket["Token Bucket (queues/dispatcher.py)"]
        Bucket -->|Select Best Provider| Selector["Provider Selector (channels/selection.py)"]
        Selector -->|HTTP Post| Drivers["Email / SMS / Webhook Adapters"]
        Drivers -.->|Retryable 5xx / 429| Fallback["Secondary Provider (SES / Vonage)"]
        Drivers -.->|Max Retries Exceeded| DLQ["Dead-Letter Queue (retries/failure.py)"]
    end
```

---

## Scaling OmniPost to 100x Traffic (10M Notifications/Day)

At 100 times the current load (~100 to 1,000 requests per second continuously):

### The First Three Bottlenecks
1. **Database Queue Lock Contention**: Running `dequeue_item` with `UPDATE queue_state ... WHERE item_id = (...)` causes database row and index locking contention when hundreds of concurrent workers query the same table.
2. **Synchronous Ingestion Connection Pool Exhaustion**: Direct database writes inside the HTTP request handler exhaust available SQLAlchemy connection pool slots during sudden traffic spikes.
3. **Upstream Vendor Rate Limits**: Third-party providers (Twilio SMS short codes at 100 rps, SendGrid IP pools) reject incoming volume with HTTP 429 Too Many Requests.

### Architectural Scaling Evolution

```mermaid
flowchart LR
    subgraph Current ["Current Architecture"]
        API1["FastAPI"] --> DB1[("PostgreSQL / SQLite")]
        Worker1["Async Worker"] --> DB1
    end

    subgraph Scale100x ["100x Scale Architecture"]
        LB["AWS ALB / Nginx"] --> APIScaled["FastAPI Replicas (x10)"]
        APIScaled --> Kafka["Apache Kafka / Redis Streams"]
        Kafka --> WorkerFleet["Worker Pods (HPA Autoscaled)"]
        WorkerFleet --> ProviderPool["Multi-IP Provider Egress"]
        WorkerFleet --> ReadWriteDB[("PostgreSQL (Read Replicas + Partitioning)")]
    end
```

1. **Replace DB Queue with Kafka or SQS**: Shift queue state from relational tables into Apache Kafka with 16 partitions keyed by `tenant_id` or recipient hash.
2. **Asynchronous Ingestion Buffering**: The FastAPI gateway writes incoming payloads directly into Kafka in <5ms, returning an immediate `202 Accepted` without touching relational tables.
3. **Distributed Token Bucket via Redis**: Migrate process-local token buckets into Redis clusters using atomic Lua scripts (`EVALSHA`) to enforce global rate limits across all distributed worker nodes.
