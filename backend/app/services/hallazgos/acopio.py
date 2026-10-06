"""Reglas de la etapa 2: acopio (lo sellado en el DOP de cada tanda) y proceso (lo sellado en el DPP de cada
corrida). Una función por regla."""

from app import textos
from app.models import Corrida, Tanda
from app.services.hallazgos.catalogo import Hallazgo, sujeto
from app.services.hallazgos.datos import DatosLote

# Los DOP emitidos antes de la adenda 3 de la Parte 5 guardan los códigos de la guía de remisión.
ALERTAS_ANTERIORES = {
    "peso_difiere_de_guia": "peso_difiere_del_documento",
    "guia_usada_por_otro_productor": "documento_usado_por_otro_productor",
}
ALERTAS_TANDA = (
    "volumen_acumulado_excede_tope",
    "dias_cosecha_entrega_altos",
    "peso_difiere_del_documento",
    "documento_usado_por_otro_productor",
    "liquidacion_con_productor_con_ruc",
)


def _tanda(d: DatosLote, codigo: str, t: Tanda, explicacion: str | None = None, **datos) -> Hallazgo:
    parcela = d.parcelas[t.parcela_id]
    dop = d.dop_de_tanda[t.id]
    return Hallazgo(
        codigo,
        sujeto("tanda", t.id, t.codigo),
        {"tanda": t.codigo, "parcela": parcela.codigo, "dop": dop.codigo, **datos},
        d.peso_tanda[t.id],
        explicacion=explicacion,
    )


def _contenido(d: DatosLote, t: Tanda) -> dict:
    return d.dop_de_tanda[t.id].contenido or {}


def _alertas(d: DatosLote, t: Tanda) -> list[str]:
    alertas = (_contenido(d, t).get("alertas") or {}).get("tanda") or []
    return [ALERTAS_ANTERIORES.get(a, a) for a in alertas]


def _nota(d: DatosLote, t: Tanda) -> str | None:
    return (_contenido(d, t).get("alertas") or {}).get("nota")


