"""Cruce de apoyo: cesiones en uso (capa 1) y autorizaciones de cambio de uso (capa 3), de SERFOR.

No decide ninguna variable. Si la parcela se superpone con un contrato registrado, su número se muestra
junto al requisito `tierra_forestal` para compararlo con el documento cargado; no lo reemplaza. Campos
confirmados en el metadato el 2026-10-09: CONTRA, FECINI, FECTER y SITUAC en la 1; NUMAUT en la 3. De las
cesiones en uso no se piden ni se guardan los nombres de los titulares.
"""

from datetime import UTC, datetime

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar


def _fecha(valor) -> str | None:
    """ArcGIS entrega las fechas en milisegundos desde 1970."""
    if isinstance(valor, int | float):
        return datetime.fromtimestamp(valor / 1000, UTC).date().isoformat()
    return valor or None


class ModalidadesDeAcceso:
    capa = POR_CODIGO["serfor_modalidad_acceso"]

    def cruzar(self, consulta: Consulta) -> dict:
        cesiones = separar(
            [
                fila(
                    e,
                    contrato=e.atributos.get("CONTRA"),
                    inicio=_fecha(e.atributos.get("FECINI")),
                    termino=_fecha(e.atributos.get("FECTER")),
                    situacion=e.atributos.get("SITUAC"),
                )
                for e in consulta.intersectan(self.capa, 1, "CONTRA,FECINI,FECTER,SITUAC")
            ]
        )
        cambios = separar(
            [
                fila(e, autorizacion=e.atributos.get("NUMAUT"))
                for e in consulta.intersectan(self.capa, 3, "NUMAUT")
            ]
        )
        return {"cesiones": cesiones["elementos"], "cambios_de_uso": cambios["elementos"]}
