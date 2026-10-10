"""Zonificación forestal, de SERFOR (capa 0).

Lectura del metadato del 2026-10-09 y decisiones del equipo (adenda 4, nota de la sección 10):
- La capa clasifica todo el territorio de un departamento zonificado, también las chacras: cinco categorías
  (`CATZFO`) con sus subcategorías (`SCAZFO`). Su significado sale del metadato (`types`), no se inventa.
- Cuentan como tierra de aptitud forestal o de protección las categorías 601 a 604, salvo la subcategoría
  60402 (producción agroforestal y silvopastoril). La 605 es el área agropecuaria. Superponerse solo con
  esas da `no`, y su categoría se guarda como dato.
- Un departamento "tiene zonificación en la capa" si la capa le clasifica también las chacras: si tiene
  polígonos de la categoría 605. Se pregunta a la propia capa, sin una lista fija. `NOMDEP` usa el código
  del INEI ("22" es San Martín).

Solo se pide la geometría de los polígonos forestales, para medir el área común. Los de la 605 abarcan
departamentos enteros: de ellos basta saber que tocan la parcela.
"""

from app.catalogos.capas_legales import POR_CODIGO
from app.services.capas_legales import Consulta, fila, separar

CATEGORIAS_FORESTALES = (601, 602, 603, 604)
SUBCATEGORIAS_FUERA = (60402,)
CATEGORIA_AGROPECUARIA = 605
CAMPOS = "CATZFO,SCAZFO,DOCLEG,NOMDEP"
FORESTAL = (
    f"CATZFO IN ({', '.join(map(str, CATEGORIAS_FORESTALES))}) AND "
    f"(SCAZFO IS NULL OR SCAZFO NOT IN ({', '.join(map(str, SUBCATEGORIAS_FUERA))}))"
)


def nombres(metadato: dict) -> tuple[dict[int, str], dict[int, str]]:
    """El significado de cada categoría y subcategoría, tal como lo publica la capa."""
    categorias, subcategorias = {}, {}
    for tipo in metadato.get("types") or []:
        categorias[int(tipo["id"])] = " ".join(str(tipo.get("name") or "").split())
        dominio = (tipo.get("domains") or {}).get("SCAZFO") or {}
        for valor in dominio.get("codedValues") or []:
            subcategorias[int(valor["code"])] = " ".join(str(valor.get("name") or "").split())
    return categorias, subcategorias


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


class ZonificacionForestal:
    capa = POR_CODIGO["serfor_zonificacion"]

    def cruzar(self, consulta: Consulta) -> dict:
        categorias, subcategorias = nombres(consulta.metadato(self.capa, 0))
        departamentos = {consulta.departamento} if consulta.departamento else set()

        def datos(atributos: dict) -> dict:
            categoria, subcategoria = _entero(atributos.get("CATZFO")), _entero(atributos.get("SCAZFO"))
            if atributos.get("NOMDEP"):
                departamentos.add(str(atributos["NOMDEP"]))
            return {
                "categoria": categoria,
                "categoria_nombre": categorias.get(categoria),
                "subcategoria": subcategoria,
                "subcategoria_nombre": subcategorias.get(subcategoria),
                "resolucion": atributos.get("DOCLEG"),
                "departamento": atributos.get("NOMDEP"),
            }

        forestales = separar(
            [fila(e, **datos(e.atributos)) for e in consulta.intersectan(self.capa, 0, CAMPOS, FORESTAL)]
        )
        otras = []
        for atributos in consulta.tocan(self.capa, 0, CAMPOS, f"NOT ({FORESTAL})"):
            dato = {k: v for k, v in datos(atributos).items() if v not in (None, "")}
            if dato not in otras:
                otras.append(dato)
        # ¿El departamento tiene zonificación en la capa? Solo hace falta si la parcela no toca la capa.
        zonificados = []
        if not forestales["elementos"] and not otras:
            for codigo in sorted(departamentos):
                if not codigo.isdigit():
                    continue
                donde = f"NOMDEP = '{codigo}' AND CATZFO = {CATEGORIA_AGROPECUARIA}"
                if consulta.contar(self.capa, 0, donde) > 0:
                    zonificados.append(codigo)
        return forestales | {
            "otras": otras,
            "departamentos": sorted(departamentos),
            "zonificados": zonificados,
        }
