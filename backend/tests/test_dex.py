"""Parte 9: informe de hallazgos, DEX, certificaciones y clasificación del país."""

import io
import itertools
import json
import re
import uuid
import zipfile
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app import textos
from app.catalogos import capas_legales, documentos_legales, perfil_legal, requisitos_organizacion
from app.fechas import ahora, hoy_lima
from app.models import (
    AnalisisCobertura,
    Auditoria,
    DecisionHabilitacion,
    DecisionTanda,
    Dex,
    Documento,
    Lote,
    OrdenCompra,
    Parcela,
    Productor,
    Superposicion,
)
from app.pdf import dex as pdf_dex
from app.services import hallazgos, sello
from app.services.analisis import huella_parcela
from app.services.fuentes.mapbiomas import MapBiomas
from app.services.hallazgos import acopio
from app.services.hallazgos.catalogo import CATALOGO
from app.storage import ErrorStorage
from tests import factorias
from tests.exportacion_util import tanda_final
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import (
    PDF,
    PERFIL_BASE,
    analisis_completado,
    cruce,
    declarar,
    documento_legal,
    fuentes_configuradas,
    incidencia,
    productor_listo,
)
from tests.imagenes_util import imagen, png, revision
from tests.organizacion_util import DESCRIPCION, RESULTADO, actuacion, dam, diligencia_completa, documento
from tests.proceso_util import calidad, lugar, tanda_validada
from tests.test_analisis import DOCUMENTOS_CON_NOMBRE_PROPIO, PROHIBIDAS
from tests.test_recomprobacion import documento_cooperativa, documento_embarque

NOTA = "Se habilita: expediente completo y análisis de las tres fuentes revisados por la cooperativa."
NOTA_PATRIMONIO = "Hay un muro de piedra antiguo al borde de la parcela; el cultivo no se acerca a él."
NOTA_TANDA = "Liquidación emitida por error a un productor con RUC; se anuló y se reemplazó el mismo día."
EXPLICACION_DPP = "Grano bien fermentado; la balanza se calibró ese mismo día antes de pesar."
MAPBIOMAS = {
    "clase_predominante_2020": "Mosaico de agricultura",
    "bosque_2020_ha": 0.0,
    "cambio_bosque_a_no_bosque_ha": 0.0,
    "ultimo_anio": 2024,
    "pixeles": 11,
    "pocos_pixeles": False,
}
TIPOS_EMBARQUE = ("factura_comercial", "packing_list", "certificado_origen", "certificado_fitosanitario")
ADJETIVOS = re.compile(
    r"\b(grave|leve|preocupante|segur[oa]s?|confiable|serious|minor|worrying|safe|reliable)\b", re.IGNORECASE
)
PROHIBIDAS_EN = re.compile(r"deforestation[- ]free|\bcertified\b|\bapproved\b|\bcompliant\b", re.IGNORECASE)
CALIFICAN = re.compile(r"puntaje|sem[aá]foro|\bscore\b|traffic light", re.IGNORECASE)
_contador = itertools.count(1)


def _no_llamar(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"La prueba no debía llamar a {request.url}")


@pytest.fixture
def fuentes():
    todas = fuentes_configuradas()
    todas["mapbiomas"] = MapBiomas(True, 2015, 2024, httpx.Client(transport=httpx.MockTransport(_no_llamar)))
    return todas


@pytest.fixture
def coop(sesion):
    coop = factorias.cooperativa(sesion, "Coop Exporta", codigo="CEX")
    coop.direccion_postal = "Jr. Lima 123, Tarapoto"
    coop.correo = "exporta@prueba.test"
    coop.representante_nombre = "Representante de Prueba"
    coop.representante_dni = "40000001"
    sesion.flush()
    return coop


@pytest.fixture
def admin(sesion, coop):
    return factorias.perfil(sesion, "admin_cooperativa", coop)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def lector(sesion, coop):
    return factorias.perfil(sesion, "lector", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


@pytest.fixture
def expediente_cooperativa(sesion, coop, admin):
    return {t: documento_cooperativa(sesion, coop, t, admin) for t in documentos_legales.CODIGOS_COOPERATIVA}


# ---------- Armado de escenarios ----------


def _parcela(
    api,
    sesion,
    admin,
    operador,
    productor,
    este,
    *,
    ancho=100,
    alto=100,
    whisp="low",
    gfw=None,
    mapbiomas=None,
    posesion=False,
    perfil=None,
    vence=None,
    cotejados=False,
    preparar=None,
    nota=NOTA,
) -> Parcela:
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(ancho, alto, este_m=este), nombre=f"Parcela {este}"
    )
    assert respuesta.status_code == 201, respuesta.text
    parcela = sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))
    # Adenda 4: el perfil legal (solo aplica la tenencia, salvo `perfil`) y el documento de tenencia.
    tenencia = "constancia_posesion" if posesion else "titulo_sunarp"
    valores = PERFIL_BASE | {"tenencia_tipo": "poseedor" if posesion else "propietario"} | (perfil or {})
    declarar(sesion, parcela, operador, **valores)
    # El cruce con las capas oficiales respondió lo mismo que se declaró.
    for variable in perfil_legal.CRUZABLES:
        capas = [c.codigo for c in capas_legales.CAPAS if c.variable == variable]
        cruce(sesion, parcela, variable, valores[variable], {"capas": capas})
    consultable = documentos_legales.POR_CODIGO[tenencia].registro_consultable
    documento_legal(
        sesion,
        parcela,
        tenencia,
        operador,
        vence=(vence or {}).get(tenencia),
        cotejado=cotejados and consultable,
        emitido=date(2019, 3, 1),
    )
    productor_listo(sesion, productor, operador)
    analisis_completado(sesion, parcela, "whisp", resultado=whisp)
    analisis_completado(
        sesion, parcela, "gfw", indicadores=gfw or {"alertas_desde_2021": 0, "perdida_ha_total": 0}
    )
    analisis_completado(sesion, parcela, "mapbiomas", indicadores=mapbiomas or MAPBIOMAS)
    if preparar:
        preparar(parcela)
    respuesta = api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={"nota": nota})
    assert respuesta.status_code == 200, respuesta.text
    sesion.refresh(parcela)
    return parcela


def _lote(api, sesion, coop, operador, parcelas, *, pesos=None, dop=None, dpp=None, cantidad="300.00"):
    """Un lote armado con una tanda por parcela, todas en una corrida, y una orden de `cantidad` kg."""
    n = next(_contador)
    cancha = lugar(sesion, coop.id, f"Cancha {n}")
    almacen = lugar(sesion, coop.id, f"Almacén {n}", tipo="almacen")
    grado = calidad(sesion, coop.id, f"Grado {n}")
    pesos = pesos or ["600.00", "400.00", "300.00"][: len(parcelas)]
    tandas = [
        tanda_validada(
            sesion,
            operador,
            sesion.get(Productor, p.productor_id),
            p,
            cancha,
            peso=peso,
            contenido=(dop or {}).get(i),
        )
        for i, (p, peso) in enumerate(zip(parcelas, pesos, strict=True))
    ]
    tf = tanda_final(sesion, operador, grado, almacen, tandas, peso="400.00", contenido=dpp)
    api.como(operador)
    importador = api.post(
        "/importadores",
        json={
            "razon_social": "Importadora",
            "direccion": "Calle 1, Hamburgo",
            "pais": "Alemania",
            "correo": "i@x.test",
        },
    ).json()
    orden = api.post(
        "/ordenes",
        json={
            "importador_id": importador["id"],
            "cantidad_kg": cantidad,
            "calidad_id": str(grado.id),
            "pais_destino": "Alemania",
            "lugar_destino": "Hamburgo",
            "fecha_entrega": (hoy_lima() + timedelta(days=60)).isoformat(),
        },
    ).json()
    lote = api.post(f"/ordenes/{orden['id']}/lote").json()
    confirmado = api.post(f"/lotes/{lote['id']}/confirmar", json={})
    assert confirmado.status_code == 200, confirmado.text
    return {"lote": confirmado.json(), "tandas": tandas, "tf": tf, "orden": orden, "importador": importador}


def _listo(api, sesion, datos, perfil):
    lote = datos["lote"]
    for tipo in TIPOS_EMBARQUE:
        documento_embarque(sesion, uuid.UUID(lote["id"]), tipo, perfil)
    respuesta = api.como(perfil).post(f"/lotes/{lote['id']}/recomprobar")
    assert respuesta.status_code == 200 and respuesta.json()["estado_lote"] == "listo", respuesta.text
    return lote


def _informe(api, lote) -> dict:
    respuesta = api.get(f"/lotes/{lote['id']}/hallazgos")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _codigos(informe) -> dict[str, list[dict]]:
    por_codigo: dict[str, list[dict]] = {}
    for h in informe["hallazgos"]:
        por_codigo.setdefault(h["codigo"], []).append(h)
    return por_codigo


