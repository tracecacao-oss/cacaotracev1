"""Reglas de la etapa 3 (el lote) y los hallazgos que están siempre. Una función por regla."""

from decimal import Decimal
from typing import Any

from app import textos
from app.services import cooperativa as servicio_cooperativa
from app.services.hallazgos.catalogo import (
    CRITERIO_COMPROBACION,
    NO_CUBIERTOS,
    REQUISITOS_CRITERIO_4,
    Hallazgo,
    sujeto,
)
from app.services.hallazgos.datos import DatosLote

CAMPOS_IMPORTADOR = ("razon_social", "direccion", "correo")


def _lote(d: DatosLote) -> dict:
    return sujeto("lote", d.lote.id, d.lote.codigo)


def _estado(idioma: str, estado: str) -> str:
    return textos.obtener(idioma, "estados").get(estado, estado)


def _caso_en_idiomas(d: DatosLote, comprobacion: str, caso: dict, extra: dict) -> dict[str, str]:
    """El caso en español es el texto exacto de la Parte 8; en inglés se arma con la plantilla de su tipo."""
    codigo = caso.get("codigo")
    if comprobacion == "parcelas_habilitadas":
        p = next((x for x in d.parcelas.values() if str(x.id) == caso.get("id")), None)
        valores = {
            "codigo": codigo,
            "estado": {i: _estado(i, p.habilitacion_estado if p else "") for i in textos.IDIOMAS},
        }
        en = textos.t("en", "casos.parcela_estado", **valores)
    elif comprobacion == "sin_parcelas_excluidas":
        en = textos.t("en", "casos.parcela_excluida", codigo=codigo)
    elif comprobacion in ("dops_vigentes", "dpps_vigentes"):
        registros = d.dops if comprobacion == "dops_vigentes" else d.dpps
        r = next((x for x in registros.values() if str(x.id) == caso.get("id")), None)
        ruta = "casos.dop_estado" if comprobacion == "dops_vigentes" else "casos.dpp_estado"
        en = textos.t("en", ruta, codigo=codigo, estado=_estado("en", r.estado if r else ""))
    elif comprobacion == "genealogia_cuadra":
        suma = sum((Decimal(f.kg_atribuidos) for f in d.filas), Decimal("0"))
        en = textos.t("en", "casos.genealogia", masa=textos.numero(d.masa), suma=textos.numero(suma))
    elif comprobacion == "expediente_cooperativa_completo":
        casilla = extra["casillas"].get(codigo)
        en = textos.t(
            "en",
            "casos.documento_estado",
            documento=textos.obtener("en", f"documentos.{codigo}"),
            estado=_estado("en", casilla.estado if casilla else "faltante"),
        )
    elif comprobacion in ("datos_cooperativa_completos", "importador_completo"):
        campo = extra["campos"].pop(0) if extra["campos"] else None
        dato = textos.obtener("en", "datos_faltantes").get(campo, campo) if campo else ""
        en = textos.t("en", "casos.falta_dato", dato=dato)
    elif comprobacion == "documentos_embarque_completos":
        en = textos.t("en", "casos.falta_documento", documento=textos.obtener("en", f"documentos.{codigo}"))
    else:
        en = caso.get("texto", "")
    es = caso.get("texto", "")
    if caso.get("detalle"):
        es = f"{es}. {caso['detalle'].rstrip('.')}"
    return {"es": es, "en": en}


def _peso_de_caso(d: DatosLote, caso: dict) -> Decimal | None:
    tipo, id_ = caso.get("tipo"), caso.get("id")
    if tipo == "parcela":
        return next((d.peso_parcela[p.id] for p in d.parcelas.values() if str(p.id) == id_), None)
    if tipo == "dop":
        dop = next((x for x in d.dops.values() if str(x.id) == id_), None)
        return d.peso_tanda.get(dop.tanda_id) if dop else None
    if tipo == "dpp":
        dpp = next((x for x in d.dpps.values() if str(x.id) == id_), None)
        return d.peso_corrida.get(dpp.corrida_id) if dpp else None
    return None


