# Step 5: Technology Choices & Exhaustive Comparisons

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