@pytest.fixture
def basico(api, sesion, coop, admin, operador, productor, expediente_cooperativa):
    """Lote armado de 300 kg con dos parcelas habilitadas sin alertas."""
    p1 = _parcela(api, sesion, admin, operador, productor, 0)
    p2 = _parcela(api, sesion, admin, operador, productor, 600)
    datos = _lote(api, sesion, coop, operador, [p1, p2])
    return datos | {"parcelas": (p1, p2)}


def _emitir(api, admin, lote):
    return api.como(admin).post(f"/lotes/{lote['id']}/dex", json={"entiendo": True})


# ---------- El escenario con todo ----------


@pytest.fixture
def con_todo(api, sesion, coop, admin, operador, productor, expediente_cooperativa, storage_falso):
    """Un lote armado en el que se disparan casi todas las reglas del catálogo."""
    hoy = hoy_lima()

    def preparar_p1(p):
        p.area_declarada_ha = Decimal("2")  # la calculada es 1 ha: difiere más de 20 %
        sesion.flush()
        anterior = imagen(sesion, p, date(2020, 3, 1))
        reciente = imagen(sesion, p, hoy - timedelta(days=9))
        for fila in (anterior, reciente):
            doc = sesion.get(Documento, fila.documento_natural_id)
            storage_falso.archivos[doc.ruta] = png()
        revision(sesion, p, admin, observacion_cambio="cambio_visible")
        # Adenda 4: lo que el cruce encontró y lo que declaró una persona.
        cruce(
            sesion,
            p,
            "en_anp",
            "zona_de_amortiguamiento",
            {
                "capas": ["sernanp_anp", "sernanp_amortiguamiento"],
                "zonas_de_amortiguamiento": [{"nombre": "Parque de Prueba", "capa": 8}],
                "areas_de_conservacion": [
                    {"nombre": "ACR de Prueba", "categoria": "Área de conservación regional", "capa": 3}
                ],
            },
        )
        cruce(
            sesion,
            p,
            "junto_a_cuerpo_de_agua",
            "si",
            {"capas": ["ign_hidrografia"], "nombre": "Quebrada de Prueba", "distancia_m": 35.0},
        )
        cruce(sesion, p, "en_patrimonio_cultural", "no", {"capas": ["sigda_monumentos"], "monumentos": []})
        declarar(
            sesion,
            p,
            operador,
            en_patrimonio_cultural=("si", {"nota": NOTA_PATRIMONIO}),
            en_tierra_comunal=("si", {"comunidad_nombre": "Comunidad de Prueba", "inscrita": "no_se_sabe"}),
        )
        documento_legal(sesion, p, "constancia_comunal", operador, vence=hoy + timedelta(days=10))

    p1 = _parcela(
        api,
        sesion,
        admin,
        operador,
        productor,
        0,
        whisp="more_info_needed",
        gfw={
            "alertas_desde_2021": 3,
            "perdida_ha_total": 0,
            "bosque_natural_2020_ha": 0.5,
            "alertas_dist_desde_2021": 0,
        },
        perfil={
            "en_anp": "no",
            "en_tierra_forestal": "sin_zonificacion",
            "usa_riego": "si",
            "junto_a_cuerpo_de_agua": "no",
            "en_patrimonio_cultural": "no",
        },
        preparar=preparar_p1,
    )
    excluida = _parcela(api, sesion, admin, operador, productor, 3000)

    def preparar_p2(p):
        # Adenda 4: tierra forestal sustentada por la excepción de la Ley N.º 31973 (constancia de 2019),
        # e incidencia ambiental abierta.
        declarar(sesion, p, operador, reserva_bosque_30="si")
        incidencia(sesion, p, operador, tipo="ambiental")
        gfw = sesion.scalar(
            select(AnalisisCobertura).where(
                AnalisisCobertura.parcela_id == p.id,
                AnalisisCobertura.fuente == "gfw",
                AnalisisCobertura.estado == "completado",
            )
        )
        gfw.es_aproximacion = True
        a, b = sorted([p.id, excluida.id])
        sesion.add(
            Superposicion(
                parcela_a_id=a,
                parcela_b_id=b,
                tipo="poligono_poligono",
                area_ha=Decimal("0.1500"),
                porcentaje=Decimal("1.25"),
                estado="aceptada",
                nota="Lindero compartido revisado con los dos productores en el campo.",
                cerrada_por=admin.id,
                cerrada_en=ahora(),
            )
        )
        sesion.flush()

    p2 = _parcela(
        api,
        sesion,
        admin,
        operador,
        productor,
        600,
        ancho=400,
        alto=300,
        posesion=True,
        perfil={"en_tierra_forestal": "si"},
        mapbiomas=MAPBIOMAS | {"pixeles": 6, "pocos_pixeles": True},
        preparar=preparar_p2,
    )
    excluida.habilitacion_estado = "excluida"
    sesion.flush()
    dop = {
        0: {
            "identificacion": {"misma_persona": True},
            "alertas": {
                "tanda": [
                    "volumen_acumulado_excede_tope",
                    "dias_cosecha_entrega_altos",
                    "peso_difiere_de_guia",
                    "guia_usada_por_otro_productor",
                    "liquidacion_con_productor_con_ruc",
                ],
                "parcela": [],
                "nota": NOTA_TANDA,
            },
            "tanda": {
                "documento_entrega": {
                    "tipo": "liquidacion_compra",
                    "nombre_tipo": "Liquidación de compra",
                    "numero": "L001-123",
                    "fecha_emision": "2026-09-12",
                    "documento_sha256": "ab" * 32,
                    "nivel": "documentado",
                }
            },
        }
    }
    dpp = {
        "rendimiento": {
            "ruta": "completa",
            "entrada_kg": "1000.00",
            "peso_final_kg": "400.00",
            "rendimiento": "0.400",
            "banda_min": "0.30",
            "banda_max": "0.38",
        },
        "alertas": {"alertas": ["rendimiento_sobre_banda"], "explicacion": EXPLICACION_DPP},
        "etapas": [
            {"numero": 4, "nombre": "Fermentación", "desde_plantilla": True},
            {"numero": 5, "desde_plantilla": False},
        ],
    }
    datos = _lote(api, sesion, coop, operador, [p1, p2], dop=dop, dpp=dpp)
    t1 = datos["tandas"][0]
    sesion.add(
        DecisionTanda(
            tanda_id=t1.id,
            decision="observar",
            decidida_por=operador.id,
            decidida_en=ahora() - timedelta(days=6),
            nota="Faltaba la foto del documento de entrega; se cargó y se validó.",
            requisitos={},
        )
    )
    # P1 pasó por observada después de su DOP y se volvió a habilitar.
    for minutos, decision, nota in (
        (60, "observar", "Dejó de cumplir: el expediente legal está incompleto."),
        (
            30,
            "habilitar",
            "Se renovó el documento vencido y se volvió a habilitar la parcela con todo al día.",
        ),
    ):
        sesion.add(
            DecisionHabilitacion(
                parcela_id=p1.id,
                decision=decision,
                decidida_por=None if decision == "observar" else admin.id,
                decidida_en=ahora() - timedelta(minutes=minutos),
                nota=nota,
                requisitos={
                    "requisitos": [{"codigo": "expediente_completo", "cumple": decision == "habilitar"}]
                },
                geometria_sha256=huella_parcela(p1),
            )
        )
    lote = sesion.get(Lote, uuid.UUID(datos["lote"]["id"]))
    lote.desviacion_fifo = True
    lote.motivo_desviacion = "El importador pidió grano de la cosecha de septiembre, no el más antiguo."
    sesion.flush()
    return datos | {"parcelas": (p1, p2)}


ESPERADOS_CON_TODO = {
    "analisis_requiere_revision",
    "area_discrepante",
    "superposicion_aceptada",
    "superposicion_con_excluida",
    "tenencia_solo_posesion",
    "documento_por_vencer",
    "conjuntos_registran_bosque_2020",
    "conjuntos_registran_cambio_posterior",
    "revision_de_imagenes_registrada",
    "habilitada_con_cambio_visible",
    "coordenada_no_recorrida",
    "analisis_por_aproximacion",
    "documento_sin_registro_consultable",
    "documento_sin_cotejar",
    "mapbiomas_pocos_pixeles",
    "mapbiomas_sin_cobertura_reciente",
    "imagen_previa_lejana",
    "sin_imagen_de_alta_resolucion_previa",
    "tanda_observada",
    "volumen_acumulado_excede_tope",
    "dias_cosecha_entrega_altos",
    "peso_difiere_del_documento",
    "documento_usado_por_otro_productor",
    "liquidacion_con_productor_con_ruc",
    "registro_y_validacion_misma_persona",
    "documento_entrega_sin_cotejar",
    "rendimiento_sobre_banda",
    "etapas_desde_plantilla",
    "comprobacion_fallida",
    "parcela_cambio_de_estado",
    "desviacion_fifo",
    "vinculo_fisico_no_comprobado",
    "historial_regional_no_cubierto",
    "criterio_no_cubierto",
    # Adenda 4 (tenencia_sin_documento_formal se prueba aparte: pide una tenencia solo declarada).
    "perfil_declarado_sin_cruce",
    "en_area_de_conservacion",
    "tierra_forestal_por_excepcion",
    "zonificacion_forestal_desconocida",
    "en_area_protegida",
    "comunidad_no_inscrita",
    "riego_sin_licencia",
    "instrumento_ambiental_sin_sustento",
    "junto_a_cuerpo_de_agua",
    "en_patrimonio_cultural",
    "incidencia_registrada",
}
SIEMPRE = {"vinculo_fisico_no_comprobado", "historial_regional_no_cubierto", "criterio_no_cubierto"}


