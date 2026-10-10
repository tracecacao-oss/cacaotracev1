"""Los documentos de embarque de un lote de exportación (Parte 8; adenda 6, sección 7). Se cargan antes de
emitir el DEX. El sistema no lee su contenido ni compara sus cifras con las del lote: eso lo revisa una
persona. Desde la adenda 6, cada tipo dice si es obligatorio: los cuatro de la Parte 8 lo son y la declaración
aduanera (`dam`) no. Solo los obligatorios cuentan para `documentos_embarque_completos`. La `dam` se puede
cargar también con el lote cerrado, y es el único documento de embarque con un registro consultable: SUNAT
publica la consulta de una declaración por su número (decisión del equipo del 2026-10-09: admite cotejo en
fuente).

Pedido del equipo del 2026-10-10: cada tipo dice qué es, quién lo emite y dónde se tramita, con lo que dicen
las fuentes oficiales consultadas ese día. Son textos de ayuda: no cambian qué documento es obligatorio ni qué
comprueba el lote.
- Factura: Reglamento de Comprobantes de Pago (art. 4, num. 1.1) y procedimiento DESPA-PG.02 de SUNAT
  (VII.A.1.3).
- Lista de empaque: ni DESPA-PG.02 ni la orientación aduanera de SUNAT le dan un formato.
- Certificado de origen: VUCE, "Certificado de origen"; DS 007-2022-MINCETUR; lista de entidades delegadas de
  la VUCE (actualizada el 08/07/2026); Acuerdo Comercial con la Unión Europea, Anexo II, arts. 15, 16, 20
  y 21.
- Certificado fitosanitario: SENASA, "Certificado fitosanitario" (se pide por la VUCE).
- Declaración aduanera: Ley General de Aduanas (arts. 2 y 19) y DESPA-PG.02.
"""

from dataclasses import dataclass

ENTIDADES_DELEGADAS = "https://www.vuce.gob.pe/archivos_entidades/origen/Entidades_Delegadas.pdf"
VUCE = "https://www.vuce.gob.pe/"
SUNAT_EXPORTACION = "https://www.sunat.gob.pe/orientacionaduanera/exportacion/requisitos.html"


@dataclass(frozen=True)
class TipoEmbarque:
    codigo: str
    nombre: str
    emisor_habitual: str
    que_es: str
    quien_lo_emite: str
    obligatorio: bool = True
    registro_consultable: bool = False
    # Lo que conviene saber para un destino, cuando la fuente lo dice.
    nota: str | None = None
    # Dónde se tramita: páginas oficiales, con su nombre.
    tramite: tuple[tuple[str, str], ...] = ()


TIPOS = (
    TipoEmbarque(
        "factura_comercial",
        "Factura comercial",
        "La organización",
        que_es="El comprobante de pago de la venta al importador. La aduana lo asocia a la declaración de "
        "exportación.",
        quien_lo_emite="La organización, como exportadora: una factura electrónica de SUNAT (en papel, solo "
        "en contingencia).",
        tramite=((SUNAT_EXPORTACION, "Requisitos para exportar (SUNAT)"),),
    ),
    TipoEmbarque(
        "packing_list",
        "Lista de empaque",
        "La organización",
        que_es="El detalle del embarque: los sacos o bultos, su contenido y sus pesos.",
        quien_lo_emite="La organización, como exportadora. No tiene un formato oficial.",
    ),
    TipoEmbarque(
        "certificado_origen",
        "Certificado de origen",
        "Una entidad delegada por MINCETUR",
        que_es="Prueba que el cacao es originario del Perú, para que el importador pida la preferencia "
        "arancelaria del acuerdo comercial con el país de destino.",
        quien_lo_emite="Una entidad delegada por MINCETUR (una cámara de comercio, ADEX o la SNI), a pedido "
        "de la organización por el Componente Origen de la VUCE.",
        nota="Con la Unión Europea, el acuerdo comercial acepta como prueba de origen el EUR.1 o una "
        "declaración en factura: la hace un exportador autorizado por MINCETUR o, si el envío no pasa de "
        "6000 euros, cualquier exportador.",
        tramite=(
            (VUCE, "VUCE, Componente Origen"),
            (ENTIDADES_DELEGADAS, "Entidades delegadas por MINCETUR"),
        ),
    ),
    TipoEmbarque(
        "certificado_fitosanitario",
        "Certificado fitosanitario",
        "SENASA",
        que_es="El documento oficial que certifica que el envío cumple los requisitos de sanidad vegetal "
        "del país de destino.",
        quien_lo_emite="SENASA, a pedido de la organización por la VUCE.",
        tramite=((VUCE, "VUCE"),),
    ),
    TipoEmbarque(
        "dam",
        "Declaración Aduanera de Mercancías",
        "SUNAT",
        que_es="La declaración electrónica ante SUNAT que somete el cacao al régimen de exportación "
        "definitiva. Se numera antes del embarque y se regulariza después.",
        quien_lo_emite="La transmite el agente de aduanas con el mandato de la organización, o la "
        "organización misma como despachador. SUNAT le asigna el número.",
        obligatorio=False,
        registro_consultable=True,
    ),
)
POR_CODIGO = {t.codigo: t for t in TIPOS}
CODIGOS = tuple(POR_CODIGO)
OBLIGATORIOS = tuple(t.codigo for t in TIPOS if t.obligatorio)
# Adenda 6, sección 7, regla 6: el único que se carga con el lote cerrado.
DESPUES_DEL_DEX = ("dam",)
# El número de la declaración: SUNAT lo consulta por aduana, año, régimen y número, pero no se encontró su
# formato fijo (adenda 6, sección 14): texto de 5 a 30 caracteres.
LARGO_NUMERO_DAM = (5, 30)
# Las dos consultas públicas que nombra el orientador para la declaración aduanera.
CONSULTAS_DAM = (
    ("https://ww3.sunat.gob.pe/aduanas/informli/ildua.htm", "Consulta de una declaración"),
    ("http://www.aduanet.gob.pe/aduanas/informgest/ExpoDef.htm", "Consulta de declaraciones de exportación"),
)
