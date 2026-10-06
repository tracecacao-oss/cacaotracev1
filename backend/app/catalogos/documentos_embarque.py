"""Los 4 documentos de embarque de un lote de exportación (Parte 8). Se cargan antes de emitir el DEX. El
sistema no lee su contenido ni compara sus cifras con las del lote: eso lo revisa una persona."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TipoEmbarque:
    codigo: str
    nombre: str
    emisor_habitual: str


TIPOS = (
    TipoEmbarque("factura_comercial", "Factura comercial", "La cooperativa"),
    TipoEmbarque("packing_list", "Lista de empaque", "La cooperativa"),
    TipoEmbarque("certificado_origen", "Certificado de origen", "La entidad que lo emite para el destino"),
    TipoEmbarque("certificado_fitosanitario", "Certificado fitosanitario", "SENASA"),
)
POR_CODIGO = {t.codigo: t for t in TIPOS}
CODIGOS = tuple(POR_CODIGO)
