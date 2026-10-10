"""Reglas de la etapa 1 sobre el productor (adenda 5, sección 11), con el estado de hoy, no con lo sellado en
el DOP. Una función por regla.

Su sujeto es de tipo `productor` y se nombra como en la genealogía (nombres y apellidos). Su peso en el lote
es la suma de los pesos de sus parcelas. La explicación es la nota de seguimiento, si la hay. Un productor
sin declaración vigente no genera estos hallazgos: sus parcelas ya están observadas y el lote lo informa por
esa vía. Los textos dicen "el productor declara": nunca afirman el hecho por cuenta del sistema.
"""

from app import textos
from app.catalogos import declaracion_productor as cuestionario
from app.models import DeclaracionProducto, Productor
from app.services.declaracion_productor import EstadoProductor, EstadoRequisito
from app.services.hallazgos.catalogo import Hallazgo, sujeto
from app.services.hallazgos.datos import DatosLote


def _nombre(p: Productor) -> str:
    return f"{p.nombres} {p.apellidos}".strip()


def _con_declaracion(d: DatosLote) -> list[tuple[Productor, EstadoProductor]]:
    resultado = []
    for p in d.productores_ordenados():
        estado = d.declaraciones.get(p.id)
        if estado is not None and estado.valida:
            resultado.append((p, estado))
    return resultado


def _nuevo(
    d: DatosLote, codigo: str, p: Productor, estado: EstadoProductor, referencias: list[str], **datos
) -> Hallazgo:
    # La referencia, el nivel y la diligencia del orientador (sección 11, regla 2).
    requisito = next(
        r.requisito for r in estado.requisitos.values() if referencias[0] in r.requisito.referencias
    )
    return Hallazgo(
        codigo,
        sujeto("productor", p.id, _nombre(p)),
        {
            "productor": _nombre(p),
            "referencias": ", ".join(referencias),
            "nivel_orientador": requisito.nivel,
            "diligencia": requisito.diligencia,
            **datos,
        },
        d.peso_productor(p.id),
        explicacion=estado.vigente.seguimiento_nota,
    )


def _soles(valor) -> str:
    return textos.numero(valor)


def _hecho(idioma: str, pregunta: str, valor, referencia=None) -> str:
    plantilla = textos.obtener(idioma, f"declaracion.hechos.{pregunta}")
    if isinstance(plantilla, dict):
        return plantilla[str(valor)]
    if pregunta == "jornal_soles":
        return plantilla.format(valor=_soles(valor), referencia=_soles(referencia))
    return plantilla.format(valor=f"{valor:g}" if isinstance(valor, int | float) else valor)


def _referencia_de(pregunta: str) -> str:
    return cuestionario.POR_CODIGO[pregunta].referencias[0]


def condiciones_de_trabajo_por_atender(d: DatosLote) -> list[Hallazgo]:
    """Lista cada hecho con su valor declarado, de condiciones_de_trabajo y de igualdad_y_maternidad."""
    resultado = []
    for p, estado in _con_declaracion(d):
        hechos = [
            h
            for codigo in ("condiciones_de_trabajo", "igualdad_y_maternidad")
            if estado.requisitos[codigo].estado == "por_atender"
            for h in estado.requisitos[codigo].hechos
        ]
        if not hechos:
            continue
        referencias = sorted({_referencia_de(h.pregunta) for h in hechos})
        resultado.append(
            _nuevo(
                d,
                "condiciones_de_trabajo_por_atender",
                p,
                estado,
                referencias,
                hechos={
                    i: textos.lista(i, [_hecho(i, h.pregunta, h.valor, h.referencia) for h in hechos])
                    for i in textos.IDIOMAS
                },
                declarados={h.pregunta: h.valor for h in hechos},
            )
        )
    return resultado


def menores_en_la_parcela(d: DatosLote) -> list[Hallazgo]:
    """Si son de la familia o contratados, la edad del más joven y si van a la escuela."""
    resultado = []
    for p, estado in _con_declaracion(d):
        if estado.requisitos["menores_de_edad"].estado != "por_atender":
            continue
        r = estado.vigente.respuestas
        resultado.append(
            _nuevo(
                d,
                "menores_en_la_parcela",
                p,
                estado,
                ["5.2"],
                quienes={i: _hecho(i, "menores_trabajan", r["menores_trabajan"]) for i in textos.IDIOMAS},
                edad=r.get("menor_edad_minima"),
                escuela={
                    i: _hecho(i, "menores_van_a_la_escuela", r.get("menores_van_a_la_escuela"))
                    for i in textos.IDIOMAS
                },
                menores_trabajan=r["menores_trabajan"],
                menores_van_a_la_escuela=r.get("menores_van_a_la_escuela"),
            )
        )
    return resultado


