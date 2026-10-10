"""Los documentos de embarque de un lote de exportación (Parte 8; adenda 6, sección 7). Se cargan antes de
emitir el DEX. El sistema no lee su contenido ni compara sus cifras con las del lote: eso lo revisa una
persona. Desde la adenda 6, cada tipo dice si es obligatorio: los cuatro de la Parte 8 lo son y la declaración
aduanera (`dam`) no. Solo los obligatorios cuentan para `documentos_embarque_completos`. La `dam` se puede
cargar también con el lote cerrado, y es el único documento de embarque con un registro consultable: SUNAT
publica la consulta de una declaración por su número (decisión del equipo del 2026-10-09: admite cotejo en
fuente).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TipoEmbarque:
    codigo: str
    nombre: str
    emisor_habitual: str
    obligatorio: bool = True
    registro_consultable: bool = False


TIPOS = (
    TipoEmbarque("factura_comercial", "Factura comercial", "La cooperativa"),
    TipoEmbarque("packing_list", "Lista de empaque", "La cooperativa"),
    TipoEmbarque("certificado_origen", "Certificado de origen", "La entidad que lo emite para el destino"),
    TipoEmbarque("certificado_fitosanitario", "Certificado fitosanitario", "SENASA"),
    TipoEmbarque(
        "dam", "Declaración Aduanera de Mercancías", "SUNAT", obligatorio=False, registro_consultable=True
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
