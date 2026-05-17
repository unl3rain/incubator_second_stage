import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.db import init_db
from app.services.advanced_engine import get_engine_status

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    status = get_engine_status()
    if status["provider"] == "py-draughts" and not status["available"]:
        logger.warning(
            "Advanced coach engine unavailable (%s). Falling back to heuristic analysis.",
            status["reason"],
        )
    else:
        logger.info(
            "Coach engine status: provider=%s available=%s depth=%s time_limit=%s",
            status["provider"],
            status["available"],
            status["configured_depth"],
            status["configured_time_limit"],
        )


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Checkers backend is running"}
