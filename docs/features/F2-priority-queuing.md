# F2: Multi-Tier Priority Scheduling

## Technical Specification
HIGH, MEDIUM, and LOW priority queues guaranteeing instant OTP delivery.

```mermaid
flowchart LR
    Request[Notification Request] --> Priority[Priority Queue]
    Priority --> Breaker{Circuit Breaker Closed?}
    Breaker -->|Yes| Primary[Primary Provider]
    Breaker -->|No / Failed| Secondary[Secondary Failover Provider]
```
