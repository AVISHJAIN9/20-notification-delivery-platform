import { defineConfig } from 'vitepress';
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
