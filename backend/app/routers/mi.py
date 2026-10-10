"""Endpoints del productor sobre sus propios registros. Solo tocan lo suyo."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.contexto import Contexto, requiere_rol
from app.errores import error_api
from app.models import Cooperativa
from app.routers.comun import leer_archivo
from app.routers.legalidad import Plantilla, pdf
from app.routers.parcelas import ClaseTitulo, TipoDocumentoParcela, cargar_documento_de_parcela
from app.routers.productores import crear_parcela_desde_formulario
from app.schemas.declaracion import DeclaracionProductorSalida, MiDeclaracion
from app.schemas.habilitacion import AnalisisSalida, ConvergenciaSalida, HabilitacionSalida
from app.schemas.imagenes import ImagenesSalida, RevisionSalida
from app.schemas.legalidad import LegalidadSalida
from app.schemas.parcelas import DocumentoSalida, ParcelaCambios, ParcelaDetalle, ParcelaSalida, UrlDescarga
from app.schemas.productores import MisCambios, ProductorDetalle
from app.schemas.recepcion import DopDetalle, DopSalida, TandaSalida
from app.services import (
    analisis,
    declaracion_productor,
    documentos,
    dops,
    habilitacion,
    imagenes,
    legalidad,
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
    ficha = servicio.obtener(contexto, contexto.productor_id)
    # Adenda 6, sección 5: el contacto del canal de quejas y denuncias de su organización. El sistema no
    # recibe denuncias: solo muestra a dónde llevarlas.
    cooperativa = contexto.cooperativa_id and contexto.sesion.get(Cooperativa, contexto.cooperativa_id)
    contacto = cooperativa.canal_denuncias_contacto if cooperativa else None
    return ficha.model_copy(update={"canal_denuncias_contacto": contacto})


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
    clase: Annotated[ClaseTitulo | None, Form()] = None,
):
    parcela = parcelas.parcela_visible(contexto, parcela_id)
    return cargar_documento_de_parcela(
        contexto,
        storage,
        parcela,
        tipo,
        archivo,
        numero,
        entidad_emisora,
        fecha_emision,
        fecha_vencimiento,
        clase,
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


@router.get("/parcelas/{parcela_id}/legalidad", response_model=LegalidadSalida)
def legalidad_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    """Adenda 4: el productor ve su perfil, sus requisitos y sus incidencias; no los edita."""
    return legalidad.salida(contexto.sesion, parcelas.parcela_visible(contexto, parcela_id))


@router.get("/parcelas/{parcela_id}/plantillas/{nombre}")
def plantilla_de_mi_parcela(parcela_id: uuid.UUID, nombre: Plantilla, contexto: Productor):
    return pdf(*legalidad.plantilla(contexto.sesion, parcelas.parcela_visible(contexto, parcela_id), nombre))


@router.get("/parcelas/{parcela_id}/habilitacion", response_model=HabilitacionSalida)
def habilitacion_de_mi_parcela(parcela_id: uuid.UUID, contexto: Productor):
    return habilitacion.obtener(contexto, parcelas.parcela_visible(contexto, parcela_id))


# ---------- Adenda 5: mi declaración anual ----------


def _mi_declaracion(contexto: Contexto) -> DeclaracionProductorSalida:
    declaracion_productor.productor_afiliado(contexto, contexto.productor_id)
    # El productor no ve la nota de seguimiento (sección 10).
    return declaracion_productor.salida(
        contexto.sesion, contexto.productor_id, contexto.cooperativa_id, personal=False
    )


@router.get("/declaracion", response_model=DeclaracionProductorSalida)
def mi_declaracion(contexto: Productor):
    return _mi_declaracion(contexto)


@router.post("/declaracion", response_model=DeclaracionProductorSalida, status_code=201)
def declarar(datos: MiDeclaracion, contexto: Productor):
    declaracion_productor.declarar(contexto, datos.respuestas, datos.declaro)
    return _mi_declaracion(contexto)


@router.get("/declaracion/hoja")
def hoja_de_mi_declaracion(contexto: Productor):
    """La copia de mi declaración vigente."""
    declaracion_productor.productor_afiliado(contexto, contexto.productor_id)
    estado = declaracion_productor.estado_de(contexto.sesion, contexto.productor_id, contexto.cooperativa_id)
    if estado.vigente is None:
        raise error_api(404, "sin_declaracion", "Todavía no tienes una declaración anual.")
    return pdf(*declaracion_productor.hoja(contexto.sesion, estado.vigente))


@router.post("/declaracion/documentos", response_model=DocumentoSalida, status_code=201)
def cargar_papel_de_mi_declaracion(
    contexto: Productor,
    storage: Storage,
    tipo: Annotated[Literal["relacion_trabajadores", "declaracion_renta"], Form()],
    archivo: Annotated[UploadFile, File()],
):
    documento = declaracion_productor.cargar_papel(
        contexto, storage, contexto.productor_id, None, tipo, leer_archivo(archivo)
    )
    return documento_salida(documento, None)


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
