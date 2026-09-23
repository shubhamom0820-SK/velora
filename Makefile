# Velora — developer entry points.
# Every target is a stub until the task that owns it lands. See docs/05-PLAN.md.

.DEFAULT_GOAL := help
.PHONY: help infra-up infra-down dev worker seed test lint migrate migrate-down migration types e2e

help: ## List the available targets
	@echo "Velora — make targets:"
	@grep -E '^[a-z][a-zA-Z0-9_-]*:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-13s %s\n", $$1, $$2}'

infra-up: ## Start docker: postgres+postgis, redis, minio [T-1.2]
	@echo "not yet — T-1.2"

infra-down: ## Stop the docker stack [T-1.2]
	@echo "not yet — T-1.2"

dev: ## Run infra + api + worker + web [T-1.17]
	@echo "not yet — T-1.17"

worker: ## Run the ARQ worker only [T-4.4]
	@echo "not yet — T-4.4"

seed: ## Dev data: 20 profiles, test users (refuses in production) [T-1.15]
	@echo "not yet — T-1.15"

test: ## api pytest + web vitest [T-1.5]
	@echo "not yet — T-1.5"

lint: ## ruff + mypy + eslint + tsc --noEmit [T-1.6]
	@echo "not yet — T-1.6"

migrate: ## alembic upgrade head [T-1.7]
	@echo "not yet — T-1.7"

migrate-down: ## alembic downgrade one step [T-1.7]
	@echo "not yet — T-1.7"

migration: ## New alembic revision: make migration m="message" [T-1.7]
	@echo "not yet — T-1.7"

types: ## Regenerate web/src/types/api.ts from OpenAPI [T-1.18]
	@echo "not yet — T-1.18"

e2e: ## Playwright [T-3.13]
	@echo "not yet — T-3.13"
