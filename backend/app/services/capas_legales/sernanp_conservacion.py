"""Cruce de apoyo: áreas de conservación regional (capa 3) y privada (capa 4), de SERNANP.

No decide ninguna variable: se guarda en el detalle de `en_anp` y genera el hallazgo
`en_area_de_conservacion`. Campos confirmados en el metadato el 2026-10-09: acr_nomb en la 3 y acp_nomb en
la 4.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar


class AreasDeConservacion:
    capa = POR_CODIGO["sernanp_conservacion"]

    def cruzar(self, consulta: Consulta) -> dict:
        filas = [
            fila(e, nombre=e.atributos.get("acr_nomb"), categoria="Área de conservación regional")
            for e in consulta.intersectan(self.capa, 3, "acr_nomb")
        ]
        filas += [
            fila(e, nombre=e.atributos.get("acp_nomb"), categoria="Área de conservación privada")
            for e in consulta.intersectan(self.capa, 4, "acp_nomb")
        ]
        return separar(filas)