# ---------- Reglas del catálogo ----------


def test_cada_regla_genera_su_hallazgo_con_grupo_etapa_y_criterio(api, operador, con_todo):
    informe = _informe(api.como(operador), con_todo["lote"])
    por_codigo = _codigos(informe)
    assert ESPERADOS_CON_TODO <= set(por_codigo), ESPERADOS_CON_TODO - set(por_codigo)
    for codigo, lista in por_codigo.items():
        entrada = CATALOGO[codigo]
        for h in lista:
            assert h["grupo"] == entrada.grupo and h["etapa"] == entrada.etapa
            if entrada.criterio is not None:
                assert h["criterio"] == entrada.criterio
            assert h["hecho"]["es"] and h["hecho"]["en"] and h["sujeto"]["codigo"]
    p1, p2 = con_todo["parcelas"]
    assert {h["sujeto"]["codigo"] for h in por_codigo["tenencia_solo_posesion"]} == {p2.codigo}
    # La nota de quien decidió va como explicación y el hallazgo sigue presente.
    tandas = {h["codigo"]: h for h in informe["hallazgos"] if h["sujeto"]["tipo"] == "tanda"}
    assert tandas["liquidacion_con_productor_con_ruc"]["explicacion"] == NOTA_TANDA
    assert por_codigo["rendimiento_sobre_banda"][0]["explicacion"] == EXPLICACION_DPP
    assert por_codigo["desviacion_fifo"][0]["explicacion"].startswith("El importador pidió")
    assert por_codigo["superposicion_aceptada"][0]["explicacion"].startswith("Lindero compartido")
    cambio = por_codigo["parcela_cambio_de_estado"][0]
    assert cambio["criterio"] == 4 and cambio["explicacion"].startswith("Se renovó")
    assert '"Whisp: requiere más información"' in por_codigo["analisis_requiere_revision"][0]["hecho"]["es"]
    assert '"Whisp: more_info_needed"' in por_codigo["analisis_requiere_revision"][0]["hecho"]["en"]
    # Uno por cada criterio que el sistema no cubre.
    assert sorted(h["criterio"] for h in por_codigo["criterio_no_cubierto"]) == [8, 9, 10]
    # Las comprobaciones que fallan: un hallazgo por caso (faltan los cuatro documentos de embarque).
    assert len(por_codigo["comprobacion_fallida"]) == 4
    assert informe["preliminar"] is True and informe["grupos"]["impide_cierre"]["cantidad"] == 4
    # Adenda 4: las exenciones y las 10 ha ya no generan hallazgos; los de requisito citan al orientador.
    assert "exencion_declarada" not in por_codigo and "diez_hectareas_o_mas" not in por_codigo
    riego = por_codigo["riego_sin_licencia"][0]
    assert (riego["datos"]["referencias"], riego["datos"]["diligencia"]) == ("2.4", "aligerada")
    assert riego["criterio"] == 11
    assert {h["criterio"] for h in por_codigo["incidencia_registrada"]} == {11}
    excepcion = por_codigo["tierra_forestal_por_excepcion"][0]
    assert excepcion["sujeto"]["codigo"] == p2.codigo and "sí" in excepcion["hecho"]["es"]
    agua = por_codigo["junto_a_cuerpo_de_agua"][0]["hecho"]["es"]
    assert "Quebrada de Prueba" in agua and "según la capa" in agua
    assert por_codigo["en_patrimonio_cultural"][0]["explicacion"] == NOTA_PATRIMONIO
    # Ya no hay un hallazgo por conjuntos que responden distinto.
    assert "conjuntos_discrepan" not in por_codigo
    # Siempre la proporción, nunca "algún conjunto".
    bosque = por_codigo["conjuntos_registran_bosque_2020"][0]
    assert re.match(rf"En {p1.codigo}, 1 de \d+ conjuntos de datos registra bosque", bosque["hecho"]["es"])
    texto = informe["mensaje_texto"]["es"]
    assert re.search(rf"{p1.codigo} \(1 de \d+ conjuntos de datos\)", texto), texto
    assert re.search(rf"{p1.codigo} \(1 of \d+ datasets\)", informe["mensaje_texto"]["en"])
    assert "algún" not in texto and "algun" not in texto
    # Una parcela del lote tiene revisión de imágenes: la frase sobre esa revisión aparece una vez.
    revision = [f for f in informe["no_verificado"]["es"] if f.startswith("La revisión de imágenes")]
    assert len(revision) == 1


def test_las_reglas_no_se_disparan_en_un_lote_sin_novedades(
    api, sesion, coop, admin, operador, productor, expediente_cooperativa
):
    def visitar(p):
        from tests.habilitacion_util import visita

        visita(sesion, p, operador)

    parcelas = [
        _parcela(api, sesion, admin, operador, productor, este, cotejados=True, preparar=visitar)
        for este in (0, 600)
    ]
    datos = _lote(api, sesion, coop, operador, parcelas)
    lote = _listo(api, sesion, datos, operador)
    # Adenda 6: la organización tiene su política y sus actuaciones, y el lote su declaración aduanera.
    diligencia_completa(sesion, coop, admin)
    dam(sesion, uuid.UUID(lote["id"]), operador)
    informe = _informe(api, lote)
    presentes = set(_codigos(informe))
    assert presentes == SIEMPRE | {"mapbiomas_sin_cobertura_reciente"}
    assert informe["grupos"]["impide_cierre"]["cantidad"] == 0


def test_tenencia_sin_documento_formal(api, sesion, coop, admin, operador, productor, expediente_cooperativa):
    def solo_declaracion(p):
        sesion.query(Documento).filter_by(entidad_id=p.id, tipo="constancia_posesion").delete()
        documento_legal(sesion, p, "declaracion_jurada_tenencia", operador, emitido=hoy_lima())

    parcela = _parcela(api, sesion, admin, operador, productor, 0, posesion=True, preparar=solo_declaracion)
    datos = _lote(api, sesion, coop, operador, [parcela])
    hallazgo = _codigos(_informe(api, datos["lote"]))["tenencia_sin_documento_formal"][0]
    assert (hallazgo["grupo"], hallazgo["criterio"]) == ("no_verificado", 4)
    assert hallazgo["datos"]["referencias"] == "1.1, 1.2"
    assert "declaración jurada" in hallazgo["hecho"]["es"] and "sworn statement" in hallazgo["hecho"]["en"]


def test_reglas_de_rendimiento_bajo_banda_y_peso_final(api, sesion, operador, basico):
    lote = sesion.get(Lote, uuid.UUID(basico["lote"]["id"]))
    d = hallazgos.reunir(sesion, lote, [])
    assert acopio.rendimiento_bajo_banda(d) == [] and acopio.peso_final_supera_entrada(d) == []
    dpp = next(iter(d.dpps.values()))
    for codigo, rend in (
        ("rendimiento_bajo_banda", {"rendimiento": "0.250", "banda_min": "0.30", "banda_max": "0.38"}),
        ("peso_final_supera_entrada", {"entrada_kg": "400.00", "peso_final_kg": "420.00"}),
    ):
        falso = SimpleNamespace(
            id=dpp.id,
            codigo=dpp.codigo,
            corrida_id=dpp.corrida_id,
            tanda_final_id=dpp.tanda_final_id,
            contenido={"rendimiento": rend, "alertas": {"alertas": [codigo], "explicacion": "Explicación."}},
        )
        d.dpps = {dpp.id: falso}
        generados = getattr(acopio, codigo)(d)
        assert [h.codigo for h in generados] == [codigo]
        assert generados[0].a_dict()["grupo"] == CATALOGO[codigo].grupo


# ---------- Informe ----------


def test_un_hallazgo_por_parcela_y_una_frase_en_el_mensaje(
    api, sesion, coop, admin, operador, productor, expediente_cooperativa
):
    parcelas = [_parcela(api, sesion, admin, operador, productor, este, posesion=True) for este in (0, 600)]
    datos = _lote(api, sesion, coop, operador, parcelas)
    informe = _informe(api, datos["lote"])
    posesion = _codigos(informe)["tenencia_solo_posesion"]
    assert len(posesion) == 2
    frases = [f for b in informe["mensaje"]["es"] for f in b["frases"] if "constancia de posesión" in f]
    assert len(frases) == 1
    texto = frases[0]
    assert texto.count("se apoya solo en una constancia de posesión") == 1
    assert parcelas[0].codigo in texto and parcelas[1].codigo in texto and "100.00 % del lote" in texto


