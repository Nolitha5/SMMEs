from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.data.bootstrap import bootstrap_sample_data
from app.data.factory import get_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo = get_repository()
    if get_settings().repository_backend == "memory" and not repo.list("suppliers"):
        bootstrap_sample_data(repo)
    yield


settings = get_settings()
app = FastAPI(
    title="Retail Procurement Agent API",
    description="Agent 4 Procurement subsystem (R1-R5) for the five-layer Agentic AI retail architecture.",
    version=settings.app_version,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {"service": "Retail Procurement Agent", "agents": ["R1", "R2", "R3", "R4", "R5"], "docs": "/docs"}
