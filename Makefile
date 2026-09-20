PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: dev test capture openapi

dev:
	@echo "API  http://127.0.0.1:8000/docs"
	@echo "UI   http://127.0.0.1:5173"
	$(PY) -m uvicorn api.app:app --reload --host 127.0.0.1 --port 8000 &
	cd web && npm run dev -- --host 127.0.0.1 --port 5173

test:
	$(PY) -m pytest -q

capture:
	cd web && npm run capture

openapi:
	cd web && npm run gen:api
