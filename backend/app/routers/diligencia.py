"""Adenda 6, sección 9: la política de la organización, sus actuaciones de diligencia, el cuadro de señales y
la lista de productos buscados en el registro del SENASA.

La política la carga y la anula solo un administrador. Las actuaciones las registran el administrador y el
operador; las anula solo el administrador. El lector solo ve. Otra organización recibe 404.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.contexto import Contexto, requiere_rol
from app.routers.comun import leer_archivo
from app.routers.legalidad import pdf
from app.schemas.diligencia import (
    ActuacionDetalle,
    ActuacionNueva,
    ActuacionSalida,
    Anulacion,
    DiligenciaSalida,
    PoliticasSalida,
    ProductosRevisadosSalida,
    TemaActuacion,
    TemaPolitica,
    TipoActuacion,
)
from app.services import diligencia
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(tags=["diligencia"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]

# ---------- Política ----------


@router.get("/cooperativa/politica/hoja")
def politica_para_firmar(contexto: Administrador):
    return pdf(*diligencia.hoja_politica(contexto))


@router.get("/cooperativa/politicas", response_model=PoliticasSalida)
def politicas(contexto: Lectura):
    return diligencia.politicas(contexto)


@router.post("/cooperativa/politicas", response_model=PoliticasSalida, status_code=201)
def cargar_politica(
    contexto: Administrador,
    storage: Storage,
    archivo: Annotated[UploadFile, File()],
    temas: Annotated[list[TemaPolitica], Form()],
    adoptada_en: Annotated[date, Form()],
    organo: Annotated[str, Form()],
    version_plantilla: Annotated[int | None, Form()] = None,
):
    return diligencia.cargar_politica(
        contexto, storage, leer_archivo(archivo), temas, adoptada_en, organo, version_plantilla
    )


@router.post("/cooperativa/politicas/{politica_id}/anular", response_model=PoliticasSalida)
def anular_politica(politica_id: uuid.UUID, datos: Anulacion, contexto: Administrador):
    return diligencia.anular_politica(contexto, politica_id, datos.motivo)


# ---------- Cuadro de señales y lista de productos ----------


@router.get("/cooperativa/diligencia", response_model=DiligenciaSalida)
def cuadro_de_senales(contexto: Lectura):
    return diligencia.cuadro(contexto)


@router.get("/cooperativa/productos-revisados", response_model=ProductosRevisadosSalida)
def productos_revisados(contexto: Lectura):
    return diligencia.productos(contexto)


@router.get("/cooperativa/productos-revisados/hoja")
def lista_de_productos(contexto: Lectura):
    return pdf(*diligencia.hoja_productos(contexto))


# ---------- Actuaciones ----------


@router.get("/actuaciones", response_model=list[ActuacionSalida])
def actuaciones(
    contexto: Lectura,
    tipo: TipoActuacion | None = None,
    tema: TemaActuacion | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    productor_id: uuid.UUID | None = None,
):
    return diligencia.listar(
        contexto, tipo=tipo, tema=tema, desde=desde, hasta=hasta, productor_id=productor_id
    )


@router.post("/actuaciones", response_model=ActuacionDetalle, status_code=201)
def registrar_actuacion(datos: ActuacionNueva, contexto: Registro):
    return diligencia.registrar(contexto, datos)


@router.get("/actuaciones/{actuacion_id}", response_model=ActuacionDetalle)
def ficha_de_la_actuacion(actuacion_id: uuid.UUID, contexto: Lectura):
    return diligencia.ficha(contexto, actuacion_id)


@router.post("/actuaciones/{actuacion_id}/evidencias", response_model=ActuacionDetalle, status_code=201)
def cargar_evidencia(
    actuacion_id: uuid.UUID, contexto: Registro, storage: Storage, archivo: Annotated[UploadFile, File()]
):
    return diligencia.cargar_evidencia(contexto, storage, actuacion_id, leer_archivo(archivo))


@router.post("/actuaciones/{actuacion_id}/anular", response_model=ActuacionDetalle)
def anular_actuacion(actuacion_id: uuid.UUID, datos: Anulacion, contexto: Administrador):
    return diligencia.anular(contexto, actuacion_id, datos.motivo)
