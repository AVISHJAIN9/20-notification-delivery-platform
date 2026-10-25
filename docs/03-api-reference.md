# Step 4: Complete API Reference

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
