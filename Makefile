.PHONY: all setup dev linux dev-linux dev-backend dev-frontend test lint format generate-types build run run-news run-global-news serve check \
	multica-up multica-down multica-stop multica-status multica-logs multica-bootstrap \
	scheduler-install scheduler-uninstall scheduler-status scheduler-start scheduler-stop \
	scheduler-linux-install scheduler-linux-uninstall scheduler-linux-status scheduler-linux-start scheduler-linux-stop \
	news-scheduler-install news-scheduler-uninstall news-scheduler-status news-scheduler-start news-scheduler-stop \
	news-scheduler-linux-install news-scheduler-linux-uninstall news-scheduler-linux-status news-scheduler-linux-start news-scheduler-linux-stop \
	global-news-scheduler-install global-news-scheduler-uninstall global-news-scheduler-status global-news-scheduler-start global-news-scheduler-stop \
	global-news-scheduler-linux-install global-news-scheduler-linux-uninstall global-news-scheduler-linux-status global-news-scheduler-linux-start global-news-scheduler-linux-stop \
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

dev: ## Start Multica + backend + frontend + schedulers
	@echo "Starting Multica self-host stack (docker)..."
	@bash scripts/multica.sh up-soft
	@echo "Starting backend on http://localhost:8000"
	@echo "Starting frontend on http://localhost:3000"
	@echo "Starting schedulers (launchd)..."
	@bash scheduler/install.sh
	@bash scheduler/install-news.sh
	@bash scheduler/install-global-news.sh
	@trap 'echo ""; echo "Stopping schedulers..."; \
		launchctl bootout gui/$$(id -u)/com.dailyscheduler.report 2>/dev/null; \
		launchctl bootout gui/$$(id -u)/com.dailyscheduler.news 2>/dev/null; \
		launchctl bootout gui/$$(id -u)/com.dailyscheduler.global-news 2>/dev/null; \
		echo "Stopping Multica..."; bash scripts/multica.sh stop; \
		echo "All services stopped."' INT TERM; \
		$(MAKE) -j2 dev-backend dev-frontend; \
		wait

linux: dev-linux ## Alias for dev-linux

dev-linux: ## Start Multica + backend + frontend + schedulers (Linux/WSL2, uses cron)
	@echo "Starting Multica self-host stack (docker)..."
	@bash scripts/multica.sh up-soft
	@echo "Starting backend on http://localhost:8000"
	@echo "Starting frontend on http://localhost:3000"
	@echo "Starting schedulers (cron)..."
	@bash scheduler/install-linux.sh
	@bash scheduler/install-news-linux.sh
	@bash scheduler/install-global-news-linux.sh
	@trap 'echo ""; echo "Stopping schedulers..."; \
		bash scheduler/uninstall-linux.sh; \
		crontab -l 2>/dev/null | grep -v "daily-scheduler-news" | grep -v "daily-scheduler-global-news" | crontab - 2>/dev/null; \
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

run-news: ## Run the Korean news briefing pipeline once (manual trigger)
	cd backend && uv run daily-scheduler run-news

run-global-news: ## Run the global news briefing pipeline once (manual trigger)
	cd backend && uv run daily-scheduler run-global-news

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

news-scheduler-install: ## Install & load news briefing launchd scheduler
	bash scheduler/install-news.sh

news-scheduler-uninstall: ## Unload & remove news briefing launchd scheduler
	launchctl bootout gui/$$(id -u)/com.dailyscheduler.news 2>/dev/null || true
	rm -f $(HOME)/Library/LaunchAgents/com.dailyscheduler.news.plist
	@echo "News briefing scheduler uninstalled."

news-scheduler-status: ## Show news briefing scheduler status
	@launchctl list | grep dailyscheduler.news || echo "News briefing scheduler is not loaded."

news-scheduler-start: ## Manually trigger news briefing scheduler now
	launchctl start com.dailyscheduler.news
	@echo "News briefing scheduler triggered."

