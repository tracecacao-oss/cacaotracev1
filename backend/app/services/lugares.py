"""Lugares de la cooperativa (Parte 5): la tanda se pesa en una cancha de acopio y la Parte 6 los usa en
cada etapa del proceso. Ubicación del catálogo del INEI."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import ubigeo
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.models import Lugar
from app.schemas.recepcion import LugarCambios, LugarNuevo, LugarSalida
from app.services.auditoria import aplicar_cambios, registrar_auditoria


def listar(contexto: Contexto, *, tipo: str | None = None, activos: bool | None = None) -> list[LugarSalida]:
    consulta = select(Lugar).where(Lugar.cooperativa_id == cooperativa_del_contexto(contexto))
    if tipo:
        consulta = consulta.where(Lugar.tipo == tipo)
    if activos is not None:
        consulta = consulta.where(Lugar.activo.is_(activos))
    lugares = contexto.sesion.scalars(consulta.order_by(Lugar.activo.desc(), func.lower(Lugar.nombre)))
    return [LugarSalida.model_validate(lugar) for lugar in lugares]


def lugar_visible(contexto: Contexto, lugar_id: uuid.UUID) -> Lugar:
    lugar = contexto.sesion.get(Lugar, lugar_id)
    if lugar is None or lugar.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("El lugar no existe.")
    return lugar


def _nombre_libre(contexto: Contexto, nombre: str, excepto: uuid.UUID | None = None) -> None:
    consulta = select(Lugar.id).where(
        Lugar.cooperativa_id == cooperativa_del_contexto(contexto), func.lower(Lugar.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(Lugar.id != excepto)
    if contexto.sesion.scalar(consulta):
        raise error_api(409, "lugar_duplicado", "La cooperativa ya tiene un lugar con ese nombre.")


def crear(contexto: Contexto, datos: LugarNuevo) -> LugarSalida:
    valores = datos.model_dump()
    _nombre_libre(contexto, valores["nombre"])
    ubigeo.normalizar(valores)
    lugar = Lugar(cooperativa_id=cooperativa_del_contexto(contexto), **valores)
    contexto.sesion.add(lugar)
    try:
        contexto.sesion.flush()
    except IntegrityError as exc:
        contexto.sesion.rollback()
        raise error_api(409, "lugar_duplicado", "La cooperativa ya tiene un lugar con ese nombre.") from exc
    registrar_auditoria(contexto, "lugar.crear", "lugar", lugar.id, valores)
    contexto.sesion.commit()
    return LugarSalida.model_validate(lugar)


def editar(contexto: Contexto, lugar_id: uuid.UUID, datos: LugarCambios) -> LugarSalida:
    lugar = lugar_visible(contexto, lugar_id)
    valores = datos.model_dump(exclude_unset=True)
    # Los obligatorios no se vacían con null; las coordenadas sí.
    valores = {k: v for k, v in valores.items() if v is not None or k in ("latitud", "longitud")}
    if "nombre" in valores:
        _nombre_libre(contexto, valores["nombre"], excepto=lugar.id)
    ubigeo.normalizar(valores, lugar)
    cambios = aplicar_cambios(lugar, valores)
    if cambios:
        registrar_auditoria(contexto, "lugar.editar", "lugar", lugar.id, cambios)
    contexto.sesion.commit()
    return LugarSalida.model_validate(lugar)
