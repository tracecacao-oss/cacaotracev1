"""Adenda 4: legalidad de la parcela por requisito.

Declaran el perfil el administrador y el operador; registran incidencias los dos y las cierra solo el
administrador. El productor ve lo suyo y descarga sus plantillas desde /mi.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response

from app.contexto import Contexto, requiere_rol
from app.schemas.legalidad import (
    CierreIncidencia,
    DeclaracionNueva,
    IncidenciaNueva,
    LegalidadSalida,
    NotaRequisito,
)
from app.services import legalidad
from app.services.parcelas import parcela_visible

router = APIRouter(tags=["legalidad"])
Lectura = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador", "lector", "superadmin"))]
Registro = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa", "operador"))]
Administrador = Annotated[Contexto, Depends(requiere_rol("admin_cooperativa"))]
Plantilla = Literal["declaracion-jurada-tenencia", "constancia-comunal"]


def pdf(contenido: bytes, nombre: str) -> Response:
    return Response(
        contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"},
    )


@router.get("/parcelas/{parcela_id}/legalidad", response_model=LegalidadSalida)
def legalidad_de_parcela(parcela_id: uuid.UUID, contexto: Lectura):
    return legalidad.salida(contexto.sesion, parcela_visible(contexto, parcela_id))


@router.post("/parcelas/{parcela_id}/perfil", response_model=LegalidadSalida)
def declarar_variable(parcela_id: uuid.UUID, datos: DeclaracionNueva, contexto: Registro):
    parcela = parcela_visible(contexto, parcela_id)
    legalidad.declarar(
        contexto,
        parcela,
        datos.variable,
        datos.valor,
        detalle=datos.detalle.model_dump(exclude_none=True) if datos.detalle else None,
        nota=datos.nota,
    )
    return legalidad.salida(contexto.sesion, parcela)


@router.post("/parcelas/{parcela_id}/requisitos/{requisito}/nota", response_model=LegalidadSalida)
def nota_de_requisito(
    parcela_id: uuid.UUID,
    requisito: Literal["faja_marginal", "patrimonio_cultural"],
    datos: NotaRequisito,
    contexto: Registro,
):
    parcela = parcela_visible(contexto, parcela_id)
    legalidad.registrar_nota(contexto, parcela, requisito, datos.nota)
    return legalidad.salida(contexto.sesion, parcela)


@router.post("/parcelas/{parcela_id}/cruce", response_model=LegalidadSalida, status_code=202)
def volver_a_cruzar(parcela_id: uuid.UUID, contexto: Registro):
    parcela = parcela_visible(contexto, parcela_id)
    legalidad.volver_a_cruzar(contexto, parcela)
    return legalidad.salida(contexto.sesion, parcela)


@router.post("/parcelas/{parcela_id}/incidencias", response_model=LegalidadSalida, status_code=201)
def registrar_incidencia(parcela_id: uuid.UUID, datos: IncidenciaNueva, contexto: Registro):
    parcela = parcela_visible(contexto, parcela_id)
    legalidad.registrar_incidencia(contexto, parcela, datos.tipo, datos.descripcion, datos.fuente)
    return legalidad.salida(contexto.sesion, parcela)


@router.post("/incidencias/{incidencia_id}/cerrar", response_model=LegalidadSalida)
def cerrar_incidencia(incidencia_id: uuid.UUID, datos: CierreIncidencia, contexto: Administrador):
    incidencia = legalidad.cerrar_incidencia(contexto, incidencia_id, datos.nota)
    return legalidad.salida(contexto.sesion, parcela_visible(contexto, incidencia.parcela_id))


@router.get("/parcelas/{parcela_id}/plantillas/{nombre}")
def plantilla_para_firmar(parcela_id: uuid.UUID, nombre: Plantilla, contexto: Lectura) -> Response:
    return pdf(*legalidad.plantilla(contexto.sesion, parcela_visible(contexto, parcela_id), nombre))
