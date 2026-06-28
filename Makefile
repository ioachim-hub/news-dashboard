.PHONY: install ci-install lint format typecheck \
        test test-smoke test-backend test-frontend test-e2e test-nightly test-full \
        check build

## install: install backend (editable + dev tools) and update local frontend dependencies
install:
	pip install -e '.[dev]'
	npm install
	pre-commit install

## ci-install: install backend and exact frontend dependencies from package-lock.json
ci-install:
	pip install -e '.[dev]'
	npm ci
	pre-commit install

## lint: run all linters without modifying files
lint:
	ruff check backend
	ruff format --check backend
	npm run lint --silent
	npm run format:check --silent

## format: auto-format backend and frontend code
format:
	ruff check backend --fix
	ruff format backend
	npm run lint:fix --silent
	npm run format --silent

## typecheck: run static type checkers
typecheck:
	mypy backend
	ty check backend
	pyrefly check backend
	npm run typecheck --silent

## test: run backend + frontend test suites (everyday development loop)
test:
	pytest --cov --cov-report=term-missing
	npm run test:frontend --silent

## test-smoke: fast smoke tests — backend health + core API paths, frontend app render
test-smoke:
	pytest -m smoke -v
	npm run test:frontend:smoke --silent

## test-backend: all backend pytest tests
test-backend:
	pytest -v

## test-frontend: all frontend Vitest tests
test-frontend:
	npm run test:frontend --silent

## test-e2e: Playwright end-to-end tests
test-e2e:
	npm run test:e2e --silent

## test-nightly: full suite with coverage — same as what the nightly CI runs
test-nightly:
	pytest --cov --cov-report=term-missing --cov-report=html -v
	npm run test:frontend:coverage --silent

## test-full: alias for test-nightly (complete suite with coverage)
test-full: test-nightly

## check: everything CI runs — lint, typecheck, test, build
check: lint typecheck test build

## build: production frontend build (includes tsc)
build:
	npm run build --silent
