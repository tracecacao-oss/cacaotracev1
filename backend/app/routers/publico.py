"""Endpoints públicos, sin token (Parte 5): la verificación de un DOP. Límite de 30 consultas por minuto
por dirección IP."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import obtener_sesion
from app.limite import limite_publico
from app.schemas.recepcion import DopPublico
from app.services import dops

router = APIRouter(prefix="/publico", tags=["publico"], dependencies=[Depends(limite_publico)])


@router.get("/dops/{codigo}", response_model=DopPublico)
def verificar_dop(codigo: str, sesion: Annotated[Session, Depends(obtener_sesion)]):
    return dops.publico(sesion, codigo)
