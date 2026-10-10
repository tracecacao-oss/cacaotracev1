"""Parte 10: prueba de extremo a extremo con el escenario de la cooperativa Prueba (app/demo/escenario.py).

Construye el escenario una vez, con Whisp y GFW simulados con las respuestas reales de tests/datos/, y
comprueba el estado final: parcelas, saldos de las tandas finales, lotes, genealogía del lote 1, DEX,
registros detenidos, la marca de demostración en los documentos y que otra cooperativa no ve nada de Prueba.
"""

import json
import re
import uuid
import zlib
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app import textos
from app.demo import escenario
from app.models import AnalisisCobertura, Cooperativa, Documento, Dop, Dpp, Perfil, Superposicion
from app.pdf import dex as pdf_dex
from app.pdf import dop as pdf_dop
from app.pdf.base import MARCA_AGUA, TEXTO_DEMO
from app.services import analisis, dops
from app.services import dex as servicio_dex
from app.services.fuentes import registro
from app.services.fuentes.gfw import GFW
from app.services.fuentes.whisp import Whisp
from tests import factorias
from tests.factorias import crear_parcela
from tests.habilitacion_util import fuentes_configuradas

DATOS = Path(__file__).resolve().parents[1] / "datos"
# Whisp: la respuesta real guardada, con riesgo bajo.
WHISP = (DATOS / "whisp_respuesta_real.json").read_bytes()
# GFW: la respuesta real con las cuatro consultas de la adenda trae pérdida en 2022, que pide revisión. Aquí
# va con la pérdida de la primera respuesta real (ninguna), para que ninguna parcela pida revisión.
GFW_REAL = json.loads((DATOS / "gfw_respuesta_real_adenda.json").read_text(encoding="utf-8"))
GFW_PRIMERA = json.loads((DATOS / "gfw_respuesta_real.json").read_text(encoding="utf-8"))
GFW_REAL["perdida"]["respuesta"] = GFW_PRIMERA["perdida"]["respuesta"]
CONSULTA_GFW = re.compile(r"/dataset/([^/]+)/([^/]+)/query/json")
SIN_ESPERAS = analisis.Ritmo(reloj=lambda: 0.0, dormir=lambda segundos: None)
ESTADOS = {
    "PA-00001": "habilitada",
    "PA-00002": "habilitada",
    "PA-00003": "habilitada",
    "PA-00004": "habilitada",
    "PA-00005": "habilitada",
    "PA-00006": "habilitada",
    "PA-00007": "observada",
    "PA-00008": "pendiente",
    "PA-00009": "excluida",
}
# Genealogía del lote 1: (parcela, corrida de la tanda final) y kilos con 4 decimales. Desde la tanda final 1,
# la tabla de la especificación (Parte 10, "Genealogía esperada del lote 1"). Desde la tanda final 2, lo que
# dan las reglas de las Partes 6 y 7: proporciones de 6 decimales en la corrida (0.444444, 0.333333 y la
# última ajustada a 0.222223) por 200 kg. La tabla de la Parte 10 dice 88.8889, 66.6667 y 44.4444, que solo
# salen con proporciones exactas; los totales coinciden.
GENEALOGIA_LOTE_1 = {
    ("PA-00001", 1): "200.0000",
    ("PA-00003", 1): "120.0000",
    ("PA-00004", 1): "80.0000",
    ("PA-00002", 2): "88.8888",
    ("PA-00005", 2): "66.6666",
    ("PA-00006", 2): "44.4446",
}


def _responder(peticion: httpx.Request) -> httpx.Response:
    """Whisp responde siempre lo mismo; GFW redirige "latest" a la versión concreta y responde la consulta."""
    if peticion.url.host == "whisp.openforis.org":
        return httpx.Response(200, content=WHISP, headers={"content-type": "application/json"})
    conjunto, version = CONSULTA_GFW.fullmatch(peticion.url.path).groups()
    parte = next(p for p in GFW_REAL.values() if isinstance(p, dict) and p.get("conjunto") == conjunto)
    if version == "latest":
        destino = f"https://{peticion.url.host}/dataset/{conjunto}/{parte['version']}/query/json"
        return httpx.Response(307, headers={"location": destino})
    return httpx.Response(200, json=parte["respuesta"])


