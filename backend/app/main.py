"""PRISM API – FastAPI application.

Uploads are processed per request and are not saved as persistent application data.
The multipart framework may temporarily buffer an upload before the endpoint reads it.
No database connection is made.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import processing as P
from .exporter import build_workbook

logger = logging.getLogger("prism")

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


app = FastAPI(title="PRISM API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(P.ProcessingError)
async def processing_error_handler(_: Request, exc: P.ProcessingError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.to_detail()})


def _read_upload(file: UploadFile) -> bytes:
    content = file.file.read(P.MAX_UPLOAD_BYTES + 1)
    if len(content) > P.MAX_UPLOAD_BYTES:
        raise P.ProcessingError("FILE_TOO_LARGE", "The file is larger than the 15 MB limit.", 413)
    return content


def _analyze(file: UploadFile, advanced: float, attention: float, mapping: Optional[str]) -> dict:
    content = _read_upload(file)
    try:
        return P.analyze_dataset(
            content, file.filename or "", advanced, attention, P.parse_mapping(mapping)
        )
    except P.ProcessingError:
        raise
    except Exception:  # never leak internals to the client
        logger.exception("Unexpected error while analysing upload")
        raise P.ProcessingError("INTERNAL_ERROR", "Unexpected error while processing the file.", 500)


@app.get("/")
def root() -> dict:
    return {"name": "PRISM API", "status": "ok", "docs": "/docs"}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Endpoints are plain `def` so FastAPI runs the CPU-bound pandas work in a thread pool.
@app.post("/api/analyze")
def analyze(
    file: UploadFile = File(...),
    advanced_threshold: float = Form(P.DEFAULT_ADVANCED),
    attention_threshold: float = Form(P.DEFAULT_ATTENTION),
    mapping: Optional[str] = Form(None),
) -> dict:
    return _analyze(file, advanced_threshold, attention_threshold, mapping)


@app.post("/api/export")
def export(
    file: UploadFile = File(...),
    advanced_threshold: float = Form(P.DEFAULT_ADVANCED),
    attention_threshold: float = Form(P.DEFAULT_ATTENTION),
    mapping: Optional[str] = Form(None),
) -> Response:
    result = _analyze(file, advanced_threshold, attention_threshold, mapping)
    try:
        data = build_workbook(result)
    except Exception:
        logger.exception("Unexpected error while building workbook")
        raise P.ProcessingError("INTERNAL_ERROR", "Could not build the Excel workbook.", 500)
    return Response(
        content=data,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": 'attachment; filename="PRISM_processed.xlsx"'},
    )