news-scheduler-stop: ## Unload news briefing scheduler (stop scheduled runs)
	launchctl bootout gui/$$(id -u)/com.dailyscheduler.news 2>/dev/null || true
	@echo "News briefing scheduler stopped."

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

news-scheduler-linux-install: ## Install & load news briefing cron scheduler (Linux)
	bash scheduler/install-news-linux.sh

news-scheduler-linux-uninstall: ## Unload & remove news briefing cron scheduler (Linux)
	@CRON_MARKER="# daily-scheduler-news"; \
	EXISTING=$$(crontab -l 2>/dev/null || true); \
	echo "$$EXISTING" | grep -v "$$CRON_MARKER" | crontab - 2>/dev/null || true; \
	echo "News briefing cron scheduler uninstalled."

news-scheduler-linux-status: ## Show news briefing cron scheduler status (Linux)
	@crontab -l 2>/dev/null | grep "daily-scheduler-news" || echo "News briefing scheduler is not loaded."

news-scheduler-linux-start: ## Manually trigger news briefing scheduler now (Linux)
	bash scheduler/run_news.sh
	@echo "News briefing scheduler triggered."

news-scheduler-linux-stop: ## Remove news briefing cron scheduler (Linux)
	@CRON_MARKER="# daily-scheduler-news"; \
	EXISTING=$$(crontab -l 2>/dev/null || true); \
	echo "$$EXISTING" | grep -v "$$CRON_MARKER" | crontab - 2>/dev/null || true; \
	echo "News briefing cron scheduler stopped."

global-news-scheduler-install: ## Install & load global news briefing launchd scheduler
	bash scheduler/install-global-news.sh

global-news-scheduler-uninstall: ## Unload & remove global news briefing launchd scheduler
	launchctl bootout gui/$$(id -u)/com.dailyscheduler.global-news 2>/dev/null || true
	rm -f $(HOME)/Library/LaunchAgents/com.dailyscheduler.global-news.plist
	@echo "Global news briefing scheduler uninstalled."

global-news-scheduler-status: ## Show global news briefing scheduler status
	@launchctl list | grep dailyscheduler.global-news || echo "Global news briefing scheduler is not loaded."

global-news-scheduler-start: ## Manually trigger global news briefing scheduler now
	launchctl start com.dailyscheduler.global-news
	@echo "Global news briefing scheduler triggered."

global-news-scheduler-stop: ## Unload global news briefing scheduler
	launchctl bootout gui/$$(id -u)/com.dailyscheduler.global-news 2>/dev/null || true
	@echo "Global news briefing scheduler stopped."

global-news-scheduler-linux-install: ## Install & load global news briefing cron scheduler (Linux)
	bash scheduler/install-global-news-linux.sh

global-news-scheduler-linux-uninstall: ## Unload & remove global news briefing cron scheduler (Linux)
	@CRON_MARKER="# daily-scheduler-global-news"; \
	EXISTING=$$(crontab -l 2>/dev/null || true); \
	echo "$$EXISTING" | grep -v "$$CRON_MARKER" | crontab - 2>/dev/null || true; \
	echo "Global news briefing cron scheduler uninstalled."

global-news-scheduler-linux-status: ## Show global news briefing cron scheduler status (Linux)
	@crontab -l 2>/dev/null | grep "daily-scheduler-global-news" || echo "Global news briefing scheduler is not loaded."

global-news-scheduler-linux-start: ## Manually trigger global news briefing scheduler now (Linux)
	bash scheduler/run_global_news.sh
	@echo "Global news briefing scheduler triggered."

global-news-scheduler-linux-stop: ## Remove global news briefing cron scheduler (Linux)
	@CRON_MARKER="# daily-scheduler-global-news"; \
	EXISTING=$$(crontab -l 2>/dev/null || true); \
	echo "$$EXISTING" | grep -v "$$CRON_MARKER" | crontab - 2>/dev/null || true; \
	echo "Global news briefing cron scheduler stopped."

clean: ## Remove all generated files
	rm -rf backend/.venv frontend/node_modules frontend/.next
	rm -rf backend/src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := all
