"""FastAPI app entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import jobs
from api.config import settings
from api.routes import download, jobs as jobs_routes, upload

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.init_db()
    yield


app = FastAPI(
    title="cite2fn",
    description="Convert citations in .docx documents to Bluebook or APA footnotes, endnotes, or references.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(jobs_routes.router, prefix="/api")
app.include_router(download.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "groq_configured": settings.groq_api_key is not None,
        "max_upload_mb": settings.max_upload_mb,
    }
