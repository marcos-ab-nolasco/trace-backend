.PHONY: help setup-docker generate-types docker-build docker-up docker-down docker-logs docker-restart \
	docker-migrate docker-migrate-create migrate migrate-create migrate-downgrade lint-backend lint-backend-fix \
	lint-frontend lint-frontend-fix lint lint-fix test-up test-down test-backend test-frontend test test-cov clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup-docker: ## Install dependencies
	@if [ ! -f .env ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
	fi
	@echo "Creating symlink for Docker Compose .env..."
	ln -sf ../.env infrastructure/.env
	@echo "Setup complete!"

generate-types: ## Generate TypeScript types from OpenAPI spec
	@./scripts/generate-types.sh

docker-build: ## Build Docker images
	docker compose -f infrastructure/docker-compose.yml build

docker-up: ## Start Docker Compose services
	docker compose -f infrastructure/docker-compose.yml up -d

docker-down: ## Stop Docker Compose services
	docker compose -f infrastructure/docker-compose.yml down

docker-logs: ## Show Docker Compose logs
	docker compose -f infrastructure/docker-compose.yml logs -f

docker-restart: ## Restart Docker Compose services
	docker compose -f infrastructure/docker-compose.yml restart

docker-migrate: ## Run migrations in Docker container
	docker compose -f infrastructure/docker-compose.yml exec backend alembic upgrade head

docker-migrate-create: ## Create new migration in Docker (use MESSAGE="description")
	docker compose -f infrastructure/docker-compose.yml exec backend alembic revision --autogenerate -m "$(MESSAGE)"

migrate: ## Run database migrations
	cd app/backend && alembic upgrade head

migrate-create: ## Create new migration (use MESSAGE="description")
	cd app/backend && alembic revision --autogenerate -m "$(MESSAGE)"

migrate-downgrade: ## Rollback last migration
	cd app/backend && alembic downgrade -1

lint-backend:
	cd app/backend && black --check src tests --line-length 100
	cd app/backend && ruff check src tests
	cd app/backend && mypy src

lint-backend-fix:
	cd app/backend && black src tests --line-length 100
	cd app/backend && ruff check --fix src tests

lint-frontend:
	cd app/frontend && pnpm lint:check && pnpm type-check

lint-frontend-fix:
	cd app/frontend && pnpm lint:fix

lint: ## Run linting and formatting checks (backend + frontend)
	@echo "Linting backend..."
	cd app/backend && black --check src tests --line-length 100
	cd app/backend && ruff check src tests
	cd app/backend && mypy src
	@echo "Linting frontend..."
	cd app/frontend && pnpm lint:check
	cd app/frontend && pnpm type-check

lint-fix: ## Fix linting issues (backend + frontend)
	@echo "Fixing backend lint issues..."
	cd app/backend && black src tests --line-length 100
	cd app/backend && ruff check --fix src tests
	@echo "Fixing frontend lint issues..."
	cd app/frontend && pnpm lint:fix

test-up: ## Start test database (PostgreSQL)
	docker compose -f infrastructure/docker-compose.yml up -d postgres_test
	@echo "Waiting for test database to be ready..."
	@timeout 30 bash -c 'until docker compose -f infrastructure/docker-compose.yml ps postgres_test 2>/dev/null | grep -q "healthy"; do sleep 1; done' || (echo "Timeout waiting for test database" && exit 1)
	@echo "Test database is ready!"

test-down: ## Stop test database
	docker compose -f infrastructure/docker-compose.yml stop postgres_test

test-backend: ## Run backend tests (requires test database running)
	cd app/backend && pytest -v

test-frontend:
	cd app/frontend && pnpm test

test: ## Run all tests (backend + frontend)
	cd app/backend && pytest -v
	cd app/frontend && pnpm test

test-cov: ## Run tests with coverage (backend + frontend)
	@echo "Running backend tests with coverage..."
	cd app/backend && pytest --cov=src --cov-report=html --cov-report=term
	@echo "Running frontend tests with coverage..."
	cd app/frontend && pnpm test:coverage

clean: ## Clean cache and artifacts
	@echo "Cleaning backend..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf app/backend/htmlcov
	@echo "Cleaning frontend..."
	rm -rf app/frontend/.next
	rm -rf app/frontend/out
	rm -rf app/frontend/coverage
	@echo "Cleanup complete!"
