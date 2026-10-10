"""Cotejo en fuente y validación de los datos legales de un documento (Parte 4, adenda 4 y Parte 8).

Desde la adenda 4, la legalidad de la parcela la calcula app/services/legalidad.py: aquí quedan el cotejo,
la validación de los datos legales al cargar un documento y la casilla con su estado, que usa el expediente
de la cooperativa (Parte 8). El estado se calcula al consultar, con la fecha del día. Desde la adenda 6, el
cotejo también acepta el documento de embarque con registro consultable (la declaración aduanera), aun con
el lote cerrado.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.catalogos import documentos_embarque
from app.catalogos import documentos_legales as catalogo
from app.config import get_settings
from app.contexto import Contexto
from app.errores import error_api
from app.fechas import ahora, hoy_lima
from app.models import Documento, ExencionDocumento, Parcela
from app.services.auditoria import registrar_auditoria

ORDEN = {"vigente": 0, "por_vencer": 1, "vencido": 2}


@dataclass
class Casilla:
    codigo: str
    estado: str  # vigente, por_vencer, vencido, no_aplica, no_requerida o faltante
    documento: Documento | None = None  # el que cubre la casilla
    documentos: list[Documento] = field(default_factory=list)
    exencion: ExencionDocumento | None = None
    # Solo en tenencia: el otro documento de tenencia que ya cubre la casilla (estado no_requerida).
    cubierta_por: str | None = None

    @property
    def nivel(self) -> str | None:
        if self.documento is None or self.estado not in ("vigente", "por_vencer"):
            return None
        return "verificado_en_fuente" if self.documento.cotejado_en else "documentado"


def estado_documento(documento: Documento, hoy: date, aviso_dias: int) -> str:
    vence = documento.fecha_vencimiento
    if vence is None or vence > hoy + timedelta(days=aviso_dias):
        return "vigente"
    return "por_vencer" if vence >= hoy else "vencido"


def _casilla(codigo: str, docs: list[Documento], exencion, hoy: date, aviso_dias: int) -> Casilla:
    if docs:
        # Cuenta el documento con el mejor estado y, entre esos, el de vencimiento más lejano.
        lejano = date.max
        mejor = min(
            docs,
            key=lambda d: (
                ORDEN[estado_documento(d, hoy, aviso_dias)],
                -(d.fecha_vencimiento or lejano).toordinal(),
            ),
        )
        return Casilla(codigo, estado_documento(mejor, hoy, aviso_dias), mejor, docs, exencion)
    if exencion is not None:
        return Casilla(codigo, "no_aplica", None, [], exencion)
    return Casilla(codigo, "faltante")


# ---------- Reglas de carga ----------


def no_excluida(parcela: Parcela) -> None:
    """Una parcela excluida no se edita, no se habilita ni recibe documentos. Tampoco para el superadmin."""
    if parcela.habilitacion_estado == "excluida":
        raise error_api(
            400, "parcela_excluida", "La parcela está excluida: no admite cambios, documentos ni decisiones."
        )


def validar_datos_legales(
    tipo: str, numero, entidad_emisora, fecha_emision, fecha_vencimiento, clase: str | None = None
) -> dict:
    """Un documento legal (de la parcela o, desde la Parte 8, de la cooperativa) exige número, entidad emisora
    y fecha de emisión.

    Adenda 4, sección 6: la declaración jurada y lo que firma la comunidad no llevan número ni entidad
    emisora, pero sí la fecha de firma; la declaración jurada vence sola a los DECLARACION_VIGENCIA_MESES. El
    título no inscrito dice su clase. Los tipos anteriores (laboral, tributario y zonificación) ya no se
    cargan. Adenda 6, sección 4: la declaración de renta de la organización lleva la fecha de presentación
    como emisión y vence sola a los RENTA_VIGENCIA_MESES; los dos registros de exportador ya no se cargan."""
    legal = catalogo.tipo_legal(tipo)
    if legal is None:
        return {}
    if legal.anterior:
        donde = " en la parcela" if tipo in catalogo.POR_CODIGO else ""
        raise error_api(
            422,
            "tipo_anterior",
            f"{legal.nombre} ya no se carga{donde}: los cargados se conservan como documentos anteriores.",
        )
    exigidos = [("fecha de emisión", fecha_emision)]
    if legal.requiere_numero:
        exigidos = [("número", numero), ("entidad emisora", entidad_emisora), *exigidos]
    faltan = [n for n, v in exigidos if not v]
    if faltan:
        raise error_api(422, "datos_legales_requeridos", f"Falta: {', '.join(faltan)}.")
    if fecha_emision > hoy_lima():
        raise error_api(422, "fecha_futura", "La fecha de emisión no puede ser futura.")
    if tipo == "declaracion_jurada_tenencia":
        from app.services.legalidad import vencimiento_declaracion  # evita importación circular

        fecha_vencimiento = vencimiento_declaracion(fecha_emision)
    elif tipo == "renta_anual":
        from app.services.legalidad import sumar_meses  # evita importación circular

        fecha_vencimiento = sumar_meses(fecha_emision, get_settings().renta_vigencia_meses)
    if fecha_vencimiento is not None and fecha_vencimiento <= fecha_emision:
        raise error_api(422, "vencimiento_invalido", "El vencimiento debe ser posterior a la emisión.")
    clase = (clase or "").strip() or None
    if tipo == "titulo_no_inscrito":
        if clase not in catalogo.CLASES_TITULO_NO_INSCRITO:
            raise error_api(
                422,
                "clase_requerida",
                "Indica si el título no inscrito es un título de formalización, una escritura pública o una "
                "minuta.",
            )
    elif clase is not None:
        raise error_api(422, "clase_invalida", "Solo el título no inscrito lleva clase.")
    datos = {
        "numero": (numero or "").strip() or None,
        "entidad_emisora": (entidad_emisora or "").strip() or None,
        "fecha_emision": fecha_emision,
        "fecha_vencimiento": fecha_vencimiento,
    }
    if clase:
        datos["clase"] = clase
    return datos


# ---------- Cotejo en fuente ----------


def cotejar(contexto: Contexto, documento: Documento, nota: str) -> Documento:
    """Documentos del expediente de la parcela (Parte 4) o de la cooperativa (Parte 8), y desde la adenda 6 el
    documento de embarque con registro consultable (decisión del equipo del 2026-10-09: la declaración
    aduanera, también con el lote cerrado; mismos campos y misma auditoría)."""
    tipo = catalogo.tipo_legal(documento.tipo)
    if tipo is None and documento.entidad == "lote":
        tipo = documentos_embarque.POR_CODIGO.get(documento.tipo)
    if tipo is None:
        raise error_api(400, "no_es_documento_legal", "Solo se cotejan documentos del expediente legal.")
    if documento.entidad == "parcela":
        no_excluida(contexto.sesion.get(Parcela, documento.entidad_id))
    if not tipo.registro_consultable:
        raise error_api(
            400,
            "sin_registro_consultable",
            f"{tipo.nombre} no tiene un registro público contra el cual cotejarlo: queda como documentado.",
        )
    if documento.anulado_en is not None:
        raise error_api(400, "documento_anulado", "El documento está anulado.")
    if documento.cotejado_en is not None:
        raise error_api(400, "documento_cotejado", "El documento ya tiene un cotejo registrado.")
    documento.cotejado_en = ahora()
    documento.cotejado_por = contexto.usuario_id
    documento.cotejo_nota = nota
    registrar_auditoria(
        contexto,
        "documento.cotejar",
        "documento",
        documento.id,
        {"tipo": documento.tipo, "entidad_id": documento.entidad_id, "nota": nota},
    )
    contexto.sesion.commit()
    return documento
