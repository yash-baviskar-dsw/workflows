import os
from fastapi import FastAPI

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME", "service2")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.4.6")

@app.get("/")
def read_root():
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "healthy"
    }

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
