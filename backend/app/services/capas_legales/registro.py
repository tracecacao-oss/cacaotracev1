"""Capas en uso. crear_app las fija al arrancar; las pruebas fijan las suyas, con HTTP simulado."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from app.services.capas_legales import TIEMPO_MAXIMO, CapaLegal
from app.services.capas_legales.ana_faja_marginal import FajasMarginales
from app.services.capas_legales.idep_comunidades import Comunidades
from app.services.capas_legales.ign_hidrografia import Hidrografia
from app.services.capas_legales.serfor_modalidad_acceso import ModalidadesDeAcceso
from app.services.capas_legales.serfor_zonificacion import ZonificacionForestal
from app.services.capas_legales.sernanp_amortiguamiento import ZonasDeAmortiguamiento
from app.services.capas_legales.sernanp_anp import AreasProtegidas
from app.services.capas_legales.sernanp_conservacion import AreasDeConservacion
from app.services.capas_legales.sigda_monumentos import Monumentos

MODULOS: dict[str, type] = {
    "sernanp_anp": AreasProtegidas,
    "sernanp_amortiguamiento": ZonasDeAmortiguamiento,
    "serfor_zonificacion": ZonificacionForestal,
    "idep_comunidades": Comunidades,
    "ign_hidrografia": Hidrografia,
    "sigda_monumentos": Monumentos,
    # De apoyo: no deciden ninguna variable.
    "sernanp_conservacion": AreasDeConservacion,
    "serfor_modalidad_acceso": ModalidadesDeAcceso,
    "ana_faja_marginal": FajasMarginales,
}
APOYO = ("sernanp_conservacion", "serfor_modalidad_acceso", "ana_faja_marginal")


@dataclass
class Capas:
    cliente: httpx.Client
    activas: dict[str, CapaLegal]  # las de CAPAS_LEGALES_ACTIVAS
    apoyo: dict[str, CapaLegal] = field(default_factory=dict)
    distancia_agua_m: int = 100
    dormir: Callable[[float], None] = time.sleep


_capas: list[Capas] = []


def construir(settings, cliente: httpx.Client | None = None, dormir=time.sleep) -> Capas:
    activas = [c for c in settings.lista_capas_legales if c in MODULOS and c not in APOYO]
    return Capas(
        cliente=cliente or httpx.Client(timeout=TIEMPO_MAXIMO, follow_redirects=True),
        activas={c: MODULOS[c]() for c in activas},
        apoyo={c: MODULOS[c]() for c in APOYO},
        distancia_agua_m=settings.distancia_cuerpo_agua_m,
        dormir=dormir,
    )


def fijar(capas: Capas) -> None:
    _capas[:] = [capas]


def actuales() -> Capas | None:
    return _capas[0] if _capas else None
