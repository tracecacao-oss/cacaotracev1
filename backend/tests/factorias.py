"""Datos de prueba. Son ficticios y lo parecen: nunca nombres, DNI ni RUC que pasen por reales."""

import itertools
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models import Afiliacion, Cooperativa, Perfil, Productor

_contador = itertools.count(1)


def cooperativa(sesion: Session, nombre: str = "Coop Prueba", **datos) -> Cooperativa:
    n = next(_contador)
    coop = Cooperativa(
        razon_social=f"{nombre} {n}",
        ruc=datos.pop("ruc", f"{20000000000 + n}"),
        departamento="Departamento X",
        provincia="Provincia X",
        distrito="Distrito X",
        **datos,
    )
    sesion.add(coop)
    sesion.flush()
    return coop


def perfil(sesion: Session, rol: str, coop: Cooperativa | None = None, **datos) -> Perfil:
    n = next(_contador)
    p = Perfil(
        id=datos.pop("id", uuid.uuid4()),
        rol=rol,
        cooperativa_id=coop.id if coop else None,
        nombres=datos.pop("nombres", f"Usuario {n}"),
        apellidos=datos.pop("apellidos", "Prueba"),
        correo=datos.pop("correo", None if rol == "productor" else f"usuario{n}@prueba.test"),
        debe_cambiar_clave=datos.pop("debe_cambiar_clave", False),
        **datos,
    )
    sesion.add(p)
    sesion.flush()
    return p


def productor(sesion: Session, coop: Cooperativa, dni: str | None = None, **datos) -> Productor:
    n = next(_contador)
    prod = Productor(
        dni=dni or f"{90000000 + n}",
        nombres=datos.pop("nombres", f"Demo {n}"),
        apellidos=datos.pop("apellidos", "Productor"),
        es_demo=coop.es_demo,
        **datos,
    )
    sesion.add(prod)
    sesion.flush()
    sesion.add(
        Afiliacion(productor_id=prod.id, cooperativa_id=coop.id, estado="activa", desde=date(2026, 1, 1))
    )
    sesion.flush()
    return prod


def productor_con_acceso(sesion: Session, coop: Cooperativa, **datos) -> tuple[Productor, Perfil]:
    prod = productor(sesion, coop)
    cuenta = perfil(sesion, "productor", coop, productor_id=prod.id, nombres=prod.nombres, **datos)
    return prod, cuenta


# ---------- Geometrías ficticias en San Martín ----------

LAT, LON = -6.95, -76.55


def _metros_por_grado(lat: float) -> tuple[float, float]:
    import math

    f = math.radians(lat)
    m_lat = 111132.954 - 559.822 * math.cos(2 * f) + 1.175 * math.cos(4 * f)
    m_lon = (math.pi / 180) * 6378137.0 * math.cos(f) / math.sqrt(1 - 0.00669437999014 * math.sin(f) ** 2)
    return m_lat, m_lon


def rectangulo(
    ancho_m: float, alto_m: float, este_m: float = 0, norte_m: float = 0, lat=LAT, lon=LON
) -> dict:
    """Polígono GeoJSON de ancho × alto metros, desplazado este/norte desde el origen."""
    m_lat, m_lon = _metros_por_grado(lat)
    x0, y0 = lon + este_m / m_lon, lat + norte_m / m_lat
    x1, y1 = x0 + ancho_m / m_lon, y0 + alto_m / m_lat
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def punto(este_m: float = 0, norte_m: float = 0) -> dict:
    m_lat, m_lon = _metros_por_grado(LAT)
    return {"type": "Point", "coordinates": [LON + este_m / m_lon, LAT + norte_m / m_lat]}


def datos_parcela(**cambios) -> dict:
    return {
        "nombre": "Parcela Demo",
        "departamento": "San Martín",
        "provincia": "Provincia X",
        "distrito": "Distrito X",
        "area_cultivada_ha": "0.5",
    } | cambios


def crear_parcela(api, productor_id, geometria=None, *, archivo=None, indice=None, ruta=None, **datos):
    """POST multipart de una parcela: geometría dibujada o archivo (nombre, bytes) con índice."""
    import json

    formulario = {"datos": json.dumps(datos_parcela(**datos))}
    if geometria is not None:
        formulario["geometria"] = json.dumps(geometria)
    if indice is not None:
        formulario["indice"] = str(indice)
    archivos = {"archivo": archivo} if archivo else None
    return api.post(ruta or f"/productores/{productor_id}/parcelas", data=formulario, files=archivos)
