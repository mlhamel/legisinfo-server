.PHONY: help install generate run docker-build docker-up docker-down clean

LEGISINFO_DATA_PATH ?= ../legisinfo

help:
	@echo "Available commands:"
	@echo "  install      - Set up Python virtual environment and dependencies"
	@echo "  generate     - Generate Python and ConnectRPC code stubs using buf"
	@echo "  run          - Run the FastAPI server locally (defaults to data path: $(LEGISINFO_DATA_PATH))"
	@echo "  docker-build - Build the Docker container image"
	@echo "  docker-up    - Build and launch the container stack using docker-compose"
	@echo "  docker-down  - Stop the docker-compose stack"
	@echo "  clean        - Remove generated files, caches, and build artifacts"

install:
	uv venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

generate:
	buf generate

run: generate
	LEGISINFO_DATA_PATH=$(LEGISINFO_DATA_PATH) .venv/bin/uvicorn legisinfo_server.main:app --reload --host 0.0.0.0 --port 8001

docker-build:
	docker build -t legisinfo-server:latest .

docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

clean:
	rm -rf .venv
	rm -rf src/legisinfo_server/gen/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
