"""El informe de hallazgos (Parte 9): cinco secciones, en español y en inglés, todas desde plantillas fijas.

No puntúa el lote ni concluye: cuenta hechos, los ata a su origen y dice lo que no se pudo comprobar. El
mensaje final agrupa los hallazgos del mismo código en una sola frase, de mayor a menor peso en el lote, y
termina devolviendo la conclusión al operador.
"""

from collections import Counter
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app import textos, ubigeo
from app.models import Certificacion, ConfiguracionPlataforma
from app.services import lotes as servicio_lotes
from app.services.hallazgos.catalogo import CRITERIOS, GRUPOS, ORDEN, Hallazgo
from app.services.hallazgos.datos import DatosLote

SIN_PESO = Decimal("-1")
SALTO = "\n\n"  # entre párrafos del mensaje final en texto corrido


def ordenar(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    """Por grupo; dentro de cada grupo, de mayor a menor peso en el lote (los que no tienen peso, al final),
    y luego en el orden del catálogo y por el código del sujeto."""
    return sorted(
        hallazgos,
        key=lambda h: (
            GRUPOS.index(h.entrada.grupo),
            -(h.peso if h.peso is not None else SIN_PESO),
            ORDEN[h.codigo],
            h.sujeto.get("codigo") or "",
            h.criterio or 0,
        ),
    )


# ---------- Mensaje final ----------


def _casos_por_comprobacion(idioma: str, lista: list[Hallazgo]) -> list[str]:
    """En el mensaje final, los casos de la recomprobación se resumen por comprobación: su nombre, cuántos
    casos tiene y los códigos de las parcelas, DOP o DPP que nombra. El detalle exacto va en cada hallazgo."""
    grupos: dict[str, list[Hallazgo]] = {}
    for h in lista:
        grupos.setdefault(h.datos["codigo_comprobacion"], []).append(h)
    partes = []
    for casos in grupos.values():
        nombre = textos.en_idioma(idioma, casos[0].datos["comprobacion"])
        codigos = [
            h.sujeto["codigo"]
            for h in casos
            if h.sujeto.get("tipo") in ("parcela", "dop", "dpp") and h.sujeto["codigo"]
        ]
        partes.append(f"{nombre} ({len(casos)})" + (f": {textos.lista(idioma, codigos)}" if codigos else ""))
    return partes


# Hallazgos que dicen cuántos conjuntos de datos registran algo: el mensaje final da la proporción de cada
# parcela.
CON_PROPORCION = ("conjuntos_registran_bosque_2020", "conjuntos_registran_cambio_posterior")


def _frases(idioma: str, hallazgos: list[Hallazgo]) -> list[str]:
    """Una frase por código: nombra los sujetos y suma su peso (cada sujeto cuenta una vez)."""
    por_codigo: dict[str, list[Hallazgo]] = {}
    for h in hallazgos:
        por_codigo.setdefault(h.codigo, []).append(h)
    frases = []
    for codigo, lista in por_codigo.items():
        sujetos: dict[str, Decimal | None] = {}
        for h in lista:
            clave = h.sujeto.get("codigo") or h.sujeto.get("id") or ""
            if clave not in sujetos or (h.peso is not None and sujetos[clave] is None):
                sujetos[clave] = h.peso
        pesos = [p for p in sujetos.values() if p is not None]
        peso = sum(pesos, Decimal("0")) if pesos else None
        nombres = sorted(sujetos, key=lambda s: (-(sujetos[s] if sujetos[s] is not None else SIN_PESO), s))
        if codigo in CON_PROPORCION:
            # "PA-00001 (1 de 13 conjuntos de datos)": la proporción de cada parcela, nunca "algún conjunto".
            de_sujeto = {h.sujeto.get("codigo"): h for h in lista}
            nombres = [
                textos.t(
                    idioma, "comun.proporcion_conjuntos", parcela=s, n=de_sujeto[s].datos["n"],
                    total=de_sujeto[s].datos["total"],
                )
                for s in nombres
            ]
        if codigo == "criterio_no_cubierto":
            nombres = [
                textos.t(idioma, "comun.criterio_citado", criterio=h.datos["criterio_corto"]) for h in lista
            ]
        elif codigo == "comprobacion_fallida":
            nombres = _casos_por_comprobacion(idioma, lista)
        valores: dict[str, Any] = {
            "sujetos": "; ".join(nombres)
            if codigo == "comprobacion_fallida"
            else textos.lista(idioma, nombres),
            "aporta": textos.obtener(
                idioma, "comun.aporta_uno" if len(sujetos) == 1 else "comun.aporta_varios"
            ),
            "peso": textos.numero(peso) if peso is not None else "",
            "n": len(lista),
        }
        if codigo == "analisis_requiere_revision":
            citas: list[str] = []
            for h in lista:
                for c in h.datos["citas_lista"][idioma]:
                    if c not in citas:
                        citas.append(c)
            valores["citas"] = textos.lista(idioma, citas)
        frases.append(
            (
                peso if peso is not None else SIN_PESO,
                ORDEN[codigo],
                textos.t(idioma, f"mensaje.{codigo}", **valores),
            )
        )
    return [f for _, _, f in sorted(frases, key=lambda x: (-x[0], x[1]))]


def _bloque_grupo(idioma: str, grupo: str, hallazgos: list[Hallazgo]) -> dict[str, Any]:
    """El nombre del grupo con su número de hallazgos y una frase por código."""
    del_grupo = [h for h in hallazgos if h.entrada.grupo == grupo]
    titulo = textos.t(
        idioma, "comun.grupo", grupo=textos.obtener(idioma, f"grupos.{grupo}"), n=len(del_grupo)
    )
    frases = _frases(idioma, del_grupo) if del_grupo else [textos.obtener(idioma, "comun.vacio")]
    return {"grupo": grupo, "titulo": titulo, "frases": frases}


def parrafos(bloques: list[dict[str, Any]]) -> list[str]:
    """El mensaje final como texto corrido: un párrafo por bloque."""
    return [" ".join([b["titulo"], *b["frases"]] if b["titulo"] else b["frases"]) for b in bloques]


def _encabezado(idioma: str, d: DatosLote) -> str:
    n_parcelas, n_productores = len(d.parcelas), len(d.productores)
    departamentos = sorted({ubigeo.mostrar(p.departamento) for p in d.parcelas.values() if p.departamento})
    return textos.t(
        idioma,
        "comun.encabezado",
        orden=d.orden.codigo,
        masa=textos.numero(d.masa),
        parcelas=textos.t(
            idioma, "comun.parcela_uno" if n_parcelas == 1 else "comun.parcela_varios", n=n_parcelas
        ),
        productores=textos.t(
            idioma, "comun.productor_uno" if n_productores == 1 else "comun.productor_varios", n=n_productores
        ),
        departamentos=textos.lista(idioma, departamentos),
    )


# ---------- Contexto ----------


def certificaciones_vigentes(d: DatosLote) -> list[Certificacion]:
    return list(
        d.sesion.scalars(
            select(Certificacion)
            .where(
                Certificacion.cooperativa_id == d.cooperativa.id,
                Certificacion.anulada_en.is_(None),
                Certificacion.vigente_desde <= d.hoy,
                Certificacion.vigente_hasta >= d.hoy,
            )
            .order_by(Certificacion.nombre, Certificacion.numero)
        )
    )


def contexto(d: DatosLote) -> dict[str, Any]:
    conf = d.sesion.get(ConfiguracionPlataforma, 1)
    clasificacion = None
    if conf is not None and conf.clasificacion_pais:
        clasificacion = {
            "valor": conf.clasificacion_pais,
            "fecha": conf.clasificacion_fecha.isoformat() if conf.clasificacion_fecha else None,
            "referencia": conf.clasificacion_referencia,
        }
    certificaciones = [
        {
            "nombre": c.nombre,
            "entidad_certificadora": c.entidad_certificadora,
            "numero": c.numero,
            "vigente_desde": c.vigente_desde.isoformat(),
            "vigente_hasta": c.vigente_hasta.isoformat(),
        }
        for c in certificaciones_vigentes(d)
    ]
    texto = {}
    for idioma in textos.IDIOMAS:
        if clasificacion:
            primera = textos.t(
                idioma,
                "comun.clasificacion",
                clasificacion=textos.obtener(idioma, f"clasificaciones.{clasificacion['valor']}"),
                fecha=textos.fecha(idioma, clasificacion["fecha"]),
                # Sin su punto final: la frase ya termina en punto ("2023/1115.." no).
                referencia=(clasificacion["referencia"] or "—").rstrip(" .;:,") or "—",
            )
        else:
            primera = textos.obtener(idioma, "comun.sin_clasificacion")
        if certificaciones:
            segunda = textos.t(
                idioma,
                "comun.certificaciones",
                lista=textos.lista(
                    idioma,
                    [
                        textos.t(
                            idioma,
                            "comun.certificacion",
                            nombre=c["nombre"],
                            entidad=c["entidad_certificadora"],
                            numero=c["numero"],
                            hasta=textos.fecha(idioma, c["vigente_hasta"]),
                        )
                        for c in certificaciones
                    ],
                ),
            )
        else:
            segunda = textos.obtener(idioma, "comun.sin_certificaciones")
        texto[idioma] = f"{primera} {segunda}"
    return {"clasificacion": clasificacion, "certificaciones": certificaciones, "texto": texto}


# ---------- Datos del lote ----------


def datos_lote(d: DatosLote) -> list[dict[str, Any]]:
    indicadores = {i.clave: i.valor for i in servicio_lotes.indicadores(d.sesion, d.lote, d.filas)}
    cantidad = Decimal(d.orden.cantidad_kg)
    cobertura = (d.masa * 100 / cantidad).quantize(Decimal("0.01")) if cantidad else Decimal("0")
    edades = [
        (d.hoy - a.completado_en.date()).days
        for lista in d.completados.values()
        for a in lista
        if a.completado_en is not None
    ]
    conjuntos = [c.conteos["consultados"] for c in d.convergencias.values()]
    tipos = Counter(t.doc_entrega_tipo or "guia_remision" for t in d.tandas.values())
    corridas = indicadores.get("corridas_mezcladas") or {"mezcladas": 0, "corridas": 0}

    def rango(idioma: str, valores: list[int], ruta: str) -> str:
        if not valores:
            return textos.obtener(idioma, "datos_lote.sin_dato")
        return textos.t(idioma, ruta, min=min(valores), max=max(valores))

    filas = [
        ("orden", {i: d.orden.codigo for i in textos.IDIOMAS}),
        ("masa", {i: f"{textos.numero(d.masa)} kg" for i in textos.IDIOMAS}),
        (
            "cobertura_pedido",
            {
                i: textos.t(
                    i,
                    "datos_lote.cobertura_valor",
                    pct=textos.numero(cobertura),
                    cantidad=textos.numero(cantidad),
                )
                for i in textos.IDIOMAS
            },
        ),
        ("parcelas", {i: str(len(d.parcelas)) for i in textos.IDIOMAS}),
        ("productores", {i: str(len(d.productores)) for i in textos.IDIOMAS}),
        (
            "concentracion_mayor",
            {
                i: f"{textos.numero(indicadores.get('concentracion_mayor_parcela_pct', 0))} %"
                for i in textos.IDIOMAS
            },
        ),
        (
            "concentracion_tres",
            {
                i: f"{textos.numero(indicadores.get('concentracion_tres_parcelas_pct', 0))} %"
                for i in textos.IDIOMAS
            },
        ),
        (
            "corridas_mezcladas",
            {i: textos.t(i, "datos_lote.corridas_valor", **corridas) for i in textos.IDIOMAS},
        ),
        ("antiguedad_analisis", {i: rango(i, edades, "datos_lote.dias") for i in textos.IDIOMAS}),
        ("conjuntos_por_parcela", {i: rango(i, conjuntos, "datos_lote.rango") for i in textos.IDIOMAS}),
        (
            "tandas_por_documento",
            {
                i: "; ".join(
                    f"{textos.obtener(i, f'documentos.{tipo}')}: {n}" for tipo, n in sorted(tipos.items())
                )
                or textos.obtener(i, "datos_lote.sin_dato")
                for i in textos.IDIOMAS
            },
        ),
    ]
    return [
        {
            "clave": clave,
            "etiqueta": {i: textos.obtener(i, f"datos_lote.{clave}") for i in textos.IDIOMAS},
            "valor": valor,
        }
        for clave, valor in filas
    ]


# ---------- Informe completo ----------


def armar(d: DatosLote, hallazgos: list[Hallazgo], *, preliminar: bool) -> dict[str, Any]:
    hallazgos = ordenar(hallazgos)
    grupos_mensaje = GRUPOS if preliminar else GRUPOS[1:]
    ctx = contexto(d)
    no_verificados = [h for h in hallazgos if h.entrada.grupo == "no_verificado"]
    hay_revision = any(d.evaluaciones[p].revision is not None for p in d.parcelas)
    mensaje = {}
    no_verificado = {}
    for idioma in textos.IDIOMAS:
        # Estructura fija: encabezado, los grupos con su número de hallazgos, contexto y cierre.
        mensaje[idioma] = [
            {"grupo": None, "titulo": None, "frases": [_encabezado(idioma, d)]},
            *(_bloque_grupo(idioma, g, hallazgos) for g in grupos_mensaje),
            {
                "grupo": None,
                "titulo": textos.obtener(idioma, "comun.contexto"),
                "frases": [ctx["texto"][idioma]],
            },
            {"grupo": None, "titulo": None, "frases": [textos.obtener(idioma, "comun.cierre")]},
        ]
        no_verificado[idioma] = _frases(idioma, no_verificados)
        # Solo si alguna parcela del lote tiene una revisión de imágenes (pedido del equipo del 2026-10-07).
        if hay_revision:
            no_verificado[idioma].append(textos.obtener(idioma, "comun.revision_imagenes_fija"))
    return {
        "preliminar": preliminar,
        "lote": {"id": str(d.lote.id), "codigo": d.lote.codigo, "estado": d.lote.estado},
        "secciones": {i: textos.obtener(i, "secciones") for i in textos.IDIOMAS},
        "grupos": {
            g: {
                "nombre": {i: textos.obtener(i, f"grupos.{g}") for i in textos.IDIOMAS},
                "cantidad": sum(1 for h in hallazgos if h.entrada.grupo == g),
            }
            for g in GRUPOS
        },
        "criterios": {
            str(n): {i: textos.obtener(i, f"criterios.{n}") for i in textos.IDIOMAS} for n in CRITERIOS
        },
        "datos_lote": datos_lote(d),
        "hallazgos": [h.a_dict() for h in hallazgos],
        "no_verificado": no_verificado,
        "contexto": ctx,
        "mensaje": mensaje,
        "mensaje_texto": {i: SALTO.join(parrafos(mensaje[i])) for i in textos.IDIOMAS},
    }
