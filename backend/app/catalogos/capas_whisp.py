"""Capas de Whisp: a qué pregunta responde cada columna de su respuesta y de qué conjunto de datos sale.

Armado el 2026-10-05 a partir de:
- la respuesta real guardada en `tests/datos/whisp_respuesta_real.json` (Whisp 3.0.0a17);
- la tabla oficial de Whisp `src/openforis_whisp/parameters/lookup_datasets.csv` (columnas `theme` y
  `theme_timber`) y su `layers_description.md`, en github.com/forestdatapartnership/whisp (rama main,
  commit addae78 del 2026-09-28).

Preguntas (adenda de la Parte 4):
- `estado_2020`: qué había en la parcela al 31 de diciembre de 2020. Son los temas `treecover`,
  `primary`, `naturally_reg_2020` y `planted_plantation_2020` de Whisp; esas capas son medidas de bosque.
  `SBTN_natural_2020` también responde a esta pregunta, pero mide tierra natural, no solo bosque.
- `cambio_posterior`: qué cambió después del 31 de diciembre de 2020 (`disturbance_after` y
  `agri_after_2020`). En las series anuales decide el año de la columna: Whisp marca `TMF_def_2021` a
  `TMF_def_2025` como `disturbance_before`, pero su nombre dice que la deforestación es de esos años.
- `cultivo`: cultivos y plantaciones agrícolas (`commodities` y los modelos de cultivos de 2024).
- `otra`: lo demás, como perturbaciones hasta 2020, cobertura arbórea de 2024 o concesiones.
Una columna que no está aquí se guarda con `pregunta = otra`; nunca se descarta.
"""

import re
from dataclasses import dataclass
from typing import Any

from app.catalogos.conjuntos_datos import CONJUNTOS

PREGUNTAS = ("estado_2020", "cambio_posterior", "cultivo", "otra")


@dataclass(frozen=True)
class Capa:
    pregunta: str
    conjunto: str | None
    mide_bosque: bool = False  # medida de bosque al 2020, para "registra bosque en 2020"
    serie: bool = False  # columna de un año; el mismo conjunto trae también el agregado


def _b(conjunto: str) -> Capa:
    return Capa("estado_2020", conjunto, mide_bosque=True)


EXACTAS: dict[str, Capa] = {
    # Cobertura arbórea al 2020 (theme treecover)
    "EUFO_2020": _b("jrc_gfc2020"),
    "GLAD_Primary": _b("umd_glad_primary"),
    "TMF_undist": _b("jrc_tmf"),
    "GFC_TC_2020": _b("umd_gfc"),
    "Forest_FDaP": _b("fdap_bosque"),
    "ESA_TC_2020": _b("esa_worldcover"),
    "ForTy_forest_2020": _b("forty"),
    # Bosque primario, de regeneración natural y plantado al 2020 (theme_timber)
    "GFT_primary": _b("jrc_gft2020"),
    "IFL_2020": _b("ifl"),
    "European_Primary_Forest": _b("epfd"),
    "ForTy_primary_2020": _b("forty"),
    "GFT_naturally_regenerating": _b("jrc_gft2020"),
    "ForTy_nat_reg_2020": _b("forty"),
    "GFT_planted_plantation": _b("jrc_gft2020"),
    "IIASA_planted_plantation": _b("iiasa_gfm"),
    "ForTy_planted_2020": _b("forty"),
    "ForTy_plantation_2020": _b("forty"),
    # Tierra natural al 2020: incluye vegetación baja, agua y suelo desnudo
    "SBTN_natural_2020": Capa("estado_2020", "sbtn_natural_lands"),
    # Cultivos al 2020 (theme commodities)
    "TMF_plant": Capa("cultivo", "jrc_tmf"),
    "Oil_palm_Descals": Capa("cultivo", "descals_palma"),
    "Oil_palm_FDaP": Capa("cultivo", "fdap_cultivos"),
    "Coffee_FDaP": Capa("cultivo", "fdap_cultivos"),
    "Cocoa_FDaP": Capa("cultivo", "fdap_cultivos"),
    "Cocoa_ETH": Capa("cultivo", "eth_cacao"),
    "Rubber_FDaP": Capa("cultivo", "fdap_cultivos"),
    "Rubber_RBGE": Capa("cultivo", "rbge_caucho"),
    "Rubber_RBGE_2020": Capa("cultivo", "rbge_caucho"),
    "Soy_Song_2020": Capa("cultivo", "song_soya"),
    "ForTy_tree_crops_2020": Capa("cultivo", "forty"),
    # Cultivos en 2024 (agri_after_2020): dicen qué hay, no qué cambió
    "Oil_palm_2024_FDaP": Capa("cultivo", "fdap_cultivos"),
    "Rubber_2024_FDaP": Capa("cultivo", "fdap_cultivos"),
    "Coffee_FDaP_2024": Capa("cultivo", "fdap_cultivos"),
    "Cocoa_2024_FDaP": Capa("cultivo", "fdap_cultivos"),
    # Ganancia de cultivo de 2020 a 2024: un cambio posterior
    "ESRI_crop_gain_2020_2024": Capa("cambio_posterior", "esri_lulc"),
    "ESRI_crop_gain_2024": Capa("cambio_posterior", "esri_lulc"),
    # Agregados de perturbación
    "TMF_deg_before_2020": Capa("otra", "jrc_tmf"),
    "TMF_def_before_2020": Capa("otra", "jrc_tmf"),
    "GFC_loss_before_2020": Capa("otra", "umd_gfc"),
    "ESA_fire_before_2020": Capa("otra", "esa_firecci"),
    "MODIS_fire_before_2020": Capa("otra", "modis_fire"),
    "RADD_before_2020": Capa("otra", "wur_radd"),
    "GLAD-L_before_2020": Capa("otra", "umd_glad_l"),
    "GLAD-S2_before_2020": Capa("otra", "umd_glad_s2"),
    "TMF_deg_after_2020": Capa("cambio_posterior", "jrc_tmf"),
    "TMF_def_after_2020": Capa("cambio_posterior", "jrc_tmf"),
    "GFC_loss_after_2020": Capa("cambio_posterior", "umd_gfc"),
    "MODIS_fire_after_2020": Capa("cambio_posterior", "modis_fire"),
    "RADD_after_2020": Capa("cambio_posterior", "wur_radd"),
    "DIST_after_2020": Capa("cambio_posterior", "umd_glad_dist"),
    "GLAD-L_after_2020": Capa("cambio_posterior", "umd_glad_l"),
    "GLAD-S2_after_2020": Capa("cambio_posterior", "umd_glad_s2"),
    # Cobertura arbórea en 2024 y concesiones: no responden a las dos preguntas
    "TMF_regrowth_2024": Capa("otra", "jrc_tmf"),
    "ESRI_2024_TC": Capa("otra", "esri_lulc"),
    "GFW_logging_before_2020": Capa("otra", "gfw_logging"),
}

