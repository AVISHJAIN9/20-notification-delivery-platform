# Step 9: Engineering Quality, Testing & Operations

## 1. Automated Test Suite Metrics

OmniPost is covered by **114 automated tests** across **56 test modules** running with `pytest` and `pytest-asyncio`.

```
====================== 114 passed, 364 warnings in 3.00s =======================
```

### Key Test Categories
- **Concurrent Drain Verification (`test_concurrent_workers.py`)**: 20 concurrent worker coroutines draining 100 jobs simultaneously, verifying that each job is processed exactly once with zero duplicates.
- **Timezone Matrix & DST (`test_scenarios_p20.py`, `test_quiet_hours.py`)**: Validates quiet hours calculations across New York, London, Tokyo, and Sydney across Daylight Saving Time transitions.
- **Provider Fallback & Circuit Breaker (`test_provider_fallback.py`)**: Simulates primary provider 500 errors and confirms that the secondary provider is selected automatically.
- **Dead-Letter Replay & Redrive (`test_dlq_and_replay.py`)**: Confirms that reprocessing a dead-lettered notification creates a new delivery attempt and audit log entry while preserving original notification ID.
- **SSTI Sandbox Security (`test_templates_advanced.py`)**: Validates that attempts to access `__class__` or execute OS commands inside Jinja2 templates raise sandboxing security exceptions.

---

## 2. Docker & Local Deployment

### Dockerfile
```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/src /app/backend/src
COPY frontend/src /app/frontend/src

ENV PYTHONPATH=/app/backend/src
EXPOSE 8200

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8200"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8200:8200"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:secret@postgres:5432/omnipost
    depends_on:
      - postgres

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=omnipost
    ports:
      - "5420:5432"
```
