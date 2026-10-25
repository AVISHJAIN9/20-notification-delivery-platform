# Architecture Decision Records (ADR Log)

This log records every major architectural and technical decision made during the development of OmniPost (`20-notification-delivery-platform`).

---

| ADR ID | Decision Title | Status | Deciding Factors | Chosen Solution | Trade-Off Accepted | Revisit When |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ADR-01** | Database Engine Choice | **Accepted** | Need for strict ACID unique constraints on `(tenant_id, idempotency_key)`. | PostgreSQL / SQLite with async SQLAlchemy. | Lower write throughput than Cassandra. | Volume exceeds 500M records. |
| **ADR-02** | Template Sandboxing | **Accepted** | Prevention of Server-Side Template Injection (SSTI) attacks. | Jinja2 `SandboxedEnvironment`. | Slightly higher CPU rendering latency. | Throughput requires pre-compiled bytecode. |
| **ADR-03** | Priority Queue Architecture | **Accepted** | Guarantee that 2FA OTP codes bypass marketing broadcasts. | Multi-tier priority queue with lease-based locking. | Database lock contention at high worker concurrency. | Scale exceeds 10,000 concurrent workers. |
| **ADR-04** | Rate Limiting Algorithm | **Accepted** | Need to allow legitimate bursts while strictly bounding average RPS. | In-memory Token Bucket rate limiter. | Process-local state rather than shared cluster state. | Multi-node deployment requires Redis. |
| **ADR-05** | Credential Security | **Accepted** | Zero-trust protection of third-party API keys in database. | Fernet AES-128 symmetric encryption with log masking. | Key management requires environment variable distribution. | Enterprise deployment adopts AWS KMS / HashiCorp Vault. |
| **ADR-06** | Webhook Authentication | **Accepted** | Verification of webhook payload integrity and anti-replay defense. | HMAC-SHA256 timestamped signatures (`X-Signature-SHA256`). | Receiving clients must implement HMAC verification. | Clients demand mTLS or asymmetric RSA. |
| **ADR-07** | Timezone Quiet Hours | **Accepted** | Compliance with telecom quiet-hours laws and Daylight Saving Time. | Native Python 3.9+ `zoneinfo` module with midnight wrap-around. | Requires system tzdata updates. | Real-time GPS-based geolocation routing needed. |
