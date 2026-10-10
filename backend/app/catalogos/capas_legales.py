"""Capas oficiales que se cruzan con la parcela para su perfil legal (adenda 4, sección 10).

Son servicios ArcGIS REST públicos, sin clave. Sus metadatos se leyeron con `?f=pjson` el 2026-10-09 y
coinciden con la tabla de la adenda: las capas existen con esos números, aceptan consultas espaciales y
traen los campos que se guardan (nombre y categoría del área, nombre y tipo de la comunidad, nombre del río
o del lago, nombre del monumento, categoría y subcategoría de la zonificación forestal).

`CAPAS` son las seis que deciden una variable del perfil; `APOYO`, las que solo agregan información. A cada
servicio se le envía solo la geometría.
"""

from dataclasses import dataclass

SERNANP = "https://geoservicios.sernanp.gob.pe/arcgis/rest/services/sernanp_visor/servicio_descarga/MapServer"
SERFOR_ZONIFICACION = (
    "https://geo.serfor.gob.pe/geoservicios/rest/services/Servicios_OGC/Zonificacion_Forestal/MapServer"
)
SERFOR_MODALIDAD_ACCESO = (
    "https://geo.serfor.gob.pe/geoservicios/rest/services/Servicios_OGC/Modalidad_Acceso/MapServer"
)
IDEP_COMUNIDADES = (
    "https://www.idep.gob.pe/geoportal/rest/services/INSTITUCIONALES/COMUNIDADES_NATIVAS/MapServer"
)
IGN_HIDROGRAFIA = "https://www.idep.gob.pe/geoportal/rest/services/SERVICIOS_IGN/HIDROGRAFIA_100K/MapServer"
SIGDA = "https://sigda.cultura.gob.pe/sigda/rest/services/v_3/maps_delimitado/MapServer"
ANA_FAJA_MARGINAL = "https://geosnirh.ana.gob.pe/server/rest/services/Público/FajaMarginal/MapServer"


@dataclass(frozen=True)
class Capa:
    codigo: str  # el que va en CAPAS_LEGALES_ACTIVAS
    variable: str | None  # la variable del perfil que responde; None en las de apoyo
    nombre: str  # cómo se cita en la pantalla y en el DEX
    entidad: str
    servicio: str  # dirección del MapServer
    capas: tuple[int, ...]  # números de capa dentro del servicio


CAPAS: tuple[Capa, ...] = (
    Capa(
        "sernanp_anp",
        "en_anp",
        "Áreas naturales protegidas de administración nacional y zonas reservadas",
        "SERNANP",
        SERNANP,
        (1, 2),
    ),
    Capa("sernanp_amortiguamiento", "en_anp", "Zonas de amortiguamiento", "SERNANP", SERNANP, (8,)),
    Capa(
        "serfor_zonificacion",
        "en_tierra_forestal",
        "Zonificación forestal",
        "SERFOR",
        SERFOR_ZONIFICACION,
        (0,),
    ),
    Capa(
        "idep_comunidades",
        "en_tierra_comunal",
        "Comunidades nativas y campesinas",
        "IGN, en el geoportal de la IDEP",
        IDEP_COMUNIDADES,
        (0, 1),
    ),
    Capa(
        "ign_hidrografia",
        "junto_a_cuerpo_de_agua",
        "Hidrografía de la carta nacional 1:100 000",
        "IGN",
        IGN_HIDROGRAFIA,
        (0, 1, 2),
    ),
    Capa(
        "sigda_monumentos",
        "en_patrimonio_cultural",
        "Monumentos arqueológicos prehispánicos delimitados",
        "Ministerio de Cultura, SIGDA",
        SIGDA,
        (0,),
    ),
)

APOYO: tuple[Capa, ...] = (
    Capa(
        "sernanp_conservacion", None, "Áreas de conservación regional y privada", "SERNANP", SERNANP, (3, 4)
    ),
    Capa(
        "serfor_modalidad_acceso",
        None,
        "Cesiones en uso y autorizaciones de cambio de uso",
        "SERFOR",
        SERFOR_MODALIDAD_ACCESO,
        (1, 3),
    ),
    # La adenda no pudo probarlo; el 2026-10-09 respondió con una sola capa, la 127 ("FajaMarginal").
    Capa("ana_faja_marginal", None, "Fajas marginales delimitadas", "ANA", ANA_FAJA_MARGINAL, (127,)),
)

POR_CODIGO = {c.codigo: c for c in (*CAPAS, *APOYO)}
