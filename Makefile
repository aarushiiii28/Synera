.PHONY: setup test lint check api web notebooks data demo

setup:
	pip install -e ".[dev,ml,api,notebooks]"
	pre-commit install

test:
	pytest tests/

lint:
	ruff check .

check: lint test

api:
	uvicorn backend.app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

notebooks:
	jupyter lab

data:
	python scripts/build_data.py

demo:
	python scripts/demo.py
