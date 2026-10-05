"""Parte 4: análisis de cobertura forestal, visitas de campo, expediente legal y compuerta de habilitación.

El operador y el productor arman el expediente; el administrador decide.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.contexto import Contexto, requiere_rol
from app.routers.comun import leer_archivo, modelo_desde_json
from app.schemas.habilitacion import (
    AnalisisDetalle,
    AnalisisSalida,
    AnalisisSolicitado,
    Anulacion,
    ConvergenciaSalida,
    CotejoNuevo,
    ExcluirEntrada,
    ExencionNueva,
    ExencionSalida,
    ExpedienteSalida,
    FuenteSalida,
    HabilitacionSalida,
    HabilitarEntrada,
    ResumenHabilitacion,
    VisitaNueva,
    VisitaSalida,
)
from app.schemas.parcelas import DocumentoSalida
from app.services import analisis, documentos, expediente, habilitacion, visitas
from app.services.fuentes import registro
from app.services.parcelas import parcela_visible
from app.services.productores import documento_salida
from app.storage import ClienteStorage, obtener_storage

router = APIRouter(tags=["habilitacion"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Storage = Annotated[ClienteStorage, Depends(obtener_storage)]


# ---------- Análisis de cobertura forestal ----------


@router.get("/analisis/fuentes", response_model=list[FuenteSalida])
def fuentes(contexto: Lectura):
    return analisis.fuentes_salida(registro.actuales())


@router.post("/parcelas/{parcela_id}/analisis", response_model=AnalisisSolicitado, status_code=202)
def solicitar_analisis(parcela_id: uuid.UUID, contexto: Registro):
    parcela = parcela_visible(contexto, parcela_id)
    filas = analisis.solicitar_a_pedido(contexto, registro.actuales(), parcela)
    return AnalisisSolicitado(analisis=analisis.salidas(contexto.sesion, registro.actuales(), parcela, filas))


@router.get("/parcelas/{parcela_id}/analisis", response_model=list[AnalisisSalida])
def analisis_de_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    parcela = parcela_visible(contexto, parcela_id)
    filas = analisis.de_parcelas(contexto.sesion, [parcela.id])[parcela.id]
    return analisis.salidas(contexto.sesion, registro.actuales(), parcela, filas)


@router.get("/parcelas/{parcela_id}/convergencia", response_model=ConvergenciaSalida)
def convergencia_de_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    """Adenda de la Parte 4: una fila por conjunto de datos y la frase de conteo."""
    parcela = parcela_visible(contexto, parcela_id)
    return analisis.convergencia_salida(contexto.sesion, registro.actuales(), parcela)


@router.get("/analisis/{analisis_id}", response_model=AnalisisDetalle)
def detalle_analisis(analisis_id: uuid.UUID, contexto: Lectura, storage: Storage):
    return analisis.detalle(contexto, registro.actuales(), storage, analisis_id)


# ---------- Visitas de campo ----------


@router.post("/parcelas/{parcela_id}/visitas", response_model=VisitaSalida, status_code=201)
def registrar_visita(
    parcela_id: uuid.UUID,
    contexto: Registro,
    storage: Storage,
    datos: Annotated[str, Form(description="VisitaNueva en JSON")],
    fotos: Annotated[list[UploadFile] | None, File()] = None,
):
    parcela = parcela_visible(contexto, parcela_id)
    visita = modelo_desde_json(VisitaNueva, datos, "datos")
    return visitas.registrar(contexto, storage, parcela, visita, [leer_archivo(f) for f in fotos or []])


@router.get("/parcelas/{parcela_id}/visitas", response_model=list[VisitaSalida])
def visitas_de_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    parcela_visible(contexto, parcela_id)
    return visitas.listar(contexto, parcela_id)


@router.post("/visitas/{visita_id}/anular", response_model=VisitaSalida)
def anular_visita(visita_id: uuid.UUID, datos: Anulacion, contexto: Administrador):
    return visitas.anular(contexto, visita_id, datos.motivo)


# ---------- Expediente legal ----------


@router.get("/parcelas/{parcela_id}/expediente", response_model=ExpedienteSalida)
def expediente_de_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    return expediente.salida(contexto.sesion, parcela_visible(contexto, parcela_id))


@router.post("/documentos/{documento_id}/cotejo", response_model=DocumentoSalida)
def cotejar_documento(documento_id: uuid.UUID, datos: CotejoNuevo, contexto: Registro):
    documento = documentos.documento_visible(contexto, documento_id)
    return documento_salida(expediente.cotejar(contexto, documento, datos.nota), None)


@router.post("/parcelas/{parcela_id}/exenciones", response_model=ExencionSalida, status_code=201)
def declarar_exencion(parcela_id: uuid.UUID, datos: ExencionNueva, contexto: Administrador):
    parcela = parcela_visible(contexto, parcela_id)
    e = expediente.declarar_exencion(contexto, parcela, datos.tipo, datos.motivo)
    return ExencionSalida(
        id=e.id,
        tipo=e.tipo,
        motivo=e.motivo,
        declarada_en=e.declarada_en,
        declarada_por_nombre=None,
        retirada_en=None,
    )


@router.post("/exenciones/{exencion_id}/retirar", status_code=204)
def retirar_exencion(exencion_id: uuid.UUID, contexto: Administrador) -> Response:
    expediente.retirar_exencion(contexto, exencion_id)
    return Response(status_code=204)


# ---------- Compuerta de habilitación ----------


@router.get("/parcelas/{parcela_id}/habilitacion", response_model=HabilitacionSalida)
def habilitacion_de_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    return habilitacion.obtener(contexto, parcela_visible(contexto, parcela_id))


@router.post("/parcelas/{parcela_id}/habilitar", response_model=HabilitacionSalida)
def habilitar_parcela(parcela_id: uuid.UUID, datos: HabilitarEntrada, contexto: Administrador):
    return habilitacion.habilitar(contexto, parcela_visible(contexto, parcela_id), datos.nota)


@router.post("/parcelas/{parcela_id}/excluir", response_model=HabilitacionSalida)
def excluir_parcela(parcela_id: uuid.UUID, datos: ExcluirEntrada, contexto: Administrador):
    return habilitacion.excluir(contexto, parcela_visible(contexto, parcela_id), datos)


@router.get("/habilitacion/resumen", response_model=ResumenHabilitacion)
def resumen_habilitacion(contexto: Lectura):
    return habilitacion.resumen(contexto)
