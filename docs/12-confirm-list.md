# Step 12: Items Requiring Developer Confirmation [CONFIRM WITH DEVELOPER]

This document lists all architectural assumptions identified during code inspection that require verification with the lead developer or systems architect.

---

| Item ID | Topic / Assumption | Code Reference | Developer Question & Context |
| :--- | :--- | :--- | :--- |
| **C1** | Primary & Secondary Provider Credentials | `channels/providers.py:98-100` | [CONFIRM WITH DEVELOPER]: Confirm whether SendGrid and AWS SES are the designated primary/secondary email vendors in staging and production environments. |
| **C2** | Webhook HMAC Secret Rotation Policy | `channels/providers.py:158` | [CONFIRM WITH DEVELOPER]: Confirm how often webhook signing secrets are rotated and whether dual-signing verification windows are supported for downstream consumers. |
| **C3** | Default Quiet-Hours Window | `preferences/routing.py:50` | [CONFIRM WITH DEVELOPER]: Confirm whether the default quiet-hours window should remain 22:00 to 08:00 or if tenant-specific default overrides are planned. |
| **C4** | Kafka vs Redis Streams Migration | `docs/system-design/14.7-messaging-and-queues.md` | [CONFIRM WITH DEVELOPER]: Confirm whether Apache Kafka or AWS SQS FIFO is the preferred cloud message broker for Phase 3 horizontal scaling. |
| **C5** | Idempotency Key Retention Window | `core/engine.py:124` | [CONFIRM WITH DEVELOPER]: Confirm the planned TTL for idempotency key pruning (e.g. 30 days vs 90 days) in production PostgreSQL. |
