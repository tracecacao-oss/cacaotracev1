"""Parte 9: informe de hallazgos, DEX, certificaciones de la cooperativa y clasificación del país. Emite y
anula el DEX solo un administrador; descargan el administrador y el operador; el lector solo consulta."""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.contexto import Contexto, requiere_rol
from app.routers.comun import leer_archivo
from app.schemas.dex import (
    CertificacionCambios,
    CertificacionNueva,
    CertificacionSalida,
    ConfiguracionPlataformaEntrada,
    ConfiguracionPlataformaSalida,
    DescargaDex,
    DexDetalle,
    DexSalida,
    EmisionDex,
    EstadoDex,
)
from app.schemas.recepcion import Motivo
from app.services import certificaciones, configuracion_plataforma, dex, hallazgos
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(tags=["dex"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Descarga = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Superadmin = Annotated[Contexto, Depends(requiere_rol("superadmin"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]

# ---------- Informe y DEX ----------


@router.get("/lotes/{lote_id}/hallazgos")
def informe_preliminar(lote_id: uuid.UUID, contexto: Lectura) -> dict[str, Any]:
    return hallazgos.preliminar(contexto, lote_id)


@router.get("/lotes/{lote_id}/geojson")
def geojson_preliminar(lote_id: uuid.UUID, contexto: Lectura):
    return JSONResponse(dex.geojson_preliminar(contexto, lote_id), media_type="application/geo+json")


@router.post("/lotes/{lote_id}/dex", response_model=DexDetalle, status_code=201)
def emitir_dex(lote_id: uuid.UUID, datos: EmisionDex, contexto: Administrador, storage: Storage):
    return dex.emitir(contexto, storage, lote_id, datos.entiendo)


@router.get("/dex", response_model=list[DexSalida])
def listar_dex(contexto: Lectura, estado: EstadoDex | None = None, importador_id: uuid.UUID | None = None):
    return dex.listar(contexto, estado=estado, importador_id=importador_id)


@router.get("/dex/{dex_id}", response_model=DexDetalle)
def detalle_dex(dex_id: uuid.UUID, contexto: Lectura):
    return dex.obtener(contexto, dex_id)


@router.get("/dex/{dex_id}/descargas", response_model=list[DescargaDex])
def descargas_dex(dex_id: uuid.UUID, contexto: Descarga, storage: Storage):
    return dex.descargas(contexto, storage, dex_id)


@router.post("/dex/{dex_id}/anular", response_model=DexDetalle)
def anular_dex(dex_id: uuid.UUID, datos: Motivo, contexto: Administrador):
    return dex.anular(contexto, dex_id, datos.motivo)


# ---------- Certificaciones ----------


@router.get("/certificaciones", response_model=list[CertificacionSalida])
def listar_certificaciones(contexto: Lectura):
    return certificaciones.listar(contexto)


@router.post("/certificaciones", response_model=CertificacionSalida, status_code=201)
def registrar_certificacion(
    contexto: Administrador,
    storage: Storage,
    nombre: Annotated[str, Form()],
    entidad_certificadora: Annotated[str, Form()],
    numero: Annotated[str, Form()],
    vigente_desde: Annotated[date, Form()],
    vigente_hasta: Annotated[date, Form()],
    archivo: Annotated[UploadFile, File()],
):
    try:
        datos = CertificacionNueva(
            nombre=nombre,
            entidad_certificadora=entidad_certificadora,
            numero=numero,
            vigente_desde=vigente_desde,
            vigente_hasta=vigente_hasta,
        )
    except ValidationError as exc:
        raise RequestValidationError(
            [{**e, "loc": ("body", *e.get("loc", ()))} for e in exc.errors()]
        ) from exc
    return certificaciones.registrar(contexto, storage, datos, leer_archivo(archivo))


@router.patch("/certificaciones/{certificacion_id}", response_model=CertificacionSalida)
def editar_certificacion(certificacion_id: uuid.UUID, datos: CertificacionCambios, contexto: Administrador):
    return certificaciones.editar(contexto, certificacion_id, datos)


# ---------- Configuración de plataforma ----------


@router.get("/admin/configuracion", response_model=ConfiguracionPlataformaSalida)
def configuracion(contexto: Superadmin):
    return configuracion_plataforma.salida(contexto.sesion)


@router.put("/admin/configuracion", response_model=ConfiguracionPlataformaSalida)
def cambiar_configuracion(datos: ConfiguracionPlataformaEntrada, contexto: Superadmin):
    return configuracion_plataforma.cambiar(contexto, datos)
