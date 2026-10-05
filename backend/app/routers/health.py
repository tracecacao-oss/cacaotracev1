"""Health checks. No exigen token: los usan Render y el monitor externo."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import obtener_sesion
from app.schemas.health import SaludBaseRespuesta, SaludRespuesta

log = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=SaludRespuesta)
def health(request: Request) -> SaludRespuesta:
    return SaludRespuesta(status="ok", version=request.app.state.settings.git_sha)


@router.get("/health/db", response_model=SaludBaseRespuesta)
def health_db(sesion: Annotated[Session, Depends(obtener_sesion)]) -> SaludBaseRespuesta:
    try:
        sesion.execute(text("SELECT 1"))
        version = sesion.execute(text("SELECT PostGIS_Version()")).scalar_one()
    except SQLAlchemyError as exc:
        log.error("La base de datos no responde: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail={"codigo": "base_no_disponible", "mensaje": "La base de datos no responde."},
        ) from exc
    return SaludBaseRespuesta(status="ok", postgis=version)
