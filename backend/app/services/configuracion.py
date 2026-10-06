"""Configuración de la cooperativa (Parte 5). Una fila por cooperativa; solo el administrador la cambia y
cada cambio se audita con el valor anterior y el nuevo. Un cambio no altera las tandas ya validadas: cada
decisión guarda los valores con que se evaluó."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api
from app.models import ConfiguracionCooperativa, Cooperativa
from app.schemas.recepcion import ConfiguracionCambio, ConfiguracionSalida
from app.services.auditoria import aplicar_cambios, registrar_auditoria

CAMPOS = (
    "tope_kg_seco_ha_anio",
    "factor_baba_a_seco",
    "rendimiento_min",
    "rendimiento_max",
    "dias_max_cosecha_entrega_baba",
    "dias_max_cosecha_entrega_seco",
    "tolerancia_peso_guia_pct",
    # Adenda 3 de la Parte 5.
    "dias_max_emision_doc_entrega",
)


def de_cooperativa(sesion: Session, cooperativa_id: uuid.UUID) -> ConfiguracionCooperativa:
    """La fila de la cooperativa; si no existe, la crea con los valores iniciales (sin tope)."""
    fila = sesion.get(ConfiguracionCooperativa, cooperativa_id)
    if fila is None:
        fila = ConfiguracionCooperativa(cooperativa_id=cooperativa_id)
        sesion.add(fila)
        sesion.flush()
        sesion.refresh(fila)
    return fila


def valores(fila: ConfiguracionCooperativa) -> dict[str, Decimal | int | None]:
    """Los valores con que se evalúa una tanda; se copian en cada decisión."""
    return {campo: getattr(fila, campo) for campo in CAMPOS}


def lista(sesion: Session, cooperativa_id: uuid.UUID) -> bool:
    cooperativa = sesion.get(Cooperativa, cooperativa_id)
    return de_cooperativa(sesion, cooperativa_id).tope_kg_seco_ha_anio is not None and bool(
        cooperativa.codigo
    )


def exigir_lista(sesion: Session, cooperativa_id: uuid.UUID) -> None:
    cooperativa = sesion.get(Cooperativa, cooperativa_id)
    if de_cooperativa(sesion, cooperativa_id).tope_kg_seco_ha_anio is None:
        raise error_api(
            400,
            "configuracion_incompleta",
            "Antes de recibir tandas, el administrador fija el tope de kilos por hectárea en Configuración.",
        )
    if not cooperativa.codigo:
        raise error_api(
            400,
            "configuracion_incompleta",
            "La cooperativa todavía no tiene su código de 3 a 6 letras; lo fija el equipo CacaoTrace.",
        )


def _salida(sesion: Session, cooperativa_id: uuid.UUID) -> ConfiguracionSalida:
    fila = de_cooperativa(sesion, cooperativa_id)
    cooperativa = sesion.get(Cooperativa, cooperativa_id)
    return ConfiguracionSalida(
        **valores(fila),
        codigo_cooperativa=cooperativa.codigo,
        ruc_cooperativa=cooperativa.ruc,
        tipo_organizacion=cooperativa.tipo_organizacion,
        lista=fila.tope_kg_seco_ha_anio is not None and bool(cooperativa.codigo),
    )


def obtener(contexto: Contexto) -> ConfiguracionSalida:
    return _salida(contexto.sesion, cooperativa_del_contexto(contexto))


def cambiar(contexto: Contexto, datos: ConfiguracionCambio) -> ConfiguracionSalida:
    if datos.rendimiento_min >= datos.rendimiento_max:
        raise error_api(422, "banda_invalida", "El rendimiento mínimo debe ser menor que el máximo.")
    cooperativa_id = cooperativa_del_contexto(contexto)
    fila = de_cooperativa(contexto.sesion, cooperativa_id)
    cambios = aplicar_cambios(fila, datos.model_dump())
    if cambios:
        registrar_auditoria(contexto, "configuracion.cambiar", "cooperativa", cooperativa_id, cambios)
    contexto.sesion.commit()
    return _salida(contexto.sesion, cooperativa_id)
