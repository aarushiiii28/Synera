.PHONY: setup check test lint api web notebooks data seed benchmark space demo reproduce docker clean

PY ?= python
ifeq ($(OS),Windows_NT)
  VENV_PY := .venv/Scripts/python
else
  VENV_PY := .venv/bin/python
endif

setup:
	$(PY) -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[dev,ml,api,notebooks]"
	$(VENV_PY) -m pip install torch --index-url https://download.pytorch.org/whl/cpu
	cd frontend && npm ci

check:
	$(VENV_PY) scripts/check_env.py

test:
	$(VENV_PY) -m pytest -q
	cd frontend && npm test

lint:
	$(VENV_PY) -m ruff check .
	cd frontend && npm run lint

# --- data and results -------------------------------------------------------------------------------
data:            ## fetch/cached -> harmonize -> hash -> ledger -> MANIFEST
	$(VENV_PY) scripts/build_data.py
	$(VENV_PY) scripts/build_gene_symbols.py

space:           ## Track A gene-level analysis (real NASA data)
	$(VENV_PY) scripts/build_space_biology.py

benchmark:       ## Engine report card (about 30-40 minutes; resumable)
	$(VENV_PY) scripts/run_benchmark.py

seed:            ## run the real pipeline and fill the application database
	$(VENV_PY) scripts/seed_db.py

# --- run --------------------------------------------------------------------------------------------
api:
	$(VENV_PY) -m uvicorn backend.app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

demo:            ## verify ledger + manifest, seed, start API and web, print URLs
	$(VENV_PY) scripts/demo.py

reproduce:       ## re-run every analysis and compare result hashes with the ledger
	$(VENV_PY) scripts/reproduce.py

notebooks:
	$(VENV_PY) -m jupyter lab

docker:
	docker compose up --build

clean:
	$(VENV_PY) -c "import shutil,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
