"""Catálogo de etapas, plantilla de proceso y calidades de la cooperativa (Parte 6).

La plantilla guarda los valores habituales de cada etapa (lugar, método, distancia y duración). Es solo un
punto de partida: una etapa cuenta como registrada cuando una persona la confirma con su inicio y su fin
reales. Las calidades no son texto libre: cada cooperativa mantiene su catálogo.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogos import etapas_proceso as catalogo
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.models import Calidad, Lugar, PlantillaEtapa
from app.schemas.proceso import (
    CalidadCambios,
    CalidadNueva,
    CalidadSalida,
    DatoCatalogo,
    EtapaCatalogo,
    PlantillaCambio,
    PlantillaFila,
)
from app.services.auditoria import aplicar_cambios, registrar_auditoria


def etapas() -> list[EtapaCatalogo]:
    return [
        EtapaCatalogo(
            numero=e.numero,
            nombre=e.nombre,
            tipo=e.tipo,
            tipo_nombre=catalogo.NOMBRE_TIPO[e.tipo],
            fase=e.fase,
            fase_nombre=catalogo.NOMBRE_FASE[e.fase],
            en_ruta_seco=e.en_ruta_seco,
            automatica=e.automatica,
            opcional=e.opcional,
            transporte=e.transporte,
            datos=[
                DatoCatalogo(
                    clave=d.clave,
                    etiqueta=d.etiqueta,
                    tipo=d.tipo,
                    minimo=d.minimo,
                    maximo=d.maximo,
                    unidad=d.unidad,
                )
                for d in e.datos
            ],
        )
        for e in catalogo.ETAPAS
    ]


# ---------- Plantilla ----------


def plantilla_de(sesion: Session, cooperativa_id: uuid.UUID) -> dict[int, PlantillaEtapa]:
    return {
        f.numero: f
        for f in sesion.scalars(select(PlantillaEtapa).where(PlantillaEtapa.cooperativa_id == cooperativa_id))
    }


def lugar_de_la_cooperativa(sesion: Session, cooperativa_id: uuid.UUID, lugar_id: uuid.UUID) -> Lugar:
    lugar = sesion.get(Lugar, lugar_id)
    if lugar is None or lugar.cooperativa_id != cooperativa_id:
        raise error_api(422, "lugar_invalido", "El lugar no existe en la cooperativa.")
    return lugar


def plantilla(contexto: Contexto) -> list[PlantillaFila]:
    filas = plantilla_de(contexto.sesion, cooperativa_del_contexto(contexto))
    return [
        PlantillaFila(
            numero=n,
            lugar_id=filas[n].lugar_id if n in filas else None,
            metodo=filas[n].metodo if n in filas else None,
            distancia_m=filas[n].distancia_m if n in filas else None,
            duracion_horas=filas[n].duracion_horas if n in filas else None,
        )
        for n in catalogo.NUMEROS
    ]


def cambiar_plantilla(contexto: Contexto, datos: PlantillaCambio) -> list[PlantillaFila]:
    cooperativa_id = cooperativa_del_contexto(contexto)
    actuales = plantilla_de(contexto.sesion, cooperativa_id)
    numeros = [f.numero for f in datos.filas]
    if len(numeros) != len(set(numeros)):
        raise error_api(422, "etapa_repetida", "Cada etapa va una sola vez en la plantilla.")
    cambios = {}
    for fila in datos.filas:
        etapa = catalogo.POR_NUMERO[fila.numero]
        if fila.lugar_id:
            lugar = lugar_de_la_cooperativa(contexto.sesion, cooperativa_id, fila.lugar_id)
            if not lugar.activo:
                raise error_api(422, "lugar_inactivo", f"El lugar de la etapa {fila.numero} está inactivo.")
        valores = fila.model_dump(exclude={"numero"})
        if not etapa.transporte:
            valores["distancia_m"] = None
        actual = actuales.get(fila.numero)
        if actual is None:
            actual = PlantillaEtapa(cooperativa_id=cooperativa_id, numero=fila.numero)
            contexto.sesion.add(actual)
        cambio = aplicar_cambios(actual, valores)
        if cambio:
            cambios[str(fila.numero)] = cambio
    if cambios:
        registrar_auditoria(contexto, "plantilla.cambiar", "cooperativa", cooperativa_id, {"etapas": cambios})
    contexto.sesion.commit()
    return plantilla(contexto)


# ---------- Calidades ----------


def calidades(contexto: Contexto) -> list[CalidadSalida]:
    filas = contexto.sesion.scalars(
        select(Calidad)
        .where(Calidad.cooperativa_id == cooperativa_del_contexto(contexto))
        .order_by(Calidad.nombre)
    )
    return [CalidadSalida(id=c.id, nombre=c.nombre, activo=c.activo) for c in filas]


def _nombre_libre(contexto: Contexto, cooperativa_id: uuid.UUID, nombre: str, excepto=None) -> None:
    consulta = select(Calidad.id).where(
        Calidad.cooperativa_id == cooperativa_id, Calidad.nombre.ilike(nombre)
    )
    if excepto:
        consulta = consulta.where(Calidad.id != excepto)
    if contexto.sesion.scalar(consulta) is not None:
        raise error_api(409, "calidad_repetida", "Ya existe una calidad con ese nombre.")


def crear_calidad(contexto: Contexto, datos: CalidadNueva) -> CalidadSalida:
    cooperativa_id = cooperativa_del_contexto(contexto)
    _nombre_libre(contexto, cooperativa_id, datos.nombre)
    calidad = Calidad(cooperativa_id=cooperativa_id, nombre=datos.nombre, activo=True)
    contexto.sesion.add(calidad)
    contexto.sesion.flush()
    registrar_auditoria(contexto, "calidad.crear", "calidad", calidad.id, {"nombre": datos.nombre})
    contexto.sesion.commit()
    return CalidadSalida(id=calidad.id, nombre=calidad.nombre, activo=calidad.activo)


def calidad_visible(contexto: Contexto, calidad_id: uuid.UUID) -> Calidad:
    calidad = contexto.sesion.get(Calidad, calidad_id)
    if calidad is None or calidad.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("La calidad no existe.")
    return calidad


def editar_calidad(contexto: Contexto, calidad_id: uuid.UUID, datos: CalidadCambios) -> CalidadSalida:
    calidad = calidad_visible(contexto, calidad_id)
    valores = {k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None}
    if "nombre" in valores:
        _nombre_libre(contexto, calidad.cooperativa_id, valores["nombre"], excepto=calidad.id)
    cambios = aplicar_cambios(calidad, valores)
    if cambios:
        registrar_auditoria(contexto, "calidad.editar", "calidad", calidad.id, cambios)
    contexto.sesion.commit()
    return CalidadSalida(id=calidad.id, nombre=calidad.nombre, activo=calidad.activo)


def hay_calidad_activa(sesion: Session, cooperativa_id: uuid.UUID) -> bool:
    return (
        sesion.scalar(
            select(Calidad.id).where(Calidad.cooperativa_id == cooperativa_id, Calidad.activo).limit(1)
        )
        is not None
    )
