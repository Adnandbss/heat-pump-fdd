"""FastAPI application factory. Importing this module does not load the model."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from api.deps import MtimeCache
from api.errors import ArtifactMissing, UnprocessableInput
from api.routers import dashboard, inference, thermo
from api.settings import Settings
from src.fdd.inference import FDDEngine
from src.studies.synthetic.scenarios import SyntheticScenarios


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    app.state.caches = {
        "dataset": MtimeCache(),
        "class_counts": MtimeCache(),
        "saturation": MtimeCache(),
    }
    try:
        engine = FDDEngine(settings.classifier_path, settings.metadata_path)
        app.state.engine = engine
        app.state.scenarios = SyntheticScenarios(engine)
    except FileNotFoundError:
        app.state.engine = None
        app.state.scenarios = None
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    application = FastAPI(
        title="Heat Pump FDD API",
        description="Diagnose vapour-compression heat-pump faults from cycle features or simulated conditions.",
        version="2.0.0",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "inference", "description": "Diagnose a cycle or simulate one."},
            {"name": "dashboard", "description": "Payloads that feed the React views."},
            {"name": "thermo", "description": "P-h diagram, COP curve, sweeps, ASHRAE table."},
        ],
    )
    application.state.settings = settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(ArtifactMissing)
    def artifact_missing_handler(_request: Request, exc: ArtifactMissing) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.detail})

    @application.exception_handler(UnprocessableInput)
    def unprocessable_handler(_request: Request, exc: UnprocessableInput) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.detail})

    @application.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    application.include_router(inference.router)
    application.include_router(dashboard.router)
    application.include_router(thermo.router)
    return application
