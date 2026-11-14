pull:
	python -m pipeline.pull --codes MKJ BZD --start 2019-01
serve:
	uvicorn service.api:app --port 8000
page:
	streamlit run page/app.py
bot:
	python -m bot.photon_bot
