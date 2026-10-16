.PHONY: install db migrate seed run test lint fmt

install:
	pip install -r requirements-dev.txt

db:
	docker compose up -d db

migrate:
	alembic upgrade head

seed:
	python -m scripts.seed

run:
	uvicorn app.main:app --reload

test:
	pytest --cov --cov-report=term-missing

lint:
	ruff check . && ruff format --check . && mypy

fmt:
	ruff check --fix . && ruff format .
