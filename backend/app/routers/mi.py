"""Endpoints del productor sobre sus propios registros. Solo tocan lo suyo."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.contexto import Contexto, requiere_rol
from app.routers.comun import leer_archivo
from app.routers.parcelas import TipoDocumentoParcela, cargar_documento_de_parcela
from app.routers.productores import crear_parcela_desde_formulario
from app.schemas.habilitacion import (
    AnalisisSalida,
    ConvergenciaSalida,
    ExpedienteSalida,
    HabilitacionSalida,
)
from app.schemas.imagenes import ImagenesSalida, RevisionSalida
from app.schemas.parcelas import DocumentoSalida, ParcelaCambios, ParcelaDetalle, ParcelaSalida, UrlDescarga
from app.schemas.productores import MisCambios, ProductorDetalle
from app.schemas.recepcion import DopDetalle, DopSalida, TandaSalida
from app.services import (
    analisis,
    documentos,
    dops,
    expediente,
    habilitacion,
    imagenes,
    parcelas,
    revisiones_imagenes,
    tandas,
)
from app.services import productores as servicio
from app.services.fuentes import registro
from app.services.productores import documento_salida
from app.storage import VIGENCIA_URL_FIRMADA, ClienteStorage, obtener_storage

router = APIRouter(prefix="/mi", tags=["productor"])
Productor = Annotated[Contexto, Depends(requiere_rol("productor"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]


@router.get("/productor", response_model=ProductorDetalle)
def mi_ficha(contexto: Productor):
    return servicio.obtener(contexto, contexto.productor_id)


@router.patch("/productor", response_model=ProductorDetalle)
def editar_mi_ficha(datos: MisCambios, contexto: Productor):
    return servicio.editar_telefono(contexto, datos.telefono)


@router.post("/documentos", response_model=DocumentoSalida, status_code=201)
def cargar_mi_documento(
    contexto: Productor,
    storage: Storage,
    tipo: Annotated[Literal["dni", "constancia_ppa"], Form()],
    archivo: Annotated[UploadFile, File()],
):
    documento = documentos.cargar(
        contexto,
        storage,
        entidad="productor",
        entidad_id=contexto.productor_id,
        tipo=tipo,
        archivo=leer_archivo(archivo),
    )
    return documento_salida(documento, None)


@router.get("/parcelas", response_model=list[ParcelaSalida])
def mis_parcelas(contexto: Productor):
    return parcelas.listar(contexto, productor_id=contexto.productor_id)


@router.post("/parcelas", response_model=ParcelaDetalle, status_code=201)
def crear_mi_parcela(
    contexto: Productor,
    storage: Storage,
    datos: Annotated[str, Form()],
    geometria: Annotated[str | None, Form()] = None,
    archivo: Annotated[UploadFile | None, File()] = None,
    indice: Annotated[int | None, Form()] = None,
):
    return crear_parcela_desde_formulario(
        contexto, storage, contexto.productor_id, datos, geometria, archivo, indice
    )


@router.get("/parcelas/{parcela_id}", response_model=ParcelaDetalle)
def mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    return parcelas.obtener(contexto, parcela_id)


@router.patch("/parcelas/{parcela_id}", response_model=ParcelaDetalle)
def editar_mi_parcela(parcela_id: uuid.UUID, datos: ParcelaCambios, contexto: Productor):
    return parcelas.editar(contexto, parcela_id, datos)


@router.post("/parcelas/{parcela_id}/documentos", response_model=DocumentoSalida, status_code=201)
def cargar_mi_documento_de_parcela(
    parcela_id: uuid.UUID,
    contexto: Productor,
    storage: Storage,
    tipo: Annotated[TipoDocumentoParcela, Form()],
    archivo: Annotated[UploadFile, File()],
    numero: Annotated[str | None, Form()] = None,
    entidad_emisora: Annotated[str | None, Form()] = None,
    fecha_emision: Annotated[date | None, Form()] = None,
    fecha_vencimiento: Annotated[date | None, Form()] = None,
):
    parcela = parcelas.parcela_visible(contexto, parcela_id)
    return cargar_documento_de_parcela(
        contexto, storage, parcela, tipo, archivo, numero, entidad_emisora, fecha_emision, fecha_vencimiento
    )


# ---------- Parte 4: la habilitación de mis parcelas, solo lectura ----------


@router.get("/parcelas/{parcela_id}/analisis", response_model=list[AnalisisSalida])
def analisis_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    parcela = parcelas.parcela_visible(contexto, parcela_id)
    filas = analisis.de_parcelas(contexto.sesion, [parcela.id])[parcela.id]
    # Las mismas tarjetas, sin el enlace a la respuesta completa.
    return analisis.salidas(contexto.sesion, registro.actuales(), parcela, filas, con_respuesta=False)


@router.get("/parcelas/{parcela_id}/convergencia", response_model=ConvergenciaSalida)
def convergencia_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    parcela = parcelas.parcela_visible(contexto, parcela_id)
    return analisis.convergencia_salida(contexto.sesion, registro.actuales(), parcela)


@router.get("/parcelas/{parcela_id}/imagenes", response_model=ImagenesSalida)
def imagenes_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor, storage: Storage):
    """Adenda 2: el productor ve las imágenes de sus parcelas y el resultado de las revisiones."""
    return imagenes.salida(contexto.sesion, storage, parcelas.parcela_visible(contexto, parcela_id))


@router.get("/parcelas/{parcela_id}/revisiones-imagenes", response_model=list[RevisionSalida])
def revisiones_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    return revisiones_imagenes.listar(contexto.sesion, parcelas.parcela_visible(contexto, parcela_id))


@router.get("/parcelas/{parcela_id}/expediente", response_model=ExpedienteSalida)
def expediente_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    return expediente.salida(contexto.sesion, parcelas.parcela_visible(contexto, parcela_id))


@router.get("/parcelas/{parcela_id}/habilitacion", response_model=HabilitacionSalida)
def habilitacion_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    return habilitacion.obtener(contexto, parcelas.parcela_visible(contexto, parcela_id))


# ---------- Parte 5: mis entregas y mis DOP, solo lectura ----------


@router.get("/tandas", response_model=list[TandaSalida])
def mis_tandas(contexto: Productor):
    return tandas.listar(contexto)


@router.get("/dops", response_model=list[DopSalida])
def mis_dops(contexto: Productor):
    return dops.listar(contexto)


@router.get("/dops/{dop_id}", response_model=DopDetalle)
def mi_dop(dop_id: uuid.UUID, contexto: Productor):
    return dops.obtener(contexto, dop_id)


@router.get("/dops/{dop_id}/pdf", response_model=UrlDescarga)
def pdf_de_mi_dop(dop_id: uuid.UUID, contexto: Productor, storage: Storage):
    return UrlDescarga(url=dops.url_pdf(contexto, storage, dop_id), vence_en_segundos=VIGENCIA_URL_FIRMADA)
