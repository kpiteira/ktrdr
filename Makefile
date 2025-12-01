.PHONY: test-unit test-integration test-e2e test-host test-coverage test-all test-performance lint lint-fix format typecheck quality test-fast ci validate-mcp test-container-build test-container-smoke test-container canary-up canary-down canary-logs canary-test canary-status

# Test commands
test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

test-e2e:
	uv run pytest tests/e2e/ -v

test-host:
	uv run pytest tests/host_service/ -v

test-coverage:
	uv run pytest tests/unit/ --cov=ktrdr --cov-report=html --cov-report=term-missing --cov-report=xml

test-coverage-junit:
	uv run pytest tests/unit/ --cov=ktrdr --cov-report=html --cov-report=term-missing --cov-report=xml --junit-xml=test-results.xml

test-all:
	uv run pytest -v

test-performance:
	uv run pytest tests/manual/performance/ -v

# Quality commands  
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run black ktrdr tests

typecheck:
	uv run mypy ktrdr

# Combined commands
quality: lint format typecheck
	@echo "✅ Code quality checks complete"

test-fast: test-unit
	@echo "✅ Fast tests complete"

# Validation commands
validate-mcp:
	@echo "🔍 Validating MCP tool signatures against OpenAPI spec..."
	@if lsof -i:8000 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		uv run python scripts/validate_mcp_signatures.py; \
	else \
		echo "❌ Backend not running on port 8000"; \
		echo "   Start backend: ./start_ktrdr.sh"; \
		exit 1; \
	fi

# CI command (used by GitHub Actions)
ci: test-unit lint format typecheck
	@echo "✅ CI checks complete"

# Container testing commands
# Build the production container locally
test-container-build:
	@echo "🐳 Building production container..."
	docker build -f docker/backend/Dockerfile -t ktrdr-backend:test .
	@echo "✅ Container built: ktrdr-backend:test"

# Quick smoke test - validates container can start and imports work
test-container-smoke: test-container-build
	@echo "🔥 Running smoke tests in container..."
	@echo "  → Testing Python imports..."
	docker run --rm ktrdr-backend:test python -c "from ktrdr.api.main import app; print('✅ API imports OK')"
	@echo "  → Testing CLI entry point..."
	docker run --rm ktrdr-backend:test python -c "from ktrdr.cli import app; print('✅ CLI imports OK')"
	@echo "  → Testing uvicorn startup (5s timeout)..."
	@docker run --rm -d --name ktrdr-smoke-test -p 18000:8000 ktrdr-backend:test && \
		sleep 5 && \
		(curl -sf http://localhost:18000/api/v1/health > /dev/null && echo "✅ Health check passed") || echo "⚠️  Health check skipped (no DB)"; \
		docker stop ktrdr-smoke-test > /dev/null 2>&1 || true
	@echo "✅ Smoke tests complete"

# Full test suite in container (mounts tests, installs test deps as root)
# Excludes tests that depend on files/services not packaged in container:
#   - host_service: depends on training-host-service code
#   - training_host: depends on training-host-service code
#   - scripts: depends on scripts/ directory
#   - config/test_host_services_cleanup: checks docker-compose files
#   - visualization: depends on templates not in container
test-container: test-container-build
	@echo "🧪 Running test suite in container..."
	docker run --rm \
		-v $(PWD)/tests:/home/ktrdr/app/tests:ro \
		-u root \
		--entrypoint "" \
		ktrdr-backend:test \
		sh -c "pip install --quiet pytest pytest-asyncio pytest-cov && python -m pytest tests/unit/ -v --tb=short \
			--ignore=tests/unit/host_service \
			--ignore=tests/unit/training_host \
			--ignore=tests/unit/scripts \
			--ignore=tests/unit/visualization \
			--ignore=tests/unit/config/test_host_services_cleanup.py"
	@echo "✅ Container tests complete"

# =============================================================================
# Canary Environment - Production Image Testing
# =============================================================================
# A local deployment using the production container image for pre-merge testing.
# Runs on separate ports (18000, 15003, 15004) so it doesn't conflict with dev.

# Start canary environment (requires: make test-container-build first)
canary-up:
	@if ! docker image inspect ktrdr-backend:test >/dev/null 2>&1; then \
		echo "❌ Image ktrdr-backend:test not found. Run 'make test-container-build' first."; \
		exit 1; \
	fi
	@echo "🐤 Starting canary environment..."
	docker compose -f docker-compose.canary.yml up -d
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 10
	@echo ""
	@echo "Canary environment ready:"
	@echo "  Backend API:      http://localhost:18000"
	@echo "  Backtest Worker:  http://localhost:15003"
	@echo "  Training Worker:  http://localhost:15004"
	@echo "  Database:         localhost:15432"
	@echo ""
	@echo "Run 'make canary-test' to validate, 'make canary-down' to stop"

# Stop canary environment
canary-down:
	@echo "🛑 Stopping canary environment..."
	docker compose -f docker-compose.canary.yml down
	@echo "✅ Canary stopped"

# View canary logs
canary-logs:
	docker compose -f docker-compose.canary.yml logs -f

# Check canary status
canary-status:
	@echo "📊 Canary environment status:"
	@docker compose -f docker-compose.canary.yml ps
	@echo ""
	@echo "🔍 Registered workers:"
	@curl -sf http://localhost:18000/api/v1/workers 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (backend not responding)"

# Functional tests against canary environment
canary-test:
	@echo "🧪 Running functional tests against canary..."
	@./scripts/test-canary.sh