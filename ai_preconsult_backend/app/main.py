from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import ai_preconsult_backend.app.core.env  # noqa: F401  load .env before anything else
from ai_preconsult_backend.app.api.preconsult import router as preconsult_router
from ai_preconsult_backend.app.db.sqlite_store import init_db


app = FastAPI(title="AI 预问诊后端 MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(preconsult_router)
