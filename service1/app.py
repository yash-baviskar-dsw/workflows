import os
from fastapi import FastAPI

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME", "service1")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.9")

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

@app.get("/info")
def info():
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "environment": "dev"
    }
