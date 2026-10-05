"""Correlativos por cooperativa, tipo y año (Parte 5). El UPSERT toma la fila con bloqueo: dos operadores
simultáneos nunca reciben el mismo número, y cada uno espera a que el otro confirme o revierta."""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


def siguiente(sesion: Session, cooperativa_id: uuid.UUID, tipo: str, anio: int) -> int:
    return sesion.execute(
        text(
            "INSERT INTO correlativos (cooperativa_id, tipo, anio, ultimo) VALUES (:c, :t, :a, 1) "
            "ON CONFLICT (cooperativa_id, tipo, anio) DO UPDATE SET ultimo = correlativos.ultimo + 1 "
            "RETURNING ultimo"
        ),
        {"c": cooperativa_id, "t": tipo, "a": anio},
    ).scalar_one()
