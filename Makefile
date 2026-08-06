.PHONY: help up down build test test-unit test-integration test-cov lint format migrate clean

help: ## Mostra os comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Sobe todos os containers
	docker compose -f docker/docker-compose.yml up -d

down: ## Para todos os containers
	docker compose -f docker/docker-compose.yml down

build: ## Rebuilda as imagens
	docker compose -f docker/docker-compose.yml up -d --build

migrate: ## Roda migrações do banco
	docker exec contabilidade-app alembic upgrade head

test: ## Roda todos os testes
	docker exec contabilidade-app python -m pytest -v --tb=short

test-unit: ## Roda apenas testes unitários
	docker exec contabilidade-app python -m pytest tests/unit/ -v --tb=short

test-integration: ## Roda apenas testes de integração
	docker exec contabilidade-app python -m pytest tests/integration/ -v --tb=short

test-cov: ## Roda testes com cobertura
	docker exec contabilidade-app python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=70

lint: ## Roda o linter (ruff)
	docker exec contabilidade-app ruff check src/ tests/ || echo "Ruff não instalado, pulando"
	docker exec contabilidade-app ruff format --check src/ tests/ || echo "Ruff não instalado, pulando"

format: ## Formata o código com ruff
	docker exec contabilidade-app ruff format src/ tests/ || echo "Ruff não instalado, pulando"

clean: ## Remove containers e volumes
	docker compose -f docker/docker-compose.yml down -v
