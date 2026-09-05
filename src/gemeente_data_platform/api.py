"""FastAPI application factory for the public read-only analytics API."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from gemeente_data_platform.api_models import (
    DatasetLineage,
    ErrorResponse,
    HealthResponse,
    MunicipalityPage,
    MunicipalityResponse,
    NationalPopulation,
    PopulationSeries,
    RankingItem,
    ReadyResponse,
    YearResponse,
)
from gemeente_data_platform.api_repository import REQUIRED_MART_VIEWS, MartRepository
from gemeente_data_platform.config import Settings
from gemeente_data_platform.database import create_api_database_engine
from gemeente_data_platform.pipeline_security import redact

logger = logging.getLogger("gemeente_data_platform.api")


def get_repository(request: Request) -> MartRepository:
    return request.app.state.repository


def create_app(
    settings: Settings | None = None, repository: MartRepository | None = None
) -> FastAPI:
    """Create an app without opening a database connection at import time."""
    active_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = None
        if repository is None:
            engine = create_api_database_engine(active_settings)
            app.state.repository = MartRepository(engine)
        else:
            app.state.repository = repository
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title=active_settings.api_title,
        version=active_settings.api_version,
        description="Read-only analytics API over validated municipal mart views.",
        lifespan=lifespan,
    )
    origins = active_settings.allowed_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "api request failed request_id=%s path=%s",
                request_id,
                redact(request.url.path),
            )
            response = JSONResponse(
                status_code=500,
                content={"error": "internal_error", "request_id": request_id},
            )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        request_id = request.headers.get("X-Request-ID", "unknown")
        logger.warning(
            "database unavailable request_id=%s error=%s", request_id, redact(str(exc))
        )
        return JSONResponse(
            status_code=503,
            content={"error": "database_unavailable", "request_id": request_id},
        )

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get(
        "/ready",
        response_model=ReadyResponse,
        responses={503: {"model": ErrorResponse}},
        tags=["operations"],
    )
    def ready(repo: MartRepository = Depends(get_repository)) -> ReadyResponse:
        if not repo.ready():
            raise HTTPException(
                status_code=503, detail="required mart views are unavailable"
            )
        return ReadyResponse(required_views=list(REQUIRED_MART_VIEWS))

    @app.get("/api/v1/years", response_model=list[YearResponse], tags=["analytics"])
    def years(repo: MartRepository = Depends(get_repository)):
        return repo.years()

    @app.get(
        "/api/v1/municipalities",
        response_model=MunicipalityPage,
        tags=["municipalities"],
    )
    def municipalities(
        search: str | None = Query(default=None, min_length=1, max_length=100),
        active_in_latest_period: bool | None = None,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=100),
        repo: MartRepository = Depends(get_repository),
    ) -> MunicipalityPage:
        items, total = repo.municipalities(
            search, active_in_latest_period, page, page_size
        )
        return MunicipalityPage(
            items=items, page=page, page_size=page_size, total=total
        )

    @app.get(
        "/api/v1/municipalities/{municipality_code}",
        response_model=MunicipalityResponse,
        responses={404: {"model": ErrorResponse}},
        tags=["municipalities"],
    )
    def municipality(
        municipality_code: str, repo: MartRepository = Depends(get_repository)
    ):
        item = repo.municipality(municipality_code.upper())
        if item is None:
            raise HTTPException(status_code=404, detail="municipality not found")
        return item

    @app.get(
        "/api/v1/municipalities/{municipality_code}/population",
        response_model=PopulationSeries,
        responses={404: {"model": ErrorResponse}},
        tags=["analytics"],
    )
    def population(
        municipality_code: str, repo: MartRepository = Depends(get_repository)
    ) -> PopulationSeries:
        code = municipality_code.upper()
        municipality_item = repo.municipality(code)
        if municipality_item is None:
            raise HTTPException(status_code=404, detail="municipality not found")
        return PopulationSeries(
            municipality_code=code,
            municipality_name=municipality_item["municipality_name"],
            observations=repo.population(code),
        )

    @app.get(
        "/api/v1/national/population",
        response_model=list[NationalPopulation],
        tags=["analytics"],
    )
    def national_population(repo: MartRepository = Depends(get_repository)):
        return repo.national_population()

    @app.get(
        "/api/v1/rankings/population",
        response_model=list[RankingItem],
        tags=["analytics"],
    )
    def rankings(
        year: int = Query(..., ge=1800, le=2200),
        limit: int = Query(default=10, ge=1, le=500),
        repo: MartRepository = Depends(get_repository),
    ):
        return repo.rankings(year, limit)

    @app.get(
        "/api/v1/lineage/latest",
        response_model=DatasetLineage | None,
        tags=["analytics"],
    )
    def latest_lineage(repo: MartRepository = Depends(get_repository)):
        """Expose only the latest successful load's public-safe identifiers."""
        return repo.latest_lineage()

    return app


app = create_app()
