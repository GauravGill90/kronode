.PHONY: help infra backend worker beat frontend install migrate stop restart dev test-orchestrator test-quick logs status

# Start Postgres + Redis
infra:
	docker compose up postgres redis -d

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
	@echo "Press Ctrl+C to stop all services, then run 'make stop' to clean up"

# Test the new orchestrator (quick validation)
test-quick:
	cd backend && uv run python test_orchestrator_quick.py

# Test the orchestrator end-to-end (runs real agents)
test-orchestrator:
	cd backend && uv run python test_orchestrator_e2e.py

# Test full stack integration
test-full:
	cd backend && uv run python test_e2e_full_stack.py

# Show status of running services
status:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Service Status:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo -n "Backend (uvicorn):  "
	@pgrep -f "uvicorn app.main:app" > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo -n "Celery Worker:      "
	@pgrep -f "celery -A app.celery_app worker" > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo -n "Celery Beat:        "
	@pgrep -f "celery -A app.celery_app beat" > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo -n "Frontend (Next.js): "
	@pgrep -f "next dev" > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo -n "PostgreSQL:         "
	@docker ps | grep postgres > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo -n "Redis:              "
	@docker ps | grep redis > /dev/null && echo "✓ Running" || echo "✗ Not running"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "URLs:"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Docs:     http://localhost:8000/docs"

# View logs from running services
logs:
	@echo "Tailing logs from all services (Ctrl+C to stop)..."
	@echo "Use 'make logs-backend', 'make logs-worker', or 'make logs-frontend' for specific logs"
	@tail -f backend/logs/*.log 2>/dev/null || echo "No log files found"

logs-backend:
	@docker compose logs -f postgres redis || echo "No docker logs"

logs-worker:
	@echo "Worker logs are in terminal where 'make worker' was run"

logs-frontend:
	@echo "Frontend logs are in terminal where 'make frontend' was run"

# Show help
help:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Kronode - Multi-Flow Orchestrator"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make install        Install all dependencies (backend + frontend)"
	@echo "  make migrate        Run database migrations"
	@echo ""
	@echo "Development Commands:"
	@echo "  make dev            Start everything (infra + backend + worker + frontend)"
	@echo "  make backend        Start FastAPI backend only"
	@echo "  make worker         Start Celery worker only"
	@echo "  make beat           Start Celery beat scheduler only"
	@echo "  make frontend       Start Next.js frontend only"
	@echo "  make infra          Start PostgreSQL + Redis via Docker"
	@echo ""
	@echo "Testing Commands:"
	@echo "  make test-quick     Quick orchestrator validation test"
	@echo "  make test-orchestrator  Full E2E orchestrator test"
	@echo "  make test-full      Full stack integration test"
	@echo ""
	@echo "Utility Commands:"
	@echo "  make status         Show status of all services"
	@echo "  make logs           View logs from all services"
	@echo "  make stop           Stop all running services"
	@echo "  make restart        Restart backend + worker + beat"
	@echo "  make help           Show this help message"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make install     # First time setup"
	@echo "  2. make migrate     # Set up database"
	@echo "  3. make dev         # Start everything"
	@echo "  4. Open http://localhost:3000"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