def test_pesos_suman_100_y_el_informe_es_identico_dos_veces(
    api, sesion, coop, admin, operador, productor, expediente_cooperativa
):
    parcelas = [_parcela(api, sesion, admin, operador, productor, este) for este in (0, 600, 1200)]
    datos = _lote(api, sesion, coop, operador, parcelas, pesos=["333.00", "333.00", "334.00"])
    uno, dos = _informe(api, datos["lote"]), _informe(api, datos["lote"])
    assert uno["mensaje"] == dos["mensaje"]
    assert [h["hecho"] for h in uno["hallazgos"]] == [h["hecho"] for h in dos["hallazgos"]]
    pesos = {
        h["sujeto"]["id"]: Decimal(h["peso_en_lote_pct"])
        for h in uno["hallazgos"]
        if h["sujeto"]["tipo"] == "parcela" and h["peso_en_lote_pct"]
    }
    assert len(pesos) == 3 and sum(pesos.values()) == Decimal("100")
    # Dentro de cada grupo, de mayor a menor peso.
    for grupo in ("requiere_atencion", "no_verificado"):
        valores = [
            Decimal(h["peso_en_lote_pct"]) if h["peso_en_lote_pct"] else Decimal(-1)
            for h in uno["hallazgos"]
            if h["grupo"] == grupo
        ]
        assert valores == sorted(valores, reverse=True)


def test_mensaje_final_y_secciones(api, operador, basico):
    informe = _informe(api.como(operador), basico["lote"])
    es, en = informe["mensaje"]["es"], informe["mensaje"]["en"]
    assert es[0]["frases"][0].startswith(
        f"Orden {basico['orden']['codigo']} · 300.00 kg de cacao en grano seco · 2 parcelas"
    )
    assert es[1]["titulo"] == "Impide el cierre del lote — 4."
    assert es[2]["titulo"].startswith("Requiere atención — ")
    assert es[3]["titulo"].startswith("No verificado — ")
    assert es[4]["titulo"] == "Contexto." and es[4]["frases"] == [
        "Clasificación del país no registrada. La cooperativa no registra certificaciones vigentes."
    ]
    assert es[-1]["frases"] == ["La evaluación de riesgo y su conclusión corresponden al operador."]
    assert en[-1]["frases"] == ["The risk assessment and its conclusion are the operator's responsibility."]
    assert [b["grupo"] for b in es] == [b["grupo"] for b in en]
    assert informe["mensaje_texto"]["es"].endswith(
        "La evaluación de riesgo y su conclusión corresponden al operador."
    )
    criterios = next(f for f in es[3]["frases"] if f.startswith("Los criterios"))
    assert (
        criterios.index("pueblos indígenas") < criterios.index("reclamaciones") < criterios.index("expertos")
    )
    # Ninguna parcela del lote tiene revisión de imágenes: la frase sobre esa revisión no aparece.
    assert not any(f.startswith("La revisión de imágenes") for f in informe["no_verificado"]["es"])
    claves = [f["clave"] for f in informe["datos_lote"]]
    assert {"orden", "masa", "cobertura_pedido", "conjuntos_por_parcela", "tandas_por_documento"} <= set(
        claves
    )
    # Adenda 4: el tema 11, otra información sobre la legalidad de la producción.
    assert sorted(informe["criterios"]) == sorted(str(n) for n in range(1, 12))