def comprobacion_fallida(d: DatosLote) -> list[Hallazgo]:
    """Uno por cada caso de cada comprobación de la Parte 8 que falla. En un DEX emitido no hay ninguno: un
    lote bloqueado no recibe DEX."""
    coop = d.cooperativa
    faltan_coop = [c for c in servicio_cooperativa.DATOS_DEX if not getattr(coop, c)]
    faltan_importador = [c for c in CAMPOS_IMPORTADOR if not (getattr(d.importador, c) or "").strip()]
    casillas = servicio_cooperativa.casillas(d.sesion, coop.id)
    resultado = []
    for comprobacion in d.comprobaciones:
        if comprobacion["resultado"] != "con_observaciones":
            continue
        codigo = comprobacion["codigo"]
        extra: dict[str, Any] = {
            "casillas": casillas,
            "campos": list(
                faltan_coop
                if codigo == "datos_cooperativa_completos"
                else faltan_importador
                if codigo == "importador_completo"
                else []
            ),
        }
        for caso in comprobacion["casos"]:
            tipo = caso.get("tipo") or "lote"
            sujeto_ = (
                sujeto(tipo, caso.get("id"), caso.get("codigo"))
                if tipo in ("parcela", "dop", "dpp")
                else _lote(d) | {"detalle_tipo": tipo, "detalle_codigo": caso.get("codigo")}
            )
            resultado.append(
                Hallazgo(
                    "comprobacion_fallida",
                    sujeto_,
                    {
                        "comprobacion": {
                            i: textos.obtener(i, f"comprobaciones.{codigo}") for i in textos.IDIOMAS
                        },
                        "caso": _caso_en_idiomas(d, codigo, caso, extra),
                        "codigo_comprobacion": codigo,
                    },
                    _peso_de_caso(d, caso),
                    criterio=CRITERIO_COMPROBACION.get(codigo, 3),
                )
            )
    return resultado


def parcela_cambio_de_estado(d: DatosLote) -> list[Hallazgo]:
    """La parcela pasó por observada después de emitirse el primer DOP de sus tandas en el lote."""
    resultado = []
    for p in d.parcelas_ordenadas():
        emisiones = [d.dop_de_tanda[t.id].emitido_en for t in d.tandas.values() if t.parcela_id == p.id]
        if not emisiones:
            continue
        desde = min(emisiones)
        decisiones = d.decisiones.get(p.id, [])
        observadas = [x for x in decisiones if x.decision == "observar" and x.decidida_en > desde]
        if not observadas:
            continue
        ultima = observadas[-1]
        incumplidos = [
            r["codigo"] for r in (ultima.requisitos or {}).get("requisitos", []) if not r.get("cumple")
        ]
        despues = [x for x in decisiones if x.decision == "habilitar" and x.decidida_en > ultima.decidida_en]
        resultado.append(
            Hallazgo(
                "parcela_cambio_de_estado",
                sujeto("parcela", p.id, p.codigo),
                {
                    "parcela": p.codigo,
                    "fecha": textos.fechas(ultima.decidida_en),
                    "requisitos": {
                        i: textos.lista(i, [textos.obtener(i, "requisitos").get(r, r) for r in incumplidos])
                        or "—"
                        for i in textos.IDIOMAS
                    },
                    "codigos_requisitos": incumplidos,
                    "veces": len(observadas),
                },
                d.peso_parcela[p.id],
                explicacion=despues[0].nota if despues else None,
                criterio=4 if any(r in REQUISITOS_CRITERIO_4 for r in incumplidos) else 1,
            )
        )
    return resultado


def desviacion_fifo(d: DatosLote) -> list[Hallazgo]:
    if not d.lote.desviacion_fifo:
        return []
    return [Hallazgo("desviacion_fifo", _lote(d), {"lote": d.lote.codigo}, None, d.lote.motivo_desviacion)]


# ---------- Siempre presentes ----------


def vinculo_fisico_no_comprobado(d: DatosLote) -> list[Hallazgo]:
    return [Hallazgo("vinculo_fisico_no_comprobado", _lote(d))]


def historial_regional_no_cubierto(d: DatosLote) -> list[Hallazgo]:
    return [Hallazgo("historial_regional_no_cubierto", _lote(d))]


def criterio_no_cubierto(d: DatosLote) -> list[Hallazgo]:
    return [
        Hallazgo(
            "criterio_no_cubierto",
            _lote(d),
            {
                "criterio": {i: textos.obtener(i, f"criterios.{n}") for i in textos.IDIOMAS},
                "criterio_corto": {i: textos.obtener(i, f"criterios_cortos.{n}") for i in textos.IDIOMAS},
                "numero": n,
            },
            criterio=n,
        )
        for n in NO_CUBIERTOS
    ]


REGLAS = (
    comprobacion_fallida,
    parcela_cambio_de_estado,
    desviacion_fifo,
    vinculo_fisico_no_comprobado,
    historial_regional_no_cubierto,
    criterio_no_cubierto,
)
