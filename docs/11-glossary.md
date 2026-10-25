# Step 12: Technical Glossary

Simple, precise definitions of technical terms used across OmniPost (`20-notification-delivery-platform`).

- **AsyncIO**: Python's built-in asynchronous framework using an event loop to achieve cooperative multitasking without OS thread overhead.
- **Circuit Breaker**: A resilience design pattern that detects upstream provider failures and temporarily diverts traffic to prevent cascading system crashes.
- **Dead-Letter Queue (DLQ)**: A storage buffer that holds messages that have repeatedly failed delivery and exhausted all retry attempts, isolating them for manual inspection.
- **Exponential Backoff**: An algorithm that exponentially increases the wait time between retry attempts (e.g. 1s, 2s, 4s, 8s) to give recovering services time to stabilize.
- **Full Jitter**: A randomization technique added to exponential backoff that uniformly spreads retry delays between zero and the calculated ceiling to prevent thundering herd spikes.
- **HMAC-SHA256**: Hash-based Message Authentication Code combining a cryptographic hash function with a secret key to verify data integrity and authenticity.
- **Idempotency Key**: A unique client-supplied token that guarantees performing the same operation multiple times produces the exact same outcome without duplicate actions.
- **Jinja2 SandboxedEnvironment**: A restricted AST execution environment that disables access to Python internal methods and dangerous built-ins to block Server-Side Template Injection.
- **Lease-Based Locking**: A distributed concurrency pattern where a worker claims a job for a limited duration (`locked_until`); if the worker dies, the lease expires and another worker reclaims it.
- **Monotonic State Machine**: A finite state machine whose status transitions can only move forward along allowable paths, never regressing to previous states.
- **Provider Capability Matrix**: A registry defining the features, maximum payload sizes, channels, and costs supported by each third-party delivery vendor.
- **Quiet Hours**: Defined nighttime hours (e.g. 22:00 to 08:00) during which non-critical promotional notifications are suppressed to respect user privacy and telecom regulations.
- **Role-Based Access Control (RBAC)**: An authorization approach where permissions are assigned to roles (`ADMIN`, `OPERATOR`, `VIEWER`), and users are assigned to roles.
- **Starvation Protection**: An algorithm that promotes aged, low-priority tasks when high-priority tasks continuously monopolize worker processing capacity.
- **Token Bucket Rate Limiter**: An algorithm that maintains a bucket of tokens refilled at a constant rate; each request consumes a token, allowing controlled bursts while enforcing average throughput.
