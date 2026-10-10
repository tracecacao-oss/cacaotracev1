"""Cruce de apoyo: fajas marginales delimitadas, de la ANA.

La adenda no pudo probar este servicio; el 2026-10-09 respondió con una sola capa, la 127 ("FajaMarginal").
No decide ninguna variable: lo que encuentra se guarda en el detalle de `junto_a_cuerpo_de_agua`. Se piden
todos los campos porque el metadato no publica cuáles traen el nombre.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar

CAMPOS_NOMBRE = ("NOMBRE", "nombre", "NOM_RIO", "nom_rio", "RIO", "rio", "NOMB_FM")


class FajasMarginales:
    capa = POR_CODIGO["ana_faja_marginal"]

    def cruzar(self, consulta: Consulta) -> dict:
        filas = []
        for e in consulta.intersectan(self.capa, 127, "*"):
            nombre = next((e.atributos[c] for c in CAMPOS_NOMBRE if e.atributos.get(c)), None)
            filas.append(fila(e, nombre=nombre))
        return {"fajas": separar(filas)["elementos"]}
