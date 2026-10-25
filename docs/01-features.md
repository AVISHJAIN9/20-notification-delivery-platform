# Step 2: Comprehensive Feature Inventory & Deep Traces

This document catalogs all **19 core architectural feature groups (F1 to F19)** powering OmniPost (`20-notification-delivery-platform`). Every feature has been traced directly from source code, relational models, and automated tests.

---

## Feature Matrix Overview

| Feature ID | Feature Name | Core Responsibility | Primary Code Location |
| :--- | :--- | :--- | :--- |
| **F1** | [Notification Database & State Ledger](./features/F1-notification-database.md) | Immutable system of record with monotonic state machine. | `models/store.py:51` |
| **F2** | [Template Store, Registry & Versioning](./features/F2-template-store-registry.md) | Versioned template repository with language fallback. | `templates/engine.py:39` |
| **F3** | [User Preference Store & Routing Rules](./features/F3-user-preference-store.md) | Recipient opt-out, channel preferences, and quiet hours. | `preferences/routing.py:98` |
| **F4** | [Delivery Attempt Store & Latency Auditing](./features/F4-delivery-attempt-store.md) | Forensic ledger tracking provider latency and error codes. | `models/store.py:201` |
| **F5** | [Provider Configuration Store & Encryption](./features/F5-provider-config-store.md) | Fernet encrypted provider credentials with log masking. | `channels/credentials.py:18` |
| **F6** | [Scheduled Job Store & Delayed Triggers](./features/F6-scheduled-job-store.md) | Future-dated notification scheduler with timestamp polling. | `queues/dispatcher.py:96` |
| **F7** | [Queue State Store & Lease-Based Locking](./features/F7-queue-state-store.md) | Priority queue state with lease locking and starvation prevention. | `queues/dispatcher.py:51` |
| **F8** | [Ingestion Engine, Validation & Idempotency](./features/F8-ingestion-schema-idempotency.md) | E.164 phone and email normalization with idempotency check. | `core/engine.py:100` |
| **F9** | [Monotonic State Machine & Priority Preemption](./features/F9-state-machine-priority.md) | Strict status transition map with 4-tier priority weights. | `core/engine.py:31` |
| **F10** | [Template Rendering, Personalization & SSTI](./features/F10-template-rendering-personalization.md) | Jinja2 sandboxed execution, variable interpolation, subjects. | `templates/engine.py:21` |
| **F11** | [Multi-Channel Provider Adapters](./features/F11-multichannel-provider-adapters.md) | Polymorphic drivers for Email, SMS segments, Webhook HMAC. | `channels/providers.py:32` |
| **F12** | [Provider Selection, Capabilities & Fallback](./features/F12-provider-selection-fallback.md) | Deterministic cost and health sorting with auto-failover. | `channels/selection.py:10` |
| **F13** | [Dispatcher Workers & Token Bucket Limiter](./features/F13-dispatcher-workers-ratelimiting.md) | Concurrent AsyncIO workers with token bucket rate limiting. | `queues/dispatcher.py:24` |
| **F14** | [Failure Handling, DLQ Replay & Backoff](./features/F14-failure-handling-dlq-replay.md) | Transient/permanent classification, full jitter, DLQ redrive. | `retries/failure.py:30` |
| **F15** | [Quiet Hours, Frequency Capping & Opt-Outs](./features/F15-quiet-hours-frequency-capping.md) | Timezone quiet hours with overnight wrap-around and DST. | `preferences/routing.py:43` |
| **F16** | [RESTful Delivery, Scheduling & DLQ APIs](./features/F16-backend-apis-services.md) | FastAPI endpoints for dispatch, status, templates, health. | `api/app.py:107` |
| **F17** | [Structured Logging & Prometheus Telemetry](./features/F17-observability-telemetry.md) | JSON audit logs and Prometheus delivery latency metrics. | `observability/metrics.py:12` |
| **F18** | [Security, Hashed API Keys, RBAC & Isolation](./features/F18-security-rbac-tenant-isolation.md) | SHA-256 API keys, deny-by-default RBAC, tenant isolation. | `security/auth.py:18` |
| **F19** | [Operations Console UI & Diagnostics](./features/F19-operations-console.md) | Pure-dark console layout for delivery feed, queues, DLQ. | `frontend/src/app.js:1` |