# Series anuales: el año de la columna decide la pregunta.
SERIES = (
    ("TMF_def_", "jrc_tmf"),
    ("TMF_deg_", "jrc_tmf"),
    ("GFC_loss_year_", "umd_gfc"),
    ("RADD_year_", "wur_radd"),
    ("DIST_year_", "umd_glad_dist"),
    ("GLAD-L_year_", "umd_glad_l"),
    ("GLAD-S2_year_", "umd_glad_s2"),
    ("ESA_fire_", "esa_firecci"),
    ("MODIS_fire_", "modis_fire"),
)
_ANIO = re.compile(r"(\d{4})$")

# Columnas que no son capas: datos de la parcela, metadatos y la conclusión propia de Whisp.
NO_CAPAS = {
    "plotId",
    "external_id",
    "Area",
    "Geometry_type",
    "Country",
    "ProducerCountry",
    "Admin_Level_1",
    "Centroid_lon",
    "Centroid_lat",
    "Unit",
    "In_waterbody",
    "geo",
    "whisp_processing_metadata",
}
_NO_CAPA_PREFIJOS = ("Ind_", "risk_")


def es_capa(nombre: str) -> bool:
    return nombre not in NO_CAPAS and not nombre.startswith(_NO_CAPA_PREFIJOS)


def clasificar(nombre: str) -> Capa:
    if nombre in EXACTAS:
        return EXACTAS[nombre]
    for prefijo, conjunto in SERIES:
        resto = nombre.removeprefix(prefijo)
        if resto != nombre and _ANIO.fullmatch(resto):
            return Capa("cambio_posterior" if int(resto) >= 2021 else "otra", conjunto, serie=True)
    return Capa("otra", None)


def capas(propiedades: dict[str, Any]) -> list[dict[str, Any]]:
    """Todas las capas de una respuesta de Whisp, en su orden, con su pregunta y su conjunto de datos."""
    unidad = propiedades.get("Unit")
    salida = []
    for nombre, valor in propiedades.items():
        if not es_capa(nombre):
            continue
        capa = clasificar(nombre)
        salida.append(
            {
                "nombre": nombre,
                "pregunta": capa.pregunta,
                "conjunto_de_datos": capa.conjunto,
                "conjunto_nombre": CONJUNTOS.get(capa.conjunto) if capa.conjunto else None,
                "mide_bosque": capa.mide_bosque,
                "serie": capa.serie,
                "valor": valor,
                "unidad": unidad,
            }
        )
    return salida
