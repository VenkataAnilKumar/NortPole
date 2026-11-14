# Common commands. Run `make help` for the list. Backend commands use services/core's locked environment (uv).
.PHONY: help check core-test core-test-all core-run web-install web-typecheck web-dev packs contracts

CORE_ENV = PYTHONPATH=. DISABLE_VECTOR_DB=true CACHE_BACKEND=postgres AUTH_TYPE=basic FILE_STORE_BACKEND=postgres \
	NORTPOLE_OFFLINE_TOKENIZER=true HF_HUB_OFFLINE=1

help:
	@echo "make check          structure, links and tool tests"
	@echo "make core-test      NortPole unit tests (services/core/tests/unit/nortpole)"
	@echo "make core-test-all  every backend unit test (needs the dev dependency group)"
	@echo "make core-run       start the API on port 8080 (needs Postgres; see infrastructure/profiles/local)"
	@echo "make web-install    install the web app's dependencies"
	@echo "make web-typecheck  type-check the web app"
	@echo "make web-dev        start the web app on port 3000"
	@echo "make packs          validate every workflow pack with the pack SDK"
	@echo "make contracts      regenerate packages/contracts from the code"

check:
	python tools/validate_structure.py
	python -m pytest -q tools/tests

core-test:
	cd services/core && $(CORE_ENV) uv run --no-sync python -m pytest -q tests/unit/nortpole

core-test-all:
	cd services/core && PYTHONPATH=. uv run --no-sync python -m pytest -q -n auto tests/unit --ignore=tests/unit/model_server

core-run:
	cd services/core && $(CORE_ENV) uv run --no-sync uvicorn nortpole.main:app --port 8080

web-install:
	cd apps/workspace && bun install

web-typecheck:
	cd apps/workspace && npx next typegen && npx tsc --noEmit -p tsconfig.app.json

web-dev:
	cd apps/workspace && INTERNAL_URL=http://127.0.0.1:8080 npx next dev -p 3000

packs:
	cd packages/pack-sdk && python -m nortpole_pack_sdk validate $(abspath $(wildcard packs/horizontal/*) $(wildcard packs/vertical/*/*))

contracts:
	cd services/core && $(CORE_ENV) uv run --no-sync python scripts/generate_contracts.py
