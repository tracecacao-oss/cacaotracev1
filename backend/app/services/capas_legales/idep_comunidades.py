"""Comunidades nativas (capa 0) y campesinas (capa 1), en el geoportal de la IDEP (IGN).

Campos confirmados en el metadato el 2026-10-09: nom_comuni en las dos; etnia en la 0. El tipo de comunidad
sale de la capa. Hay comunidades que no están georreferenciadas: que la parcela no figure aquí no descarta
tierra comunal.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar


class Comunidades:
    capa = POR_CODIGO["idep_comunidades"]

    def cruzar(self, consulta: Consulta) -> dict:
        filas = [
            fila(e, nombre=e.atributos.get("nom_comuni"), tipo="nativa", etnia=e.atributos.get("etnia"))
            for e in consulta.intersectan(self.capa, 0, "nom_comuni,etnia")
        ]
        filas += [
            fila(e, nombre=e.atributos.get("nom_comuni"), tipo="campesina")
            for e in consulta.intersectan(self.capa, 1, "nom_comuni")
        ]
        return separar(filas)