---

## Detailed Feature Specifications

### F1: Notification Database & Relational State Ledger (NTF-001)

- **Responsibility**: High-integrity notification database storing immutable records, delivery states, tenant attribution, and UTC timestamps.
- **Code Reference**: `store.py:51-85 (NotificationRecord), store.py:404-460 (create_notification, get_notification, update_status)`
- **Database Schema**: `notifications (id, tenant_id, user_id, channel, status, priority, idempotency_key, body, subject, metadata_json, scheduled_for, delivered_at, created_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F1-notification-database.md)

#### Say It Out Loud
> "I built the notification database layer using SQLAlchemy and async PostgreSQL sessions to serve as the immutable system of record for all dispatch requests. When a request enters the pipeline, the engine commits a NotificationRecord with a monotonic status state machine starting at PENDING. I chose a relational schema with a composite unique index on tenant_id and idempotency_key over NoSQL because strict duplicate prevention and atomic state transitions are non-negotiable in financial and auth notification systems. If the database connection drops or times out during insertion, the async engine rolls back the transaction and returns a 503 service unavailable with an error request ID so upstream callers can safely retry. One trade-off of this design is that write operations to a single primary table can bottleneck under massive load, which I would address by range-partitioning the notifications table by month or tenant."

---

### F2: Template Store, Registry & Versioning (NTF-002, NTF-009, NTF-028, NTF-029)

- **Responsibility**: Versioned notification template catalog supporting subject and body templates, language tagging, and multi-tenant isolation.
- **Code Reference**: `store.py:89-125 (TemplateRecord), templates/engine.py:39-74 (register_template, get_template_version)`
- **Database Schema**: `templates (id, tenant_id, name, channel, version, language, body_template, subject_template, status, is_active, approved_by, approved_at, deactivated_by, deactivated_at, created_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F2-template-store-registry.md)

#### Say It Out Loud
> "I designed the template registry to allow engineering and product teams to manage notification copy independently of application deployments. In `backend/src/templates/engine.py`, templates are identified by tenant, template name, version, and language code. When selecting a template, the engine queries the latest active version or a pinned version number. I rejected storing templates in static JSON files or code constants because business requirements demand zero-downtime copy updates and multilingual support. If a requested template does not exist, the engine raises an explicit ValueError and logs the missing template name. One limitation is that templates are fetched per delivery request; in a high-volume production environment, I would add a local in-memory LRU cache with Redis Pub/Sub invalidation to eliminate database read overhead."

---

### F3: User Preference Store & Routing Rules (NTF-003, NTF-084, NTF-085, NTF-087)

- **Responsibility**: Per-user preference store defining global opt-out, channel-level opt-ins, category preferences, and quiet hours configuration.
- **Code Reference**: `store.py:131-195 (UserPreferenceRecord), preferences/routing.py:98-160 (evaluate_dispatch)`
- **Database Schema**: `user_preferences (id, tenant_id, user_id, opt_out_all, channel_opt_in_json, categories_opt_in_json, preferred_channel, max_daily_notifications, quiet_hours_start, quiet_hours_end, timezone, updated_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F3-user-preference-store.md)

#### Say It Out Loud
> "I built the user preference store to give recipients granular control over their messaging experience and ensure regulatory compliance with anti-spam laws. The store maintains per-user preferences including global opt-out flags, channel-specific toggles for email and SMS, category opt-ins for marketing versus security alerts, and local timezone definitions. I opted to store category and channel maps as structured JSON fields inside the preference record, giving us schema flexibility without requiring migration scripts every time a product team adds a new notification category. If an unconfigured user receives an alert, the engine defaults to permissive delivery while logging a debug notice. A limitation is that high-frequency preference lookups create database read contention, which I would mitigate using a Redis cache layer with a 5-minute TTL."

---

### F4: Delivery Attempt Store & Latency Auditing (NTF-004)

- **Responsibility**: Granular ledger recording every provider interaction, external transaction IDs, response latencies, and error codes.
- **Code Reference**: `store.py:201-230 (DeliveryAttemptRecord), store.py:603-635 (record_delivery_attempt)`
- **Database Schema**: `delivery_attempts (id, notification_id, provider_id, status, error_code, error_message, latency_ms, attempted_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F4-delivery-attempt-store.md)