def test_lote_bloqueado_muestra_el_caso_exacto(api, sesion, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    p1 = basico["parcelas"][0]
    titulo = sesion.scalar(
        select(Documento).where(Documento.entidad_id == p1.id, Documento.tipo == "titulo_sunarp")
    )
    titulo.fecha_vencimiento = hoy_lima() - timedelta(days=1)
    sesion.flush()
    assert api.post(f"/lotes/{lote['id']}/recomprobar").json()["estado_lote"] == "bloqueado"
    informe = _informe(api, lote)
    casos = [h for h in informe["hallazgos"] if h["grupo"] == "impide_cierre"]
    assert casos and all(h["codigo"] == "comprobacion_fallida" for h in casos)
    assert any(p1.codigo in h["hecho"]["es"] and "observada" in h["hecho"]["es"] for h in casos)
    assert informe["mensaje"]["es"][1]["titulo"].startswith("Impide el cierre del lote — ")


def test_textos_con_las_mismas_claves_y_sin_valoraciones():
    es, en = textos.cargar("es"), textos.cargar("en")

    def forma(valor):
        if isinstance(valor, dict):
            return {k: forma(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return len(valor)
        return None

    assert forma(es) == forma(en)

    def cadenas(valor):
        if isinstance(valor, dict):
            for v in valor.values():
                yield from cadenas(v)
        elif isinstance(valor, list):
            for v in valor:
                yield from cadenas(v)
        elif isinstance(valor, str):
            yield valor

    for idioma in (es, en):
        for cadena in cadenas(idioma):
            limpia = cadena
            for nombre in DOCUMENTOS_CON_NOMBRE_PROPIO:
                limpia = limpia.replace(nombre, "")
            assert not ADJETIVOS.search(limpia), cadena
            assert not PROHIBIDAS.search(limpia), cadena
            assert not PROHIBIDAS_EN.search(limpia), cadena
            assert not CALIFICAN.search(limpia), cadena
    # Las plantillas de hallazgos y del mensaje cubren todo el catálogo.
    assert set(es["hallazgo"]) == set(CATALOGO) == set(es["mensaje"])


# ---------- Emisión ----------


def test_emision_completa(api, sesion, admin, operador, basico, storage_falso):
    lote = _listo(api, sesion, basico, operador)
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 201, respuesta.text
    dex = respuesta.json()
    assert dex["estado"] == "vigente" and re.fullmatch(r"DEX-CEX-\d{4}-\d{6}", dex["codigo"])
    assert sesion.get(Lote, uuid.UUID(lote["id"])).estado == "cerrado"
    assert sesion.get(OrdenCompra, uuid.UUID(basico["orden"]["id"])).estado == "cerrada"
    detalle = api.get(f"/lotes/{lote['id']}").json()
    assert detalle["estado"] == "cerrado" and detalle["dex"]["codigo"] == dex["codigo"]
    # Seis archivos y el paquete guardados.
    archivos = {a["clave"] for a in dex["archivos"]}
    assert archivos == {"pdf_es", "pdf_en", "geojson", "anexo_ii", "hallazgos", "leeme", "paquete"}
    # Adenda 4: el respaldo de cada parcela trae su legalidad por requisito, con las seis capas consultadas.
    sellado = sesion.get(Dex, uuid.UUID(dex["id"])).contenido
    # Adenda 5: versión 3, con el bloque de las declaraciones de los productores.
    assert sellado["version"] == 4
    assert [x["estado"] for x in sellado["productores"]] == ["vigente"] * len(sellado["productores"])
    for respaldo in sellado["respaldo"]:
        leg = respaldo["legalidad"]
        tenencia = next(r for r in leg["requisitos"] if r["codigo"] == "tenencia")
        assert (tenencia["estado"], tenencia["documento"]["tipo"]) == ("sustentado", "titulo_sunarp")
        assert tenencia["referencias"] == ["1.1", "1.2"]
        assert len(leg["capas"]) == 6 and "no es jurídicamente vinculante" in leg["aviso_orientador"]
        assert "expediente" not in respaldo
    docs = list(sesion.scalars(select(Documento).where(Documento.entidad == "dex")))
    assert len(docs) == 7 and all(d.ruta in storage_falso.archivos for d in docs)
    paquete = next(d for d in docs if d.tipo == "dex_paquete")
    with zipfile.ZipFile(io.BytesIO(storage_falso.archivos[paquete.ruta])) as zz:
        nombres = set(zz.namelist())
        contenidos = {n: zz.read(n) for n in nombres}
    codigo = dex["codigo"]
    assert nombres == {
        f"{codigo}-es.pdf",
        f"{codigo}-en.pdf",
        "parcelas.geojson",
        "anexo_ii.json",
        "hallazgos.json",
        "LEEME.txt",
    }
    assert contenidos[f"{codigo}-es.pdf"].startswith(b"%PDF") and contenidos[f"{codigo}-en.pdf"].startswith(
        b"%PDF"
    )
    # GeoJSON: FeatureCollection con una geometría por parcela, al menos 6 decimales y sin datos personales.
    texto_geo = contenidos["parcelas.geojson"].decode("utf-8")
    geo = json.loads(texto_geo)
    assert geo["type"] == "FeatureCollection" and len(geo["features"]) == 2
    codigos = {p.codigo for p in basico["parcelas"]}
    for f in geo["features"]:
        assert f["type"] == "Feature" and f["geometry"]["type"] == "Polygon"
        assert f["properties"] == {
            "ProductionPlace": f["properties"]["ProductionPlace"],
            "ProducerCountry": "PE",
        }
        assert f["properties"]["ProductionPlace"] in codigos
    assert all(len(n.split(".")[1]) >= 6 for n in re.findall(r"-?\d+\.\d+", texto_geo))
    productor = sesion.get(Productor, basico["parcelas"][0].productor_id)
    assert productor.dni not in texto_geo and productor.nombres not in texto_geo
    # Anexo II: afirmación de riesgo y firma vacías, con su nota.
    anexo = json.loads(contenidos["anexo_ii.json"])
    campos = {c["punto"]: c for c in anexo["campos"]}
    assert [c["punto"] for c in anexo["campos"]] == [1, 2, 3, 4, 5, 6]
    assert campos[5]["valor"] is None and campos[5]["nota"]["es"] == "corresponde al operador"
    assert set(campos[6]["valor"].values()) == {None} and campos[6]["nota"]["es"] == "corresponde al operador"
    assert (
        campos[1]["nota"]["es"] == "a confirmar por el operador"
        and campos[1]["valor"]["nombre"] == "Importadora"
    )
    assert campos[2]["valor"]["codigo_sistema_armonizado"] == "1801"
    assert campos[2]["valor"]["nombre_cientifico"] == "Theobroma cacao L."
    # Informe sellado: el grupo que impide el cierre está vacío.
    informe = json.loads(contenidos["hallazgos.json"])["informe"]
    assert informe["preliminar"] is False and informe["grupos"]["impide_cierre"]["cantidad"] == 0
    assert not informe["mensaje"]["es"][1]["titulo"].startswith("Impide")
    leeme = contenidos["LEEME.txt"].decode("utf-8")
    assert codigo in leeme and dex["contenido_sha256"] in leeme and f"#/verificar/dex/{codigo}" in leeme
    # Contenido sellado sin DNI, teléfono ni dirección del productor.
    sellado = json.dumps(sesion.get(Dex, uuid.UUID(dex["id"])).contenido, ensure_ascii=False)
    assert productor.dni not in sellado
    for dato in (productor.telefono, productor.direccion_postal):
        assert not dato or dato not in sellado
    assert f"{productor.nombres} {productor.apellidos}" in sellado
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert "dex.emitir" in acciones
    # Tras el DEX, el lote no cambia ni sus documentos de embarque se anulan.
    embarque = sesion.scalar(
        select(Documento).where(Documento.entidad == "lote", Documento.entidad_id == uuid.UUID(lote["id"]))
    )
    respuesta = api.como(admin).post(
        f"/documentos/{embarque.id}/anular", json={"motivo": "Se cargó otra factura."}
    )
    assert respuesta.status_code == 400
    assert api.post(f"/lotes/{lote['id']}/anular", json={"motivo": "Ya no se exporta."}).status_code == 400


def test_permisos_y_validaciones_al_emitir(api, sesion, admin, operador, lector, basico):
    lote = basico["lote"]
    assert _emitir(api, admin, lote).status_code == 400  # armado
    lote = _listo(api, sesion, basico, operador)
    assert api.como(operador).post(f"/lotes/{lote['id']}/dex", json={"entiendo": True}).status_code == 403
    assert api.como(lector).post(f"/lotes/{lote['id']}/dex", json={"entiendo": True}).status_code == 403
    api.como(admin)
    assert api.post(f"/lotes/{lote['id']}/dex", json={"entiendo": False}).status_code == 422
    assert api.post(f"/lotes/{lote['id']}/dex", json={}).status_code == 422
    assert sesion.scalar(select(func.count()).select_from(Dex)) == 0


def test_parcela_observada_un_minuto_antes_bloquea(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    p1 = basico["parcelas"][0]
    titulo = sesion.scalar(
        select(Documento).where(Documento.entidad_id == p1.id, Documento.tipo == "titulo_sunarp")
    )
    titulo.fecha_vencimiento = hoy_lima() - timedelta(days=1)
    sesion.flush()
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "lote_bloqueado"
    assert sesion.get(Lote, uuid.UUID(lote["id"])).estado == "bloqueado"
    assert sesion.scalar(select(func.count()).select_from(Dex)) == 0
    # Un lote bloqueado tampoco recibe DEX.
    assert _emitir(api, admin, lote).status_code == 400


def test_si_falla_un_archivo_nada_cambia(api, sesion, admin, operador, basico, storage_falso, monkeypatch):
    lote = _listo(api, sesion, basico, operador)
    subir = storage_falso.subir
    llamadas = []

    def falla_al_tercero(ruta, contenido, tipo_mime):
        llamadas.append(ruta)
        if len(llamadas) == 3:
            raise ErrorStorage("sin espacio")
        subir(ruta, contenido, tipo_mime)

    monkeypatch.setattr(storage_falso, "subir", falla_al_tercero)
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 503
    assert sesion.scalar(select(func.count()).select_from(Dex)) == 0
    assert sesion.get(Lote, uuid.UUID(lote["id"])).estado == "listo"
    assert sesion.get(OrdenCompra, uuid.UUID(basico["orden"]["id"])).estado == "con_lote"
    assert all(r in storage_falso.borrados for r in llamadas[:2])
    assert not any("/dex/" in r for r in storage_falso.archivos)


def test_dex_sellado_no_cambia(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    dex = _emitir(api, admin, lote).json()
    antes = api.get(f"/dex/{dex['id']}").json()
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("UPDATE dex SET contenido = '{}'::jsonb WHERE id = :id"), {"id": dex["id"]})
    p1 = basico["parcelas"][0]
    p1.nombre = "Otro nombre"
    sesion.get(Productor, p1.productor_id).nombres = "Otro"
    sesion.flush()
    despues = api.get(f"/dex/{dex['id']}").json()
    assert (
        despues["contenido"] == antes["contenido"]
        and despues["contenido_sha256"] == antes["contenido_sha256"]
    )


def test_anular_y_volver_a_emitir(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    primero = _emitir(api, admin, lote).json()
    motivo = {"motivo": "El importador cambió el puerto de destino."}
    assert api.como(operador).post(f"/dex/{primero['id']}/anular", json=motivo).status_code == 403
    anulado = api.como(admin).post(f"/dex/{primero['id']}/anular", json=motivo)
    assert anulado.status_code == 200 and anulado.json()["estado"] == "anulado"
    assert sesion.get(Lote, uuid.UUID(lote["id"])).estado == "armado"
    assert sesion.get(OrdenCompra, uuid.UUID(basico["orden"]["id"])).estado == "con_lote"
    publico = api.get(f"/publico/dex/{primero['codigo']}").json()
    assert publico["estado"] == "anulado"
    assert api.post(f"/dex/{primero['id']}/anular", json=motivo).status_code == 400
    # Para emitir de nuevo hay que recomprobar; la nueva emisión recibe un código nuevo.
    assert _emitir(api, admin, lote).status_code == 400
    assert api.post(f"/lotes/{lote['id']}/recomprobar").json()["estado_lote"] == "listo"
    segundo = _emitir(api, admin, lote)
    assert segundo.status_code == 201 and segundo.json()["codigo"] != primero["codigo"]
    viejo = api.get(f"/dex/{primero['id']}").json()
    assert viejo["estado"] == "anulado" and viejo["contenido"] and viejo["archivos"]
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert "dex.anular" in acciones
    lista = api.get("/dex").json()
    assert {x["codigo"] for x in lista} == {primero["codigo"], segundo.json()["codigo"]}
    assert [x["codigo"] for x in api.get("/dex", params={"estado": "anulado"}).json()] == [primero["codigo"]]


def test_verificacion_publica_sin_token(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    dex = _emitir(api, admin, lote).json()
    api.headers.pop("Authorization", None)
    respuesta = api.get(f"/publico/dex/{dex['codigo'].lower()}")
    assert respuesta.status_code == 200
    publicos = {"codigo", "estado", "emitido_en", "contenido_sha256", "cooperativa", "es_demo", "agregado"}
    assert set(respuesta.json()) == publicos
    assert (
        respuesta.json()["estado"] == "vigente"
        and respuesta.json()["contenido_sha256"] == dex["contenido_sha256"]
    )
    assert api.get("/publico/dex/DEX-XXX-2026-000999").status_code == 404


def test_descargas(api, sesion, admin, operador, lector, basico):
    lote = _listo(api, sesion, basico, operador)
    dex = _emitir(api, admin, lote).json()
    assert api.como(lector).get(f"/dex/{dex['id']}/descargas").status_code == 403
    respuesta = api.como(operador).get(f"/dex/{dex['id']}/descargas")
    assert respuesta.status_code == 200
    urls = respuesta.json()
    assert [u["clave"] for u in urls][0] == "paquete" and len(urls) == 7
    assert all("vence=300" in u["url"] for u in urls)
    assert api.como(lector).get(f"/dex/{dex['id']}").status_code == 200
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert "dex.descargar" in acciones


def test_dex_con_imagenes_y_notas_en_los_dos_idiomas(api, sesion, admin, operador, con_todo):
    lote = _listo(api, sesion, con_todo, operador)
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 201, respuesta.text
    dex = respuesta.json()
    contenido = dex["contenido"]
    assert any("imagenes" in r for r in contenido["respaldo"])
    url = dex["url_verificacion"]
    es = " ".join(pdf_dex.documento(contenido, dex["contenido_sha256"], url, "es").textos)
    en = " ".join(pdf_dex.documento(contenido, dex["contenido_sha256"], url, "en").textos)
    # Lo que escribió una persona aparece en español bajo "Original text in Spanish".
    assert f"Original text in Spanish: {NOTA_TANDA}" in en and NOTA_TANDA in es
    assert "Original text in Spanish" not in es
    for texto in (es, en):
        limpio = texto
        for nombre in DOCUMENTOS_CON_NOMBRE_PROPIO:
            limpio = limpio.replace(nombre, "")
        assert (
            not PROHIBIDAS.search(limpio)
            and not PROHIBIDAS_EN.search(limpio)
            and not CALIFICAN.search(limpio)
        )
    for bloque in contenido["informe"]["mensaje"]["es"]:
        for frase in bloque["frases"]:
            assert frase in es
    # Mismas cifras en los dos idiomas.
    for numero in re.findall(r"\d+\.\d{2} %", contenido["informe"]["mensaje_texto"]["es"]):
        assert numero in en
    for nombre, datos in (
        ("anexo_ii", contenido),
        ("hallazgos", contenido["informe"]),
    ):
        texto = json.dumps(datos, ensure_ascii=False)
        assert not CALIFICAN.search(texto), nombre


# ---------- Contexto: clasificación del país y certificaciones ----------


def test_clasificacion_del_pais(api, sesion, admin, operador, basico):
    superadmin = factorias.perfil(sesion, "superadmin")
    assert api.como(admin).get("/admin/configuracion").status_code == 403
    assert api.como(admin).put("/admin/configuracion", json={"clasificacion_pais": "bajo"}).status_code == 403
    api.como(superadmin)
    assert api.get("/admin/configuracion").json()["clasificacion_pais"] is None
    incompleta = api.put("/admin/configuracion", json={"clasificacion_pais": "estandar"})
    assert incompleta.status_code == 422
    datos = {
        "clasificacion_pais": "estandar",
        "clasificacion_fecha": "2026-10-03",
        # Con su punto final: el informe no lo duplica al cerrar la frase.
        "clasificacion_referencia": "Reglamento de Ejecución de la Comisión (publicación de prueba).",
    }
    respuesta = api.put("/admin/configuracion", json=datos)
    assert respuesta.status_code == 200 and respuesta.json()["clasificacion_pais"] == "estandar"
    informe = _informe(api.como(operador), basico["lote"])
    assert informe["contexto"]["texto"]["es"].startswith(
        "Perú figura como riesgo estándar en la clasificación registrada el 3 de octubre de 2026"
    )
    assert informe["contexto"]["texto"]["en"].startswith("Peru is listed as standard risk")
    for idioma in ("es", "en"):
        assert "prueba)." in informe["contexto"]["texto"][idioma]
        assert ".." not in informe["contexto"]["texto"][idioma]
    auditoria = sesion.scalar(select(Auditoria).where(Auditoria.accion == "plataforma.configurar"))
    assert auditoria is not None and auditoria.cooperativa_id is None


def test_certificaciones(api, sesion, admin, operador, lector, basico):
    formulario = {
        "nombre": "Orgánico de prueba",
        "entidad_certificadora": "Certificadora de prueba",
        "numero": "ORG-001",
        "vigente_desde": (hoy_lima() - timedelta(days=30)).isoformat(),
        "vigente_hasta": (hoy_lima() + timedelta(days=300)).isoformat(),
    }
    archivo = {"archivo": ("certificacion.pdf", PDF, "application/pdf")}
    assert api.como(operador).post("/certificaciones", data=formulario, files=archivo).status_code == 403
    respuesta = api.como(admin).post("/certificaciones", data=formulario, files=archivo)
    assert respuesta.status_code == 201, respuesta.text
    cert = respuesta.json()
    assert cert["estado"] == "vigente" and cert["documento_id"]
    malo = formulario | {"vigente_hasta": "2020-01-01"}
    assert api.post("/certificaciones", data=malo, files=archivo).status_code == 422
    assert [c["id"] for c in api.como(lector).get("/certificaciones").json()] == [cert["id"]]
    informe = _informe(api.como(operador), basico["lote"])
    assert "Orgánico de prueba (Certificadora de prueba, n.º ORG-001" in informe["contexto"]["texto"]["es"]
    editada = api.como(admin).patch(f"/certificaciones/{cert['id']}", json={"numero": "ORG-002"})
    assert editada.status_code == 200 and editada.json()["numero"] == "ORG-002"
    assert (
        api.patch(f"/certificaciones/{cert['id']}", json={"anular": True, "motivo": "corto"}).status_code
        == 422
    )
    anulada = api.patch(
        f"/certificaciones/{cert['id']}", json={"anular": True, "motivo": "La certificadora la retiró."}
    )
    assert anulada.status_code == 200 and anulada.json()["estado"] == "anulada"
    assert api.patch(f"/certificaciones/{cert['id']}", json={"numero": "ORG-003"}).status_code == 400
    informe = _informe(api.como(operador), basico["lote"])
    assert "no registra certificaciones vigentes" in informe["contexto"]["texto"]["es"]
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert "certificacion.registrar" in acciones and acciones.count("certificacion.editar") == 2


def test_geojson_preliminar(api, operador, basico):
    respuesta = api.como(operador).get(f"/lotes/{basico['lote']['id']}/geojson")
    assert respuesta.status_code == 200 and respuesta.headers["content-type"].startswith(
        "application/geo+json"
    )
    geo = respuesta.json()
    assert geo["type"] == "FeatureCollection"
    assert {f["properties"]["ProductionPlace"] for f in geo["features"]} == {
        p.codigo for p in basico["parcelas"]
    }


def test_otra_cooperativa_no_ve_ni_opera(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    dex = _emitir(api, admin, lote).json()
    respuesta = api.como(admin).post(
        "/certificaciones",
        data={
            "nombre": "Comercio justo",
            "entidad_certificadora": "Certificadora",
            "numero": "CJ-1",
            "vigente_desde": "2026-01-01",
            "vigente_hasta": "2027-01-01",
        },
        files={"archivo": ("c.pdf", PDF, "application/pdf")},
    )
    cert = respuesta.json()
    otra = factorias.cooperativa(sesion, "Coop Ajena", codigo="AJE")
    ajeno = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(ajeno)
    assert api.get(f"/lotes/{lote['id']}/hallazgos").status_code == 404
    assert api.get(f"/lotes/{lote['id']}/geojson").status_code == 404
    assert api.post(f"/lotes/{lote['id']}/dex", json={"entiendo": True}).status_code == 404
    assert api.get(f"/dex/{dex['id']}").status_code == 404
    assert api.get(f"/dex/{dex['id']}/descargas").status_code == 404
    assert (
        api.post(f"/dex/{dex['id']}/anular", json={"motivo": "Prueba de otra cooperativa."}).status_code
        == 404
    )
    assert api.get("/dex").json() == []
    assert api.get("/certificaciones").json() == []
    assert api.patch(f"/certificaciones/{cert['id']}", json={"numero": "X"}).status_code == 404
    documento = sesion.scalar(select(Documento).where(Documento.entidad == "dex"))
    assert api.get(f"/documentos/{documento.id}/url").status_code in (403, 404)


def test_el_pdf_del_dex_de_demostracion_lleva_la_marca_en_su_idioma():
    marcas = {"es": "DEMOSTRACIÓN — DATOS FICTICIOS", "en": "DEMONSTRATION — FICTITIOUS DATA"}
    for idioma, marca in marcas.items():
        pdf = pdf_dex.Pdf("DEX-PRUEBA", idioma, demo=True)
        pdf.add_page()
        pdf.add_page()
        pdf.output()
        assert pdf.textos.count(marca) == 4  # dos páginas; su ancho y su texto pasan por normalize_text
        real = pdf_dex.Pdf("DEX-PRUEBA", idioma)
        real.add_page()
        real.output()
        assert marca not in real.textos


def test_el_pdf_del_dex_lleva_el_uso_del_suelo_en_su_idioma(
    api, sesion, admin, operador, basico, storage_falso
):
    """Pedido del 2026-10-08: el historial de MapBiomas, con los nombres de la leyenda oficial en cada
    idioma."""
    from app.catalogos import mapbiomas_peru_c3 as leyenda
    from tests.test_recepcion import HISTORIAL_MAPBIOMAS

    lote = _listo(api, sesion, basico, operador)
    dex = sesion.get(Dex, uuid.UUID(_emitir(api, admin, lote).json()["id"]))
    contenido = json.loads(json.dumps(dex.contenido))
    # Cada parcela tiene un análisis vigente de MapBiomas: se le pone la serie por año.
    mapbiomas = next(f for f in contenido["respaldo"][0]["cobertura"] if f["fuente"] == "mapbiomas")
    mapbiomas["indicadores"] = HISTORIAL_MAPBIOMAS
    esperado = {
        "es": ("Uso del suelo por año (ha), según MapBiomas Perú", "Mosaico agropecuario"),
        "en": ("Land use by year (ha), according to MapBiomas Peru", "Mosaic of agriculture and pasture"),
    }
    for idioma, (titulo, clase) in esperado.items():
        pdf = pdf_dex.documento(contenido, dex.contenido_sha256, "https://ejemplo.test", idioma)
        pdf.output()
        escrito = "\n".join(pdf.textos)
        assert titulo in escrito and clase in escrito and "0.2700" in escrito
    # Cada clase de la leyenda tiene su nombre oficial en inglés.
    assert set(leyenda.NOMBRES_EN) == set(leyenda.CLASES)
    assert leyenda.nombre(33, "en") == "River, lake or ocean" and leyenda.nombre(0, "en") == "No data"


# ---------- Adenda 5: los hallazgos y las declaraciones de los productores ----------

SEGUIMIENTO_PRODUCTOR = (
    "Se visitó al productor el 5 de octubre: se le explicó la jornada legal, el manejo de envases y se "
    "acordó revisar en enero."
)
DECLARACION_CON_TODO = {
    "quien_trabaja": "permanentes",
    "trabajadores_numero": 3,
    "acuerdo_por_escrito": "no",
    "jornal_soles": 50,
    "horas_por_dia": 10,
    "seguro_salud": "ninguno",
    "equipo_proteccion": "si",
    "pueden_dejar_el_trabajo": "no",
    "menores_trabajan": "si_contratados",
    "menor_edad_minima": 15,
    "menores_van_a_la_escuela": "algunos",
    "usa_agroquimicos": "si",
    "productos": [
        {"nombre": "Herbicida X", "tipo": "herbicida"},
        {"nombre": "Abono Y", "tipo": "fertilizante"},
    ],
    "quien_aplica": "trabajadores",
    "destino_envases": "quema",
    "ventas_superan_75_uit": "no_sabe",
}
CODIGOS_PRODUCTOR = {
    "condiciones_de_trabajo_por_atender",
    "menores_en_la_parcela",
    "trabajo_no_libre",
    "agroquimico_no_figura",
    "envases_por_atender",
    "agroquimicos_sin_revisar",
    "permanentes_sin_relacion",
    "tributos_sin_sustento",
}


@pytest.fixture
def con_declaraciones(api, sesion, coop, admin, operador, productor, expediente_cooperativa):
    """Un productor con dos parcelas que declara de todo y otro, con una, que trabaja con su familia."""
    from tests.habilitacion_util import declarar_anual

    vecino = factorias.productor(sesion, coop, nombres="Vecino", apellidos="Familiar")
    p1 = _parcela(api, sesion, admin, operador, productor, 0)
    p2 = _parcela(api, sesion, admin, operador, productor, 600)
    p3 = _parcela(api, sesion, admin, operador, vecino, 1200)
    declaracion = declarar_anual(
        sesion, productor, operador, DECLARACION_CON_TODO, revisiones={"Herbicida X": "no_figura"}
    )
    ruta = f"/productores/{productor.id}/declaraciones/{declaracion.id}/seguimiento"
    assert api.como(admin).put(ruta, json={"nota": SEGUIMIENTO_PRODUCTOR}).status_code == 200
    datos = _lote(api, sesion, coop, operador, [p1, p2, p3])
    return datos | {"parcelas": (p1, p2, p3), "vecino": vecino}


def test_hallazgos_del_productor(api, sesion, operador, productor, con_declaraciones):
    from app.services.hallazgos.datos import cargar

    informe = _informe(api.como(operador), con_declaraciones["lote"])
    del_productor = [h for h in informe["hallazgos"] if h["sujeto"]["tipo"] == "productor"]
    por_codigo = {h["codigo"]: h for h in del_productor}
    assert set(por_codigo) == CODIGOS_PRODUCTOR
    nombre = f"{productor.nombres} {productor.apellidos}"
    p1, p2, _ = con_declaraciones["parcelas"]
    d = cargar(sesion, sesion.get(Lote, uuid.UUID(con_declaraciones["lote"]["id"])))
    peso = d.peso_parcela[p1.id] + d.peso_parcela[p2.id]
    for h in del_productor:
        entrada = CATALOGO[h["codigo"]]
        assert (h["grupo"], h["etapa"], h["criterio"]) == (entrada.grupo, 1, 11)
        assert h["sujeto"]["codigo"] == nombre and h["peso_en_lote_pct"] == f"{peso:.2f}"
        assert h["explicacion"] == SEGUIMIENTO_PRODUCTOR
        assert h["datos"]["referencias"] and h["datos"]["nivel_orientador"] and h["datos"]["diligencia"]
        assert h["hecho"]["es"].startswith(f"{nombre} declara") or "declara" in h["hecho"]["es"]
        assert "declares" in h["hecho"]["en"]
    condiciones = por_codigo["condiciones_de_trabajo_por_atender"]["hecho"]["es"]
    assert "10 horas" in condiciones and "EsSalud" in condiciones
    assert por_codigo["condiciones_de_trabajo_por_atender"]["datos"]["referencias"] == "4.2, 4.4"
    menores = por_codigo["menores_en_la_parcela"]["hecho"]["es"]
    assert "contratadas" in menores and "15 años" in menores and "solo algunas van a la escuela" in menores
    no_figura = por_codigo["agroquimico_no_figura"]["hecho"]["es"]
    assert "Herbicida X" in no_figura and textos.fecha("es", hoy_lima()) in no_figura
    assert "Abono Y" in por_codigo["agroquimicos_sin_revisar"]["hecho"]["es"]
    assert "quema" in por_codigo["envases_por_atender"]["hecho"]["es"]
    assert "no sabe" in por_codigo["tributos_sin_sustento"]["hecho"]["es"]
    assert por_codigo["condiciones_de_trabajo_por_atender"]["grupo"] == "requiere_atencion"
    assert por_codigo["permanentes_sin_relacion"]["grupo"] == "no_verificado"
    # El vecino trabaja con su familia: ningún hallazgo. El mensaje final dice cada código una vez.
    assert all(h["sujeto"]["codigo"] == nombre for h in del_productor)
    assert informe["mensaje_texto"]["es"].count("Productores que declaran") >= 1


def test_un_productor_sin_declaracion_vigente_no_genera_estos_hallazgos(
    api, sesion, operador, productor, con_declaraciones
):
    from tests.habilitacion_util import declarar_anual

    # Su declaración vence: la de hoy se reemplaza por la misma, firmada hace 13 meses.
    declarar_anual(
        sesion,
        productor,
        operador,
        DECLARACION_CON_TODO,
        declarada_en=hoy_lima() - timedelta(days=400),
    )
    informe = _informe(api.como(operador), con_declaraciones["lote"])
    assert not [h for h in informe["hallazgos"] if h["sujeto"]["tipo"] == "productor"]


def test_el_dex_trae_las_declaraciones_de_los_productores(
    api, sesion, admin, operador, productor, con_declaraciones
):
    lote = _listo(api, sesion, con_declaraciones, operador)
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 201, respuesta.text
    dex = sesion.get(Dex, uuid.UUID(respuesta.json()["id"]))
    productores = dex.contenido["productores"]
    assert [x["productor"] for x in productores] == [
        f"{productor.nombres} {productor.apellidos}",
        "Vecino Familiar",
    ]
    primero = productores[0]
    assert primero["seguimiento"] == SEGUIMIENTO_PRODUCTOR and len(primero["requisitos"]) == 7
    # Nombres y apellidos, nunca el DNI.
    assert productor.dni not in json.dumps(productores)
    for idioma, titulo, totales in (
        ("es", "Declaraciones de los productores", "Productores del lote"),
        ("en", "Producers' declarations", "Producers in the lot"),
    ):
        documento = pdf_dex.documento(dex.contenido, dex.contenido_sha256, "https://x.test", idioma)
        texto = " ".join(documento.textos)
        assert titulo in texto and totales in texto
        assert "Vecino Familiar" in texto and SEGUIMIENTO_PRODUCTOR in texto


# ---------- Adenda 6: la organización, la declaración aduanera y el DEX ----------


def test_asociacion_con_su_identidad_basta_para_un_lote_listo(
    api, sesion, coop, admin, operador, productor, expediente_cooperativa
):
    """Sección 13: una asociación con ficha RUC, partida y poderes vigentes, sin nada más."""
    coop.tipo_organizacion = "asociacion"
    for codigo in ("renta_anual", "rnca"):
        expediente_cooperativa[codigo].anulado_en = ahora()
    sesion.flush()
    p1 = _parcela(api, sesion, admin, operador, productor, 0)
    lote = _listo(api, sesion, _lote(api, sesion, coop, operador, [p1]), operador)
    por_codigo = _codigos(_informe(api, lote))
    assert "registro_cooperativas_sin_sustento" not in por_codigo
    tributos = por_codigo["tributos_organizacion_sin_sustento"][0]
    assert (tributos["grupo"], tributos["etapa"], tributos["criterio"]) == ("no_verificado", 3, 11)
    assert tributos["sujeto"]["tipo"] == "organizacion" and coop.razon_social in tributos["hecho"]["es"]
    assert por_codigo["lote_sin_dam"][0]["sujeto"]["tipo"] == "lote"
    assert {"politica_incompleta", "sin_actuaciones_de_diligencia"} <= set(por_codigo)
    assert all(por_codigo[c][0]["grupo"] == "no_verificado" for c in ("politica_incompleta", "lote_sin_dam"))


def test_lote_bloqueado_por_un_registro_que_salio_vuelve_a_listo(
    api, sesion, coop, admin, operador, productor, expediente_cooperativa
):
    """Sección 8: un lote bloqueado solo por registro_aduanas pasa a listo en la siguiente recomprobación. Y
    una cooperativa agraria sin su constancia de inscripción también queda lista."""
    expediente_cooperativa["rnca"].anulado_en = ahora()
    p1 = _parcela(api, sesion, admin, operador, productor, 0)
    datos = _lote(api, sesion, coop, operador, [p1])
    sesion.get(Lote, uuid.UUID(datos["lote"]["id"])).estado = "bloqueado"
    sesion.flush()
    lote = _listo(api, sesion, datos, operador)
    registro = _codigos(_informe(api, lote))["registro_cooperativas_sin_sustento"][0]
    assert registro["grupo"] == "no_verificado" and "faltante" in registro["hecho"]["es"]


def test_declaracion_aduanera_despues_del_dex(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    emitido = _emitir(api, admin, lote)
    assert emitido.status_code == 201, emitido.text
    dex = emitido.json()
    sellado = {h["codigo"]: h for h in dex["contenido"]["informe"]["hallazgos"]}
    assert (sellado["lote_sin_dam"]["grupo"], sellado["lote_sin_dam"]["criterio"]) == ("no_verificado", 11)

    def cargar(tipo, **datos):
        return api.como(operador).post(
            f"/lotes/{lote['id']}/documentos",
            data={"tipo": tipo, **datos},
            files={"archivo": (f"{tipo}.pdf", PDF + str(datos).encode(), "application/pdf")},
        )

    # Con el lote cerrado, la factura comercial no se carga, como antes; la declaración aduanera sí.
    factura = cargar(
        "factura_comercial", numero="F001-9", entidad_emisora="Emisor", fecha_emision="2026-10-01"
    )
    assert factura.status_code == 400
    assert cargar("dam", numero="1234", fecha_emision=str(hoy_lima())).status_code == 422
    assert cargar("dam", numero="DAM-PRUEBA-0002").status_code == 422
    futura = str(hoy_lima() + timedelta(days=1))
    assert cargar("dam", numero="DAM-PRUEBA-0002", fecha_emision=futura).status_code == 422
    cargada = cargar("dam", numero="DAM-PRUEBA-0002", fecha_emision=str(hoy_lima()))
    assert cargada.status_code == 201, cargada.text
    assert cargada.json()["entidad_emisora"] == "SUNAT"
    embarque = api.get(f"/lotes/{lote['id']}/documentos").json()
    tipos = {t["codigo"]: t for t in embarque["tipos"]}
    assert not tipos["dam"]["obligatorio"] and tipos["dam"]["editable"] and tipos["dam"]["cargado"]
    assert len(tipos["dam"]["consultas"]) == 2 and tipos["dam"]["registro_consultable"]
    assert not tipos["factura_comercial"]["editable"] and embarque["completo"]
    # El DEX no cambia: su contenido y su huella son los mismos.
    fila = sesion.get(Dex, uuid.UUID(dex["id"]))
    sesion.refresh(fila)
    assert fila.contenido_sha256 == dex["contenido_sha256"] == sello.huella(fila.contenido)
    detalle = api.get(f"/dex/{dex['id']}").json()
    assert detalle["contenido"] == dex["contenido"]
    assert [a["numero"] for a in detalle["agregado"]] == ["DAM-PRUEBA-0002"]
    # Admite cotejo, también con el lote cerrado.
    cotejo = api.post(
        f"/documentos/{cargada.json()['id']}/cotejo",
        json={"nota": "Consulta pública de SUNAT por número: coincide con el archivo."},
    )
    assert cotejo.status_code == 200, cotejo.text
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert "documento.cotejar" in acciones
    # La verificación pública la muestra aparte.
    api.headers.pop("Authorization", None)
    publico = api.get(f"/publico/dex/{dex['codigo']}").json()
    [agregado] = publico["agregado"]
    assert agregado["numero"] == "DAM-PRUEBA-0002" and agregado["cotejado"]
    assert agregado["fecha_numeracion"] == str(hoy_lima()) and agregado["cargado_en"]
    assert publico["contenido_sha256"] == dex["contenido_sha256"]


def test_el_dex_trae_la_organizacion_y_su_diligencia(
    api, sesion, coop, admin, operador, productor, con_declaraciones
):
    diligencia_completa(sesion, coop, admin)
    campo = actuacion(
        sesion, coop, admin, tipo="verificacion_en_campo", temas=("trabajo",), productores=(productor.id,)
    )
    documento(sesion, coop.id, "actuacion", campo.id, "evidencia_actuacion", admin)
    lote = _listo(api, sesion, con_declaraciones, operador)
    dam(sesion, uuid.UUID(lote["id"]), operador)
    # Los hallazgos del productor traen las actuaciones que lo alcanzaron.
    informe = _informe(api.como(operador), lote)
    del_productor = [h for h in informe["hallazgos"] if h["sujeto"]["tipo"] == "productor"]
    assert del_productor
    for h in del_productor:
        assert [a["tipo"]["es"] for a in h["datos"]["actuaciones"]] == ["Verificación en campo"]
    assert not {"politica_incompleta", "sin_actuaciones_de_diligencia", "lote_sin_dam"} & set(
        _codigos(informe)
    )
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 201, respuesta.text
    dex = sesion.get(Dex, uuid.UUID(respuesta.json()["id"]))
    c = dex.contenido
    assert [d["codigo"] for d in c["exportador"]["documentos"]] == [
        "ficha_ruc",
        "partida_sunarp",
        "vigencia_poderes",
        "renta_anual",
        "rnca",
    ]
    assert "dam" in [x["tipo"] for x in c["embarque"]]
    o = c["organizacion"]
    assert {r["codigo"]: r["estado"] for r in o["requisitos"]} == {
        "identidad": "sustentado",
        "tributos": "sustentado",
        "registro_cooperativas": "sustentado",
        "integridad": "sustentado",
        "actuaciones": "sustentado",
    }
    assert [x["tema"] for x in o["politica"]] == list(requisitos_organizacion.CODIGOS_TEMAS)
    assert o["canal_denuncias"] is True and len(o["actuaciones"]) == 2
    assert {a["nivel"] for a in o["actuaciones"]} == {"declarado", "documentado"}
    # Ni la evidencia ni los productores alcanzados salen del sistema.
    sellado = json.dumps(o, ensure_ascii=False)
    assert productor.dni not in sellado and productor.apellidos not in sellado and "evidencia" not in sellado
    for idioma, titulo, alcanzaron in (
        ("es", "La organización y su diligencia", "Actuaciones de la organización que lo alcanzaron"),
        ("en", "The organisation and its due diligence", "Actions of the organisation that reached them"),
    ):
        texto = " ".join(pdf_dex.documento(c, dex.contenido_sha256, "https://x.test", idioma).textos)
        assert titulo in texto and DESCRIPCION in texto and RESULTADO in texto and alcanzaron in texto
        limpio = texto
        for nombre in DOCUMENTOS_CON_NOMBRE_PROPIO:
            limpio = limpio.replace(nombre, "")
        assert not PROHIBIDAS.search(limpio) and not PROHIBIDAS_EN.search(limpio)
        # Un DEX emitido antes de la adenda 6 se sigue leyendo, sin la sección.
        anterior = {k: v for k, v in c.items() if k != "organizacion"}
        texto = " ".join(pdf_dex.documento(anterior, dex.contenido_sha256, "https://x.test", idioma).textos)
        assert titulo not in texto
