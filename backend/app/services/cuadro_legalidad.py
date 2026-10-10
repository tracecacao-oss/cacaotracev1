"""Cuadro de legalidad por requisito del lote (adenda 7, sección 5).

Toma cada requisito del orientador y cuenta, para un lote, a cuántos sujetos les aplica y en qué estado está
cada uno, con el porcentaje de la masa del lote que aportan. Lo calcula desde lo que ya está cargado, con los
mismos datos que reúne el informe de hallazgos (`hallazgos.datos.DatosLote`), y no repite reglas: lee el
estado de cada requisito de los servicios de las adendas 4 (parcela), 5 (productor) y 6 (organización), y la
declaración aduanera del lote.

No concluye: no tiene fila de totales ni ningún número que resuma el lote, y no califica un estado. Mientras
el lote no está cerrado se calcula al consultarlo, con el estado de hoy ("preliminar"); al emitir el DEX se
sella en su contenido y desde entonces se muestra el sellado.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app import textos
from app.catalogos import cuadro_legalidad as catalogo
from app.catalogos import documentos_embarque, documentos_legales
from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.fechas import ahora
from app.models import Documento, Lote
from app.services import cooperativa as servicio_cooperativa
from app.services import embarque
from app.services.documentos import NOMBRES_TIPO
from app.services.hallazgos.datos import DatosLote

CON_CUADRO = ("armado", "bloqueado", "listo")
CERO = Decimal("0")


def _pct(valor: Decimal) -> str:
    return f"{valor:.2f}"


def _sustento_parcela(estado) -> str:
    if estado.sustento is not None:
        doc = estado.sustento
        nombre = documentos_legales.POR_CODIGO.get(doc.tipo)
        texto = nombre.nombre if nombre else NOMBRES_TIPO.get(doc.tipo, doc.tipo)
        return f"{texto} N.º {doc.numero}" if doc.numero else texto
    if estado.nota:
        return f"Nota: {estado.nota}"
    return estado.motivo


def _sujetos_parcela(d: DatosLote, fila: catalogo.Fila) -> list[dict[str, Any]]:
    salida = []
    for p in d.parcelas_ordenadas():
        leg = d.evaluaciones[p.id].legalidad
        if fila.fuente == "incidencia_ambiental":
            ambientales = [i for i in leg.incidencias if i.tipo == "ambiental"]
            abiertas = [i for i in ambientales if i.estado == "abierta"]
            if not ambientales:
                estado, nivel, sustento = "no_aplica", None, "Sin incidencias ambientales registradas."
            elif abiertas:
                estado, nivel, sustento = (
                    "por_atender",
                    None,
                    f"{len(abiertas)} incidencia(s) ambiental(es) abierta(s).",
                )
            else:
                estado, nivel = "sustentado", "declarado"
                sustento = f"Incidencia cerrada: {ambientales[0].cierre_nota}"
        else:
            r = leg.requisitos[fila.fuente]
            estado, nivel, sustento = r.estado, r.nivel, _sustento_parcela(r)
        salida.append(
            {
                "tipo": "parcela",
                "id": str(p.id),
                "codigo": p.codigo,
                "nombre": p.nombre,
                "estado": estado,
                "nivel": nivel if estado in catalogo.CON_SUSTENTO else None,
                "peso": d.peso_parcela[p.id],
                "sustento": sustento,
            }
        )
    return salida


def _sujetos_productor(d: DatosLote, fila: catalogo.Fila) -> list[dict[str, Any]]:
    salida = []
    for p in d.productores_ordenados():
        estado_productor = d.declaraciones.get(p.id)
        r = estado_productor.requisitos.get(fila.fuente) if estado_productor else None
        if r is None:
            estado, nivel, sustento = "sin_dato", None, "Falta la declaración anual vigente."
        else:
            estado, nivel = r.estado, r.nivel_verificacion
            sustento = (
                ", ".join(NOMBRES_TIPO.get(x.tipo, x.tipo) for x in r.documentos)
                if r.documentos
                else r.motivo
            )
        salida.append(
            {
                "tipo": "productor",
                "id": str(p.id),
                "codigo": None,
                "nombre": f"{p.nombres} {p.apellidos}".strip(),
                "estado": estado,
                "nivel": nivel if estado in catalogo.CON_SUSTENTO else None,
                "peso": d.peso_productor(p.id),
                "sustento": sustento,
            }
        )
    return salida


def _cuenta(sujetos: list[dict[str, Any]], estados: tuple[str, ...]) -> dict[str, Any]:
    elegidos = [s for s in sujetos if s["estado"] in estados]
    return {"n": len(elegidos), "pct": _pct(sum((s["peso"] for s in elegidos), CERO))}


def _fila_con_cuentas(fila: catalogo.Fila, sujetos: list[dict[str, Any]]) -> dict[str, Any]:
    """Sección 5.3: le aplica a, con sustento (y su nivel), por atender y sin sustento. Cada cuenta con el
    porcentaje de la masa del lote que aportan sus sujetos."""
    aplican = [s for s in sujetos if s["estado"] != "no_aplica"]
    con = [s for s in aplican if s["estado"] in catalogo.CON_SUSTENTO]
    return {
        "conteo": True,
        "sujetos_lote": len(sujetos),
        "aplica": {"n": len(aplican), "pct": _pct(sum((s["peso"] for s in aplican), CERO))},
        "con_sustento": {
            **_cuenta(aplican, catalogo.CON_SUSTENTO),
            "niveles": {n: sum(1 for s in con if s["nivel"] == n) for n in catalogo.NIVELES},
        },
        "por_atender": _cuenta(aplican, catalogo.POR_ATENDER),
        "sin_sustento": _cuenta(aplican, catalogo.SIN_SUSTENTO),
        "sujetos": [{**s, "peso": _pct(s["peso"])} for s in sujetos],
    }


def _fila_organizacion(fila: catalogo.Fila, requisitos: dict) -> dict[str, Any]:
    r = requisitos[fila.fuente]
    return {
        "conteo": False,
        "estado": r.estado,
        "nivel": None,
        "falta": list(r.falta),
        "falta_codigos": list(r.falta_codigos),
    }


def _fila_aduanas(d: DatosLote) -> dict[str, Any]:
    declaracion = embarque.vigente(d.sesion, d.lote.id)
    nombre = documentos_embarque.POR_CODIGO["dam"].nombre
    if declaracion is None:
        return {
            "conteo": False,
            "estado": "sin_sustento",
            "nivel": None,
            "falta": [nombre],
            "falta_codigos": ["dam"],
        }
    documento = d.sesion.get(Documento, declaracion.documento_id)
    c = embarque.comparar(d.sesion, declaracion, d.lote)
    return {
        "conteo": False,
        "estado": "sustentado",
        "nivel": "verificado_en_fuente" if documento and documento.cotejado_en else "documentado",
        "falta": [],
        "falta_codigos": [],
        "numero": declaracion.numero,
        "difiere": c.difiere,
    }


def no_se_piden(idioma: str) -> list[dict[str, str]]:
    nombres = textos.obtener(idioma, "cuadro.no_se_piden")
    return [
        {"referencia": ref, "requisito": nombres[ref][0], "motivo": nombres[ref][1]}
        for ref in catalogo.NO_SE_PIDEN
    ]


def calcular(d: DatosLote, *, sellado: bool = False, dex: str | None = None) -> dict[str, Any]:
    """El cuadro de un lote, con las 21 filas y los requisitos que no se piden. Sin totales."""
    requisitos = {r.codigo: r for r in servicio_cooperativa.requisitos(d.sesion, d.cooperativa, d.hoy)}
    filas = []
    for fila in catalogo.FILAS:
        base = {
            "codigo": fila.codigo,
            "nombre": fila.nombre,
            "de": fila.de,
            "referencias": list(fila.referencias),
            "nivel_orientador": fila.nivel,
            "diligencia": fila.diligencia,
            "nivel_texto": fila.nivel_texto,
        }
        if fila.de == "parcela":
            base |= _fila_con_cuentas(fila, _sujetos_parcela(d, fila))
        elif fila.de == "productor":
            base |= _fila_con_cuentas(fila, _sujetos_productor(d, fila))
        elif fila.de == "organizacion":
            base |= _fila_organizacion(fila, requisitos)
        else:
            base |= _fila_aduanas(d)
        filas.append(base)
    return {
        "estado": "sellado" if sellado else "preliminar",
        "calculado_en": ahora().isoformat(),
        "dex": dex,
        "lote": d.lote.codigo,
        "filas": filas,
        "no_se_piden": no_se_piden("es"),
    }


# ---------- Consulta ----------


def _sellado(sesion: Session, lote: Lote) -> dict[str, Any] | None:
    from app.services import dex  # evita importación circular

    vigente = dex.de_lote(sesion, lote.id)
    if vigente is None or vigente.estado != "vigente":
        return None
    return (vigente.contenido or {}).get("legalidad_por_requisito") or {
        "estado": "no_disponible",
        "dex": vigente.codigo,
        "lote": lote.codigo,
        "filas": [],
        "no_se_piden": [],
    }


def cuadro(contexto: Contexto, lote_id: uuid.UUID) -> dict[str, Any]:
    """Sección 5.4: preliminar mientras el lote no está cerrado; el sellado en el DEX desde que lo está. Un
    DEX emitido antes de la adenda 7 no lo trae: responde "no_disponible"."""
    from app.services.hallazgos.datos import cargar  # evita importación circular
    from app.services.lotes import lote_visible

    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id)
    if lote.estado == "cerrado":
        sellado = _sellado(sesion, lote)
        if sellado is not None:
            return sellado
    if lote.estado not in CON_CUADRO:
        raise error_api(
            400,
            "lote_sin_cuadro",
            "El cuadro de legalidad se calcula para un lote armado, bloqueado o listo, y se sella con su "
            "DEX.",
        )
    return calcular(cargar(sesion, lote))


def fila(contexto: Contexto, lote_id: uuid.UUID, codigo: str) -> dict[str, Any]:
    """Los sujetos de una fila, cada uno con su estado, su peso y su sustento."""
    if codigo not in catalogo.POR_CODIGO:
        raise no_encontrado("Esa fila no existe en el cuadro.")
    datos = cuadro(contexto, lote_id)
    encontrada = next((f for f in datos["filas"] if f["codigo"] == codigo), None)
    if encontrada is None:
        raise no_encontrado("Ese cuadro no trae esa fila.")
    return {"estado": datos["estado"], "dex": datos.get("dex"), "lote": datos.get("lote"), "fila": encontrada}
