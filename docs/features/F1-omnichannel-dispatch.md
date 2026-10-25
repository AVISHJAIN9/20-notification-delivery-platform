# F1: Omnichannel Notification Dispatch Engine

## Technical Specification
Unified dispatch across Email, SMS, Webhook, and Push channels.

```mermaid
flowchart LR
    Request[Notification Request] --> Priority[Priority Queue]
    Priority --> Breaker{Circuit Breaker Closed?}
    Breaker -->|Yes| Primary[Primary Provider]
    Breaker -->|No / Failed| Secondary[Secondary Failover Provider]
```
