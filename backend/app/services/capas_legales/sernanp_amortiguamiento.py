"""Zonas de amortiguamiento de las áreas naturales protegidas, de SERNANP (capa 8).

Campos confirmados en el metadato el 2026-10-09: anp_nomb (el área a la que pertenece) y c_nomb. Si la parcela
no está dentro de un área y se superpone con una zona: `en_anp = zona_de_amortiguamiento`.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar


class ZonasDeAmortiguamiento:
    capa = POR_CODIGO["sernanp_amortiguamiento"]

    def cruzar(self, consulta: Consulta) -> dict:
        return separar(
            [
                fila(e, nombre=e.atributos.get("anp_nomb"), categoria=e.atributos.get("c_nomb"))
                for e in consulta.intersectan(self.capa, 8, "anp_nomb,c_nomb,anp_codi")
            ]
        )