#### Say It Out Loud
> "I implemented the delivery attempt store to provide a forensic audit trail of every network call made to third-party providers. Every time an email, SMS, or webhook adapter sends a message, it records the exact provider ID, execution latency in milliseconds, outcome status, and upstream error message. I used a foreign key to the parent notification record with indexing on notification_id and provider_id. If a database write fails here, it is caught in a fallback block so the delivery itself is not aborted. The main limitation is rapid table growth, which I would solve with table partitioning and automated cold-storage archiving."

---

### F5: Provider Configuration Store & Encryption (NTF-005, NTF-010, NTF-049)

- **Responsibility**: Encrypted configuration store for third-party provider credentials, priorities, and rate limits.
- **Code Reference**: `store.py:236-268 (ProviderConfigRecord), channels/credentials.py:18-80 (ProviderCredentialManager)`
- **Database Schema**: `provider_configs (id, tenant_id, channel, provider_name, credentials_json, priority, rate_limit_rps, is_active, created_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F5-provider-config-store.md)

#### Say It Out Loud
> "I built the provider configuration store to decouple upstream vendor integrations from application code. Tenant administrators can register multiple providers per channel, defining their priority rank and requests-per-second limits. In `backend/src/channels/credentials.py`, all sensitive credentials like SendGrid API keys and Twilio tokens are encrypted at rest using AES-128 via Fernet and masked on all API outputs and console logs. I chose symmetric encryption over external KMS for local portability while providing a clean abstraction for AWS KMS or HashiCorp Vault. If decryption fails due to key mismatch, the engine flags the provider as unhealthy and triggers an alert. In the future, I would integrate automated secret rotation hooks."

---

### F6: Scheduled Job Store & Delayed Triggers (NTF-006, NTF-011, NTF-058, NTF-059)

- **Responsibility**: Persistent store and poller for future-dated notifications, automated onboarding sequences, and reminder alerts.
- **Code Reference**: `store.py:273-302 (ScheduledJobRecord), queues/dispatcher.py:96-126 (ScheduledQueueManager)`
- **Database Schema**: `scheduled_jobs (job_id, notification_id, tenant_id, run_at, status, created_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F6-scheduled-job-store.md)

#### Say It Out Loud
> "I implemented the scheduled job engine to handle delayed notifications, such as appointment reminders and onboarding drip campaigns. When a payload arrives with a `scheduled_for` timestamp, the system persists a `ScheduledJobRecord` with an indexed `run_at` timestamp. In `backend/src/queues/dispatcher.py`, the `ScheduledQueueManager` periodically polls for jobs where `run_at <= now` and status is PENDING, atomically marking them EXECUTED and pushing the parent notification into the priority queue. I rejected external cron systems like Celery Beat or Quartz to keep the infrastructure lightweight and self-contained within our async database engine. If a polling cycle fails, un-executed jobs remain pending and fire on the next pass without loss. To scale this past 10,000 scheduled jobs per minute, I would migrate the index to Redis Sorted Sets using timestamps as scores."

---

### F7: Queue State Store & Lease-Based Locking (NTF-007, NTF-056, NTF-057)

