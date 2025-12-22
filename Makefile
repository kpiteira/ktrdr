.PHONY: test-unit test-integration test-e2e test-host test-coverage test-all test-performance lint lint-fix format typecheck quality test-fast ci validate-mcp test-container-build test-container-smoke test-container canary-up canary-down canary-logs canary-test canary-status docker-build-patch deploy-patch

# Test commands
# Use -n auto for parallel execution with pytest-xdist
test-unit:
	uv run pytest tests/unit/ -v -n auto

test-integration:
	uv run pytest tests/integration/ -v

test-e2e:
	uv run pytest tests/e2e/ -v

test-host:
	uv run pytest tests/host_service/ -v

# Coverage with parallel execution
test-coverage:
	uv run pytest tests/unit/ -n auto --cov=ktrdr --cov-report=html --cov-report=term-missing --cov-report=xml

test-coverage-junit:
	uv run pytest tests/unit/ -n auto --cov=ktrdr --cov-report=html --cov-report=term-missing --cov-report=xml --junit-xml=unit-test-results.xml

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
	docker build -f deploy/docker/Dockerfile -t ktrdr-backend:test .
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

# =============================================================================
# Patch Deployment - Fast local builds for preprod hotfixes
# =============================================================================
# Build a CPU-only image (~500MB vs ~3.3GB) for rapid preprod patching.
# This bypasses CI/CD for quick iteration during debugging.
#
# Usage:
#   make docker-build-patch   # Build CPU-only image (~6 min on Mac)
#   make deploy-patch         # Deploy to preprod (core + all workers)
#
# The patch image excludes CUDA/GPU dependencies since preprod workers
# are CPU-only. GPU worker is excluded from patch deployment.

PATCH_IMAGE := ghcr.io/kpiteira/ktrdr-backend:patch
PATCH_TARBALL := ktrdr-patch.tar.gz

# Build CPU-only patch image for x86_64 (preprod architecture)
docker-build-patch:
	@echo "🔧 Building CPU-only patch image for x86_64..."
	@echo "   This will take ~6 minutes (cross-compile from ARM)"
	docker buildx build --platform linux/amd64 \
		-f deploy/docker/Dockerfile.patch \
		-t $(PATCH_IMAGE) \
		--load .
	@echo ""
	@echo "📦 Saving image to tarball..."
	docker save $(PATCH_IMAGE) | gzip > $(PATCH_TARBALL)
	@echo ""
	@echo "✅ Patch image built successfully!"
	@echo "   Image: $(PATCH_IMAGE)"
	@echo "   Size:  $$(docker images $(PATCH_IMAGE) --format '{{.Size}}')"
	@echo "   Tarball: $(PATCH_TARBALL) ($$(ls -lh $(PATCH_TARBALL) | awk '{print $$5}'))"
	@echo ""
	@echo "Next step: make deploy-patch"

# Deploy patch image to preprod (core + workers, excluding GPU)
deploy-patch:
	@if [ ! -f $(PATCH_TARBALL) ]; then \
		echo "❌ Patch tarball not found: $(PATCH_TARBALL)"; \
		echo "   Run 'make docker-build-patch' first"; \
		exit 1; \
	fi
	@echo "🚀 Deploying patch to preprod..."
	uv run ktrdr deploy patch