def tanda_observada(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for t in d.tandas_ordenadas():
        observaciones = [x for x in d.decisiones_tanda.get(t.id, []) if x.decision == "observar"]
        if observaciones:
            motivos = [x.nota for x in observaciones if x.nota]
            resultado.append(
                _tanda(d, "tanda_observada", t, " / ".join(motivos) or None, veces=len(observaciones))
            )
    return resultado


def _regla_de_alerta(codigo: str):
    def regla(d: DatosLote) -> list[Hallazgo]:
        return [_tanda(d, codigo, t, _nota(d, t)) for t in d.tandas_ordenadas() if codigo in _alertas(d, t)]

    regla.__name__ = codigo
    regla.__doc__ = f"La tanda se validó con la alerta {codigo}, sellada en su DOP, y con su nota."
    return regla


volumen_acumulado_excede_tope = _regla_de_alerta("volumen_acumulado_excede_tope")
dias_cosecha_entrega_altos = _regla_de_alerta("dias_cosecha_entrega_altos")
peso_difiere_del_documento = _regla_de_alerta("peso_difiere_del_documento")
documento_usado_por_otro_productor = _regla_de_alerta("documento_usado_por_otro_productor")
liquidacion_con_productor_con_ruc = _regla_de_alerta("liquidacion_con_productor_con_ruc")


def registro_y_validacion_misma_persona(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for t in d.tandas_ordenadas():
        identificacion = _contenido(d, t).get("identificacion") or {}
        if "misma_persona" in identificacion:
            misma = bool(identificacion["misma_persona"])
        else:
            validaciones = [x for x in d.decisiones_tanda.get(t.id, []) if x.decision == "validar"]
            misma = bool(validaciones) and validaciones[-1].decidida_por == t.registrada_por
        if misma:
            resultado.append(_tanda(d, "registro_y_validacion_misma_persona", t, _nota(d, t)))
    return resultado


def documento_entrega_sin_cotejar(d: DatosLote) -> list[Hallazgo]:
    """El documento de entrega se adjunta (documentado), pero nadie lo coteja en SUNAT: la guía de remisión
    no tiene registro público consultable."""
    resultado = []
    for t in d.tandas_ordenadas():
        bloque = _contenido(d, t).get("tanda") or {}
        documento = bloque.get("documento_entrega") or bloque.get("guia_remision")
        tipo = (documento or {}).get("tipo") or (
            "guia_remision" if "guia_remision" in bloque else t.doc_entrega_tipo
        )
        if not tipo or (documento or {}).get("nivel") == "verificado_en_fuente":
            continue
        resultado.append(
            _tanda(
                d,
                "documento_entrega_sin_cotejar",
                t,
                documento={i: textos.obtener(i, f"documentos.{tipo}") for i in textos.IDIOMAS},
                tipo=tipo,
                numero=(documento or {}).get("numero") or t.doc_entrega_numero,
            )
        )
    return resultado


# ---------- Proceso ----------


def _dpp_de(d: DatosLote, corrida: Corrida):
    return next((x for x in d.dpps.values() if x.corrida_id == corrida.id), None)


def _corrida(d: DatosLote, codigo: str, c: Corrida, explicacion: str | None = None, **datos) -> Hallazgo:
    dpp = _dpp_de(d, c)
    return Hallazgo(
        codigo,
        sujeto("corrida", c.id, c.codigo),
        {"corrida": c.codigo, "dpp": dpp.codigo if dpp else None, **datos},
        d.peso_corrida[c.id],
        explicacion=explicacion,
    )


def _sellado(d: DatosLote, c: Corrida) -> dict:
    dpp = _dpp_de(d, c)
    return (dpp.contenido if dpp else None) or {}


def _rendimiento(d: DatosLote, codigo: str) -> list[Hallazgo]:
    resultado = []
    for c in d.corridas_ordenadas():
        contenido = _sellado(d, c)
        alertas = contenido.get("alertas") or {}
        if codigo not in (alertas.get("alertas") or []):
            continue
        r = contenido.get("rendimiento") or {}
        banda = (
            f"{r['banda_min']}–{r['banda_max']}"
            if r.get("banda_min") is not None and r.get("banda_max")
            else "—"
        )
        resultado.append(
            _corrida(
                d,
                codigo,
                c,
                alertas.get("explicacion"),
                rendimiento=r.get("rendimiento") or "—",
                banda=banda,
                entrada=textos.numero(r["entrada_kg"]) if r.get("entrada_kg") else "—",
                salida=textos.numero(r["peso_final_kg"]) if r.get("peso_final_kg") else "—",
            )
        )
    return resultado


def rendimiento_sobre_banda(d: DatosLote) -> list[Hallazgo]:
    return _rendimiento(d, "rendimiento_sobre_banda")


def rendimiento_bajo_banda(d: DatosLote) -> list[Hallazgo]:
    return _rendimiento(d, "rendimiento_bajo_banda")


def peso_final_supera_entrada(d: DatosLote) -> list[Hallazgo]:
    return _rendimiento(d, "peso_final_supera_entrada")


def etapas_desde_plantilla(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for c in d.corridas_ordenadas():
        etapas = [e for e in (_sellado(d, c).get("etapas") or []) if e.get("desde_plantilla")]
        if etapas:
            resultado.append(
                _corrida(d, "etapas_desde_plantilla", c, n=len(etapas), etapas=[e["numero"] for e in etapas])
            )
    return resultado


REGLAS = (
    tanda_observada,
    volumen_acumulado_excede_tope,
    dias_cosecha_entrega_altos,
    peso_difiere_del_documento,
    documento_usado_por_otro_productor,
    liquidacion_con_productor_con_ruc,
    registro_y_validacion_misma_persona,
    documento_entrega_sin_cotejar,
    rendimiento_sobre_banda,
    rendimiento_bajo_banda,
    peso_final_supera_entrada,
    etapas_desde_plantilla,
)