def trabajo_no_libre(d: DatosLote) -> list[Hallazgo]:
    return [
        _nuevo(d, "trabajo_no_libre", p, estado, ["5.3", "5.4"])
        for p, estado in _con_declaracion(d)
        if estado.requisitos["trabajo_libre"].estado == "por_atender"
    ]


def _productos(idioma: str, productos: list[DeclaracionProducto], con_fecha: bool) -> str:
    def uno(x: DeclaracionProducto) -> str:
        tipo = textos.obtener(idioma, f"declaracion.tipos_producto.{x.tipo}")
        if not con_fecha:
            return f"{x.nombre} ({tipo})"
        fecha = textos.fecha(idioma, x.revisado_en)
        return textos.t(idioma, "declaracion.producto_consultado", nombre=x.nombre, tipo=tipo, fecha=fecha)

    return textos.lista(idioma, [uno(x) for x in productos])


def agroquimico_no_figura(d: DatosLote) -> list[Hallazgo]:
    """Lista cuáles y la fecha de consulta."""
    resultado = []
    for p, estado in _con_declaracion(d):
        r: EstadoRequisito = estado.requisitos["agroquimicos"]
        if not r.no_figuran:
            continue
        resultado.append(
            _nuevo(
                d,
                "agroquimico_no_figura",
                p,
                estado,
                ["2.3"],
                productos={i: _productos(i, r.no_figuran, True) for i in textos.IDIOMAS},
                nombres=[x.nombre for x in r.no_figuran],
            )
        )
    return resultado


def envases_por_atender(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p, estado in _con_declaracion(d):
        if estado.requisitos["envases"].estado != "por_atender":
            continue
        destino = estado.vigente.respuestas["destino_envases"]
        resultado.append(
            _nuevo(
                d,
                "envases_por_atender",
                p,
                estado,
                ["2.7"],
                destino={i: _hecho(i, "destino_envases", destino) for i in textos.IDIOMAS},
                destino_envases=destino,
            )
        )
    return resultado


def agroquimicos_sin_revisar(d: DatosLote) -> list[Hallazgo]:
    resultado = []
    for p, estado in _con_declaracion(d):
        r = estado.requisitos["agroquimicos"]
        if not r.sin_revisar:
            continue
        resultado.append(
            _nuevo(
                d,
                "agroquimicos_sin_revisar",
                p,
                estado,
                ["2.3"],
                productos={i: _productos(i, r.sin_revisar, False) for i in textos.IDIOMAS},
                nombres=[x.nombre for x in r.sin_revisar],
            )
        )
    return resultado


def permanentes_sin_relacion(d: DatosLote) -> list[Hallazgo]:
    """Con trabajadores permanentes y sin la relación cargada, aunque el requisito esté por atender."""
    return [
        _nuevo(d, "permanentes_sin_relacion", p, estado, ["4.1"])
        for p, estado in _con_declaracion(d)
        if "relacion_trabajadores" in estado.requisitos["condiciones_de_trabajo"].falta
    ]


def tributos_sin_sustento(d: DatosLote) -> list[Hallazgo]:
    """Dice qué falta, o que el productor no sabe."""
    resultado = []
    for p, estado in _con_declaracion(d):
        r = estado.requisitos["tributos"]
        if r.estado != "sin_sustento":
            continue
        if "ventas_no_sabe" in r.falta:
            falta = textos.ambos("declaracion.tributos_no_sabe")
        else:
            falta = {
                i: textos.t(
                    i,
                    "declaracion.tributos_falta",
                    faltan=textos.lista(i, [textos.obtener(i, f"declaracion.falta.{f}") for f in r.falta]),
                )
                for i in textos.IDIOMAS
            }
        resultado.append(
            _nuevo(d, "tributos_sin_sustento", p, estado, ["7.1"], falta=falta, faltantes=list(r.falta))
        )
    return resultado


REGLAS = (
    condiciones_de_trabajo_por_atender,
    menores_en_la_parcela,
    trabajo_no_libre,
    agroquimico_no_figura,
    envases_por_atender,
    agroquimicos_sin_revisar,
    permanentes_sin_relacion,
    tributos_sin_sustento,
)
