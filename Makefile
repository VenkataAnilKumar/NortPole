# Common commands. Run `make help` for the list. Backend commands use services/core's locked environment (uv).
.PHONY: help check core-test core-test-ci core-test-all core-run web-install web-typecheck web-dev packs contracts sbom ci

CORE_ENV = PYTHONPATH=. DISABLE_VECTOR_DB=true CACHE_BACKEND=postgres AUTH_TYPE=basic FILE_STORE_BACKEND=postgres \
	NORTPOLE_OFFLINE_TOKENIZER=true HF_HUB_OFFLINE=1

help:
	@echo "make check          structure, links and tool tests"
	@echo "make core-test      NortPole unit tests (services/core/tests/unit/nortpole)"
	@echo "make core-test-ci   the NortPole-owned backend tests the CI job runs"
	@echo "make sbom           write the software bill of materials (sbom.cdx.json)"
	@echo "make ci             everything the CI jobs run, in one command (the same steps as .github/workflows/ci.yml)"
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

# The backend tests CI runs for NortPole's own modules (the nightly job runs the whole suite).
CORE_CI_TESTS = tests/unit/nortpole/action_binding tests/unit/nortpole/actions tests/unit/nortpole/audit_log \
	tests/unit/nortpole/extensions tests/unit/nortpole/external_permissions tests/unit/nortpole/integrations \
	tests/unit/nortpole/knowledge_access tests/unit/nortpole/secrets_sealing tests/unit/nortpole/packs \
	tests/unit/nortpole/redaction tests/unit/nortpole/route_policy tests/unit/nortpole/tasks \
	tests/unit/nortpole/tool_catalog tests/unit/nortpole/user_preferences tests/unit/nortpole/test_schedule_cadence.py \
	tests/unit/nortpole/skills/test_bundled_skill_scripts.py tests/unit/nortpole/test_domain_boundaries.py \
	tests/unit/nortpole/test_contracts_current.py tests/unit/nortpole/server/test_route_contract.py

core-test-ci:
	cd services/core && $(CORE_ENV) uv run --no-sync python -m pytest -q $(CORE_CI_TESTS)

sbom:
	python tools/sbom/generate_sbom.py --out sbom.cdx.json

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

# What the CI jobs run, so a failing GitHub run can be reproduced (and checked) on any machine.
ci: check packs sbom core-test-ci web-typecheck
