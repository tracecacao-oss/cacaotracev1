"""Parcelas de la cooperativa: listado, mapa, análisis de archivos, edición y exportación."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse

from app.contexto import Contexto, requiere_rol
from app.models import Parcela
from app.routers.comun import leer_archivo
from app.schemas.parcelas import (
    AnalisisArchivo,
    DocumentoSalida,
    ParcelaCambios,
    ParcelaDetalle,
    ParcelaSalida,
)
from app.services import documentos
from app.services import parcelas as servicio
from app.services.expediente import no_excluida, validar_datos_legales
from app.services.geometria import TAMANO_MAXIMO_ARCHIVO
from app.services.productores import documento_salida
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(prefix="/parcelas", tags=["parcelas"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Analisis = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "productor"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]
Alerta = Literal["area_discrepante", "diez_hectareas_o_mas", "superposicion", "sin_sustento_midagri"]
TipoDocumentoParcela = Literal[
    "sustento_midagri",
    "titulo_sunarp",
    "constancia_posesion",
    "cusaf",
    "autorizacion_serfor",
    "sunafil",
    "sunat",
    "zonificacion",
]


def cargar_documento_de_parcela(
    contexto: Contexto,
    storage: ClienteStorage,
    parcela: Parcela,
    tipo: str,
    archivo: UploadFile,
    numero,
    entidad_emisora,
    fecha_emision,
    fecha_vencimiento,
) -> DocumentoSalida:
    """La comparten el personal y el productor (sobre sus parcelas)."""
    no_excluida(parcela)
    datos_legales = validar_datos_legales(tipo, numero, entidad_emisora, fecha_emision, fecha_vencimiento)
    documento = documentos.cargar(
        contexto,
        storage,
        entidad="parcela",
        entidad_id=parcela.id,
        tipo=tipo,
        archivo=leer_archivo(archivo),
        datos_legales=datos_legales,
    )
    return documento_salida(documento, None)


@router.get("", response_model=list[ParcelaSalida])
def listar_parcelas(
    contexto: Lectura,
    productor_id: uuid.UUID | None = None,
    estado: Literal["activa", "inactiva"] | None = None,
    alerta: Alerta | None = None,
    formato: Annotated[Literal["json", "geojson"], Query()] = "json",
):
    """Con ?formato=geojson devuelve un FeatureCollection para el mapa."""
    items = servicio.listar(contexto, productor_id=productor_id, estado=estado, alerta=alerta)
    if formato == "geojson":
        return JSONResponse(servicio.coleccion_geojson(contexto, items), media_type="application/geo+json")
    return items


@router.post("/analizar-archivo", response_model=AnalisisArchivo)
def analizar_archivo(
    contexto: Analisis,
    archivo: Annotated[UploadFile, File()],
    productor_id: Annotated[uuid.UUID | None, Form()] = None,
    excluir_parcela_id: Annotated[uuid.UUID | None, Form()] = None,
):
    """Analiza un GeoJSON o KML y devuelve sus geometrías con validaciones. No guarda nada.

    La interfaz también envía aquí la geometría dibujada, como archivo GeoJSON, para validarla
    antes de avanzar; con productor_id anticipa las superposiciones."""
    if contexto.rol == "productor":
        productor_id = contexto.productor_id if productor_id else None
    return AnalisisArchivo(
        geometrias=servicio.analizar(
            contexto, leer_archivo(archivo, TAMANO_MAXIMO_ARCHIVO), productor_id, excluir_parcela_id
        )
    )


@router.get("/{parcela_id}", response_model=ParcelaDetalle)
def detalle_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    return servicio.obtener(contexto, parcela_id)


@router.patch("/{parcela_id}", response_model=ParcelaDetalle)
def editar_parcela(parcela_id: uuid.UUID, datos: ParcelaCambios, contexto: Registro):
    return servicio.editar(contexto, parcela_id, datos)


@router.post("/{parcela_id}/desactivar", response_model=ParcelaDetalle)
def desactivar_parcela(parcela_id: uuid.UUID, contexto: Registro):
    return servicio.desactivar(contexto, parcela_id)


@router.get("/{parcela_id}/geojson")
def exportar_geojson(parcela_id: uuid.UUID, contexto: Lectura):
    return JSONResponse(servicio.exportar_geojson(contexto, parcela_id), media_type="application/geo+json")


@router.post("/{parcela_id}/documentos", response_model=DocumentoSalida, status_code=201)
def cargar_documento(
    parcela_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    tipo: Annotated[TipoDocumentoParcela, Form()],
    archivo: Annotated[UploadFile, File()],
    numero: Annotated[str | None, Form()] = None,
    entidad_emisora: Annotated[str | None, Form()] = None,
    fecha_emision: Annotated[date | None, Form()] = None,
    fecha_vencimiento: Annotated[date | None, Form()] = None,
):
    """Sustento de MIDAGRI o uno de los 7 documentos legales (Parte 4), con sus datos."""
    parcela = servicio.parcela_visible(contexto, parcela_id)
    return cargar_documento_de_parcela(
        contexto, storage, parcela, tipo, archivo, numero, entidad_emisora, fecha_emision, fecha_vencimiento
    )
