"""Paquete de simulación (pedido del equipo del 2026-10-06): el escenario completo de las dos cooperativas se
carga por la capa de servicios sin que falle ningún paso, con Whisp y GFW simulados sin alertas, y las cifras
del guion cuadran con lo que calcula la aplicación. También se genera el ZIP."""

import importlib.util
import json
import zipfile
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.demo import simulacion as sim
from app.demo.escenario import EscenarioDetenido
from app.fechas import hoy_lima
from app.models import Dex, Dop, Lote, LoteGenealogia, Parcela, Tanda, TandaFinal
from app.services import analisis
from app.services.fuentes import registro
from tests import factorias
from tests.e2e import test_flujo_completo as e2e
from tests.habilitacion_util import fuentes_configuradas

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generar_simulacion.py"
SIN_ESPERAS = analisis.Ritmo(reloj=lambda: 0.0, dormir=lambda segundos: None)
# En el camino feliz nada pide atención: las exenciones que declara el guion van en No verificado.
ATENCION_PERMITIDA: set[str] = set()


def _whisp_limpio() -> bytes:
    """La respuesta real de Whisp con todas sus cifras de cobertura en cero: ningún conjunto ve bosque."""
    respuesta = json.loads(e2e.WHISP)
    for feature in respuesta["data"]["features"]:
        props = feature["properties"]
        for clave, valor in props.items():
            if isinstance(valor, float) and clave not in ("Area", "Centroid_lon", "Centroid_lat"):
                props[clave] = 0.0
    return json.dumps(respuesta).encode("utf-8")


WHISP_LIMPIO = _whisp_limpio()


def _responder(peticion):
    if peticion.url.host == "whisp.openforis.org":
        return httpx.Response(200, content=WHISP_LIMPIO, headers={"content-type": "application/json"})
    return e2e._responder(peticion)


