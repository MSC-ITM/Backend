
.PHONY: dev test lint type spec seed fmt

dev:
	uvicorn app.main:app --reload

test:
	pytest -q

lint:
	ruff check . && black --check .

fmt:
	black . && ruff check . --fix

type:
	mypy app

spec:
	schemathesis run spec/openapi/openapi.yaml --checks all
