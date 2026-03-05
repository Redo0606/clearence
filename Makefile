# Clearence - Common development tasks
# Run `make help` for available targets

.PHONY: help install run test lint format clean docker-build docker-up docker-down

help:
	@echo "Clearence - Available targets:"
	@echo "  make install       - Install package with dev dependencies (editable)"
	@echo "  make run           - Run the FastAPI app with uvicorn (reload)"
	@echo "  make test          - Run pytest"
	@echo "  make lint          - Run ruff check"
	@echo "  make format        - Run ruff format"
	@echo "  make clean         - Remove __pycache__, .pytest_cache, .ruff_cache"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-up     - Start with docker compose"
	@echo "  make docker-down   - Stop docker compose"

install:
	pip install -e ".[dev]"

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

lint:
	ruff check .

format:
	ruff format .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
