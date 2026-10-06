"""Ayudas para las pruebas de la Parte 6: tandas validadas con su DOP, lugares, calidades y el registro de
todas las etapas de una corrida."""

import itertools
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.catalogos import etapas_proceso as catalogo
from app.fechas import ahora
from app.models import Calidad, Dop, Lugar, Parcela, Perfil, Productor, Tanda
from app.services import sello

_contador = itertools.count(1)


def lugar(sesion, cooperativa_id: uuid.UUID, nombre: str, tipo: str = "cancha_acopio") -> Lugar:
    fila = Lugar(
        cooperativa_id=cooperativa_id,
        nombre=nombre,
        tipo=tipo,
        departamento="SAN MARTIN",
        provincia="PICOTA",
        distrito="PICOTA",
    )
    sesion.add(fila)
    sesion.flush()
    return fila


def calidad(sesion, cooperativa_id: uuid.UUID, nombre: str = "Grado 1") -> Calidad:
    fila = Calidad(cooperativa_id=cooperativa_id, nombre=nombre, activo=True)
    sesion.add(fila)
    sesion.flush()
    return fila


def tanda_validada(
    sesion,
    operador: Perfil,
    productor: Productor,
    parcela: Parcela,
    cancha: Lugar,
    *,
    peso: str = "1000.00",
    producto: str = "baba",
    recibida: datetime | None = None,
) -> Tanda:
    """Una tanda validada con su DOP vigente, sin pasar por la validación (el PDF no hace falta aquí)."""
    n = next(_contador)
    recibida = recibida or ahora() - timedelta(days=5)
    tanda = Tanda(
        cooperativa_id=operador.cooperativa_id,
        codigo=f"TD-2026-9{n:05d}",
        productor_id=productor.id,
        parcela_id=parcela.id,
        lugar_id=cancha.id,
        recibida_en=recibida,
        estado_producto=producto,
        peso_kg=Decimal(peso),
        variedad="ccn_51",
        cosecha_desde=date(2026, 9, 1),
        cosecha_hasta=date(2026, 9, 10),
        estado="validada",
        registrada_por=operador.id,
    )
    sesion.add(tanda)
    sesion.flush()
    contenido = {"tanda": {"codigo": tanda.codigo}}
    sesion.add(
        Dop(
            cooperativa_id=tanda.cooperativa_id,
            codigo=f"DOP-PRU-2026-9{n:05d}",
            tanda_id=tanda.id,
            productor_id=productor.id,
            parcela_id=parcela.id,
            emitido_en=recibida,
            emitido_por=operador.id,
            contenido=contenido,
            contenido_sha256=sello.huella(contenido),
            estado="vigente",
        )
    )
    sesion.flush()
    return tanda


def datos_de_etapa(numero: int, lugar_id, momento: datetime, *, calidad_id=None, peso_final="400.00") -> dict:
    """Una etapa completa, una hora después de la anterior."""
    etapa = catalogo.POR_NUMERO[numero]
    datos = {
        "lugar_id": str(lugar_id),
        "inicio": momento.isoformat(),
        "fin": (momento + timedelta(minutes=50)).isoformat(),
        "metodo": "Método de prueba",
        "responsable": "Operador de prueba",
    }
    if etapa.transporte:
        datos["distancia_m"] = "120.0"
    propios = {
        13: {"humedad_pct": "7.0"},
        17: {"calidad_id": str(calidad_id)} if calidad_id else {},
        19: {"peso_final_kg": peso_final},
        21: {"numero_sacos": 6},
    }
    if numero in propios:
        datos["datos"] = propios[numero]
    return datos


def registrar_todas(api, corrida: dict, lugar_id, *, calidad_id, peso_final="400.00", salvo=()) -> dict:
    """Registra en orden todas las etapas pendientes y editables, desde hace tres días."""
    inicio = ahora() - timedelta(days=3)
    for etapa in corrida["etapas"]:
        if not etapa["editable"] or etapa["numero"] in salvo:
            continue
        momento = inicio + timedelta(hours=etapa["numero"])
        respuesta = api.patch(
            f"/corridas/{corrida['id']}/etapas/{etapa['numero']}",
            json=datos_de_etapa(
                etapa["numero"], lugar_id, momento, calidad_id=calidad_id, peso_final=peso_final
            ),
        )
        assert respuesta.status_code == 200, respuesta.text
        corrida = respuesta.json()
    return corrida
