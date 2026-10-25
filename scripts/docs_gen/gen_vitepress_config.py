"""
VitePress Configuration and Theme Generator.
Generates:
- docs/.vitepress/config.mjs
- docs/.vitepress/theme/index.js
- docs/.vitepress/theme/custom.css
- docs/index.md
- docs/README.md
"""

import os

def generate_vitepress_config(docs_dir: str):
    vp_dir = os.path.join(docs_dir, ".vitepress")
    theme_dir = os.path.join(vp_dir, "theme")
    os.makedirs(theme_dir, exist_ok=True)

    # config.mjs
    config_content = """import { defineConfig } from 'vitepress';
import { withMermaid } from 'vitepress-plugin-mermaid';

export default withMermaid(
  defineConfig({
    title: 'OmniPost Documentation',
    description: 'Enterprise Omnichannel Notification Delivery Router & Platform in Python, FastAPI, and React.',
    appearance: 'dark',
    base: '/',
    themeConfig: {
      nav: [
        { text: 'Guide', link: '/00a-project-analysis' },
        { text: 'Features', link: '/01-features' },
        { text: 'API Reference', link: '/03-api-reference' },
        { text: 'System Design', link: '/system-design/' },
        { text: 'Tech Choices', link: '/04-tech-comparisons' },
        { text: 'Interview Q&A', link: '/09-interview-qa' },
        { text: 'Say It Out Loud', link: '/14-say-it-out-loud' },
        { text: 'Checklist', link: '/13-master-checklist' }
      ],
      sidebar: [
        {
          text: 'Project Overview',
          collapsed: false,
          items: [
            { text: 'Project Type Detection', link: '/00-project-type' },
            { text: 'Full Project Analysis', link: '/00a-project-analysis' },
            { text: '30s & 2m Pitch', link: '/00b-project-pitch' },
            { text: 'Project Map & Hierarchy', link: '/00-project-map' }
          ]
        },
        {
          text: 'Feature Specifications',
          collapsed: false,
          items: [
            { text: 'Feature Inventory (Overview)', link: '/01-features' },
            { text: 'F1: Notification Database', link: '/features/F1-notification-database' },
            { text: 'F2: Template Store & Registry', link: '/features/F2-template-store-registry' },
            { text: 'F3: User Preference Store', link: '/features/F3-user-preference-store' },
            { text: 'F4: Delivery Attempt Store', link: '/features/F4-delivery-attempt-store' },
            { text: 'F5: Provider Config & Encryption', link: '/features/F5-provider-config-store' },
            { text: 'F6: Scheduled Job Store', link: '/features/F6-scheduled-job-store' },
            { text: 'F7: Queue State & Lease Locking', link: '/features/F7-queue-state-store' },
            { text: 'F8: Ingestion & Idempotency', link: '/features/F8-ingestion-schema-idempotency' },
            { text: 'F9: State Machine & Priority', link: '/features/F9-state-machine-priority' },
            { text: 'F10: Template Personalization', link: '/features/F10-template-rendering-personalization' },
            { text: 'F11: Multi-Channel Adapters', link: '/features/F11-multichannel-provider-adapters' },
            { text: 'F12: Provider Selection & Fallback', link: '/features/F12-provider-selection-fallback' },
            { text: 'F13: Workers & Token Bucket', link: '/features/F13-dispatcher-workers-ratelimiting' },
            { text: 'F14: Retries, Backoff & DLQ', link: '/features/F14-failure-handling-dlq-replay' },
            { text: 'F15: Quiet Hours & Frequency Caps', link: '/features/F15-quiet-hours-frequency-capping' },
            { text: 'F16: Backend REST APIs', link: '/features/F16-backend-apis-services' },
            { text: 'F17: Observability & Metrics', link: '/features/F17-observability-telemetry' },
            { text: 'F18: Security, RBAC & Isolation', link: '/features/F18-security-rbac-tenant-isolation' },
            { text: 'F19: Operations Console UI', link: '/features/F19-operations-console' }
          ]
        },
        {
          text: 'Architecture & System Design',
          collapsed: false,
          items: [
            { text: 'System Design Overview', link: '/system-design/' },
            { text: '14.1 Capacity Estimation', link: '/system-design/14.1-requirements-and-estimation' },
            { text: '14.2 Architecture Styles', link: '/system-design/14.2-architecture-styles' },
            { text: '14.3 Networking & Protocols', link: '/system-design/14.3-networking-and-communication' },
            { text: '14.4 Load Balancing & Scaling', link: '/system-design/14.4-load-balancing-and-scaling' },
            { text: '14.5 Databases & Storage Engine', link: '/system-design/14.5-databases-and-storage' },
            { text: '14.6 Caching & Compiled AST', link: '/system-design/14.6-caching' },
            { text: '14.7 Messaging & Priority Queues', link: '/system-design/14.7-messaging-and-queues' },
            { text: '14.8 Consistency & Concurrency', link: '/system-design/14.8-consistency-and-concurrency' },
            { text: '14.9 Reliability & Circuit Breaker', link: '/system-design/14.9-reliability-and-resilience' },
            { text: '14.10 Rate Limiting Algorithms', link: '/system-design/14.10-api-design-and-rate-limiting' },
            { text: '14.11 Security & Zero Trust', link: '/system-design/14.11-security-architecture' },
            { text: '14.12 Search & AI Integration', link: '/system-design/14.12-search-and-ai-architecture' },
            { text: '14.13 Real-Time Webhooks & SSE', link: '/system-design/14.13-real-time-systems' },
            { text: '14.14 Observability & Prometheus', link: '/system-design/14.14-observability-and-operations' },
            { text: '14.15 Performance Engineering', link: '/system-design/14.15-performance-engineering' },
            { text: '14.16 Cost Modeling & Economics', link: '/system-design/14.16-cost-and-trade-offs' },
            { text: '14.17 Classic System Design Problems', link: '/system-design/14.17-classic-system-design' },
            { text: 'Architecture Decisions (ADR Log)', link: '/system-design/decisions' }
          ]
        },
        {
          text: 'Technical Deep Dives',
          collapsed: false,
          items: [
            { text: 'Step-by-Step Build Order', link: '/02-build-order' },
            { text: 'API Reference (All Endpoints)', link: '/03-api-reference' },
            { text: 'Tech Choices Comparisons', link: '/04-tech-comparisons' },
            { text: 'System Architecture', link: '/05-architecture' },
            { text: 'Security Audit & OWASP Top 10', link: '/06-security' },
            { text: 'AI Integration Deep Dive', link: '/07-ai-integration' },
            { text: 'Quality & Operations (114 Tests)', link: '/08-quality-and-ops' }
          ]
        },
        {
          text: 'Interview & Readiness',
          collapsed: false,
          items: [
            { text: 'Interview Q&A (150+ Questions)', link: '/09-interview-qa' },
            { text: 'Say It Out Loud (Spoken Scripts)', link: '/14-say-it-out-loud' },
            { text: 'Gaps & Production Roadmap', link: '/10-gaps-and-improvements' },
            { text: 'Technical Glossary', link: '/11-glossary' },
            { text: 'Developer Confirmation List', link: '/12-confirm-list' },
            { text: 'Master Checklist (All 275 Items)', link: '/13-master-checklist' }
          ]
        }
      ],
      search: {
        provider: 'local'
      },
      outline: [2, 3]
    },
    mermaid: {
      theme: 'dark'
    },
    vite: {
      optimizeDeps: {
        include: ['mermaid', 'fastdom', 'fastdom/extensions/fastdom-promised.js']
      },
      ssr: {
        noExternal: ['mermaid', 'vitepress-plugin-mermaid', 'fastdom']
      }
    }
  })
);
"""
    with open(os.path.join(vp_dir, "config.mjs"), "w") as fp:
        fp.write(config_content)

    # theme/index.js
    theme_js = """import DefaultTheme from 'vitepress/theme';
import './custom.css';

export default {
  ...DefaultTheme
};
"""
    with open(os.path.join(theme_dir, "index.js"), "w") as fp:
        fp.write(theme_js)

    # theme/custom.css (Pure black dark mode #000000)
    custom_css = """:root {
  --vp-c-brand: #ec4899;
  --vp-c-brand-light: #f472b6;
  --vp-c-brand-dark: #db2777;
  --vp-font-family-base: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif;
  --vp-font-family-mono: 'JetBrains Mono', source-code-pro, Menlo, Monaco, Consolas, "Courier New", monospace;
}

.dark {
  --vp-c-bg: #000000 !important;
  --vp-c-bg-alt: #000000 !important;
  --vp-c-bg-elv: #0a0a0a !important;
  --vp-c-bg-soft: #0a0a0a !important;
  --vp-sidebar-bg-color: #000000 !important;
  --vp-c-border: #222222 !important;
  --vp-c-divider: #222222 !important;
}

html.dark body {
  background-color: #000000 !important;
  color: #f1f5f9;
}

table {
  display: table;
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
}

th, td {
  border: 1px solid #262626 !important;
  padding: 0.65rem 1rem !important;
}

th {
  background-color: #121212 !important;
  font-weight: 600;
}
"""
    with open(os.path.join(theme_dir, "custom.css"), "w") as fp:
        fp.write(custom_css)

    # docs/index.md (Hero home page)
    index_md = """---
layout: home

hero:
  name: "OmniPost"
  text: "Omnichannel Notification Delivery Platform"
  tagline: "Prioritized queues, automated circuit breaker provider fallback, exponential backoff retries, and timezone-aware quiet-hours compliance."
  actions:
    - theme: brand
      text: Project Overview
      link: /00a-project-analysis
    - theme: alt
      text: 2-Minute Pitch
      link: /00b-project-pitch
    - theme: alt
      text: System Design
      link: /system-design/
    - theme: alt
      text: Master Checklist (275)
      link: /13-master-checklist

features:
  - title: "F1-F7: Relational State Ledgers"
    details: "Nine relational tables powering immutable delivery tracking, versioned templates, user preferences, and lease-based queue states."
    link: /features/F1-notification-database
  - title: "F8-F9: Monotonic State Machine"
    details: "Strict request idempotency with E.164 phone and email normalization, and 4-tier priority preemption (URGENT, HIGH, NORMAL, LOW)."
    link: /features/F9-state-machine-priority
  - title: "F10: SSTI-Safe Template Engine"
    details: "Jinja2 SandboxedEnvironment preventing template injection attacks while enabling dynamic conditionals, loops, and language fallback."
    link: /features/F10-template-rendering-personalization
  - title: "F11-F12: Provider Fallback Routing"
    details: "Polymorphic drivers for Email, SMS segments, and Webhook HMAC-SHA256 with deterministic cost and health failover."
    link: /features/F12-provider-selection-fallback
  - title: "F13-F14: Workers, Backoff & DLQ"
    details: "Asynchronous workers with token bucket rate limiting, exponential backoff with full jitter, and manual DLQ redrive APIs."
    link: /features/F14-failure-handling-dlq-replay
  - title: "F15: Timezone-Aware Quiet Hours"
    details: "Enforces quiet hours with midnight wrap-around and rolling 24-hour frequency capping across global timezones with DST."
    link: /features/F15-quiet-hours-frequency-capping
  - title: "F16-F18: Security & Zero-Trust RBAC"
    details: "FastAPI REST API protected by SHA-256 hashed API keys, deny-by-default RBAC, and adversarial multi-tenant data isolation."
    link: /features/F18-security-rbac-tenant-isolation
  - title: "High-Scale Systems Design"
    details: "Comprehensive architectural deep dive modeling 10 million notifications/day across 17 technical chapters and an ADR log."
    link: /system-design/14.1-requirements-and-estimation
  - title: "Interview Ready Q&A (150+)"
    details: "150+ categorized technical questions and answers paired with first-person 'Say It Out Loud' interview rehearsal scripts."
    link: /09-interview-qa
---
"""
    with open(os.path.join(docs_dir, "index.md"), "w") as fp:
        fp.write(index_md)

    # docs/README.md
    readme_md = """# OmniPost Documentation Index

Welcome to the documentation suite for **OmniPost (20-Notification-Delivery-Platform)**.

## Reading Order

1. [Step 0: Project Type Classification](./00-project-type.md)
2. [Step 0: Full Project Analysis & Traces](./00a-project-analysis.md)
3. [Step 2.5: 30s & 2m Technical Pitch](./00b-project-pitch.md)
4. [Step 1: Project Map & Codebase Hierarchy](./00-project-map.md)
5. [Step 2: Feature Inventory Overview](./01-features.md)
   - [F1: Notification Database](./features/F1-notification-database.md)
   - [F2: Template Store & Versioning](./features/F2-template-store-registry.md)
   - [F3: User Preference Store](./features/F3-user-preference-store.md)
   - [F4: Delivery Attempt Store](./features/F4-delivery-attempt-store.md)
   - [F5: Provider Config & Encryption](./features/F5-provider-config-store.md)
   - [F6: Scheduled Job Store](./features/F6-scheduled-job-store.md)
   - [F7: Queue State & Lease Locking](./features/F7-queue-state-store.md)
   - [F8: Ingestion & Idempotency](./features/F8-ingestion-schema-idempotency.md)
   - [F9: State Machine & Priority](./features/F9-state-machine-priority.md)
   - [F10: Template Rendering & SSTI](./features/F10-template-rendering-personalization.md)
   - [F11: Multi-Channel Adapters](./features/F11-multichannel-provider-adapters.md)
   - [F12: Provider Selection & Fallback](./features/F12-provider-selection-fallback.md)
   - [F13: Workers & Token Bucket](./features/F13-dispatcher-workers-ratelimiting.md)
   - [F14: Retries, Backoff & DLQ](./features/F14-failure-handling-dlq-replay.md)
   - [F15: Quiet Hours & Frequency Caps](./features/F15-quiet-hours-frequency-capping.md)
   - [F16: Backend REST APIs](./features/F16-backend-apis-services.md)
   - [F17: Observability & Telemetry](./features/F17-observability-telemetry.md)
   - [F18: Security, RBAC & Isolation](./features/F18-security-rbac-tenant-isolation.md)
   - [F19: Operations Console UI](./features/F19-operations-console.md)
6. [Step 3: Step-by-Step Build Order](./02-build-order.md)
7. [Step 4: Complete API Reference](./03-api-reference.md)
8. [Step 5: Technology Choices Comparisons](./04-tech-comparisons.md)
9. [Step 6: System Architecture & Scaling](./05-architecture.md)
10. [Step 7: Security Audit & OWASP Top 10](./06-security.md)
11. [Step 8: AI Integration Deep Dive](./07-ai-integration.md)
12. [Step 9: Quality Engineering & Operations](./08-quality-and-ops.md)
13. [Step 10: Technical Interview Q&A (150+)](./09-interview-qa.md)
14. [Step 2.5: Say It Out Loud (Spoken Scripts)](./14-say-it-out-loud.md)
15. [Step 11: Gaps & Production Roadmap](./10-gaps-and-improvements.md)
16. [Step 12: Technical Glossary](./11-glossary.md)
17. [Step 12: Developer Confirmation List](./12-confirm-list.md)
18. [Step 13: Master Checklist (All 275 Items)](./13-master-checklist.md)
19. [Step 14: System Design Deep Dive Suite](./system-design/)
"""
    with open(os.path.join(docs_dir, "README.md"), "w") as fp:
        fp.write(readme_md)

if __name__ == "__main__":
    generate_vitepress_config("/Users/avishjain/avishjain9-repos/20-notification-delivery-platform/docs")
    print("VitePress configuration and themes generated.")
