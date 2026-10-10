"""Ayudas para las pruebas de la Parte 4 y de la adenda 4: fuentes simuladas y registros listos para
habilitar."""

import itertools
import uuid
from datetime import date, datetime, timedelta

import httpx
from geoalchemy2.shape import from_shape, to_shape

from app.fechas import ahora, hoy_lima
from app.models import (
    AnalisisCobertura,
    Documento,
    Parcela,
    ParcelaIncidencia,
    ParcelaVariable,
    Perfil,
    Productor,
    VisitaCampo,
)
from app.services.analisis import huella_parcela
from app.services.fuentes.gfw import GFW
from app.services.fuentes.whisp import Whisp

PDF = b"%PDF-1.7\n% documento legal de prueba\n"
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
_contador = itertools.count(1)


def _no_llamar(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"La prueba no debía llamar a {request.url}")


def fuentes_configuradas(transporte=None) -> dict:
    """Whisp y GFW con clave de prueba. Sin transporte, cualquier llamada real hace fallar la prueba."""
    cliente = httpx.Client(transport=httpx.MockTransport(transporte or _no_llamar))
    return {"whisp": Whisp("clave-prueba", cliente), "gfw": GFW("clave-prueba", cliente)}


def documento_legal(
    sesion,
    parcela: Parcela,
    tipo: str,
    perfil: Perfil,
    *,
    vence: date | None = None,
    emitido: date | None = None,
    cotejado: bool = False,
    clase: str | None = None,
) -> Documento:
    n = next(_contador)
    documento = Documento(
        cooperativa_id=parcela.cooperativa_registro_id,
        entidad="parcela",
        entidad_id=parcela.id,
        tipo=tipo,
        ruta=f"prueba/{parcela.id}/{n}.pdf",
        nombre_original=f"{tipo}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=100,
        sha256=f"{n:064x}",
        subido_por=perfil.id,
        numero=f"N-{n}",
        entidad_emisora="Entidad de prueba",
        fecha_emision=emitido or date(2020, 1, 1),
        fecha_vencimiento=vence,
        cotejado_en=ahora() if cotejado else None,
        cotejado_por=perfil.id if cotejado else None,
        clase=clase,
    )
    sesion.add(documento)
    sesion.flush()
    return documento


# Adenda 4: un perfil legal en el que solo aplica la tenencia.
PERFIL_BASE = {
    "tenencia_tipo": "propietario",
    "en_anp": "no",
    "en_tierra_forestal": "no",
    "en_tierra_comunal": "no",
    "junto_a_cuerpo_de_agua": "no",
    "en_patrimonio_cultural": "no",
    "usa_riego": "no",
    "anio_instalacion_cultivo": "2015",
}


def declarar(sesion, parcela: Parcela, perfil: Perfil, **valores) -> None:
    """Declaraciones vigentes del perfil legal, como si las hubiera hecho `perfil` (sin pasar por la API)."""
    for variable, valor in valores.items():
        for anterior in sesion.query(ParcelaVariable).filter_by(
            parcela_id=parcela.id, variable=variable, origen="declarado", vigente=True
        ):
            anterior.vigente = False
        sesion.flush()
        detalle = None
        if isinstance(valor, tuple):
            valor, detalle = valor
        sesion.add(
            ParcelaVariable(
                parcela_id=parcela.id,
                variable=variable,
                valor=valor,
                detalle=detalle,
                origen="declarado",
                registrada_por=perfil.id,
                registrada_en=ahora(),
            )
        )
    sesion.flush()


def cruce(
    sesion, parcela: Parcela, variable: str, valor: str, detalle: dict | None = None
) -> ParcelaVariable:
    """Un resultado del cruce con una capa oficial."""
    for anterior in sesion.query(ParcelaVariable).filter_by(
        parcela_id=parcela.id, variable=variable, origen="cruce", vigente=True
    ):
        anterior.vigente = False
    sesion.flush()
    fila = ParcelaVariable(
        parcela_id=parcela.id,
        variable=variable,
        valor=valor,
        detalle=detalle or {"capas": []},
        origen="cruce",
        fuente="Capa de prueba. Consultada el 09/10/2026.",
        registrada_en=ahora(),
    )
    sesion.add(fila)
    sesion.flush()
    return fila


