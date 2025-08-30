.PHONY: test-unit test-integration test-e2e test-host test-coverage test-all test-performance lint lint-fix format typecheck quality test-fast ci

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

# CI command (used by GitHub Actions)
ci: test-unit lint format typecheck
	@echo "✅ CI checks complete"