@pytest.fixture
def fuentes():
    return fuentes_configuradas(_responder)


@pytest.fixture(autouse=True)
def _restaurar_fuentes():
    """El escenario deja sus fuentes en uso, como al arrancar la API; al terminar vuelven las de antes."""
    antes = dict(registro.actuales())
    yield
    registro.fijar(antes)


def _construir(sesion, auth_falso, storage_falso, fuentes) -> escenario.Escenario:
    return escenario.construir(
        sesion,
        factorias.perfil(sesion, "superadmin"),
        auth=auth_falso,
        storage=storage_falso,
        fuentes=fuentes,
        ritmo=SIN_ESPERAS,
        espera_maxima=timedelta(0),
    )


def _ok(respuesta: httpx.Response):
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _paginas_y_marcas(pdf: bytes) -> tuple[int, int]:
    """Páginas del PDF y flujos de página con la marca de agua (texto girado en el gris de la marca). Cada
    flujo se lee con su /Length exacto: sus bytes comprimidos pueden contener cualquier valor."""
    gris = " ".join(f"{c / 255:.4f}" for c in MARCA_AGUA).encode() + b" rg"
    paginas = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", pdf))
    marcas = 0
    for m in re.finditer(rb"<<\s*/Filter /FlateDecode\s*/Length (\d+)\s*>>\nstream\n", pdf):
        flujo = pdf[m.end() : m.end() + int(m.group(1))]
        try:
            contenido = zlib.decompress(flujo)
        except zlib.error:
            continue
        marcas += gris in contenido and b" cm" in contenido
    return paginas, marcas


def _con_marca_en_cada_pagina(storage_falso, documento: Documento) -> None:
    pdf = storage_falso.archivos[documento.ruta]
    paginas, marcas = _paginas_y_marcas(pdf)
    assert pdf.startswith(b"%PDF") and paginas >= 1
    assert marcas == paginas, f"{documento.nombre_original}: {marcas} de {paginas} páginas con la marca"


