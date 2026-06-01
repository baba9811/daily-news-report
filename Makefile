.PHONY: all setup dev linux dev-linux dev-backend dev-frontend test lint format generate-types build run serve check \
	multica-up multica-down multica-stop multica-status multica-logs multica-bootstrap multica-add-member \
	multica-runtime multica-register-agents multica-agents-setup \
	scheduler-install scheduler-uninstall scheduler-status scheduler-start scheduler-stop \
	scheduler-linux-install scheduler-linux-uninstall scheduler-linux-status scheduler-linux-start scheduler-linux-stop \
	clean help

# ============================================================
# Daily Scheduler - Development Commands
# ============================================================
# `make` (no args) starts everything: backend + frontend + scheduler

all: dev ## Default: start backend + frontend dev servers

setup: ## Initial project setup (run once)
	cp -n .env.example .env 2>/dev/null || true
	cd backend && uv sync --extra dev
	cd frontend && yarn install
	cd backend && uv run daily-scheduler init-db
	@echo ""
	@echo "Setup complete! Edit .env with your credentials, then run: make"

dev: ## Start Multica + backend + frontend + scheduler
	@echo "Starting Multica self-host stack (docker)..."
	@bash scripts/multica.sh up-soft
	@echo "Starting backend on http://localhost:8000"
	@echo "Starting frontend on http://localhost:3000"
	@echo "Starting scheduler (launchd)..."
	@bash scheduler/install.sh
	@trap 'echo ""; echo "Stopping scheduler..."; \
		launchctl bootout gui/$$(id -u)/com.dailyscheduler.report 2>/dev/null; \
		echo "Stopping Multica..."; bash scripts/multica.sh stop; \
		echo "All services stopped."' INT TERM; \
		$(MAKE) -j2 dev-backend dev-frontend; \
		wait

linux: dev-linux ## Alias for dev-linux

dev-linux: ## Start Multica + backend + frontend + scheduler (Linux/WSL2, uses cron)
	@echo "Starting Multica self-host stack (docker)..."
	@bash scripts/multica.sh up-soft
	@echo "Starting backend on http://localhost:8000"
	@echo "Starting frontend on http://localhost:3000"
	@echo "Starting scheduler (cron)..."
	@bash scheduler/install-linux.sh
	@trap 'echo ""; echo "Stopping scheduler..."; \
		bash scheduler/uninstall-linux.sh; \
		echo "Stopping Multica..."; bash scripts/multica.sh stop; \
		echo "All services stopped."' INT TERM; \
		$(MAKE) -j2 dev-backend dev-frontend; \
		wait

dev-backend: ## Start FastAPI dev server (auto-reload)
	cd backend && uv run uvicorn daily_scheduler.main:app \
		--reload --host 127.0.0.1 --port 8000

dev-frontend: ## Start Next.js dev server
	cd frontend && yarn dev

# ── Multica self-host stack (docker compose) ────────────────
multica-up: ## Start the Multica self-host stack and wait for health
	bash scripts/multica.sh up

multica-down: ## Stop & remove the Multica stack (data volumes preserved)
	bash scripts/multica.sh down

multica-stop: ## Stop the Multica stack (containers + data kept, fast restart)
	bash scripts/multica.sh stop

multica-bootstrap: ## Create a Multica PAT + workspace and write them to .env
	bash scripts/multica-bootstrap.sh

multica-add-member: ## Invite a human into the Multica council workspace (EMAIL=you@example.com [ROLE=admin])
	bash scripts/multica-add-member.sh "$(EMAIL)" "$(ROLE)"

multica-runtime: ## Register this machine as a Multica runtime (install CLI + start daemon)
	bash scripts/multica-runtime.sh

multica-register-agents: ## Create the workspace-visible council agents + squad + skill
	python3 scripts/multica-register-agents.py

multica-agents-setup: multica-runtime multica-register-agents ## Runtime + agents in one shot

multica-status: ## Show Multica stack status + backend health probe
	bash scripts/multica.sh status

multica-logs: ## Tail the Multica stack logs
	bash scripts/multica.sh logs

test: ## Run all tests (backend unit + frontend typecheck + static analysis)
	cd backend && uv run pytest tests/ -v
	cd backend && uv run pyrefly check src/
	cd backend && uv run pylint src/daily_scheduler/
	cd frontend && yarn typecheck
	cd frontend && yarn oxlint

lint: ## Run linting and static analysis
	cd backend && uv run ruff check src/
	cd backend && uv run ruff format --check src/
	cd backend && uv run pyrefly check src/
	cd backend && uv run pylint src/daily_scheduler/
	cd frontend && yarn lint
	cd frontend && yarn oxlint

generate-types: ## Generate TypeScript types from OpenAPI spec
	cd backend && uv run python scripts/export_openapi.py ../frontend/openapi.json
	cd frontend && yarn generate:types

format: ## Auto-format all code
	cd backend && uv run ruff check --fix src/
	cd backend && uv run ruff format src/

build: ## Build frontend for production
	cd frontend && yarn build

run: ## Run the daily report pipeline once (manual trigger)
	cd backend && uv run daily-scheduler run

serve: ## Start production server (API + built frontend)
	cd backend && uv run daily-scheduler serve

check: ## Verify configuration and dependencies
	cd backend && uv run daily-scheduler check

scheduler-install: ## Install & load launchd scheduler
	bash scheduler/install.sh

scheduler-uninstall: ## Unload & remove launchd scheduler
	launchctl bootout gui/$$(id -u)/com.dailyscheduler.report 2>/dev/null || true
	rm -f $(HOME)/Library/LaunchAgents/com.dailyscheduler.report.plist
	@echo "Scheduler uninstalled."

scheduler-status: ## Show scheduler status
	@launchctl list | grep dailyscheduler || echo "Scheduler is not loaded."

scheduler-start: ## Manually trigger scheduler now
	launchctl start com.dailyscheduler.report
	@echo "Scheduler triggered."

scheduler-stop: ## Unload scheduler (stop scheduled runs)
	launchctl bootout gui/$$(id -u)/com.dailyscheduler.report 2>/dev/null || true
	@echo "Scheduler stopped."

scheduler-linux-install: ## Install & load cron scheduler (Linux)
	bash scheduler/install-linux.sh

scheduler-linux-uninstall: ## Unload & remove cron scheduler (Linux)
	bash scheduler/uninstall-linux.sh

scheduler-linux-status: ## Show cron scheduler status (Linux)
	@crontab -l 2>/dev/null | grep "daily-scheduler" || echo "Scheduler is not loaded."

scheduler-linux-start: ## Manually trigger scheduler now (Linux)
	bash scheduler/run_daily.sh
	@echo "Scheduler triggered."

scheduler-linux-stop: ## Remove cron scheduler (Linux)
	bash scheduler/uninstall-linux.sh

clean: ## Remove all generated files
	rm -rf backend/.venv frontend/node_modules frontend/.next
	rm -rf backend/src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := all
