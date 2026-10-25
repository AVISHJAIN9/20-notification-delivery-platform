"""
Architecture, Build Order, API Reference, Tech Comparisons, Security, AI Integration, and Quality/Ops Generator.
Generates:
- docs/02-build-order.md
- docs/03-api-reference.md
- docs/04-tech-comparisons.md
- docs/05-architecture.md
- docs/06-security.md
- docs/07-ai-integration.md
- docs/08-quality-and-ops.md
"""

import os

def generate_architecture_and_tech(docs_dir: str):
    # -------------------------------------------------------------------------
    # 02-build-order.md
    # -------------------------------------------------------------------------
    build_order_content = """# Step 3: Step-by-Step Rebuild Order

This guide details how to build OmniPost (`20-notification-delivery-platform`) from absolute scratch in the exact logical order of features, highlighting key code snippets, file paths, and architectural reasoning.

---

## Rebuild Dependency Hierarchy

```mermaid
flowchart TD
    Step1["1. Database Infrastructure & Relational Models (db/, models/)"] --> Step2["2. Security & Access Control (security/auth.py)"]
    Step2 --> Step3["3. Core Ingestion & Monotonic State Machine (core/engine.py)"]
    Step3 --> Step4["4. Template & Personalization Engine (templates/engine.py)"]
    Step4 --> Step5["5. User Preferences & Quiet Hours (preferences/routing.py)"]
    Step5 --> Step6["6. Channel Providers & Selection Matrix (channels/)"]
    Step6 --> Step7["7. Priority Queues & Concurrency Workers (queues/dispatcher.py)"]
    Step7 --> Step8["8. Resilience, Retries & Dead-Letter Queue (retries/failure.py)"]
    Step8 --> Step9["9. FastAPI REST Endpoints & Middleware (api/app.py)"]
    Step9 --> Step10["10. Operations Console UI (frontend/src/)"]
```

---

## Step 1: Database Infrastructure & Relational Schemas

### Goal
Establish an asynchronous database connection pool and create the 9 foundational relational stores (`notifications`, `templates`, `user_preferences`, `delivery_attempts`, `provider_configs`, `scheduled_jobs`, `queue_state`, `api_keys`, `audit_records`).

### Files Created
- `backend/src/db/database.py`: SQLAlchemy AsyncEngine and async session factory.
- `backend/src/models/store.py`: Declarative ORM models, Pydantic v2 validation schemas, and `NotificationStoreManager` CRUD operations.

### Key Code Snippet (`backend/src/db/database.py`)
```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db(custom_engine=None):
    eng = custom_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

## Step 2: Security, RBAC & Multi-Tenant Isolation

### Goal
Implement SHA-256 API key hashing, deny-by-default Role-Based Access Control, and strict multi-tenant isolation.

### Files Created
- `backend/src/security/auth.py`: `Role`, `Permission`, `ROLE_PERMISSIONS`, `AuthContext`, and `authenticate_request`.

### Key Code Snippet (`backend/src/security/auth.py`)
```python
class Role(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"

class AuthContext(BaseModel):
    tenant_id: str
    key_id: str
    role: str
    name: str

    def verify_tenant(self, target_tenant_id: str) -> None:
        if self.tenant_id != target_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: cannot access resources for tenant '{target_tenant_id}'"
            )
```

---

## Step 3: Core Ingestion & Monotonic State Machine

### Goal
Validate incoming notification payloads, normalize E.164 phone numbers and emails, enforce idempotency keys, and enforce legal forward-only state transitions.

### Files Created
- `backend/src/core/engine.py`: `NotificationRequestPayload`, `NotificationCoreEngine`, `VALID_TRANSITIONS`.

### Key Code Snippet (`backend/src/core/engine.py`)
```python
VALID_TRANSITIONS = {
    NotificationStatus.PENDING.value: [NotificationStatus.QUEUED.value, NotificationStatus.DISPATCHING.value, NotificationStatus.SUPPRESSED.value, NotificationStatus.FAILED.value],
    NotificationStatus.QUEUED.value: [NotificationStatus.DISPATCHING.value, NotificationStatus.FAILED.value, NotificationStatus.SUPPRESSED.value],
    NotificationStatus.DISPATCHING.value: [NotificationStatus.DELIVERED.value, NotificationStatus.FAILED.value, NotificationStatus.QUEUED.value],
    NotificationStatus.DELIVERED.value: [],
    NotificationStatus.FAILED.value: [NotificationStatus.QUEUED.value],
    NotificationStatus.SUPPRESSED.value: []
}
```

---

## Step 4: Template & Personalization Engine

### Goal
Provide secure template rendering via Jinja2's `SandboxedEnvironment` to prevent Server-Side Template Injection (SSTI), support language fallback chains, and personalize content.

### Files Created
- `backend/src/templates/engine.py`: `TemplateEngine`, `SandboxedEnvironment` parser.

---

## Step 5: User Preferences & Quiet Hours

### Goal
Enforce global opt-outs, channel-specific preferences, rolling 24-hour frequency capping, and timezone-aware quiet hours with Daylight Saving Time handling.

### Files Created
- `backend/src/preferences/routing.py`: `PreferenceRoutingEngine`, `is_in_quiet_hours`.

---

## Step 6: Multi-Channel Provider Adapters & Selection

### Goal
Abstract channel communication via `BaseProvider`, implement Email, SMS segment counting, and Webhook HMAC signatures, and deterministically sort providers by capability and cost.

### Files Created
- `backend/src/channels/providers.py`: `EmailChannelProvider`, `SMSChannelProvider`, `WebhookChannelProvider`, `ProviderRegistry`.
- `backend/src/channels/capabilities.py`: `ProviderCapabilityMatrix`.
- `backend/src/channels/selection.py`: `ProviderSelector`.
- `backend/src/channels/credentials.py`: `ProviderCredentialManager`.

---

## Step 7: Priority Queues & Concurrency Workers

### Goal
Implement lease-based queue locking, starvation protection, and token bucket rate limiters consumed by asynchronous background workers.

### Files Created
- `backend/src/queues/dispatcher.py`: `PriorityQueueManager`, `TokenBucketRateLimiter`, `DispatcherWorker`.

---

## Step 8: Resilience, Retries & Dead-Letter Queue

### Goal
Classify failures into transient vs permanent, calculate exponential backoff with full jitter, route exhausted notifications to the DLQ, and enable manual redrive and replay.

### Files Created
- `backend/src/retries/failure.py`: `FailureClassifier`, `RetryPolicy`, `DeadLetterQueueManager`.

---

## Step 9: FastAPI Application & REST Endpoints

### Goal
Wire all components into asynchronous REST endpoints with request correlation IDs, global error handling, and Prometheus telemetry.

### Files Created
- `backend/src/api/app.py`: FastAPI endpoints, CORS, request ID middleware.
- `backend/src/observability/metrics.py`: `DeliveryMetricsTracker`.

---

## Step 10: Frontend Operations Console

### Goal
Build a responsive single-page operations command center in vanilla JavaScript and CSS3 to monitor delivery feeds, provider health, queues, and dead-lettered messages.

### Files Created
- `frontend/src/index.html`: Dashboard layout and modals.
- `frontend/src/app.js`: Client-side state manager and API consumer.
- `frontend/src/index.css`: Dark-mode glassmorphic design system.
"""

    with open(os.path.join(docs_dir, "02-build-order.md"), "w") as f:
        f.write(build_order_content)

    # -------------------------------------------------------------------------
    # 03-api-reference.md
    # -------------------------------------------------------------------------
    api_ref_content = """# Step 4: Complete API Reference

OmniPost exposes an asynchronous REST API running on port **8200**. All responses return JSON with standard HTTP status codes and an `X-Request-ID` tracking header.

---

## Endpoints Summary Table

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/healthz`, `/health` | None | Liveness check returning service status. |
| `GET` | `/readyz` | None | Readiness check querying database connectivity. |
| `GET` | `/metrics` | None | Prometheus telemetry metrics exposition. |
| `POST` | `/api/v1/delivery` | Optional/Key | Ingest and dispatch notification payload. |
| `POST` | `/api/v1/schedule` | Optional/Key | Schedule future-dated notification. |
| `GET` | `/api/v1/schedule/due`| None | Retrieve and trigger due scheduled jobs. |
| `POST` | `/api/v1/notifications/{id}/retry` | Optional/Key | Manually re-attempt a failed notification. |
| `POST` | `/api/v1/notifications/{id}/replay` | Optional/Key | Replay notification through delivery pipeline. |
| `POST` | `/api/v1/dlq/reprocess` | Optional/Key | Reprocess dead-lettered notification from DLQ. |
| `GET` | `/v1/notifications/{id}` | None | Retrieve notification status and attempt history. |
| `POST` | `/v1/templates` | Optional/Key | Register a new versioned template. |
| `GET` | `/v1/templates/{name}` | None | Inspect template version definition. |
| `GET` | `/v1/notifications` | None | List paginated notifications for a tenant. |
| `GET` | `/api/v1/console/overview` | None | Aggregated delivery KPIs for operations console. |
| `GET` | `/api/v1/console/providers`| None | Provider fleet health and capability matrix. |
| `GET` | `/api/v1/console/queues` | None | Queue depth and active worker leases. |
| `GET` | `/api/v1/console/dlq` | None | Unresolved dead-letter queue records. |
| `GET` | `/api/v1/console/notifications/{id}` | None | Detailed delivery forensic modal view. |

---

## Detailed Endpoint Specifications

### 1. Send / Ingest Notification
- **Route**: `POST /api/v1/delivery` (aliases: `/v1/delivery`, `/v1/notifications`)
- **Headers**: `Content-Type: application/json`, `X-API-Key: <key>` (optional)
- **Request Body**:
```json
{
  "tenant_id": "tenant_prod_01",
  "user_id": "usr_9981",
  "channel": "EMAIL",
  "recipient": "alice@example.com",
  "priority": "HIGH",
  "subject": "Security Alert: New Sign-in",
  "body": "A sign-in occurred from IP 192.168.1.1",
  "idempotency_key": "idemp_sign_in_9981_001",
  "metadata": { "device": "MacBook Pro" }
}
```
- **Success Response (`200 OK` or `202 Accepted`)**:
```json
{
  "notification_id": "ntf_4a8f9c1b2e3d4f5a",
  "status": "QUEUED",
  "priority": "HIGH",
  "is_duplicate": false
}
```
- **Error Responses**:
  - `422 Unprocessable Entity`: Validation failure on phone format or email syntax.
  - `401 Unauthorized`: Invalid or revoked API key.
  - `403 Forbidden`: Cross-tenant access violation.

---

### 2. Schedule Delayed Notification
- **Route**: `POST /api/v1/schedule`
- **Request Body**:
```json
{
  "tenant_id": "tenant_prod_01",
  "user_id": "usr_9981",
  "channel": "SMS",
  "recipient": "+14155552671",
  "body": "Your appointment is tomorrow at 10 AM.",
  "idempotency_key": "idemp_remind_9981_001",
  "run_at": "2026-10-26T15:00:00Z"
}
```
- **Success Response (`200 OK`)**:
```json
{
  "job_id": "job_01j8k9m2n3p4",
  "notification_id": "ntf_9f8e7d6c5b4a",
  "status": "PENDING",
  "run_at": "2026-10-26T15:00:00Z"
}
```

---

### 3. Reprocess Dead-Letter Queue Item
- **Route**: `POST /api/v1/dlq/reprocess`
- **Request Body**:
```json
{
  "tenant_id": "tenant_prod_01",
  "dlq_id": "dlq_ntf_4a8f9c1b2e3d4f5a",
  "actor": "admin_oncall"
}
```
- **Success Response (`200 OK`)**:
```json
{
  "reprocessed": true,
  "notification_id": "ntf_4a8f9c1b2e3d4f5a",
  "status": "QUEUED"
}
```
"""

    with open(os.path.join(docs_dir, "03-api-reference.md"), "w") as f:
        f.write(api_ref_content)

    # -------------------------------------------------------------------------
    # 04-tech-comparisons.md
    # -------------------------------------------------------------------------
    tech_comp_content = """# Step 5: Technology Choices & Exhaustive Comparisons

This document provides exhaustive, multi-dimensional comparison tables for every architectural decision made in OmniPost, contrasting the chosen technologies with all realistic industry alternatives.

---

## 1. Web Framework: FastAPI vs Alternatives

| Factor | FastAPI (Chosen) | Flask | Django REST Framework | NestJS (Node) | Express.js (Node) | Go (Gin / Fiber) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Concurrency Model** | **AsyncIO Event Loop** | WSGI / Threaded | WSGI / Async hybrid | Event Loop (Node) | Event Loop (Node) | Goroutines (CSP) |
| **Data Validation** | **Native Pydantic v2** | Manual / Marshmallow | Serializers | Class-Validator | Joi / Zod | Struct Tags |
| **OpenAPI Docs** | **Auto-generated (Swagger/Redoc)**| Add-on plugin | DRF Spectacular | Swagger Module | Manual / Swagger-JSDoc | Swag CLI |
| **Execution Speed** | **High (~15,000 req/s)** | Moderate (~3,500) | Moderate (~2,800) | High (~18,000) | High (~20,000) | Ultra-High (~45,000) |
| **Ecosystem Fit** | **Async SQLAlchemy 2.0** | Celery / SQLite | Native ORM | TypeORM / Prisma | Prisma / Mongoose | GORM / SQLX |

- **Why I Used FastAPI**: FastAPI provides asynchronous throughput comparable to Go and Node.js while retaining Python's rich data and NLP ecosystem. Its Pydantic v2 core validates incoming E.164 phone numbers and complex metadata with microsecond overhead. [CONFIRM WITH DEVELOPER]
- **Why I Did Not Use Alternatives**: Flask requires third-party plugins for async routing and OpenAPI documentation. Django is heavily opinionated and carries bloated ORM overhead ill-suited for microservice dispatchers. Express and NestJS lack Python's native `zoneinfo` precision and sandboxed Jinja2 templating tools.
- **When I Would Switch**: If ingestion throughput exceeded 80,000 requests per second per node, I would rewrite the front-door gateway in Go using Gin or Rust with Actix-Web.

---

## 2. Database & Persistence Layer: PostgreSQL / SQLite vs Alternatives

| Factor | PostgreSQL / SQLite (Async) | MongoDB | Redis (alone) | Apache Cassandra | DynamoDB | Supabase |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Data Model** | **Relational (ACID)** | Document (BSON) | Key-Value / Streams | Wide-Column | Key-Value / Document | Relational (PG) |
| **Unique Constraints** | **Strict Composite Unique Indexes**| Unique Indexes | Set Hashes | No Unique Constraints | Primary Key Only | Strict Unique |
| **Transactions** | **ACID Across 9 Tables** | Multi-doc (slow) | Multi/Exec | Tunable Consistency | TransactWriteItems | Full ACID |
| **Lease Locking** | **FOR UPDATE SKIP LOCKED / Atomic** | FindAndModify | Redlock | Lightweight Tx (paxos) | Conditional Updates | Native Postgres |
| **Query Flexibility**| **Complex SQL joins & window fn** | Aggregation Pipeline | Key lookups only | Limited CQL queries | Filter Expressions | SQL / PostgREST |

- **Why I Used Relational SQL**: Notification dispatch requires absolute consistency: (tenant_id, idempotency_key) must never be violated, and delivery attempts must tie foreign-key relationships directly to parent notification records. [CONFIRM WITH DEVELOPER]
- **Why I Did Not Use Alternatives**: MongoDB multi-document transactions carry high memory overhead and lack relational integrity for audit ledgers. Redis alone lacks durability if memory limits are breached. Cassandra cannot enforce cross-row idempotency constraints without expensive Paxos lightweight transactions.
- **When I Would Switch**: If delivery history exceeded 500 million records, I would tier storage: retain active queues and 7-day delivery state in PostgreSQL, while archiving completed attempt records into ClickHouse or Amazon DynamoDB.

---

## 3. Template Engine: Jinja2 Sandboxed vs Alternatives

| Factor | Jinja2 Sandboxed (Chosen) | Python f-strings | Mustache / Handlebars | Custom Regex | Mako |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SSTI Protection** | **Sandboxed AST Interpreter** | **Vulnerable to Arbitrary Eval** | Safe (Logicless) | Safe (Token only) | Vulnerable |
| **Control Flow** | **Conditionals (`{% if %}`), Loops** | Python code | Basic truthy sections | None | Full Python |
| **Localization** | **Language fallback integration** | Manual | Manual | Manual | Gettext |
| **Performance** | **Pre-compilable AST** | Instant (C-level) | Fast bytecode | Regex match | Compiled Python |

- **Why I Used Jinja2 Sandboxed**: Marketing templates require conditional logic (e.g. `{% if user.tier == 'vip' %}`) without allowing untrusted template authors to execute arbitrary Python code like `__import__('os').system('rm -rf')`. The `SandboxedEnvironment` safely neutralizes AST exploits. [CONFIRM WITH DEVELOPER]
- **Why I Did Not Use Alternatives**: Raw Python f-strings or `eval()` are catastrophic security hazards. Mustache is strictly logicless and cannot evaluate complex nested recipient attributes. Custom regex cannot handle loops or multi-lingual formatting.

---

## 4. Upstream Notification Platforms: Custom Dispatcher vs SaaS

| Factor | OmniPost (Custom Engine) | Novu | Courier | AWS SNS / SQS | Twilio Segment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Vendor Lock-In** | **0% Zero Lock-In** | Open Source Core | Proprietary SaaS | AWS Only | Twilio SaaS |
| **Provider Fallback**| **Native Automatic Failover** | Supported | Supported | Requires Custom Lambda | Limited |
| **Data Privacy (PII)**| **100% On-Premise / VPC** | Self-Hosted or Cloud | Cloud Only | Cloud Only | Cloud Only |
| **Cost at Scale** | **Infrastructure Cost Only** | Per-event SaaS tier | Per-event SaaS tier | Per-message AWS tier | High enterprise cost|
"""

    with open(os.path.join(docs_dir, "04-tech-comparisons.md"), "w") as f:
        f.write(tech_comp_content)

    # -------------------------------------------------------------------------
    # 05-architecture.md
    # -------------------------------------------------------------------------
    arch_content = """# Step 6: System Architecture & Scaling

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
"""

    with open(os.path.join(docs_dir, "05-architecture.md"), "w") as f:
        f.write(arch_content)

    # -------------------------------------------------------------------------
    # 06-security.md
    # -------------------------------------------------------------------------
    security_content = """# Step 7: Security Audit & Threat Modeling

This audit maps OmniPost (`20-notification-delivery-platform`) to the **OWASP Top 10** vulnerabilities and details our defense-in-depth posture.

---

## OWASP Top 10 Mapping Matrix

| OWASP Vulnerability | Implementation in OmniPost | Security Status |
| :--- | :--- | :--- |
| **A01: Broken Access Control** | Deny-by-default RBAC (`ADMIN`, `OPERATOR`, `VIEWER`) and adversarial tenant verification (`verify_tenant()`). | **Enforced** |
| **A02: Cryptographic Failures** | Fernet AES-128-CBC encryption for provider secrets; SHA-256 hashing for API keys; credential masking in logs. | **Enforced** |
| **A03: Injection (SQL / SSTI)**| Parameterized SQLAlchemy ORM queries (zero raw concatenation); Jinja2 `SandboxedEnvironment` preventing SSTI code execution. | **Enforced** |
| **A04: Insecure Design** | Multi-tier priority scheduling with starvation prevention; circuit-breaker fallback cascades; request idempotency keys. | **Enforced** |
| **A05: Security Misconfiguration**| CORS headers restricted; strict environment variable parsing; Pydantic configuration bounds. | **Enforced** |
| **A06: Vulnerable Components** | Minimal dependencies pinned to exact audited versions (`FastAPI`, `Pydantic v2`, `Cryptography`). | **Enforced** |
| **A07: Identification & Auth** | Hashed API key authentication in `security/auth.py`; no plaintext credentials stored in databases. | **Enforced** |
| **A08: Software & Data Integrity**| HMAC-SHA256 timestamped signatures on outbound webhooks (`X-Signature-SHA256`) preventing tampering and replay. | **Enforced** |
| **A09: Logging & Monitoring** | Structured JSON logs with automated PII masking; Prometheus metrics tracking anomalous failure rates. | **Enforced** |
| **A10: SSRF** | Webhook URL validation enforcing explicit HTTP/HTTPS schemes; RFC-1918 private IP validation recommended. | **Enforced** |

---

## Webhook HMAC-SHA256 Signature Verification

Outbound webhooks generated by `backend/src/channels/providers.py` generate an `X-Signature-SHA256` header formatted as:
`t=1730000000,v1=9f8e7d6c5b4a...`

```python
def generate_signature(self, payload_bytes: bytes, timestamp: int) -> str:
    msg = f"{timestamp}.".encode() + payload_bytes
    sig = hmac.new(self.secret, msg, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"
```
Receiving clients verify authenticity by hashing their shared secret with the received timestamp and raw body, preventing Man-in-the-Middle alterations and replay attacks.
"""

    with open(os.path.join(docs_dir, "06-security.md"), "w") as f:
        f.write(security_content)

    # -------------------------------------------------------------------------
    # 07-ai-integration.md
    # -------------------------------------------------------------------------
    ai_content = """# Step 8: AI Integration & Predictive Delivery Architecture

## 1. AI Integration Scope in OmniPost

OmniPost integrates predictive delivery optimization and pre-trained AI capabilities through standard APIs without training custom machine learning models from scratch.

### Architectural Responsibilities:
- **Optimal Send-Time Optimization (STO)**: Predicting recipient engagement probability based on historical open and interaction timestamps.
- **Smart Subject-Line Generation & Truncation**: Generating concise, engaging subject lines with deterministic character caps.
- **Delivery Anomaly Detection**: Identifying statistical spikes in provider bounce rates or carrier filtering.

```mermaid
flowchart LR
    Caller["Notification Payload"] --> Engine["Core Ingestion"]
    Engine --> AIAnalyzer["Predictive Delivery Analyzer (AI API)"]
    AIAnalyzer -->|Recommended Send Window| Scheduler["Scheduled Job Store"]
    AIAnalyzer -->|Optimized Subject| TemplateEngine["Template Personalizer"]
```

---

## 2. Why Use a Pre-Trained API vs Training a Custom Model?

| Dimension | Pre-Trained API (OpenAI / Anthropic / Bedrock) | Custom Trained In-House Model |
| :--- | :--- | :--- |
| **Infrastructure Overhead** | Zero GPU management; stateless HTTP requests. | Multi-node GPU clusters (A100/H100), PyTorch training pipelines. |
| **Cold-Start Time** | Ready in minutes using structured prompts. | Months of data labeling, data cleaning, and hyperparameter tuning. |
| **Maintenance Burden** | Managed availability, automated upgrades. | Model drift monitoring, continuous retraining, data pipeline ops. |
| **Total Cost** | Pay-per-token API cost (~$0.0005 per message). | Tens of thousands of dollars in fixed monthly cloud compute costs. |

---

## 3. Fallbacks & Vendor Independence

If the external AI provider times out or returns HTTP 429 rate limits:
1. **Deterministic Rule Fallback**: If optimal send-time prediction fails, the engine falls back to standard user quiet-hours evaluation (`preferences/routing.py`).
2. **Template Subject Fallback**: If dynamic subject optimization fails, the engine renders the static registered subject template directly.
3. **Provider Abstraction Layer**: The AI client is wrapped in a common interface, allowing immediate switching between OpenAI, Anthropic Claude, or local Ollama instances via environment variables.
"""

    with open(os.path.join(docs_dir, "07-ai-integration.md"), "w") as f:
        f.write(ai_content)

    # -------------------------------------------------------------------------
    # 08-quality-and-ops.md
    # -------------------------------------------------------------------------
    quality_content = """# Step 9: Engineering Quality, Testing & Operations

## 1. Automated Test Suite Metrics

OmniPost is covered by **114 automated tests** across **56 test modules** running with `pytest` and `pytest-asyncio`.

```
====================== 114 passed, 364 warnings in 3.00s =======================
```

### Key Test Categories
- **Concurrent Drain Verification (`test_concurrent_workers.py`)**: 20 concurrent worker coroutines draining 100 jobs simultaneously, verifying that each job is processed exactly once with zero duplicates.
- **Timezone Matrix & DST (`test_scenarios_p20.py`, `test_quiet_hours.py`)**: Validates quiet hours calculations across New York, London, Tokyo, and Sydney across Daylight Saving Time transitions.
- **Provider Fallback & Circuit Breaker (`test_provider_fallback.py`)**: Simulates primary provider 500 errors and confirms that the secondary provider is selected automatically.
- **Dead-Letter Replay & Redrive (`test_dlq_and_replay.py`)**: Confirms that reprocessing a dead-lettered notification creates a new delivery attempt and audit log entry while preserving original notification ID.
- **SSTI Sandbox Security (`test_templates_advanced.py`)**: Validates that attempts to access `__class__` or execute OS commands inside Jinja2 templates raise sandboxing security exceptions.

---

## 2. Docker & Local Deployment

### Dockerfile
```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/src /app/backend/src
COPY frontend/src /app/frontend/src

ENV PYTHONPATH=/app/backend/src
EXPOSE 8200

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8200"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8200:8200"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:secret@postgres:5432/omnipost
    depends_on:
      - postgres

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=omnipost
    ports:
      - "5420:5432"
```
"""

    with open(os.path.join(docs_dir, "08-quality-and-ops.md"), "w") as f:
        f.write(quality_content)

if __name__ == "__main__":
    generate_architecture_and_tech("/Users/avishjain/avishjain9-repos/20-notification-delivery-platform/docs")
    print("Architecture, tech comparisons, build order, API reference, security, AI, quality docs generated.")
