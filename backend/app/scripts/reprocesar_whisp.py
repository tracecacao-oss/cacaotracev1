"""Reprocesa los análisis de Whisp ya completados desde su respuesta guardada (adenda de la Parte 4).

Los análisis anteriores al detalle por capa no tienen `indicadores.capas`. Esta tarea lee la respuesta
completa que quedó en Storage como `respuesta_analisis` y la vuelve a interpretar. No vuelve a consultar
a Whisp. Es idempotente: un análisis que ya tiene `capas` no se toca, así que correrla de nuevo no
cambia nada. La API la corre sola al arrancar; también se puede correr a mano:

    python -m app.scripts.reprocesar_whisp
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import AnalisisCobertura, Documento
from app.services.fuentes.whisp import Whisp
from app.storage import ClienteStorage, ErrorStorage

log = logging.getLogger(__name__)


def reprocesar(sesion: Session, storage: ClienteStorage) -> int:
    """Agrega `capas` a cada análisis de Whisp completado que no las tiene. Devuelve cuántos cambió."""
    whisp = Whisp(None)  # sin clave: solo interpreta, nunca consulta
    pendientes = sesion.scalars(
        select(AnalisisCobertura).where(
            AnalisisCobertura.fuente == "whisp",
            AnalisisCobertura.estado == "completado",
            AnalisisCobertura.respuesta_documento_id.is_not(None),
        )
    ).all()
    cambiados = 0
    for analisis in pendientes:
        if "capas" in (analisis.indicadores or {}):
            continue
        documento = sesion.get(Documento, analisis.respuesta_documento_id)
        try:
            contenido = storage.descargar(documento.ruta)
            _, indicadores, _ = whisp.interpretar(contenido)
        except (ErrorStorage, ValueError, KeyError, IndexError, TypeError) as exc:
            log.warning("No se pudo reprocesar el análisis %s: %s", analisis.id, type(exc).__name__)
            continue
        analisis.indicadores = {**(analisis.indicadores or {}), "capas": indicadores["capas"]}
        flag_modified(analisis, "indicadores")
        cambiados += 1
    sesion.commit()
    return cambiados


def main() -> None:
    from app.config import get_settings
    from app.db import SesionLocal
    from app.storage import crear_storage

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    storage = crear_storage(get_settings())
    if storage is None:
        raise SystemExit("Falta SUPABASE_SECRET_KEY: sin Storage no se pueden leer las respuestas guardadas.")
    with SesionLocal() as sesion:
        cambiados = reprocesar(sesion, storage)
    print(f"Análisis de Whisp reprocesados: {cambiados}")


if __name__ == "__main__":
    main()
