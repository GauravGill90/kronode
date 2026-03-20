.PHONY: infra backend worker beat frontend install migrate stop restart dev

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

# Kill all running backend/worker/beat/frontend processes
stop:
	@pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@pkill -f "celery -A app.celery_app" 2>/dev/null || true
	@pkill -f "watchfiles.*celery" 2>/dev/null || true
	@pkill -f "next dev" 2>/dev/null || true
	@sleep 1
	@echo "All services stopped."

# Stop everything, then start backend + worker + beat in background
restart: stop
	cd backend && uv run uvicorn app.main:app --reload &
	cd backend && uv run watchfiles --filter python "celery -A app.celery_app worker --loglevel=info --pool=solo" app/ &
	cd backend && uv run celery -A app.celery_app beat --loglevel=info &
	@sleep 2
	@echo "Backend + Worker + Beat restarted."

# Start everything (infra + backend + worker + beat + frontend)
dev: infra
	cd backend && uv run uvicorn app.main:app --reload &
	cd backend && uv run watchfiles --filter python "celery -A app.celery_app worker --loglevel=info --pool=solo" app/ &
	cd backend && uv run celery -A app.celery_app beat --loglevel=info &
	cd frontend && pnpm dev &
	@echo "All services started. Backend: 8000, Frontend: 3000"
