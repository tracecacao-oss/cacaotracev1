"""Catálogo oficial de ubicaciones del Perú para las listas de departamento, provincia y distrito."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app import ubigeo
from app.contexto import Contexto, obtener_contexto
from app.schemas.ubigeos import CatalogoUbigeos

router = APIRouter(tags=["catalogos"])


@router.get("/ubigeos", response_model=CatalogoUbigeos)
def ubigeos(contexto: Annotated[Contexto, Depends(obtener_contexto)], response: Response):
    # El catálogo solo cambia con un deploy: el navegador puede guardarlo un día.
    response.headers["Cache-Control"] = "private, max-age=86400"
    return {
        "fuente": ubigeo.FUENTE,
        "departamentos": [
            {"nombre": dep, "provincias": [{"nombre": p, "distritos": d} for p, d in provincias.items()]}
            for dep, provincias in ubigeo.catalogo().arbol.items()
        ],
    }
