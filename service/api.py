"""Device record API.  Run:  uvicorn service.api:app --reload --port 8000"""
from fastapi import FastAPI, HTTPException

from . import record

app = FastAPI(title="Rap Sheet")


@app.get("/health")
def health():
    return {"ok": True, "has_data": record.has_data()}


@app.get("/search")
def search(q: str):
    """Text a user typed (or text read off a label) -> candidate devices."""
    if not record.has_data():
        s = record.sample_record()
        return {"results": [{"device_key": s["device_key"], **s["device"], "score": 1.0}], "sample": True}
    return {"results": record.search(q), "sample": False}


@app.get("/device/{device_key}")
def device(device_key: str):
    if not record.has_data():
        return record.sample_record()
    rec = record.build(device_key)
    if rec is None:
        raise HTTPException(404, "No reports found for that device")
    return rec