@pytest.fixture(scope="module")
def generador():
    spec = importlib.util.spec_from_file_location("generar_simulacion", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def fuentes():
    antes = dict(registro.actuales())
    yield fuentes_configuradas(_responder)
    registro.fijar(antes)


def test_los_datos_cumplen_las_reglas_antes_de_cargar():
    simulacion = sim.armar(hoy_lima())
    hoy = simulacion.hoy
    dnis = [p.dni for c in simulacion.cooperativas for p in c.productores]
    dnis += [c.representante_dni for c in simulacion.cooperativas]
    assert len(dnis) == len(set(dnis))
    for c in simulacion.cooperativas:
        assert c.ruc == sim.ruc_valido(c.ruc[:10])
        assert len(c.parcelas) == 9 and len(c.tandas) == 9
        assert all(Decimal("1.5") <= p.area_ha < 4 for p in c.parcelas)
        documentos = [*c.documentos, *(d for p in c.parcelas for d in p.documentos), *c.orden.embarque]
        for d in documentos:
            assert d.emision <= hoy and d.emision.month >= 8
            assert d.vencimiento is None or d.vencimiento > sim.date(2027, 3, 31)
        numeros = [d.numero for d in documentos] + [t.liquidacion.numero for t in c.tandas]
        assert len(numeros) == len(set(numeros))
        for t in c.tandas:
            assert t.recibida_en.date() <= hoy and (t.recibida_en.date() - t.cosecha_hasta).days <= 7
        for corrida in c.corridas:
            pasos = [e for e in corrida.etapas if not e.no_ocurrio]
            assert all(a.fin <= b.inicio for a, b in zip(pasos, pasos[1:], strict=False))
            assert pasos[-1].fin.date() < hoy
        esp = sim.esperado(c)
        assert all(Decimal("0.330") <= r <= Decimal("0.450") for r in esp.rendimiento.values())
        assert sum(k for *_, k in esp.genealogia) == c.orden.cantidad
    # Ninguna parcela se superpone con otra, de la misma cooperativa o de la otra.
    formas = [sim.shape(p.geometria) for c in simulacion.cooperativas for p in c.parcelas]
    assert not any(a.intersects(b) for i, a in enumerate(formas) for b in formas[i + 1 :])


def test_las_cifras_esperadas_usan_las_reglas_de_la_aplicacion():
    from app.services.corridas import proporciones
    from app.services.lotes import _ajustar

    for pesos in (["300", "300", "400"], ["450", "400", "350", "500", "375", "425"], ["1", "1", "1"]):
        pesos = [Decimal(p) for p in pesos]
        assert sim.proporciones(pesos) == proporciones(pesos)
    valores = [Decimal("33.3333"), Decimal("33.3333"), Decimal("33.3333")]
    assert sim.ajustar(valores, Decimal("100")) == _ajustar(list(valores), Decimal("100"))


def test_la_simulacion_carga_completa_por_servicios(sesion, auth_falso, storage_falso, fuentes, generador):
    simulacion = sim.armar(hoy_lima())
    superadmin = factorias.perfil(sesion, "superadmin")
    try:
        ids = sim.cargar(
            sesion,
            superadmin,
            auth=auth_falso,
            storage=storage_falso,
            fuentes=fuentes,
            ritmo=SIN_ESPERAS,
            simulacion=simulacion,
            pdf=generador.pdf,
        )
    except EscenarioDetenido as exc:  # el mensaje dice qué paso falló
        pytest.fail(str(exc))
    for c in simulacion.cooperativas:
        r = ids[c.clave]
        esp = sim.esperado(c)
        parcelas = [sesion.get(Parcela, r["parcelas"][p.clave]) for p in c.parcelas]
        assert [p.codigo for p in parcelas] == [p.codigo for p in c.parcelas]
        assert {p.habilitacion_estado for p in parcelas} == {"habilitada"}
        assert [(p.departamento, p.provincia, p.distrito) for p in parcelas] == [
            p.ubicacion for p in c.parcelas
        ]
        tandas = [sesion.get(Tanda, r["tandas"][t.clave]) for t in c.tandas]
        assert {t.estado for t in tandas} == {"validada"}
        dops = sesion.scalars(select(Dop).where(Dop.tanda_id.in_([t.id for t in tandas]))).all()
        assert len(dops) == 9 and all(d.contenido["es_demo"] for d in dops)
        for clave, saldo in esp.saldo.items():
            assert sesion.get(TandaFinal, r["finales"][clave]).saldo_kg == saldo
        lote = sesion.get(Lote, r["lote"])
        assert lote.estado == "cerrado" and lote.masa_neta_kg == c.orden.cantidad
        codigo_de = {r["parcelas"][p.clave]: p.clave for p in c.parcelas}
        obtenida = sorted(
            (codigo_de[f.parcela_id], Decimal(f.kg_atribuidos))
            for f in sesion.scalars(select(LoteGenealogia).where(LoteGenealogia.lote_id == lote.id))
        )
        assert obtenida == sorted((parcela, kg) for parcela, _, _, kg in esp.genealogia)
        dex = sesion.get(Dex, r["dex"])
        assert dex.estado == "vigente" and dex.contenido["es_demo"] is True
        atencion = {
            h["codigo"] for h in dex.contenido["informe"]["hallazgos"] if h["grupo"] == "requiere_atencion"
        }
        assert atencion <= ATENCION_PERMITIDA, atencion
        assert not [h for h in dex.contenido["informe"]["hallazgos"] if h["grupo"] == "impide_cierre"]


def test_el_paquete_trae_todos_los_archivos(tmp_path, generador):
    destino = generador.generar(hoy_lima(), tmp_path)
    with zipfile.ZipFile(destino) as zip_:
        nombres = zip_.namelist()
        guion = zip_.read("cacaotrace-simulacion/guion-de-carga.html").decode("utf-8")
        pdfs = [zip_.read(n) for n in nombres if n.endswith(".pdf")]
    # Por cooperativa: 6 de la cooperativa, 3 DNI, 9 parcelas x (2 geometrías + 4 documentos),
    # 9 liquidaciones y 4 de embarque. Más el guion y el LEEME.
    # Adenda 4: cada parcela trae su GeoJSON, su KML y su título (ya no los documentos laborales,
    # tributarios ni de zonificación). Adenda 5: cada productor trae la hoja firmada de su declaración.
    assert len(nombres) == 2 * (6 + 3 + 3 + 9 * 3 + 9 + 4) + 2
    assert len(pdfs) == 2 * (6 + 3 + 3 + 9 * 1 + 9 + 4) and all(p.startswith(b"%PDF") for p in pdfs)
    assert sum(n.endswith(".geojson") for n in nombres) == sum(n.endswith(".kml") for n in nombres) == 18
    # Nombres de archivos y carpetas sin tildes ni eñes.
    assert all(n.isascii() for n in nombres)
    simulacion = sim.armar(hoy_lima())
    for c in simulacion.cooperativas:
        assert c.razon_social in guion and c.orden.importador.eori in guion
        for d in c.documentos:
            assert d.archivo in guion
    assert guion.count("class='copiar'") > 300
