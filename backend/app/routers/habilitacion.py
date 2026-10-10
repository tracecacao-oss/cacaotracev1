"""Parte 4: análisis de cobertura forestal, cotejo de documentos y compuerta de habilitación.

Desde la adenda 4 la legalidad de la parcela vive en app/routers/legalidad.py. El administrador decide.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.contexto import Contexto, requiere_rol
from app.errores import error_api
from app.schemas.habilitacion import (
    AnalisisDetalle,
    AnalisisSalida,
    AnalisisSolicitado,
    ColaAnalisis,
    ConvergenciaSalida,
    CotejoNuevo,
    ExcluirEntrada,
    FuenteSalida,
    HabilitacionSalida,
    HabilitarEntrada,
    ResumenHabilitacion,
)
from app.schemas.parcelas import DocumentoSalida
from app.services import analisis, documentos, expediente, habilitacion
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


@router.get("/analisis/cola", response_model=ColaAnalisis)
def cola_de_analisis(contexto: Lectura):
    """Parte 10: la cola atiende una consulta a la vez; la interfaz muestra cuántas esperan."""
    return ColaAnalisis(en_cola=analisis.en_cola(contexto.sesion))


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


# ---------- Cotejo en fuente ----------


@router.post("/documentos/{documento_id}/cotejo", response_model=DocumentoSalida)
def cotejar_documento(documento_id: uuid.UUID, datos: CotejoNuevo, contexto: Registro):
    documento = documentos.documento_visible(contexto, documento_id)
    return documento_salida(expediente.cotejar(contexto, documento, datos.nota), None)


@router.post("/parcelas/{parcela_id}/exenciones", status_code=422)
def declarar_exencion(parcela_id: uuid.UUID, contexto: Administrador):
    """Adenda 4, sección 6: ya no se declaran exenciones; las anteriores se conservan como historial."""
    parcela_visible(contexto, parcela_id)
    raise error_api(
        422,
        "exenciones_sin_efecto",
        "Ya no se declaran exenciones: el sistema calcula qué requisitos no aplican desde el perfil legal.",
    )


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