def test_flujo_completo_de_la_cooperativa_prueba(api, sesion, auth_falso, storage_falso, fuentes):
    esc = _construir(sesion, auth_falso, storage_falso, fuentes)
    # La administradora entra por primera vez con su contraseña temporal y la cambia, como cualquier persona.
    admin = sesion.get(Perfil, esc.usuarios["admin"])
    cambio = {"clave_actual": esc.claves[admin.correo], "clave_nueva": "demo-prueba-2026"}
    assert api.como(admin).post("/me/clave", json=cambio).status_code == 204

    # --- La cooperativa, su marca y su base ---
    coop = sesion.get(Cooperativa, esc.cooperativa_id)
    assert (coop.razon_social, coop.codigo, coop.ruc, coop.es_demo) == (
        "Cooperativa Prueba (demostración)",
        "PRB",
        "20000000001",
        True,
    )
    assert (coop.departamento, coop.provincia, coop.distrito) == ("SAN MARTIN", "PICOTA", "PICOTA")
    assert _ok(api.get("/me"))["es_demo"] is True
    assert sorted(u["rol"] for u in _ok(api.get("/usuarios"))["items"]) == [
        "admin_cooperativa",
        "lector",
        "operador",
    ]
    assert all(c.endswith("@cooperativa-prueba.test") for c in esc.claves if "@" in c)
    productores = _ok(api.get("/productores"))["items"]
    padron = sorted((f"{p['nombres']} {p['apellidos']}", p["dni"], p["es_demo"]) for p in productores)
    assert padron == sorted(
        (f"Demo {nombre}", f"{n:08d}", True) for n, nombre in enumerate(escenario.PRODUCTORES, start=1)
    )
    assert all(p["nivel_identidad"] == "documentado" and p["consentimiento_datos_en"] for p in productores)
    uno = _ok(api.get(f"/productores/{esc.productores['Demo Uno']}"))
    assert uno["acceso"]["existe"] and uno["acceso"]["activo"]
    configuracion = _ok(api.get("/configuracion"))
    assert Decimal(configuracion["tope_kg_seco_ha_anio"]) == Decimal("1500")
    assert configuracion["factor_baba_a_seco"] == "0.390"  # el resto, valores iniciales
    assert sorted(lu["tipo"] for lu in _ok(api.get("/lugares"))) == ["almacen", "cancha_acopio", "planta"]
    assert sorted(c["nombre"] for c in _ok(api.get("/calidades"))) == ["Grado 1", "Grado 2"]
    plantilla = _ok(api.get("/proceso/plantilla"))
    assert len(plantilla) == 23 and all(f["lugar_id"] and f["metodo"] for f in plantilla)
    expediente_coop = _ok(api.get("/cooperativa/expediente"))
    assert expediente_coop["estado"] == "completo" and len(expediente_coop["casillas"]) == 6
    assert _ok(api.get("/cooperativa"))["faltan_datos"] == []
    assert [i["razon_social"] for i in _ok(api.get("/importadores"))] == ["Importador Demo B.V."]

    # --- Parcelas ---
    lista = {p["codigo"]: p for p in _ok(api.get("/parcelas"))}
    assert {codigo: p["habilitacion_estado"] for codigo, p in lista.items()} == ESTADOS
    assert all("analisis_requiere_revision" not in p["alertas"] for p in lista.values())
    assert round(Decimal(lista["PA-00001"]["area_calculada_ha"]), 1) == Decimal("2.1")
    assert round(Decimal(lista["PA-00002"]["area_calculada_ha"]), 1) == Decimal("1.4")
    assert Decimal(lista["PA-00003"]["area_cultivada_ha"]) == Decimal("0.2")
    punto = lista["PA-00005"]
    assert (punto["tipo_geometria"], Decimal(punto["area_declarada_ha"])) == ("punto", Decimal("1.8"))
    gfw_del_punto = sesion.scalar(
        select(AnalisisCobertura).where(
            AnalisisCobertura.parcela_id == uuid.UUID(punto["id"]), AnalisisCobertura.fuente == "gfw"
        )
    )
    assert gfw_del_punto.es_aproximacion and gfw_del_punto.estado == "completado"

    # Adenda 4: legalidad por requisito.
    def legalidad(codigo):
        return _ok(api.get(f"/parcelas/{esc.parcelas[codigo]}/legalidad"))

    def requisito(leg, codigo):
        return next(r for r in leg["requisitos"] if r["codigo"] == codigo)

    tenencia = requisito(legalidad("PA-00001"), "tenencia")
    assert (tenencia["sustento"]["tipo"], tenencia["sustento_nivel"]) == (
        "titulo_sunarp",
        "verificado_en_fuente",
    )
    assert "tenencia_solo_posesion" in legalidad("PA-00003")["alertas"]
    pa6 = legalidad("PA-00006")
    assert pa6["perfil_completo"] and requisito(pa6, "tierra_forestal")["estado"] == "no_aplica"
    aceptadas = _ok(api.get("/superposiciones", params={"estado": "aceptada"}))
    assert [{p["codigo"] for p in s["parcelas"]} for s in aceptadas] == [{"PA-00006", "PA-00007"}]
    assert aceptadas[0]["nota"]
    pa7 = _ok(api.get(f"/parcelas/{esc.parcelas['PA-00007']}/habilitacion"))
    assert [r["codigo"] for r in pa7["requisitos"] if not r["cumple"]] == ["tenencia_sustentada"]
    assert pa7["decisiones"][0]["decision"] == "observar"
    anulado = sesion.get(Documento, esc.documento_anulado_id)
    assert (anulado.tipo, anulado.anulado_en is not None) == ("titulo_sunarp", True)
    pa8 = legalidad("PA-00008")
    assert pa8["perfil_completo"] is False
    assert _ok(api.get("/tandas", params={"parcela_id": str(esc.parcelas["PA-00009"])})) == []
    pa9 = _ok(api.get(f"/parcelas/{esc.parcelas['PA-00009']}/habilitacion"))
    assert pa9["decisiones"][0]["decision"] == "excluir"

    # --- Corridas y stock ---
    finales = {tf["id"]: tf for tf in _ok(api.get("/tandas-finales"))}
    tf = {n: finales[str(esc.tandas_finales[n])] for n in (1, 2, 3)}
    assert [(tf[n]["peso_seco_kg"], tf[n]["saldo_kg"], tf[n]["calidad"]) for n in (1, 2, 3)] == [
        ("400.00", "0.00", "Grado 1"),
        ("450.00", "100.00", "Grado 1"),
        ("300.00", "0.00", "Grado 1"),
    ]
    assert [tf[n]["estado"] for n in (1, 2, 3)] == ["agotada", "en_stock", "agotada"]
    assert tf[1]["ingreso_stock_en"] < tf[2]["ingreso_stock_en"] < tf[3]["ingreso_stock_en"]
    corrida = {n: _ok(api.get(f"/corridas/{esc.corridas[n]}")) for n in (1, 2, 3, 4)}
    assert [corrida[n]["estado"] for n in (1, 2, 3, 4)] == ["consolidada"] * 3 + ["en_proceso"]
    assert corrida[1]["rendimiento"]["rendimiento"] == "0.400" and corrida[1]["alertas"] == []
    assert corrida[2]["rendimiento"]["rendimiento"] == "0.500"
    assert corrida[2]["alertas"] == ["rendimiento_sobre_banda"]
    assert (corrida[3]["ruta"], corrida[3]["tipo_manejo"]) == ("seco", "segregado")
    assert [len(corrida[n]["tandas"]) for n in (1, 2, 3, 4)] == [3, 3, 1, 2]

    # --- Órdenes y lotes ---
    lote = {n: _ok(api.get(f"/lotes/{esc.lotes[n]}")) for n in (1, 2, 3)}
    assert [lote[n]["estado"] for n in (1, 2, 3)] == ["cerrado", "bloqueado", "listo"]
    assert lote[1]["dex"]["estado"] == "vigente" and lote[1]["desviacion_fifo"] is False
    assert lote[2]["desviacion_fifo"] is True and lote[2]["motivo_desviacion"]
    assert [(a["codigo"], a["kg_asignados"]) for a in lote[2]["asignaciones"]] == [
        (tf[3]["codigo"], "300.00")
    ]
    casos = [
        caso["texto"]
        for c in lote[2]["recomprobacion"]["comprobaciones"]
        if c["resultado"] == "con_observaciones"
        for caso in c["casos"]
    ]
    assert len(casos) == 1 and "PA-00007" in casos[0] and "observada" in casos[0]
    assert lote[3]["dex"] is None
    assert [(a["codigo"], a["kg_asignados"]) for a in lote[3]["asignaciones"]] == [
        (tf[2]["codigo"], "150.00")
    ]
    orden = {n: _ok(api.get(f"/ordenes/{esc.ordenes[n]}")) for n in (1, 2, 3, 4)}
    assert [orden[n]["estado"] for n in (1, 2, 3, 4)] == ["cerrada", "con_lote", "con_lote", "abierta"]
    assert orden[4]["lote"] is None and orden[4]["cantidad_kg"] == "100.00"

    # --- Genealogía del lote 1 ---
    genealogia = _ok(api.get(f"/lotes/{esc.lotes[1]}/genealogia"))
    numero_de = {tf[n]["id"]: n for n in (1, 2, 3)}
    filas = {
        (f["parcela_codigo"], numero_de[f["tanda_final"]["id"]]): f["kg_atribuidos"]
        for f in genealogia["filas"]
    }
    assert filas == GENEALOGIA_LOTE_1
    por_tanda_final = {n: sum(Decimal(k) for (_, m), k in filas.items() if m == n) for n in (1, 2)}
    assert por_tanda_final == {1: Decimal("400.0000"), 2: Decimal("200.0000")}
    assert genealogia["masa_neta_kg"] == "600.00"
    assert sum(Decimal(k) for k in filas.values()) == Decimal("600.0000")

    # --- DEX del lote 1 ---
    dex = _ok(api.get(f"/dex/{esc.dex_id}"))
    contenido = dex["contenido"]
    assert dex["estado"] == "vigente" and dex["codigo"].startswith("DEX-PRB-")
    assert contenido["es_demo"] is True
    assert contenido["identificacion"]["lote"]["codigo"] == lote[1]["codigo"]
    assert contenido["importador"]["razon_social"] == "Importador Demo B.V."
    parcelas_dex = sorted(p["codigo"] for p in contenido["genealogia"]["parcelas"])
    assert parcelas_dex == [f"PA-0000{n}" for n in range(1, 7)]
    assert Decimal(contenido["producto"]["masa_neta_kg"]) == Decimal("600")
    assert contenido["recomprobacion"]["resultado"] == "sin_observaciones"
    assert len(contenido["embarque"]) == 4
    archivos = {
        d.tipo: d
        for d in sesion.scalars(
            select(Documento).where(Documento.entidad == "dex", Documento.entidad_id == esc.dex_id)
        )
    }
    for tipo in ("dex_geojson", "dex_anexo_ii", "dex_hallazgos"):
        assert json.loads(storage_falso.archivos[archivos[tipo].ruta])["es_demo"] is True, tipo
    for idioma in ("es", "en"):
        _con_marca_en_cada_pagina(storage_falso, archivos[f"dex_pdf_{idioma}"])
    url = servicio_dex.url_verificacion(dex["codigo"])
    pdf = pdf_dex.documento(contenido, dex["contenido_sha256"], url, "en")
    assert pdf.marca_agua == textos.obtener("en", "pdf.demo")

    # --- DOP y DPP: marca en el contenido sellado y en cada página del PDF ---
    dops_ = list(sesion.scalars(select(Dop).where(Dop.cooperativa_id == esc.cooperativa_id)))
    dpps_ = list(sesion.scalars(select(Dpp).where(Dpp.cooperativa_id == esc.cooperativa_id)))
    assert (len(dops_), len(dpps_)) == (9, 3)
    assert all(d.contenido["es_demo"] is True for d in [*dops_, *dpps_])
    for d in [*dops_, *dpps_]:
        _con_marca_en_cada_pagina(storage_falso, sesion.get(Documento, d.pdf_documento_id))
    primero = dops_[0]
    url = dops.url_verificacion(primero.codigo)
    pdf = pdf_dop.documento(primero.contenido, primero.contenido_sha256, url)
    assert pdf.marca_agua == TEXTO_DEMO and TEXTO_DEMO in pdf.textos
    api.headers.pop("Authorization", None)
    assert _ok(api.get(f"/publico/dops/{primero.codigo}"))["es_demo"] is True
    assert _ok(api.get(f"/publico/dex/{dex['codigo']}"))["es_demo"] is True

    # --- Registros detenidos para la demo ---
    api.como(admin)
    sin_validar = _ok(api.get(f"/tandas/{esc.tandas['sin validar']}"))
    assert (sin_validar["estado"], sin_validar["parcela"]["codigo"], sin_validar["peso_kg"]) == (
        "registrada",
        "PA-00003",
        "600.00",
    )
    assert "volumen_acumulado_excede_tope" in sin_validar["alertas"]
    assert sin_validar["puede_validar"] and sin_validar["nota_obligatoria"]
    observada = _ok(api.get(f"/tandas/{esc.tandas['observada']}"))
    assert (observada["estado"], observada["parcela"]["codigo"]) == ("observada", "PA-00004")
    assert observada["decisiones"][0]["decision"] == "observar" and observada["decisiones"][0]["nota"]
    assert corrida[4]["puede_consolidar"] and corrida[4]["faltan_para_consolidar"] == []
    assert all(e["situacion"] in ("registrada", "no_ocurrio") for e in corrida[4]["etapas"])
    assert [lo["estado"] for lo in _ok(api.get("/lotes"))].count("listo") == 1

    # --- Otra cooperativa no ve nada de Prueba ---
    otra = factorias.cooperativa(sesion, "Coop Real", ruc="20999999991", codigo="REAL")
    otro_admin = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(otro_admin)
    assert _ok(api.get("/me"))["es_demo"] is False
    assert _ok(api.get("/productores"))["items"] == []
    for ruta in (
        "/parcelas",
        "/tandas",
        "/dops",
        "/corridas",
        "/dpps",
        "/tandas-finales",
        "/importadores",
        "/ordenes",
        "/lotes",
        "/dex",
        "/lugares",
        "/calidades",
        "/superposiciones",
    ):
        assert _ok(api.get(ruta)) == [], ruta
    for ruta in (
        f"/productores/{esc.productores['Demo Uno']}",
        f"/parcelas/{esc.parcelas['PA-00001']}",
        f"/tandas/{esc.tandas['corrida 1 PA-00001']}",
        f"/dops/{primero.id}",
        f"/corridas/{esc.corridas[1]}",
        f"/tandas-finales/{esc.tandas_finales[1]}",
        f"/ordenes/{esc.ordenes[1]}",
        f"/lotes/{esc.lotes[1]}",
        f"/lotes/{esc.lotes[1]}/genealogia",
        f"/dex/{esc.dex_id}",
    ):
        assert api.get(ruta).status_code == 404, ruta
    # Un productor real con el DNI de Demo Uno no choca con él (la unicidad es por dni y es_demo), y su
    # parcela, en el mismo lugar que PA-00001, no abre superposición con ella: las de demostración solo se
    # comparan entre sí.
    real = factorias.productor(sesion, otra, dni="00000001")
    operador_real = factorias.perfil(sesion, "operador", otra)
    geometria = escenario.geometria(escenario.POR_CODIGO["PA-00001"])
    respuesta = crear_parcela(api.como(operador_real), real.id, geometria, nombre="Parcela real")
    assert respuesta.status_code == 201, respuesta.text
    assert "superposicion" not in respuesta.json()["alertas"]
    assert (
        sesion.scalar(
            select(Superposicion).where(
                Superposicion.estado == "abierta",
                (Superposicion.parcela_a_id == esc.parcelas["PA-00001"])
                | (Superposicion.parcela_b_id == esc.parcelas["PA-00001"]),
            )
        )
        is None
    )


