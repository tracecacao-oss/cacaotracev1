"""Documentos: descarga con URL firmada de 5 minutos y anulación con motivo."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.contexto import Contexto, requiere_rol
from app.schemas.parcelas import Anulacion, DocumentoSalida, UrlDescarga
from app.services import documentos as servicio
from app.services.productores import documento_salida
from app.storage import VIGENCIA_URL_FIRMADA, ClienteStorage, obtener_storage

router = APIRouter(prefix="/documentos", tags=["documentos"])
Lectura = Annotated[
    Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin", "productor"))
]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]


@router.get("/{documento_id}/url", response_model=UrlDescarga)
def url_de_descarga(documento_id: uuid.UUID, contexto: Lectura, storage: Storage):
    return UrlDescarga(
        url=servicio.url_firmada(contexto, storage, documento_id), vence_en_segundos=VIGENCIA_URL_FIRMADA
    )


@router.post("/{documento_id}/anular", response_model=DocumentoSalida)
def anular_documento(documento_id: uuid.UUID, datos: Anulacion, contexto: Registro):
    return documento_salida(servicio.anular(contexto, documento_id, datos.motivo), None)
