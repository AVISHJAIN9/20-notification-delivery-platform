# Step 1: Project Structure & Dependency Map

## File Hierarchy

```
20-notification-delivery-platform/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   └── app.py                  # FastAPI application entry, routers, CORS & error middleware
│   │   ├── channels/
│   │   │   ├── capabilities.py         # Provider capability matrix & feature filtering (NTF-051)
│   │   │   ├── credentials.py          # Fernet symmetric encryption & log masking (NTF-049)
│   │   │   ├── providers.py            # Email, SMS, and Webhook HMAC adapters & registry (NTF-042 - NTF-048)
│   │   │   └── selection.py            # Deterministic cost & health provider selection (NTF-052)
│   │   ├── clock.py                    # Deterministic time provider for testing (Clock)
│   │   ├── core/
│   │   │   └── engine.py               # Notification core ingestion, validation, state machine (NTF-014 - NTF-021)
│   │   ├── db/
│   │   │   └── database.py             # SQLAlchemy AsyncEngine & AsyncSessionLocal setup
│   │   ├── models/
│   │   │   └── store.py                # 9 relational schemas & NotificationStoreManager CRUD operations
│   │   ├── observability/
│   │   │   ├── metrics.py              # Prometheus metrics tracker (latencies, counts, rates)
│   │   │   └── structured_logger.py    # Structured JSON log formatting with context injection
│   │   ├── preferences/
│   │   │   └── routing.py              # Timezone quiet hours, frequency capping & opt-out rules (NTF-084 - NTF-093)
│   │   ├── queues/
│   │   │   └── dispatcher.py           # Priority queues, lease-based locking, token bucket limiter (NTF-056 - NTF-062)
│   │   ├── retries/
│   │   │   └── failure.py              # Error classification, exponential backoff, DLQ manager (NTF-070 - NTF-083)
│   │   ├── security/
│   │   │   └── auth.py                 # SHA-256 API key authentication, RBAC, tenant isolation (NTF-125 - NTF-127)
│   │   └── templates/
│   │       └── engine.py               # Jinja2 Sandboxed template engine, personalization, approval (NTF-028 - NTF-041)
│   └── tests/                          # 56 automated pytest test suites (114 passing tests)
├── frontend/
│   ├── src/
│   │   ├── app.js                      # Vanilla JavaScript operations console controller & API client
│   │   ├── index.css                   # Premium pure-dark glassmorphic CSS design system
│   │   └── index.html                  # Operations console layout (Delivery Feed, Providers, Queues, DLQ)
│   └── tests/                          # Frontend integration test suites
├── docs/                               # VitePress documentation portal (Vue.js style)
├── FEATURES.csv                        # Master feature traceability matrix
├── PROGRESS.md                         # Milestone implementation progress log
├── SPEC.txt                            # System design specification & invariants
└── package.json                        # VitePress documentation tooling dependencies
```

---

## Technology Stack & Exact Versions

| Component | Technology | Version | Purpose in Project |
| :--- | :--- | :--- | :--- |
| **Backend Runtime** | Python | `3.13.9` | High-performance asynchronous execution runtime. |
| **Web Framework** | FastAPI | `>=0.115.0` | Asynchronous ASGI REST API framework with OpenAPI generation. |
| **Data Validation** | Pydantic | `>=2.9.0` | Strongly-typed request/response validation and settings management. |
| **ORM / Persistence** | SQLAlchemy | `>=2.0.35` | Async SQL toolkit, declarative models, and query builder. |
| **Async DB Driver** | aiosqlite | `>=0.20.0` | Asynchronous SQLite driver for unit/integration testing. |
| **Templating Engine** | Jinja2 | `>=3.1.4` | Sandboxed template parsing and variable interpolation. |
| **Security Encryption**| Cryptography | `>=43.0.0` | Fernet AES-128-CBC credential encryption at rest. |
| **Testing Framework** | Pytest | `8.4.2` | Test runner and assertion framework. |
| **Async Testing** | pytest-asyncio| `1.4.0` | AsyncIO event loop fixture management. |
| **Documentation** | VitePress | `^1.6.4` | Pure black Vue.js-style static documentation site generator. |
| **Diagrams Tooling** | Mermaid.js | `^11.4.1` | Native markdown diagram rendering plugin for VitePress. |

---

## Environment Variables & Configuration

| Variable Name | Required | Default Value | Purpose | Code Location |
| :--- | :--- | :--- | :--- | :--- |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///:memory:` | SQLAlchemy database connection URI. | `backend/src/db/database.py:9` |
| `PORT` | No | `8200` | Port for FastAPI backend application. | `SPEC.txt:6` |
| `PROVIDER_CREDENTIAL_KEY` | No | `default-notification-platform-secret-32b` | Symmetric key for Fernet credential encryption. | `backend/src/channels/credentials.py:28` |
| `LOG_LEVEL` | No | `INFO` | Logging threshold level (DEBUG, INFO, WARN, ERROR). | `backend/src/observability/structured_logger.py` |
