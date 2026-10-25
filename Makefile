.PHONY: test up down clean run audit verify lint e2e

test:
	PYTHONPATH=backend/src python -m pytest backend/tests frontend/tests -v

audit:
	python3 ../../tools/audit_fakes.py --project .

verify: audit test

lint:
	python3 -m ruff check backend/ || true

e2e:
	PYTHONPATH=backend/src pytest backend/tests frontend/tests -v

up:
	docker compose -f deploy/docker-compose.yml up -d

down:
	docker compose -f deploy/docker-compose.yml down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +

run:
	PYTHONPATH=backend/src uvicorn api.app:app --host 0.0.0.0 --port 8200 --reload
