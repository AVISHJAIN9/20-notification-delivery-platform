# Step 2.5: Project Pitch (30-Second & 2-Minute Spoken Scripts)

## 30-Second Elevator Pitch
> "I built an enterprise-grade omnichannel notification delivery platform using Python, FastAPI, and React that handles mission-critical alerts across Email, SMS, Push, and Webhooks. It features prioritized queues that ensure two-factor authentication codes bypass marketing blasts, automated provider fallback routing that swaps degraded vendors within 50 milliseconds, and an intelligent quiet-hours engine that suppresses non-urgent alerts during recipient nighttime."

---

## 2-Minute Technical Interview Pitch
> "In distributed platforms, notification delivery is inherently brittle because it depends on third-party provider APIs like SendGrid or Twilio that experience intermittent outages, rate limits, and network latency spikes. Furthermore, marketing bulk broadcasts can easily starve urgent transactional OTPs.
>
> To solve this, I designed and built **OmniPost**, a resilient notification delivery platform.
>
> First, in `backend/src/queues/dispatcher.py`, the system implements a strict Multi-Tier Priority Queue with four priority tiers: URGENT, HIGH, NORMAL, and LOW. Critical authentication OTPs and security alerts enter with a priority weight of 100 and preempt background marketing newsletters, guaranteeing sub-second dispatch latency regardless of queue depth. To prevent low-priority jobs from starving indefinitely, the queue incorporates aging thresholds.
>
> Second, to insulate the platform against third-party provider outages, I built an automated Provider Selection and Fallback Engine in `backend/src/channels/selection.py`. When an upstream provider returns HTTP 5xx errors or connection timeouts, the system automatically shifts traffic to a secondary failover provider (such as AWS SES or Vonage) deterministically based on health and cost without dropping messages.
>
> Third, for failed messages, the system implements exponential backoff retries with full jitter in `backend/src/retries/failure.py`. Messages that exhaust their retry budget are routed to a Dead-Letter Queue with automated manual redrive and replay capabilities, generating new delivery attempts and immutable audit records.
>
> Fourth, an intelligent Preference Routing Engine in `backend/src/preferences/routing.py` respects user quiet hours based on their local timezone—handling overnight wrap-around windows and Daylight Saving Time adjustments—while enforcing rolling 24-hour frequency capping.
>
> The administrative console provides real-time visibility into queue depth, provider health, and delivery logs. The platform is backed by 114 automated tests running via `pytest`."
