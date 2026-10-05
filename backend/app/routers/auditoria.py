"""Auditoría: solo lectura. No existe endpoint que la modifique."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.contexto import Contexto, requiere_rol
from app.schemas.auditoria import AuditoriaSalida
from app.schemas.comunes import Pagina
from app.services.auditoria import consulta_auditoria
from app.services.paginacion import ParametrosPaginacion, paginar

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=Pagina[AuditoriaSalida])
def listar_auditoria(
    contexto: Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "superadmin"))],
    paginacion: ParametrosPaginacion,
    desde: date | None = None,
    hasta: date | None = None,
    usuario_id: uuid.UUID | None = None,
    accion: Annotated[str | None, Query(max_length=60)] = None,
):
    # El superadmin sin cooperativa elegida ve la auditoría de toda la plataforma.
    todas = contexto.rol == "superadmin" and contexto.cooperativa_id is None
    consulta = consulta_auditoria(
        contexto.cooperativa_id, todas=todas, desde=desde, hasta=hasta, usuario_id=usuario_id, accion=accion
    )
    filas, total = paginar(contexto.sesion, consulta, paginacion)
    items = [
        AuditoriaSalida.model_validate(registro).model_copy(update={"usuario_nombre": nombre})
        for registro, nombre in filas
    ]
    return Pagina(items=items, total=total, pagina=paginacion.pagina, por_pagina=paginacion.por_pagina)
