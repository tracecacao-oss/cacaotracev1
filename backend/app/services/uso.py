"""Parte 10: espacio usado en archivos y en base de datos, en total y por cooperativa, contra el plan.

Los archivos se cuentan con `documentos.tamano_bytes`: todo lo que se sube a Storage tiene su fila, también
los anulados, que siguen ocupando espacio. La base se mide con `pg_database_size`; lo de cada cooperativa
es una aproximación, la suma del tamaño de sus filas en las tablas que llevan su id, sin índices.
"""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contexto import Contexto
from app.models import Base, Cooperativa, Documento
from app.schemas.plataforma import UsoCooperativa, UsoSalida
from app.services import analisis

MB = 1024 * 1024
COLUMNAS_DE_COOPERATIVA = ("cooperativa_id", "cooperativa_registro_id")


def _porcentaje(usado: int, limite_mb: int) -> float:
    return round(usado / (limite_mb * MB) * 100, 1)


def _base_por_cooperativa(sesion: Session) -> dict:
    total: dict = {}
    for tabla in Base.metadata.sorted_tables:
        columna = next((c for c in COLUMNAS_DE_COOPERATIVA if c in tabla.c), None)
        if columna is None:
            continue
        # Los nombres salen del modelo, no de una petición.
        consulta = f'SELECT "{columna}", sum(pg_column_size(t.*)) FROM "{tabla.name}" t'  # noqa: S608
        consulta += " GROUP BY 1"
        filas = sesion.execute(text(consulta))
        for cooperativa_id, bytes_ in filas:
            if cooperativa_id is not None:
                total[cooperativa_id] = total.get(cooperativa_id, 0) + int(bytes_ or 0)
    return total


def uso(contexto: Contexto) -> UsoSalida:
    sesion = contexto.sesion
    settings = get_settings()
    archivos = {
        fila.cooperativa_id: (fila.cantidad, int(fila.bytes_))
        for fila in sesion.execute(
            select(
                Documento.cooperativa_id,
                func.count().label("cantidad"),
                func.coalesce(func.sum(Documento.tamano_bytes), 0).label("bytes_"),
            ).group_by(Documento.cooperativa_id)
        )
    }
    base = _base_por_cooperativa(sesion)
    storage_bytes = sum(b for _, b in archivos.values())
    db_bytes = int(sesion.scalar(text("SELECT pg_database_size(current_database())")))
    por_cooperativa = [
        UsoCooperativa(
            cooperativa_id=c.id,
            cooperativa=c.nombre_comercial or c.razon_social,
            es_demo=c.es_demo,
            archivos=archivos.get(c.id, (0, 0))[0],
            storage_bytes=archivos.get(c.id, (0, 0))[1],
            db_bytes_aprox=base.get(c.id, 0),
        )
        for c in sesion.scalars(select(Cooperativa))
    ]
    por_cooperativa.sort(key=lambda u: (-u.storage_bytes, -u.db_bytes_aprox, u.cooperativa))
    return UsoSalida(
        archivos=sum(n for n, _ in archivos.values()),
        storage_bytes=storage_bytes,
        limite_storage_mb=settings.limite_storage_mb,
        storage_pct=_porcentaje(storage_bytes, settings.limite_storage_mb),
        db_bytes=db_bytes,
        limite_db_mb=settings.limite_db_mb,
        db_pct=_porcentaje(db_bytes, settings.limite_db_mb),
        analisis_en_cola=analisis.en_cola(sesion),
        por_cooperativa=por_cooperativa,
    )
