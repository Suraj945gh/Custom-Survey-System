"""The web app.  Run:  uvicorn app.main:app --reload   then open http://localhost:8000/docs"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, surveys, users
from app.api.schemas import IssueOut
from app.config import settings
from app.db import create_tables
from app.services.errors import ServiceError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Custom Survey System",
        description="Upload, check, approve and run questionnaires.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError):
        body: dict = {"detail": exc.message}
        if exc.issues:
            body["issues"] = [IssueOut.of(i).model_dump() for i in exc.issues]
        return JSONResponse(status_code=exc.status, content=body)

    @app.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(surveys.router)
    return app


app = create_app()
