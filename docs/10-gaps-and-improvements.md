# Step 11: Gaps, Roadmap & Production Hardening

This document outlines architectural trade-offs knowingly accepted in the current codebase and provides an engineering roadmap ranked by priority (P0, P1, P2) with concrete implementation suggestions.

---

## Priority Engineering Roadmap

| Priority | Feature / Gap | Current State | Production Target & Fix |
| :--- | :--- | :--- | :--- |
| **P0** | **Distributed Message Backbone** | Database table queue (`queue_state`). | Replace relational queue state with **Apache Kafka** or **AWS SQS FIFO** for infinite horizontal queue scaling. |
| **P0** | **Distributed Rate Limiting** | Process-local token bucket (`TokenBucketRateLimiter`). | Migrate token bucket to **Redis Cluster** via Lua scripts (`EVALSHA`) to enforce shared rate limits across worker clusters. |
| **P1** | **Active Circuit Breaker** | Deterministic fallback sorting based on reported health. | Implement sliding-window circuit breakers (CLOSED, OPEN, HALF-OPEN) using Netflix Hystrix or Resilience4j algorithms. |
| **P1** | **Quiet-Hours Postponement Queue** | Suppressed messages terminate in `SUPPRESSED` status. | Add delayed queue release: hold suppressed notifications and automatically dispatch when local morning window opens (e.g. 08:01 AM). |
| **P1** | **Real-Time Console Push** | Operations console polls backend endpoints periodically. | Implement **Server-Sent Events (SSE)** or **WebSockets** for zero-latency live delivery feed updates. |
| **P2** | **Cold Storage Archival** | Delivery attempts remain in primary relational table. | Implement daily pg_partman partition rotation; archive records older than 90 days into ClickHouse or Amazon S3 Parquet. |
| **P2** | **Mutual TLS (mTLS)** | API key authentication in HTTP headers. | Enforce mTLS certificates for all inter-service communication within the service mesh. |