def test_sin_claves_de_whisp_ni_gfw_se_detiene_y_lo_explica(sesion, auth_falso, storage_falso):
    with pytest.raises(escenario.EscenarioDetenido) as detenido:
        _construir(sesion, auth_falso, storage_falso, {"whisp": Whisp(None), "gfw": GFW(None)})
    assert detenido.value.paso == "Análisis de cobertura"
    assert "falta la clave de Whisp y GFW" in detenido.value.motivo
    # Se detuvo después de crear las parcelas, sin forzar nada.
    coop = sesion.scalar(select(Cooperativa).where(Cooperativa.codigo == "PRB"))
    assert coop.es_demo
    assert sesion.scalar(select(AnalisisCobertura).where(AnalisisCobertura.cooperativa_id == coop.id)) is None


def test_un_paso_rechazado_detiene_el_escenario_con_su_motivo(sesion, auth_falso, storage_falso, fuentes):
    factorias.cooperativa(sesion, "Otra", ruc="20999999992", codigo="PRB")
    with pytest.raises(escenario.EscenarioDetenido) as detenido:
        _construir(sesion, auth_falso, storage_falso, fuentes)
    assert detenido.value.paso == "Crear la cooperativa Prueba y su administrador"
    assert "[codigo_en_uso]" in detenido.value.motivo
