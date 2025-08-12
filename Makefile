# Makefile for Subscription Tracker API
# Professional development workflow commands

.PHONY: help install dev test lint format clean migrate docker build deploy

# Default target
help:
	@echo "Available commands:"
	@echo "  install    - Install dependencies"
	@echo "  dev        - Run development server"
	@echo "  test       - Run tests"
	@echo "  lint       - Run linting checks"
	@echo "  format     - Format code"
	@echo "  clean      - Clean up temporary files"
	@echo "  migrate    - Run database migrations"
	@echo "  docker     - Build and run Docker container"
	@echo "  build      - Build production package"
	@echo "  deploy     - Deploy to staging/production"

# Development setup
install:
	python -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt

install-poetry:
	poetry install --with dev

# Development server
dev:
	./venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload

dev-poetry:
	poetry run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload

# Testing
test:
	./venv/bin/pytest src/tests/ -v

test-poetry:
	poetry run pytest src/tests/ -v

test-coverage:
	poetry run pytest --cov=src --cov-report=html --cov-report=term-missing

# Code quality
lint:
	poetry run flake8 src/
	poetry run mypy src/

format:
	poetry run black src/
	poetry run isort src/

format-check:
	poetry run black --check src/
	poetry run isort --check-only src/

# Database operations
migrate:
	./venv/bin/alembic upgrade head

migrate-create:
	./venv/bin/alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade:
	./venv/bin/alembic downgrade -1

# Docker operations
docker-build:
	docker build -t subscription-tracker-api .

docker-run:
	docker run -p 8000:8000 subscription-tracker-api

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/

# Security
security-check:
	poetry run safety check
	poetry run bandit -r src/

# Production
build:
	poetry build

# Environment setup
setup-pre-commit:
	poetry run pre-commit install
	poetry run pre-commit autoupdate

# Quick start for new developers
quickstart: install migrate dev

# Full CI pipeline
ci: format-check lint test security-check