from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.routers import answer_resolution, data, imports, study, textbooks
from app.schemas import HealthResponse


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Korean Learning Platform API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.include_router(imports.router, prefix="/api/v1")
    app.include_router(textbooks.router, prefix="/api/v1")
    app.include_router(textbooks.lesson_router, prefix="/api/v1")
    app.include_router(data.router, prefix="/api/v1")
    app.include_router(answer_resolution.router, prefix="/api/v1")
    app.include_router(study.router, prefix="/api/v1")

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    def health(session: Session = Depends(get_session)) -> HealthResponse:
        session.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="available")

    return app


app = create_app()
