"""Áreas naturales protegidas de administración nacional (capa 1) y zonas reservadas (capa 2), de SERNANP.

Campos confirmados en el metadato el 2026-10-09: anp_nomb, anp_cate y anp_codi en la capa 1; zr_nomb y zr_codi
en la capa 2. Una superposición da `en_anp = dentro`, con el nombre y la categoría del área.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar


class AreasProtegidas:
    capa = POR_CODIGO["sernanp_anp"]

    def cruzar(self, consulta: Consulta) -> dict:
        filas = [
            fila(e, nombre=e.atributos.get("anp_nomb"), categoria=e.atributos.get("anp_cate"))
            for e in consulta.intersectan(self.capa, 1, "anp_nomb,anp_cate,anp_codi")
        ]
        filas += [
            fila(e, nombre=e.atributos.get("zr_nomb"), categoria="Zona Reservada")
            for e in consulta.intersectan(self.capa, 2, "zr_nomb,zr_codi")
        ]
        return separar(filas)
