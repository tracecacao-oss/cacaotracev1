"""Ayudas para las pruebas de la Parte 7: tandas finales en stock con su corrida consolidada, las proporciones
de sus tandas de origen y su DPP vigente, sin recorrer las 23 etapas (eso ya lo prueba la Parte 6)."""

import itertools
from datetime import datetime
from decimal import Decimal

from app.fechas import ahora
from app.models import Calidad, Corrida, CorridaTanda, Dpp, Lugar, Perfil, Tanda, TandaFinal
from app.services import sello
from app.services.corridas import proporciones

_contador = itertools.count(1)


def tanda_final(
    sesion,
    operador: Perfil,
    calidad: Calidad,
    almacen: Lugar,
    tandas: list[Tanda],
    *,
    peso: str,
    ingreso: datetime | None = None,
    manejo: str = "mezclado",
) -> TandaFinal:
    """Una corrida consolidada con esas tandas (proporción por su peso de entrada) y su tanda final."""
    n = next(_contador)
    ingreso = ingreso or ahora()
    corrida = Corrida(
        cooperativa_id=operador.cooperativa_id,
        codigo=f"CP-2026-8{n:05d}",
        ruta="completa",
        tipo_manejo=manejo,
        estado="consolidada",
        abierta_por=operador.id,
        abierta_en=ingreso,
        iniciada_en=ingreso,
        consolidada_en=ingreso,
    )
    sesion.add(corrida)
    sesion.flush()
    for t, p in zip(tandas, proporciones([Decimal(t.peso_kg) for t in tandas]), strict=True):
        sesion.add(CorridaTanda(corrida_id=corrida.id, tanda_id=t.id, peso_kg=t.peso_kg, proporcion=p))
    final = TandaFinal(
        cooperativa_id=operador.cooperativa_id,
        codigo=f"TF-2026-8{n:05d}",
        corrida_id=corrida.id,
        peso_seco_kg=Decimal(peso),
        saldo_kg=Decimal(peso),
        humedad_pct=Decimal("7.0"),
        calidad=calidad.nombre,
        calidad_id=calidad.id,
        numero_sacos=6,
        lugar_id=almacen.id,
        ingreso_stock_en=ingreso,
        estado="en_stock",
    )
    sesion.add(final)
    sesion.flush()
    contenido = {"tanda_final": final.codigo}
    sesion.add(
        Dpp(
            cooperativa_id=operador.cooperativa_id,
            codigo=f"DPP-PRU-2026-8{n:05d}",
            corrida_id=corrida.id,
            tanda_final_id=final.id,
            emitido_en=ingreso,
            emitido_por=operador.id,
            contenido=contenido,
            contenido_sha256=sello.huella(contenido),
            estado="vigente",
        )
    )
    sesion.flush()
    return final
