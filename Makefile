# =============================================================================
# SepsisAI-Orchestrator  —  Developer shortcuts
# =============================================================================
# Run `make help` to see all available targets.

.DEFAULT_GOAL := help
COMPOSE       := docker compose

.PHONY: help build up down seed logs test clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker images locally
	$(COMPOSE) build

up: ## Start MongoDB + AI service + Dashboard
	$(COMPOSE) up -d

down: ## Stop all services and remove volumes
	$(COMPOSE) down -v

seed: ## Run CDA preprocessing to load sample data into MongoDB
	$(COMPOSE) run --rm cda-preprocessing

logs: ## Tail logs from every running service
	$(COMPOSE) logs -f

test: ## Quick smoke-test: hit the AI health endpoint
	@echo "--- AI Service health ---"
	@curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || echo "AI service not reachable"
	@echo ""
	@echo "--- Dashboard ---"
	@curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501

clean: ## Remove all generated CSV files from data/
	rm -rf data/sample/*.csv
