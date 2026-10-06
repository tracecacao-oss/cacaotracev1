"""Parte 7: importadores, órdenes de compra, lotes de exportación con su genealogía y la trazabilidad en los
dos sentidos. Crean y modifican el administrador y el operador; el lector solo consulta."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.contexto import Contexto, requiere_rol
from app.schemas.exportacion import (
    Confirmacion,
    EstadoLote,
    EstadoOrden,
    Genealogia,
    ImportadorCambios,
    ImportadorNuevo,
    ImportadorSalida,
    LoteDetalle,
    LoteSalida,
    OrdenCambios,
    OrdenDetalle,
    OrdenNueva,
    OrdenSalida,
    Recorrido,
    Seleccion,
    SugerenciaFifo,
)
from app.schemas.recepcion import Motivo
from app.services import lotes, ordenes, trazabilidad

router = APIRouter(tags=["exportacion"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]

# ---------- Importadores ----------


@router.get("/importadores", response_model=list[ImportadorSalida])
def listar_importadores(contexto: Lectura):
    return ordenes.importadores(contexto)


@router.post("/importadores", response_model=ImportadorSalida, status_code=201)
def crear_importador(datos: ImportadorNuevo, contexto: Registro):
    return ordenes.crear_importador(contexto, datos)


@router.patch("/importadores/{importador_id}", response_model=ImportadorSalida)
def editar_importador(importador_id: uuid.UUID, datos: ImportadorCambios, contexto: Registro):
    return ordenes.editar_importador(contexto, importador_id, datos)


# ---------- Órdenes de compra ----------


@router.get("/ordenes", response_model=list[OrdenSalida])
def listar_ordenes(
    contexto: Lectura,
    estado: EstadoOrden | None = None,
    importador_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
):
    return ordenes.listar(contexto, estado=estado, importador_id=importador_id, desde=desde, hasta=hasta)


@router.post("/ordenes", response_model=OrdenDetalle, status_code=201)
def crear_orden(datos: OrdenNueva, contexto: Registro):
    return ordenes.crear(contexto, datos)


@router.get("/ordenes/{orden_id}", response_model=OrdenDetalle)
def detalle_orden(orden_id: uuid.UUID, contexto: Lectura):
    return ordenes.obtener(contexto, orden_id)


@router.patch("/ordenes/{orden_id}", response_model=OrdenDetalle)
def editar_orden(orden_id: uuid.UUID, datos: OrdenCambios, contexto: Registro):
    return ordenes.editar(contexto, orden_id, datos)


@router.post("/ordenes/{orden_id}/anular", response_model=OrdenDetalle)
def anular_orden(orden_id: uuid.UUID, datos: Motivo, contexto: Registro):
    return ordenes.anular(contexto, orden_id, datos.motivo)


# ---------- Lotes ----------


@router.post("/ordenes/{orden_id}/lote", response_model=LoteDetalle, status_code=201)
def crear_lote(orden_id: uuid.UUID, contexto: Registro):
    return lotes.crear(contexto, orden_id)


@router.get("/lotes", response_model=list[LoteSalida])
def listar_lotes(contexto: Lectura, estado: EstadoLote | None = None):
    return lotes.listar(contexto, estado)


@router.get("/lotes/{lote_id}", response_model=LoteDetalle)
def detalle_lote(lote_id: uuid.UUID, contexto: Lectura):
    return lotes.obtener(contexto, lote_id)


@router.get("/lotes/{lote_id}/sugerencia-fifo", response_model=SugerenciaFifo)
def sugerencia_fifo(lote_id: uuid.UUID, contexto: Lectura):
    return lotes.sugerencia_fifo(contexto, lote_id)


@router.put("/lotes/{lote_id}/asignaciones", response_model=LoteDetalle)
def cambiar_seleccion(lote_id: uuid.UUID, datos: Seleccion, contexto: Registro):
    return lotes.cambiar_seleccion(contexto, lote_id, datos)


@router.post("/lotes/{lote_id}/confirmar", response_model=LoteDetalle)
def confirmar_lote(lote_id: uuid.UUID, datos: Confirmacion, contexto: Registro):
    return lotes.confirmar(contexto, lote_id, datos)


@router.post("/lotes/{lote_id}/anular", response_model=LoteDetalle)
def anular_lote(lote_id: uuid.UUID, datos: Motivo, contexto: Registro):
    return lotes.anular(contexto, lote_id, datos.motivo)


@router.get("/lotes/{lote_id}/genealogia", response_model=Genealogia)
def genealogia(lote_id: uuid.UUID, contexto: Lectura):
    return lotes.genealogia(contexto, lote_id)


# ---------- Trazabilidad ----------


@router.get("/trazabilidad/parcelas/{parcela_id}", response_model=Recorrido)
def trazar_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    return trazabilidad.de_parcela(contexto, parcela_id)


@router.get("/trazabilidad/productores/{productor_id}", response_model=Recorrido)
def trazar_productor(productor_id: uuid.UUID, contexto: Lectura):
    return trazabilidad.de_productor(contexto, productor_id)


@router.get("/trazabilidad/dops/{dop_id}", response_model=Recorrido)
def trazar_dop(dop_id: uuid.UUID, contexto: Lectura):
    return trazabilidad.de_dop(contexto, dop_id)
