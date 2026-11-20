from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import pipelines, signals
from .config import settings
from .db import init_db
from .pipelines.runner import mark_interrupted_runs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    mark_interrupted_runs()
    yield


app = FastAPI(title="Options Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipelines.router)
app.include_router(signals.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "alpaca_configured": bool(settings.alpaca_key and settings.alpaca_secret),
        "finnhub_configured": bool(settings.finnhub_key),
        "option_feed": settings.alpaca_option_feed,
    }
