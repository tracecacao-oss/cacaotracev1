"""Catálogo cerrado de hallazgos (Parte 9, con las adendas de la Parte 4 y la adenda 3 de la Parte 5).

Cada código nace de una regla que ya existe en las Partes 3 a 8. Nadie escribe hallazgos a mano: las notas
de las personas aparecen solo como explicación de un hallazgo.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app import textos

GRUPOS = ("impide_cierre", "requiere_atencion", "no_verificado")
CRITERIOS = tuple(range(1, 11))
# Criterios que el sistema no cubre: se nombran para que el operador sepa qué le queda por cubrir.
NO_CUBIERTOS = (8, 9, 10)


@dataclass(frozen=True)
class Entrada:
    grupo: str
    etapa: int
    criterio: int | None  # None: lo fija cada hallazgo (según la comprobación, el requisito o el criterio)


CATALOGO: dict[str, Entrada] = {
    # Etapa 1, parcela
    "analisis_requiere_revision": Entrada("requiere_atencion", 1, 1),
    "diez_hectareas_o_mas": Entrada("requiere_atencion", 1, 1),
    "area_discrepante": Entrada("requiere_atencion", 1, 3),
    "superposicion_aceptada": Entrada("requiere_atencion", 1, 3),
    "superposicion_con_excluida": Entrada("requiere_atencion", 1, 3),
    "tenencia_solo_posesion": Entrada("requiere_atencion", 1, 4),
    # Pedido del equipo del 2026-10-07: una declaración de la cooperativa sin documento que la respalde.
    "exencion_declarada": Entrada("no_verificado", 1, 4),
    "documento_por_vencer": Entrada("requiere_atencion", 1, 4),
    # Adenda de la Parte 4, sección 8
    "conjuntos_registran_bosque_2020": Entrada("requiere_atencion", 1, 1),
    "conjuntos_registran_cambio_posterior": Entrada("requiere_atencion", 1, 1),
    # Adenda 2 de la Parte 4, sección 12
    "revision_de_imagenes_registrada": Entrada("requiere_atencion", 1, 1),
    "habilitada_con_cambio_visible": Entrada("requiere_atencion", 1, 1),
    "coordenada_no_recorrida": Entrada("no_verificado", 1, 1),
    "analisis_por_aproximacion": Entrada("no_verificado", 1, 1),
    "documento_sin_registro_consultable": Entrada("no_verificado", 1, 5),
    "documento_sin_cotejar": Entrada("no_verificado", 1, 5),
    "mapbiomas_pocos_pixeles": Entrada("no_verificado", 1, 1),
    "mapbiomas_sin_cobertura_reciente": Entrada("no_verificado", 1, 1),
    "imagen_previa_lejana": Entrada("no_verificado", 1, 1),
    "sin_imagen_de_alta_resolucion_previa": Entrada("no_verificado", 1, 1),
    # Etapa 2, acopio (lo sellado en el DOP de cada tanda)
    "tanda_observada": Entrada("requiere_atencion", 2, 3),
    "volumen_acumulado_excede_tope": Entrada("requiere_atencion", 2, 3),
    "dias_cosecha_entrega_altos": Entrada("requiere_atencion", 2, 3),
    "peso_difiere_del_documento": Entrada("requiere_atencion", 2, 3),
    "documento_usado_por_otro_productor": Entrada("requiere_atencion", 2, 3),
    "liquidacion_con_productor_con_ruc": Entrada("requiere_atencion", 2, 5),
    "registro_y_validacion_misma_persona": Entrada("requiere_atencion", 2, 5),
    "documento_entrega_sin_cotejar": Entrada("no_verificado", 2, 5),
    # Etapa 2, proceso (lo sellado en el DPP de cada corrida)
    "rendimiento_sobre_banda": Entrada("requiere_atencion", 2, 3),
    "rendimiento_bajo_banda": Entrada("requiere_atencion", 2, 3),
    "peso_final_supera_entrada": Entrada("requiere_atencion", 2, 3),
    "etapas_desde_plantilla": Entrada("no_verificado", 2, 3),
    # Etapa 3, lote
    "comprobacion_fallida": Entrada("impide_cierre", 3, None),
    "parcela_cambio_de_estado": Entrada("requiere_atencion", 3, None),
    "desviacion_fifo": Entrada("requiere_atencion", 3, 3),
    # Siempre presentes
    "vinculo_fisico_no_comprobado": Entrada("no_verificado", 3, 3),
    "historial_regional_no_cubierto": Entrada("no_verificado", 1, 1),
    "criterio_no_cubierto": Entrada("no_verificado", 3, None),
}
ORDEN = {codigo: i for i, codigo in enumerate(CATALOGO)}

# Criterio de cada comprobación de la Parte 8 (decisión de construcción del 2026-10-06, a confirmar con el
# equipo): las parcelas, al 1; DOP, DPP, genealogía y embarque, al 3 (la cadena); los datos y documentos de
# la cooperativa y del importador, al 5 (la información que respalda la declaración).
CRITERIO_COMPROBACION = {
    "parcelas_habilitadas": 1,
    "sin_parcelas_excluidas": 1,
    "dops_vigentes": 3,
    "dpps_vigentes": 3,
    "genealogia_cuadra": 3,
    "expediente_cooperativa_completo": 5,
    "datos_cooperativa_completos": 5,
    "importador_completo": 5,
    "documentos_embarque_completos": 3,
}
# Requisitos de habilitación que tocan la tenencia y la legalidad (criterio 4); los demás, criterio 1.
REQUISITOS_CRITERIO_4 = ("expediente_completo", "productor_listo")


@dataclass
class Hallazgo:
    codigo: str
    sujeto: dict[str, str | None]  # {"tipo": "parcela", "id": "...", "codigo": "PA-00001"}
    datos: dict[str, Any] = field(default_factory=dict)
    peso: Decimal | None = None
    explicacion: str | None = None
    criterio: int | None = None

    @property
    def entrada(self) -> Entrada:
        return CATALOGO[self.codigo]

    def hecho(self) -> dict[str, str]:
        return textos.ambos(f"hallazgo.{self.codigo}", **self.datos)

    def a_dict(self) -> dict[str, Any]:
        entrada = self.entrada
        return {
            "codigo": self.codigo,
            "grupo": entrada.grupo,
            "etapa": entrada.etapa,
            "criterio": self.criterio or entrada.criterio,
            "sujeto": self.sujeto,
            "hecho": self.hecho(),
            "datos": _limpio(self.datos),
            "peso_en_lote_pct": f"{self.peso:.2f}" if self.peso is not None else None,
            "explicacion": self.explicacion,
        }


def _limpio(valor: Any) -> Any:
    """Datos listos para JSON: decimales como texto."""
    if isinstance(valor, dict):
        return {k: _limpio(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_limpio(v) for v in valor]
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def sujeto(tipo: str, id_: Any, codigo: str | None) -> dict[str, str | None]:
    return {"tipo": tipo, "id": str(id_) if id_ is not None else None, "codigo": codigo}
