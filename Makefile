.PHONY: help dev dev-down test test-api test-web test-all lint lint-api lint-web typecheck typecheck-api typecheck-web eval build scanner-build scanner-test scanner-scan clean

# Use bash for path handling
SHELL := /usr/bin/env bash

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ===== Dev =====
dev: ## Start all services via docker compose
	docker compose up -d
	@echo "API: http://localhost:8000"
	@echo "Web: http://localhost:3000"
	@echo "Docs: http://localhost:8000/docs"

dev-down: ## Stop all services
	docker compose down

# ===== Tests =====
test: test-api test-web ## Run all tests

test-api: ## Run API tests
	cd apps/api && uv run pytest -v

test-web: ## Run web tests
	cd apps/web && pnpm test

# ===== Lint =====
lint: lint-api lint-web ## Lint all code

lint-api: ## Lint Python code
	cd apps/api && uv run ruff check . && uv run ruff format --check .

lint-web: ## Lint JS/TS code
	cd apps/web && pnpm lint && pnpm format:check

# ===== Typecheck =====
typecheck: typecheck-api typecheck-web ## Run type checkers

typecheck-api: ## Run mypy on Python code
	cd apps/api && uv run mypy src/

typecheck-web: ## Run tsc on JS/TS code
	cd apps/web && pnpm typecheck

# ===== Eval =====
eval: ## Run reference-set evaluation
	cd apps/api && uv run python -m scripts.eval

# ===== Build =====
build: ## Build all production artifacts
	docker compose -f docker-compose.prod.yml build

# ===== Scanner =====
scanner-build: ## Build the scanner container image
	docker build -t skillissue/scanner:dev scanner/

scanner-test: ## Run scanner self-tests
	docker run --rm --network none -v $(PWD)/scanner/fixtures:/work/src:ro skillissue/scanner:dev python -m pytest

scanner-scan: ## Scan a directory using the scanner image
	docker run --rm \
		--network none \
		--read-only \
		--cap-drop ALL \
		--security-opt no-new-privileges \
		--pids-limit 256 \
		--memory 1g --memory-swap 1g \
		--cpus 1.5 \
		--user 10001:10001 \
		--tmpfs /tmp:rw,nosuid,size=256m \
		-v $(PWD)/$(TARGET):/work/src:ro \
		-v $(PWD)/.scanner-out:/out:rw \
		skillissue/scanner:dev \
		python -m scanner_runner --src /work/src --out /out

# ===== Cleanup =====
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf .scanner-out dist build