- **Responsibility**: State store powering atomic dequeueing, lease-based locking, starvation protection, and duplicate prevention.
- **Code Reference**: `store.py:307-332 (QueueStateRecord), store.py:856-940 (dequeue_item), queues/dispatcher.py:51-95 (PriorityQueueManager)`
- **Database Schema**: `queue_state (item_id, queue_name, priority, payload_json, lock_token, locked_until, enqueued_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F7-queue-state-store.md)

#### Say It Out Loud
> "I designed the queue state engine to provide robust, lease-based distributed queueing directly backed by our database. In `backend/src/models/store.py`, each enqueued notification has a priority weight, payload, and lease fields: `lock_token` and `locked_until`. When a worker calls `dequeue_item`, it executes an atomic query that orders by priority descending and enqueued timestamp ascending, filtering for unlocked or expired leases. If a worker crashes mid-delivery, its lease expires after 30 seconds, allowing a peer worker to reclaim the job automatically without message loss. To prevent low-priority notifications from starving when high-priority bursts occur, I built an optional starvation threshold that prioritizes aged jobs regardless of their priority level. I chose lease locking over Redis BLPOP because it guarantees message survivability and persistence across restarts without requiring Redis cluster replication. If concurrent workers attempt to claim the same row, database transaction isolation and atomic update statements ensure exactly one worker wins. A limitation of database queues is disk I/O lock contention at high concurrency, which is why at enterprise scale I would back this with Apache Kafka or Amazon SQS."

---

### F8: Ingestion Engine, Schema Validation & Request Idempotency (NTF-014, NTF-015, NTF-016, NTF-018, NTF-019)

- **Responsibility**: Front-door ingestion pipeline validating E.164 phone numbers, RFC-5322 emails, URLs, and enforcing idempotency keys.
- **Code Reference**: `core/engine.py:50-90 (NotificationRequestPayload), core/engine.py:100-163 (NotificationCoreEngine.ingest_request)`
- **Database Schema**: `IngestionResult (notification_id, status, priority_weight, is_duplicate, recipient_normalized)`
- **Deep Dive Document**: [Read Full Specification](./features/F8-ingestion-schema-idempotency.md)

#### Say It Out Loud
> "I built the request ingestion pipeline in `backend/src/core/engine.py` to act as the strict gatekeeper for the entire messaging platform. Using Pydantic v2, every incoming payload is validated: email addresses are checked against RFC patterns, phone numbers are stripped of delimiters and normalized into E.164 international format, and webhook targets are validated as HTTP/HTTPS URLs. Next, the engine generates a globally unique notification ID prefixed with `ntf_` and queries the database for an existing record matching `tenant_id` and `idempotency_key`. If a matching key is found, the engine immediately returns the existing notification status and ID with `is_duplicate=True`, completely bypassing redundant downstream provider calls. I chose application-level idempotency paired with database unique constraints to eliminate duplicate billing and prevent users from receiving multiple OTP codes. If validation fails, the API responds with a structured 422 error detailing the invalid field. One limitation is that idempotency keys are retained indefinitely; in a massive production environment, I would add a TTL pruning job to archive idempotency keys older than 30 days."

---

### F9: Monotonic State Machine & Priority Preemption (NTF-020, NTF-021)

- **Responsibility**: Finite state machine enforcing legal status transitions and mapping priorities to numerical weights.
- **Code Reference**: `core/engine.py:31-47 (PRIORITY_WEIGHTS, VALID_TRANSITIONS), core/engine.py:164-188 (transition_state)`
- **Database Schema**: `States: PENDING -> QUEUED -> DISPATCHING -> DELIVERED | FAILED | SUPPRESSED`
- **Deep Dive Document**: [Read Full Specification](./features/F9-state-machine-priority.md)

#### Say It Out Loud
> "I designed the notification state machine to guarantee that delivery status transitions are strictly monotonic and auditable. The allowable lifecycle moves from PENDING to QUEUED, then DISPATCHING, and terminates in DELIVERED, SUPPRESSED, or FAILED. Any illegal transition—such as moving backwards from DELIVERED to QUEUED—is caught and rejected with an explicit error. Alongside the state machine, I implemented priority weighting: URGENT maps to 100, HIGH to 50, NORMAL to 10, and LOW to 0. When workers drain the queue, high-priority jobs naturally preempt bulk newsletters. I chose a formal dictionary-driven transition map over ad-hoc status assignments to prevent race conditions during concurrent retries. A limitation is that state changes are synchronous database updates; at higher scales, I would broadcast state events over an event bus like Kafka."

---

### F10: Template Variable Substitution, Localization & Personalization (NTF-033, NTF-034, NTF-037, NTF-039, NTF-041)

- **Responsibility**: Secure template rendering via Jinja2 SandboxedEnvironment with variable substitution, localization fallback, and subject truncation.
- **Code Reference**: `templates/engine.py:21-38 (SandboxedEnvironment render), templates/engine.py:198-260 (substitute_variables, personalize_content, generate_subject)`
- **Database Schema**: `Context merging: merged = {**context, 'user': user_profile}; Sandboxed Jinja2 AST`
- **Deep Dive Document**: [Read Full Specification](./features/F10-template-rendering-personalization.md)

#### Say It Out Loud
> "I built the template rendering and personalization engine in `backend/src/templates/engine.py` to produce customized messaging while protecting our servers against security vulnerabilities. The engine supports two rendering modes: lightweight regex token substitution for simple &#123;&#123;user.name&#125;&#125; variables, and Jinja2's `SandboxedEnvironment` for complex logic like conditional blocks and loops. By using the SandboxedEnvironment, any malicious attempts to exploit Server-Side Template Injection (SSTI) to access Python internals or execute shell commands are completely blocked. Additionally, I implemented a language fallback chain: if a template in French Canadian (`fr-CA`) is not found, the selector falls back to generic French (`fr`), and finally to default English (`en`). Dynamic subjects are sanitized and truncated to 150 characters with an ellipsis to prevent carrier header rejections. If a variable is missing in the payload, the regex replacer preserves the token or provides a graceful fallback rather than crashing. The limitation is that template rendering consumes CPU; I would optimize this by pre-compiling templates into bytecode upon registration."

---

### F11: Multi-Channel Provider Adapters (Email, SMS, Webhook HMAC) (NTF-042, NTF-043, NTF-045, NTF-047, NTF-048)

- **Responsibility**: Abstracted provider drivers for Email, SMS segment calculation, and Webhooks with HMAC-SHA256 signatures.
- **Code Reference**: `channels/providers.py:32-51 (BaseProvider), channels/providers.py:52-102 (Email), channels/providers.py:104-150 (SMS), channels/providers.py:152-204 (Webhook), channels/providers.py:206-241 (ProviderRegistry)`
- **Database Schema**: `ProviderResult (success, provider_id, channel, external_id, error_code, error_message, latency_ms, metadata)`
- **Deep Dive Document**: [Read Full Specification](./features/F11-multichannel-provider-adapters.md)

#### Say It Out Loud
> "I implemented the multi-channel provider layer using the Strategy and Factory design patterns in `backend/src/channels/providers.py`. Microservices interact with a single abstract `BaseProvider` interface and never write channel-specific code. The Email driver validates envelope structures and assigns priority headers. The SMS driver calculates 160-character GSM segments so billing and carrier payload limits are tracked before dispatch. The Webhook provider signs outbound HTTP requests using HMAC-SHA256 over a timestamped payload, formatting an `X-Signature-SHA256` header (`t=timestamp,v1=signature`) that allows receiving servers to prevent replay attacks. All adapters track network execution latency in milliseconds and return a normalized `ProviderResult`. I chose this polymorphic adapter approach over vendor SDKs to keep our service mesh completely decoupled from external vendors. If an invalid phone number or email reaches the provider, it returns a normalized PERMANENT error code without throwing an unhandled exception. The limitation is that mock drivers are currently configured in-memory; in a production deployment, these adapters would call the actual HTTP APIs of SendGrid, Twilio, and AWS SES via connection-pooled HTTP clients like `httpx`."

---

### F12: Provider Selection, Capabilities Matrix & Automatic Fallback (NTF-051, NTF-052, NTF-054)

- **Responsibility**: Deterministic provider capability filtering, cost optimization, and multi-provider failover routing.
- **Code Reference**: `channels/capabilities.py:10-60 (ProviderCapabilities, ProviderCapabilityMatrix), channels/selection.py:10-72 (ProviderSelector)`
- **Database Schema**: `Sort key: (health_rank: 0=healthy, cost_per_message_cents: ASC, provider_id: ASC)`
- **Deep Dive Document**: [Read Full Specification](./features/F12-provider-selection-fallback.md)

#### Say It Out Loud
> "I designed the provider selection and fallback engine to guarantee reliable delivery even during major third-party cloud outages. In `backend/src/channels/capabilities.py`, each registered provider declares a capability matrix: supported channels, attachment limits, template support, maximum payload size, and cost per message. When a dispatch request occurs, `ProviderSelector` filters candidate providers based on required features and health status. Eligible providers are deterministically sorted: healthy providers come first, then lowest cost per message, with provider ID as an alphabetical tie-breaker. If the primary provider experiences elevated errors or timeouts, the dispatcher automatically cascades down the pre-calculated fallback chain to the secondary provider—for example, switching from SendGrid to AWS SES—without losing the message or requiring human intervention. I chose deterministic sorting over random load balancing because enterprise billing teams require predictable cost optimization. If all providers in the chain fail, the notification is marked for retry or sent to the DLQ. A limitation is that health status is currently polled; I would improve this by integrating an active circuit breaker state machine like Netflix Hystrix with sliding-window error rate triggers."

---

### F13: Asynchronous Dispatcher Workers & Rate-Limited Token Bucket (NTF-060, NTF-062, NTF-068, NTF-069)

- **Responsibility**: High-throughput asynchronous dispatcher workers with token bucket rate limiting and non-blocking polling.
- **Code Reference**: `queues/dispatcher.py:24-50 (TokenBucketRateLimiter), queues/dispatcher.py:127-185 (DispatcherWorker)`
- **Database Schema**: `TokenBucket: (tokens = min(cap, tokens + elapsed * rate_rps); tokens >= 1.0)`
- **Deep Dive Document**: [Read Full Specification](./features/F13-dispatcher-workers-ratelimiting.md)

#### Say It Out Loud
> "I built the asynchronous dispatcher worker and rate-limiting system in `backend/src/queues/dispatcher.py` to consume queued notifications efficiently while protecting upstream provider quotas. The worker continuously leases notifications using our database lease manager. Before dispatching to a provider, it queries an in-memory `TokenBucketRateLimiter` configured per provider or tenant. The token bucket refills continuously based on elapsed monotonic clock time; if sufficient tokens exist, a token is decremented and delivery proceeds. If the rate limit is exceeded, the worker yields execution without dropping the message, leaving it in the queue until the bucket refills. I chose the token bucket algorithm over a fixed window because it smoothly accommodates legitimate bursts while strictly bounding average throughput, preventing provider 429 throttling. Our test suite includes a test with 20 concurrent workers draining 100 jobs simultaneously, proving zero duplicate processing and 100% item delivery. One limitation of an in-memory token bucket is that rate limits are enforced per process; to scale across a multi-node worker cluster, I would migrate the token bucket to Redis using Lua scripts."

---

### F14: Failure Classification, Exponential Backoff & DLQ Redrive/Replay (NTF-070, NTF-071, NTF-073, NTF-075, NTF-076, NTF-077, NTF-078, NTF-081, NTF-082, NTF-083)

- **Responsibility**: Resilience engine classifying errors into transient vs permanent, calculating backoff with jitter, and managing DLQ redrives.
- **Code Reference**: `retries/failure.py:30-94 (FailureClassifier), retries/failure.py:95-129 (RetryPolicy), retries/failure.py:153-330 (DeadLetterQueueManager)`
- **Database Schema**: `dead_letter_queue (id, notification_id, tenant_id, failure_reason, attempt_count, created_at)`
- **Deep Dive Document**: [Read Full Specification](./features/F14-failure-handling-dlq-replay.md)

#### Say It Out Loud
> "I designed the failure handling and recovery engine in `backend/src/retries/failure.py` to build enterprise resilience into our messaging pipeline. When a delivery fails, the `FailureClassifier` evaluates the error code or HTTP response. Permanent errors—like invalid recipient addresses, malformed payloads, or 401 unauthorized—are immediately marked non-retryable and moved to FAILED status, preventing wasted provider spend. Transient errors—like 429 rate limits, 503 service unavailable, or network timeouts—trigger our exponential backoff retry policy. The retry policy calculates delay using the formula `min(max_delay, base_delay * 2^(attempt-1))` with full jitter to prevent thundering herd spikes against recovering providers, while honoring any upstream `Retry-After` HTTP headers. When a notification exhausts all retries, it is routed into the Dead-Letter Queue (DLQ). The operations console can inspect failed messages and trigger manual retries or full replays. Reprocessing a DLQ item re-queues the notification, records a new delivery attempt, and logs an immutable audit event without duplicating delivered alerts. A limitation is that retried messages go back into the main queue; I would improve this by creating dedicated retry delay queues."

---

### F15: Timezone-Aware Quiet Hours, Frequency Capping & Opt-Out Suppression (NTF-086, NTF-088, NTF-089, NTF-090, NTF-093)

- **Responsibility**: Compliance and user experience engine suppressing promotional notifications during recipient quiet hours and daily caps.
- **Code Reference**: `preferences/routing.py:43-81 (is_in_quiet_hours with DST), preferences/routing.py:82-97 (get_daily_send_count), preferences/routing.py:98-180 (evaluate_dispatch)`
- **Database Schema**: `SuppressionReason: OPT_OUT_GLOBAL | OPT_OUT_CHANNEL | OPT_OUT_CATEGORY | FREQUENCY_CAPPED | QUIET_HOURS`
- **Deep Dive Document**: [Read Full Specification](./features/F15-quiet-hours-frequency-capping.md)

#### Say It Out Loud
> "I built the quiet hours and frequency capping engine in `backend/src/preferences/routing.py` to prevent notification fatigue and ensure compliance with telecom quiet-hours regulations. When evaluating an outbound notification, the engine converts current UTC time into the recipient's local IANA timezone using Python's `zoneinfo` module, properly accounting for Daylight Saving Time shifts. The quiet-hours algorithm seamlessly handles overnight wrap-around windows—such as 10:00 PM to 8:00 AM—where start time is numerically greater than end time. If the recipient is in quiet hours or has exceeded their daily frequency cap over a rolling 24-hour window, promotional notifications are suppressed and transitioned to SUPPRESSED status with a clear audit reason. However, critical transactional alerts and URGENT priority messages like password resets and fraud warnings bypass quiet hours and frequency caps completely. I chose native `zoneinfo` over UTC offsets because offsets do not adapt to daylight saving transitions. If an invalid timezone string is provided, the engine safely falls back to UTC. One enhancement I would add is quiet-hours queuing, where suppressed messages are held and automatically released when the recipient's local morning window opens."

---

### F16: RESTful Delivery, Scheduling, Retry & Template APIs (NTF-098, NTF-099, NTF-100, NTF-101, NTF-103, NTF-105, NTF-109, NTF-110)

- **Responsibility**: Unified REST API endpoints for dispatching, status tracking, delayed scheduling, DLQ reprocessing, and health checks.
- **Code Reference**: `api/app.py:107-140 (Health & Ready), api/app.py:192-315 (Delivery API), api/app.py:319-365 (Schedule API), api/app.py:371-450 (Retry & DLQ API), api/app.py:481-515 (Template API)`
- **Database Schema**: `FastAPI ASGI routes with Pydantic request/response models and OpenAPI documentation`
- **Deep Dive Document**: [Read Full Specification](./features/F16-backend-apis-services.md)

#### Say It Out Loud
> "I implemented the core REST API layer in `backend/src/api/app.py` using FastAPI to provide a clean, asynchronous interface for our entire microservice architecture. The API exposes unified endpoints: `/api/v1/delivery` for ingesting notifications across any channel, `/api/v1/schedule` for future-dated dispatch, `/api/v1/notifications/{id}/retry` and `/replay` for operator interventions, and `/api/v1/dlq/reprocess` for batch dead-letter recovery. The application includes liveness (`/healthz`) and readiness (`/readyz`) probes that verify database connectivity for Kubernetes orchestration. I configured global middleware that injects a unique `X-Request-ID` into every HTTP response header and formats all unhandled exceptions into structured JSON error envelopes. I chose FastAPI over Flask or Django because its asynchronous nature and Pydantic integration offer high throughput and automatic Swagger documentation. If a client submits malformed data, FastAPI returns a detailed 422 Unprocessable Entity response highlighting the invalid parameter. The limitation is that our API currently handles ingress synchronously; at 50,000 requests per second, I would place an API Gateway and an ingestion queue buffer like Kafka in front of these endpoints."

---

### F17: Structured Logging & Prometheus Metrics Telemetry (NTF-114, NTF-116, NTF-117)

- **Responsibility**: Telemetry engine generating structured JSON audit logs and Prometheus counters/gauges for delivery latency and error rates.
- **Code Reference**: `observability/metrics.py:12-143 (DeliveryMetricsTracker), observability/structured_logger.py:1-60 (StructuredLogger)`
- **Database Schema**: `Metrics: notification_delivery_success_total, notification_delivery_failure_total, p50/p95 latency distributions`
- **Deep Dive Document**: [Read Full Specification](./features/F17-observability-telemetry.md)

#### Say It Out Loud
> "I built the observability subsystem in `backend/src/observability/metrics.py` to give engineering and operations teams real-time visibility into messaging health. The `DeliveryMetricsTracker` records every delivery attempt, calculating p50 and p95 latency percentiles, overall success rates, and error code distributions across providers and channels. It formats these metrics into standard Prometheus exposition format via the `/metrics` endpoint. In `backend/src/observability/structured_logger.py`, all application logs are output as structured JSON objects containing timestamps, log levels, tenant IDs, and request correlation IDs. I chose structured JSON over plain text logs so that log ingestion systems like Datadog, Elasticsearch, and CloudWatch can parse and index fields without fragile regular expressions. If an unexpected error occurs, the logger automatically serializes the full stack trace. A limitation of our in-memory metrics tracker is that metrics reset on process restart; for multi-node deployments, I would export metrics directly to a Prometheus Pushgateway or StatsD daemon."

---

### F18: Security, Hashed API Keys, RBAC & Tenant Isolation (NTF-125, NTF-126, NTF-127, NTF-133)

- **Responsibility**: Zero-trust security layer enforcing SHA-256 API key hashing, deny-by-default RBAC roles, and adversarial tenant isolation.
- **Code Reference**: `security/auth.py:18-55 (Role, Permission, ROLE_PERMISSIONS), security/auth.py:57-78 (AuthContext, verify_tenant), security/auth.py:83-132 (authenticate_request, require_permission)`
- **Database Schema**: `api_keys (id, tenant_id, key_hash, role, name, is_active); audit_records (id, tenant_id, actor, action, resource_type, resource_id, details_json)`
- **Deep Dive Document**: [Read Full Specification](./features/F18-security-rbac-tenant-isolation.md)

#### Say It Out Loud
> "I designed the security and access control architecture in `backend/src/security/auth.py` adhering to zero-trust principles. Calling microservices authenticate using an API key passed in the `X-API-Key` or `Authorization: Bearer` header. The raw API key is never stored in plaintext; instead, it is hashed using SHA-256 and matched against the `api_keys` database table. I implemented a deny-by-default Role-Based Access Control (RBAC) model with three roles: ADMIN, OPERATOR, and VIEWER. Each endpoint enforces strict permission checks: for example, triggering a DLQ replay requires `notification:retry`, which is granted only to ADMIN and OPERATOR roles. Furthermore, every request enforces adversarial multi-tenant data isolation: if a token belonging to Tenant A attempts to access Tenant B's notification or preference records, the `verify_tenant` method immediately aborts the request with a 403 Forbidden. Every administrative action automatically generates an immutable entry in the `audit_records` table. If an invalid or revoked key is provided, the API returns a 401 Unauthorized. A future enhancement would be adding mutual TLS (mTLS) for inter-service communication."

---

### F19: Operations Console UI & Real-Time Monitoring (NTF-139, NTF-140, NTF-141, NTF-146, NTF-148, NTF-150)

- **Responsibility**: Responsive single-page operations dashboard with real-time delivery logs, provider fleet health, queue depth, and DLQ viewer.
- **Code Reference**: `frontend/src/app.js:1-140 (Navigation, Modals, Forms), frontend/src/app.js:150-455 (API fetching, state management, renderers)`
- **Database Schema**: `Tabs: Live Delivery Console, Provider Fleet Dashboard, Queue & Worker Monitoring, Dead-Letter Queue Viewer`
- **Deep Dive Document**: [Read Full Specification](./features/F19-operations-console.md)

#### Say It Out Loud
> "I built the frontend operations console using semantic HTML5, modern vanilla JavaScript, and a custom dark-mode CSS design system to give on-call engineers an immediate visual command center. The console features four operational views: an Overview dashboard displaying live delivery KPI counters and a direct notification dispatch form, a Provider Fleet dashboard showing vendor capabilities and status, a Queue Monitor showing backlog depth across priority tiers, and a Dead-Letter Queue viewer with one-click manual redrive buttons. Clicking any notification opens a diagnostic modal displaying the complete delivery attempt history with provider latencies. I chose vanilla JavaScript and native CSS over React or Vue for this internal console to achieve instantaneous load times with zero build-step overhead and zero client bundle bloat. If the backend API is unreachable, the console displays helpful fallback cards and error toasts rather than crashing. One future improvement would be replacing our periodic polling with Server-Sent Events (SSE) or WebSockets to stream live delivery updates instantly."

---

