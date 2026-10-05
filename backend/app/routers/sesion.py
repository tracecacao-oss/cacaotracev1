"""Sesión: GET /me, POST /me/clave y POST /me/consentimiento."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.auth_admin import ClienteAuthAdmin, obtener_auth_admin
from app.contexto import Contexto, obtener_contexto, requiere_rol
from app.schemas.sesion import CambioClave, Consentimiento, MeRespuesta
from app.services import sesion as servicio

router = APIRouter(tags=["sesion"])


@router.get("/me", response_model=MeRespuesta)
def me(contexto: Annotated[Contexto, Depends(obtener_contexto)]) -> MeRespuesta:
    return servicio.datos_me(contexto)


@router.post("/me/clave", status_code=204)
def cambiar_clave(
    datos: CambioClave,
    contexto: Annotated[Contexto, Depends(obtener_contexto)],
    auth: Annotated[ClienteAuthAdmin, Depends(obtener_auth_admin)],
) -> Response:
    servicio.cambiar_clave(contexto, auth, datos.clave_actual, datos.clave_nueva)
    return Response(status_code=204)


@router.post("/me/consentimiento", status_code=204)
def consentimiento(
    datos: Consentimiento,
    contexto: Annotated[Contexto, Depends(requiere_rol("productor"))],
) -> Response:
    servicio.registrar_consentimiento(contexto, datos.version_texto)
    return Response(status_code=204)
