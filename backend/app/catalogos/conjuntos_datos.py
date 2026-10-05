"""Conjuntos de datos que consultan las fuentes del análisis de cobertura (adenda de la Parte 4).

La tabla de convergencia tiene una fila por conjunto de datos, no por API: si el mismo conjunto llega
por Whisp y por GFW, se cuenta una vez. Los nombres salen de la documentación de cada fuente: el
`layers_description.md` de Whisp, los metadatos de cada conjunto en la API de GFW y la leyenda de
MapBiomas Perú.
"""

CONJUNTOS = {
    "jrc_gfc2020": "JRC Global Forest Cover 2020 (Bourgoin et al.)",
    "jrc_gft2020": "JRC Global Forest Types 2020",
    "jrc_tmf": "JRC Tropical Moist Forests (Vancutsem et al. 2021)",
    "umd_glad_primary": "UMD/GLAD bosque primario húmedo tropical (Turubanova et al. 2018)",
    "umd_gfc": "UMD Global Forest Change (Hansen et al.)",
    "esa_worldcover": "ESA WorldCover 2020 (Zanaga et al.)",
    "fdap_bosque": "Forest Data Partnership, persistencia de bosque 2020",
    "fdap_cultivos": "Forest Data Partnership, modelos de cultivos",
    "forty": "ForTy, tipología de bosques 2020 (Google Nature Trace e IIASA)",
    "sbtn_natural_lands": "SBTN Natural Lands Map v1.1, 2020 (Science Based Targets Network)",
    "descals_palma": "Palma aceitera (Descals et al. 2021)",
    "eth_cacao": "Mapa de cacao ETH (Kalischek et al.)",
    "rbge_caucho": "Caucho del sudeste asiático 2020 (RBGE)",
    "song_soya": "Soya en Sudamérica (Song et al.)",
    "wur_radd": "Alertas RADD (Reiche et al.)",
    "umd_glad_dist": "Alertas DIST-ALERT (UMD/GLAD y NASA)",
    "umd_glad_l": "Alertas GLAD-L, Landsat (UMD/GLAD)",
    "umd_glad_s2": "Alertas GLAD-S2, Sentinel-2 (UMD/GLAD)",
    "esa_firecci": "ESA Fire CCI 5.1 (área quemada)",
    "modis_fire": "MODIS MCD64A1 (área quemada)",
    "ifl": "Paisajes forestales intactos 2020 (Potapov et al.)",
    "epfd": "Bosques primarios de Europa (Sabatini et al.)",
    "iiasa_gfm": "IIASA Global Forest Management",
    "esri_lulc": "Esri Land Cover 10 m (Karra et al.)",
    "gfw_logging": "Concesiones madereras (GFW)",
    # Llegan por otras fuentes; se nombran aquí para que la tabla de convergencia use un solo nombre.
    "gfw_integrated_alerts": "Alertas integradas de deforestación de GFW (GLAD-L, GLAD-S2 y RADD)",
    "mapbiomas_peru_c3": "MapBiomas Perú, Colección 3",
}
