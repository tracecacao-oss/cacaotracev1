"""Sesión del usuario. La Parte 2 amplía GET /me con perfil, rol y cooperativa."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import UsuarioToken, usuario_actual
from app.schemas.sesion import MeRespuesta

router = APIRouter(tags=["sesion"])


@router.get("/me", response_model=MeRespuesta)
def me(usuario: Annotated[UsuarioToken, Depends(usuario_actual)]) -> MeRespuesta:
    return MeRespuesta(id=usuario.id, email=usuario.email)
