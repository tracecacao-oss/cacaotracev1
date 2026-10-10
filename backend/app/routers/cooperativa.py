"""Parte 8: datos y expediente legal de la cooperativa, documentos de embarque del lote, recomprobación y
pendientes. Los documentos de la cooperativa los carga solo un administrador; los de embarque, el
administrador o el operador. Desde la adenda 6, la declaración aduanera también se carga con el lote cerrado.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.catalogos import documentos_embarque, documentos_legales
from app.contexto import Contexto, requiere_rol
from app.routers.comun import leer_archivo
from app.schemas.cooperativa import (
    CooperativaCambios,
    CooperativaPropia,
    EmbarqueSalida,
    ExpedienteCooperativa,
    PendientesSalida,
    RecomprobacionSalida,
)
from app.schemas.diligencia import Anulacion
from app.schemas.parcelas import DocumentoSalida
from app.services import cooperativa, embarque, pendientes, recomprobacion
from app.services.productores import documento_salida
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(tags=["cooperativa"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]
# Los anteriores también se admiten aquí para responder con su motivo (adenda 6, sección 4, regla 4).
TipoLegalCooperativa = Literal[documentos_legales.TODOS_COOPERATIVA]
TipoEmbarque = Literal[documentos_embarque.CODIGOS]

# ---------- Cooperativa ----------


@router.get("/cooperativa", response_model=CooperativaPropia)
def datos_de_la_cooperativa(contexto: Lectura):
    return cooperativa.obtener(contexto)


@router.patch("/cooperativa", response_model=CooperativaPropia)
def editar_cooperativa(datos: CooperativaCambios, contexto: Administrador):
    return cooperativa.editar(contexto, datos)


@router.get("/cooperativa/expediente", response_model=ExpedienteCooperativa)
def expediente_de_la_cooperativa(contexto: Lectura):
    return cooperativa.expediente(contexto)


@router.post("/cooperativa/documentos", response_model=DocumentoSalida, status_code=201)
def cargar_documento_de_la_cooperativa(
    contexto: Administrador,
    storage: Storage,
    tipo: Annotated[TipoLegalCooperativa, Form()],
    archivo: Annotated[UploadFile, File()],
    numero: Annotated[str | None, Form()] = None,
    entidad_emisora: Annotated[str | None, Form()] = None,
    fecha_emision: Annotated[date | None, Form()] = None,
    fecha_vencimiento: Annotated[date | None, Form()] = None,
):
    """Un documento legal de la organización que aplica a su tipo, con número, entidad emisora y fechas."""
    documento = cooperativa.cargar_documento(
        contexto,
        storage,
        tipo,
        leer_archivo(archivo),
        numero=numero,
        entidad_emisora=entidad_emisora,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
    )
    return documento_salida(documento, None)


# ---------- Lote: embarque y recomprobación ----------


@router.post("/lotes/{lote_id}/documentos", response_model=DocumentoSalida, status_code=201)
def cargar_documento_de_embarque(
    lote_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    tipo: Annotated[TipoEmbarque, Form()],
    archivo: Annotated[UploadFile, File()],
    numero: Annotated[str | None, Form()] = None,
    entidad_emisora: Annotated[str | None, Form()] = None,
    fecha_emision: Annotated[date | None, Form()] = None,
    peso_neto_kg: Annotated[Decimal | None, Form(max_digits=10, decimal_places=2)] = None,
    subpartida: Annotated[str | None, Form(max_length=20)] = None,
):
    """Adenda 7: la declaración aduanera lleva además su peso neto y su subpartida; `fecha_emision` es su
    fecha de numeración."""
    documento = embarque.cargar(
        contexto,
        storage,
        lote_id,
        tipo,
        leer_archivo(archivo),
        numero,
        entidad_emisora,
        fecha_emision,
        peso_neto_kg,
        subpartida,
    )
    return documento_salida(documento, None)


@router.post("/lotes/{lote_id}/declaracion-aduanera/anular", response_model=EmbarqueSalida)
def anular_declaracion_aduanera(lote_id: uuid.UUID, datos: Anulacion, contexto: Administrador):
    """Adenda 7: se anula con motivo, junto con su archivo; después se puede cargar otra."""
    return embarque.anular_declaracion(contexto, lote_id, datos.motivo)


@router.get("/lotes/{lote_id}/documentos", response_model=EmbarqueSalida)
def documentos_de_embarque(lote_id: uuid.UUID, contexto: Lectura):
    return embarque.listar(contexto, lote_id)


@router.post("/lotes/{lote_id}/recomprobar", response_model=RecomprobacionSalida)
def recomprobar_lote(lote_id: uuid.UUID, contexto: Registro):
    return recomprobacion.recomprobar(contexto, lote_id)


@router.get("/lotes/{lote_id}/recomprobaciones", response_model=list[RecomprobacionSalida])
def historial_de_recomprobaciones(lote_id: uuid.UUID, contexto: Lectura):
    return recomprobacion.historial(contexto, lote_id)


# ---------- Pendientes ----------


@router.get("/pendientes", response_model=PendientesSalida)
def pendientes_de_la_cooperativa(contexto: Lectura):
    return pendientes.pendientes(contexto)
