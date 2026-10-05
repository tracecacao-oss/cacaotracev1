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
