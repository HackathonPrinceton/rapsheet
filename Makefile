# Rebuild everything from the public API:  make all
PY ?= python

pull:
	$(PY) -m pipeline.pull --codes MKJ BZD --start 2019-01
sample:
	$(PY) -m pipeline.deaths sample
label:
	$(PY) -m pipeline.label
deaths:
	$(PY) -m pipeline.deaths train
	$(PY) -m pipeline.deaths score
	$(PY) -m pipeline.explain
test:
	$(PY) -m pytest -q tests
evaluate:
	$(PY) -m pipeline.evaluate
scores:
	$(PY) -m pipeline.import_scores death_scores_mkj.csv death_scores_bzd.csv
warning:
	$(PY) -m pipeline.warning
models: deaths warning
all: pull models
serve:
	uvicorn service.api:app --port 8000
page:
	streamlit run page/app.py
bot:
	$(PY) -m bot.photon_bot
demo:
	$(PY) start_demo.py
alerts:
	$(PY) -m bot.alerts --dry-run
.PHONY: test pull sample label deaths evaluate scores warning models all serve page bot demo alerts
