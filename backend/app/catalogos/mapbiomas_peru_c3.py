"""Leyenda oficial de MapBiomas Perú, Colección 3.

Copiada del documento "Códigos de los valores del píxel de las clases de cobertura y uso de suelo del
Perú usados en la Colección 3" (Leyenda_MapBiomasPeru_3-Leyenda-CortaENES.pdf), publicado en
peru.mapbiomas.org, sección Descargas > Información de las leyendas (consultado el 2026-10-05).

Los nombres en inglés (NOMBRES_EN) son los de la misma leyenda bilingüe, tal como se publica en
old-peru.mapbiomas.org (Descargas > Información de las leyendas, consultado el 2026-10-08): el sitio nuevo
ya muestra la Colección 4.

Cuentan como bosque las clases de "1. Formación boscosa" según esa leyenda: Bosque, Bosque seco, Manglar
y Bosque inundable (y el código 1 del propio grupo). La plantación forestal está en "3. Área agropecuaria".
"""

# código -> (nombre, grupo de nivel 1)
CLASES: dict[int, tuple[str, str]] = {
    1: ("Formación boscosa", "Formación boscosa"),
    3: ("Bosque", "Formación boscosa"),
    4: ("Bosque seco", "Formación boscosa"),
    5: ("Manglar", "Formación boscosa"),
    6: ("Bosque inundable", "Formación boscosa"),
    10: ("Formación natural no boscosa", "Formación natural no boscosa"),
    11: ("Zona pantanosa o pastizal inundable", "Formación natural no boscosa"),
    12: ("Pastizal / herbazal", "Formación natural no boscosa"),
    29: ("Afloramiento rocoso", "Formación natural no boscosa"),
    66: ("Matorral", "Formación natural no boscosa"),
    70: ("Loma costera", "Formación natural no boscosa"),
    13: ("Otra formación no boscosa", "Formación natural no boscosa"),
    14: ("Área agropecuaria", "Área agropecuaria"),
    15: ("Pasto", "Área agropecuaria"),
    18: ("Agricultura", "Área agropecuaria"),
    35: ("Palma aceitera", "Área agropecuaria"),
    40: ("Arroz", "Área agropecuaria"),
    72: ("Otros cultivos", "Área agropecuaria"),
    9: ("Plantación forestal", "Área agropecuaria"),
    21: ("Mosaico agropecuario", "Área agropecuaria"),
    22: ("Área sin vegetación", "Área sin vegetación"),
    23: ("Playa", "Área sin vegetación"),
    24: ("Infraestructura urbana", "Área sin vegetación"),
    30: ("Minería", "Área sin vegetación"),
    32: ("Salina costera", "Área sin vegetación"),
    61: ("Salar", "Área sin vegetación"),
    68: ("Otra área natural sin vegetación", "Área sin vegetación"),
    25: ("Otra área sin vegetación", "Área sin vegetación"),
    26: ("Cuerpo de agua", "Cuerpo de agua"),
    33: ("Río, lago u océano", "Cuerpo de agua"),
    31: ("Acuicultura", "Cuerpo de agua"),
    34: ("Glaciar", "Cuerpo de agua"),
    27: ("No observado", "No observado"),
}
# código -> nombre en inglés, copiado de la leyenda bilingüe (sin los espacios de más del documento).
NOMBRES_EN: dict[int, str] = {
    1: "Forest formation",
    3: "Forest",
    4: "Dry forest",
    5: "Mangrove",
    6: "Flooded forest",
    10: "Non-forest formation",
    11: "Swamp or Flooded Grassland",
    12: "Grasslands / herbaceous",
    29: "Rocky Outcrop",
    66: "Scrubland",
    70: "Fog oasis",
    13: "Other non-forest formations",
    14: "Agricultural area",
    15: "Pasture",
    18: "Agriculture",
    35: "Oil palm",
    40: "Rice",
    72: "Other crops",
    9: "Planted forest",
    21: "Mosaic of agriculture and pasture",
    22: "Non-vegetated area",
    23: "Beach",
    24: "Infrastructure",
    30: "Mining",
    32: "Coastal Salt flat",
    61: "Salt flat",
    68: "Other natural non vegetated area",
    25: "Other non vegetated area",
    26: "Water body",
    33: "River, lake or ocean",
    31: "Aquaculture",
    34: "Glacier",
    27: "Not observed",
}
BOSQUE = frozenset({1, 3, 4, 5, 6})
# El 0 no figura en la leyenda: un píxel con 0 se informa como "Sin dato".
SIN_DATO = 0


def nombre(codigo: int, idioma: str = "es") -> str:
    if idioma == "en":
        if codigo == SIN_DATO:
            return "No data"
        return NOMBRES_EN.get(codigo, f"Class {codigo} (outside the Collection 3 legend)")
    if codigo == SIN_DATO:
        return "Sin dato"
    if codigo in CLASES:
        return CLASES[codigo][0]
    return f"Clase {codigo} (fuera de la leyenda de la Colección 3)"
