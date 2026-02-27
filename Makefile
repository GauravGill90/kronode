.PHONY: infra backend worker beat frontend install migrate

# Start Postgres + Redis
infra:
	docker-compose up postgres redis -d

# Start FastAPI backend
backend:
	cd backend && uv run uvicorn app.main:app --reload

# Start Celery worker (with auto-reload on file changes)
worker:
	cd backend && uv run watchfiles --filter python "celery -A app.celery_app worker --loglevel=info --pool=solo" app/

# Start Celery beat scheduler (PR polling every 60s)
beat:
	cd backend && uv run celery -A app.celery_app beat --loglevel=info

# Start Next.js frontend
frontend:
	cd frontend && pnpm dev

# Install all dependencies
install:
	cd backend && uv sync
	cd frontend && pnpm install

# Run database migrations
migrate:
	cd backend && uv run alembic upgrade head
