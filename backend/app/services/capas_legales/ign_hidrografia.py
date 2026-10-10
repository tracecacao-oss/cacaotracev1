"""Hidrografía de la carta nacional 1:100 000, del IGN: ríos como línea (capa 0), lagos y lagunas (capa 1) y
ríos como área (capa 2). Campo NOMBRE en las tres, confirmado en el metadato el 2026-10-09.

Se buscan los cuerpos de agua a DISTANCIA_CUERPO_AGUA_M metros o menos del lindero. A esa escala la capa tiene
decenas de metros de imprecisión: la distancia es aproximada.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta

TIPOS = {0: "río", 1: "lago o laguna", 2: "río"}


class Hidrografia:
    capa = POR_CODIGO["ign_hidrografia"]

    def cruzar(self, consulta: Consulta) -> dict:
        cuerpos = []
        for numero in (0, 1, 2):
            for e in consulta.cercanos(self.capa, numero, "NOMBRE", consulta.distancia_agua_m):
                cuerpos.append(
                    {"nombre": e.atributos.get("NOMBRE"), "tipo": TIPOS[numero], "capa": numero} | e.medidas()
                )
        cuerpos.sort(key=lambda c: c["distancia_m"])
        return {"elementos": cuerpos, "distancia_maxima_m": consulta.distancia_agua_m}