def incidencia(sesion, parcela: Parcela, perfil: Perfil, tipo: str = "tenencia") -> ParcelaIncidencia:
    i = ParcelaIncidencia(
        parcela_id=parcela.id,
        tipo=tipo,
        descripcion="Un vecino reclama parte del lindero norte de la parcela ante el juez de paz local.",
        fuente="Juez de paz del caserío",
        registrada_por=perfil.id,
        registrada_en=ahora(),
    )
    sesion.add(i)
    sesion.flush()
    return i


def legalidad_completa(sesion, parcela: Parcela, perfil: Perfil, **valores) -> None:
    """Adenda 4: perfil legal completo (solo aplica la tenencia, salvo `valores`) y título vigente."""
    declarar(sesion, parcela, perfil, **(PERFIL_BASE | valores))
    documento_legal(sesion, parcela, "titulo_sunarp", perfil)


def productor_listo(sesion, productor: Productor, perfil: Perfil) -> None:
    """DNI documentado y consentimiento registrado."""
    n = next(_contador)
    sesion.add(
        Documento(
            cooperativa_id=perfil.cooperativa_id,
            entidad="productor",
            entidad_id=productor.id,
            tipo="dni",
            ruta=f"prueba/dni/{n}.pdf",
            nombre_original="dni.pdf",
            tipo_mime="application/pdf",
            tamano_bytes=100,
            sha256=f"{n + 10**6:064x}",
            subido_por=perfil.id,
        )
    )
    productor.consentimiento_datos_en = ahora()
    productor.consentimiento_origen = "cooperativa"
    sesion.flush()


def analisis_completado(
    sesion,
    parcela: Parcela,
    fuente: str,
    *,
    resultado: str | None = "low",
    indicadores: dict | None = None,
    hace: timedelta = timedelta(days=1),
) -> AnalisisCobertura:
    if indicadores is None:
        indicadores = (
            {"alertas_desde_2021": 0, "perdida_ha_total": 0} if fuente == "gfw" else {"risk_pcrop": resultado}
        )
    momento = ahora() - hace
    analisis = AnalisisCobertura(
        parcela_id=parcela.id,
        cooperativa_id=parcela.cooperativa_registro_id,
        fuente=fuente,
        estado="completado",
        geometria=from_shape(to_shape(parcela.geometria), srid=4326),
        geometria_sha256=huella_parcela(parcela),
        resultado_fuente=resultado if fuente == "whisp" else None,
        indicadores=indicadores,
        version_fuente="prueba",
        solicitado_en=momento,
        completado_en=momento,
        reintentar_en=momento,
        intentos=1,
    )
    sesion.add(analisis)
    sesion.flush()
    return analisis


def visita(
    sesion,
    parcela: Parcela,
    perfil: Perfil,
    *,
    motivo: str = "analisis_requiere_revision",
    perimetro: bool = True,
    fecha: date | None = None,
    creada: datetime | None = None,
) -> VisitaCampo:
    v = VisitaCampo(
        id=uuid.uuid4(),
        parcela_id=parcela.id,
        cooperativa_id=perfil.cooperativa_id,
        fecha=fecha or hoy_lima(),
        realizada_por_nombre="Técnico de prueba",
        realizada_por_cargo="Técnico de campo",
        registrada_por=perfil.id,
        motivo=motivo,
        perimetro_recorrido=perimetro,
        uso_observado="cacao_bajo_sombra",
        descripcion="Cacao bajo sombra de guaba e inga; se recorrió todo el lindero.",
        creado_en=creada or ahora(),
    )
    sesion.add(v)
    sesion.flush()
    return v
