"""Monumentos arqueológicos prehispánicos delimitados, del SIGDA del Ministerio de Cultura (capa 0).

Campos confirmados en el metadato el 2026-10-09: nomb_map, clas_map y resol. La capa trae los monumentos
delimitados, no todos los sitios arqueológicos.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar


class Monumentos:
    capa = POR_CODIGO["sigda_monumentos"]

    def cruzar(self, consulta: Consulta) -> dict:
        return separar(
            [
                fila(
                    e,
                    nombre=e.atributos.get("nomb_map"),
                    clase=e.atributos.get("clas_map"),
                    resolucion=e.atributos.get("resol"),
                )
                for e in consulta.intersectan(self.capa, 0, "nomb_map,clas_map,resol")
            ]
        )
