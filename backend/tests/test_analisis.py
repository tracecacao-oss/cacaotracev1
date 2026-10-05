"""Parte 4: análisis de cobertura forestal. Ninguna prueba llama a Whisp ni a GFW: el HTTP se simula."""

import re
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from app.fechas import ahora
from app.models import AnalisisCobertura, Auditoria, Parcela
from app.services import analisis
from tests import factorias
from tests.factorias import crear_parcela, punto, rectangulo
from tests.habilitacion_util import analisis_completado, fuentes_configuradas

RAIZ = Path(__file__).resolve().parents[2]


class Simulado:
    """Transporte HTTP falso: responde según la URL y guarda lo que se envió."""

    def __init__(self, whisp=None, gfw=None):
        self.whisp = whisp or []
        self.gfw = gfw or []
        self.peticiones: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.peticiones.append(request)
        cola = self.whisp if "whisp" in request.url.host else self.gfw
        if not cola:
            raise AssertionError(f"Llamada no prevista a {request.url}")
        return cola.pop(0)


@pytest.fixture
def simulado():
    return Simulado()


@pytest.fixture
def fuentes(simulado):
    return fuentes_configuradas(simulado)


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion, "Coop Secreta")


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(
        sesion, coop, dni="81234567", nombres="Nombre Secreto", apellidos="Apellido Secreto"
    )


def _parcela(api, sesion, operador, productor, geometria=None, **datos) -> Parcela:
    respuesta = crear_parcela(api.como(operador), productor.id, geometria or rectangulo(100, 100), **datos)
    assert respuesta.status_code == 201, respuesta.text
    return sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))


def _filas(sesion, parcela, fuente=None):
    consulta = sesion.query(AnalisisCobertura).filter_by(parcela_id=parcela.id)
    if fuente:
        consulta = consulta.filter_by(fuente=fuente)
    return consulta.order_by(AnalisisCobertura.solicitado_en).all()


def _procesar(sesion, fuentes, storage):
    ritmo = analisis.Ritmo(reloj=lambda: 0.0, dormir=lambda s: None)
    return analisis.procesar_siguiente(sesion, fuentes, storage, ritmo)


def _ya(sesion):
    """Adelanta los reintentos para no esperar en la prueba."""
    for fila in sesion.query(AnalisisCobertura).filter_by(estado="pendiente"):
        fila.reintentar_en = ahora() - timedelta(seconds=1)
    sesion.flush()


# --- Solicitud ---


def test_crear_parcela_solicita_un_analisis_por_fuente(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    filas = _filas(sesion, parcela)
    assert sorted(f.fuente for f in filas) == ["gfw", "whisp"]
    assert {f.estado for f in filas} == {"pendiente"}
    assert {f.solicitado_por for f in filas} == {None}
    auditoria = sesion.query(Auditoria).filter_by(accion="analisis.solicitar").one()
    assert auditoria.usuario_id is None  # lo lanzó el sistema


def test_sin_clave_de_whisp(api, sesion, operador, productor, fuentes):
    fuentes["whisp"]._clave = None
    parcela = _parcela(api, sesion, operador, productor)
    assert [f.fuente for f in _filas(sesion, parcela)] == ["gfw"]
    estado = {f["fuente"]: f["configurada"] for f in api.get("/analisis/fuentes").json()}
    assert estado == {"whisp": False, "gfw": True}


def test_repetir_analisis_a_pedido(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    respuesta = api.post(f"/parcelas/{parcela.id}/analisis")
    assert respuesta.status_code == 202
    assert len(respuesta.json()["analisis"]) == 2
    assert len(_filas(sesion, parcela)) == 4  # nunca se sobrescribe: se agregan filas
    assert sesion.query(Auditoria).filter_by(accion="analisis.solicitar", usuario_id=operador.id).count() == 1


def test_el_lector_y_el_productor_no_solicitan(api, sesion, coop, operador):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _parcela(api, sesion, operador, productor)
    lector = factorias.perfil(sesion, "lector", coop)
    assert api.como(lector).post(f"/parcelas/{parcela.id}/analisis").status_code == 403
    assert api.como(cuenta).post(f"/parcelas/{parcela.id}/analisis").status_code == 403


# --- Cola y fallos ---


def test_whisp_responde_500_tres_veces(api, sesion, operador, productor, simulado, fuentes, storage_falso):
    parcela = _parcela(api, sesion, operador, productor)
    sesion.query(AnalisisCobertura).filter_by(fuente="gfw").delete()
    simulado.whisp = [httpx.Response(500, json={"code": "analysis_error", "message": "x"}) for _ in range(3)]
    for _ in range(3):
        _ya(sesion)
        assert _procesar(sesion, fuentes, storage_falso)
    fila = _filas(sesion, parcela, "whisp")[0]
    assert (fila.estado, fila.intentos) == ("error", 3)
    assert "500" in fila.error_detalle
    assert fila.resultado_fuente is None and fila.respuesta_documento_id is None
    assert not _procesar(sesion, fuentes, storage_falso)


def test_whisp_responde_429_y_se_respeta_la_espera(
    api, sesion, operador, productor, simulado, fuentes, storage_falso
):
    parcela = _parcela(api, sesion, operador, productor)
    sesion.query(AnalisisCobertura).filter_by(fuente="gfw").delete()
    simulado.whisp = [
        httpx.Response(
            429,
            json={
                "code": "auth_rate_limit_exceeded",
                "message": "Rate limit exceeded. Try again in 40 seconds.",
            },
        )
    ]
    assert _procesar(sesion, fuentes, storage_falso)
    fila = _filas(sesion, parcela, "whisp")[0]
    assert fila.estado == "pendiente"
    espera = (fila.reintentar_en - ahora()).total_seconds()
    assert 35 < espera <= 41
    # Antes de que pase la espera no se vuelve a intentar.
    assert not _procesar(sesion, fuentes, storage_falso)


def test_punto_se_envia_como_circulo_a_gfw(api, sesion, operador, productor):
    parcela = _parcela(
        api, sesion, operador, productor, punto(), area_declarada_ha="3", area_cultivada_ha="2"
    )
    whisp, gfw = _filas(sesion, parcela, "whisp")[0], _filas(sesion, parcela, "gfw")[0]
    assert whisp.es_aproximacion is False
    assert gfw.es_aproximacion is True
    circulo = sesion.scalar(
        text("SELECT ST_Area(geometria::geography) FROM analisis_cobertura WHERE id = :i"),
        {"i": gfw.id},
    )
    assert abs(circulo / 10_000 - 3) < 0.1  # un círculo de 3 ha


def test_a_las_fuentes_no_va_ningun_dato_personal(
    api, sesion, operador, productor, simulado, fuentes, storage_falso
):
    _parcela(api, sesion, operador, productor)
    simulado.whisp = [httpx.Response(500, json={})]
    simulado.gfw = [httpx.Response(500, json={})]
    _procesar(sesion, fuentes, storage_falso)
    _procesar(sesion, fuentes, storage_falso)
    assert len(simulado.peticiones) == 2
    for peticion in simulado.peticiones:
        cuerpo = peticion.content.decode()
        for dato in ("81234567", "Nombre Secreto", "Apellido Secreto", "Coop Secreta"):
            assert dato not in cuerpo
        assert "geometry" in cuerpo


# --- Vigencia, obsolescencia y recuperación ---


def test_cambiar_la_geometria_deja_obsoletos_los_analisis(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    sesion.query(AnalisisCobertura).delete()
    analisis_completado(sesion, parcela, "whisp")
    analisis_completado(sesion, parcela, "gfw")
    assert all(a["vigente"] for a in api.get(f"/parcelas/{parcela.id}/analisis").json())
    api.patch(
        f"/parcelas/{parcela.id}", json={"geometria": rectangulo(100, 120), "motivo": "Lindero corregido."}
    )
    lista = api.get(f"/parcelas/{parcela.id}/analisis").json()
    completados = [a for a in lista if a["estado"] == "completado"]
    assert all(a["obsoleto"] and not a["vigente"] for a in completados)
    assert sorted(a["fuente"] for a in lista if a["estado"] == "pendiente") == ["gfw", "whisp"]


def test_analisis_mas_viejo_que_la_vigencia(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    analisis_completado(sesion, parcela, "whisp", hace=timedelta(days=181))
    viejo = next(a for a in api.get(f"/parcelas/{parcela.id}/analisis").json() if a["estado"] == "completado")
    assert viejo["vigente"] is False and viejo["obsoleto"] is False
    assert "sin_analisis_vigente" in api.get(f"/parcelas/{parcela.id}").json()["alertas"]


def test_al_arrancar_lo_atascado_vuelve_a_la_cola(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    fila = _filas(sesion, parcela, "whisp")[0]
    fila.estado = "en_proceso"
    sesion.flush()
    sesion.execute(
        text("UPDATE analisis_cobertura SET actualizado_en = now() - interval '20 minutes' WHERE id = :i"),
        {"i": fila.id},
    )
    analisis.recuperar_atascados(sesion)
    sesion.refresh(fila)
    assert fila.estado == "pendiente"


def test_tarea_diaria_renueva_15_dias_antes(api, sesion, operador, productor, fuentes):
    parcela = _parcela(api, sesion, operador, productor)
    sesion.query(AnalisisCobertura).delete()
    analisis_completado(sesion, parcela, "whisp", hace=timedelta(days=170))
    analisis_completado(sesion, parcela, "gfw", hace=timedelta(days=10))
    assert analisis.renovar_por_caducar(sesion, fuentes) == 1
    pendientes = [f.fuente for f in _filas(sesion, parcela) if f.estado == "pendiente"]
    assert pendientes == ["whisp"]


def test_alertas_de_revision_y_error(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    analisis_completado(sesion, parcela, "whisp", resultado="more_info_needed")
    analisis_completado(
        sesion, parcela, "gfw", indicadores={"alertas_desde_2021": 3, "perdida_ha_total": 0.25}
    )
    alertas = api.get(f"/parcelas/{parcela.id}").json()["alertas"]
    assert "analisis_requiere_revision" in alertas
    tarjetas = {
        a["fuente"]: a
        for a in api.get(f"/parcelas/{parcela.id}/analisis").json()
        if a["estado"] == "completado"
    }
    assert tarjetas["whisp"]["resultado_texto"] == "Whisp: requiere más información"
    assert tarjetas["gfw"]["resultado_texto"] == "GFW: 3 alertas y 0.25 ha de pérdida desde 2021"


def test_respuesta_que_no_se_puede_interpretar(
    api, sesion, operador, productor, simulado, fuentes, storage_falso
):
    """La respuesta queda guardada como evidencia, sin resultado, y pide revisión en campo."""
    parcela = _parcela(api, sesion, operador, productor)
    sesion.query(AnalisisCobertura).filter_by(fuente="whisp").delete()
    forma_inesperada = {"data": [{"otra_columna": 1}], "status": "success"}
    simulado.gfw = [httpx.Response(200, json=forma_inesperada) for _ in range(2)]
    assert _procesar(sesion, fuentes, storage_falso)
    fila = _filas(sesion, parcela, "gfw")[0]
    assert fila.estado == "completado"
    assert fila.respuesta_documento_id is not None
    assert fila.error_detalle.startswith("La respuesta no se pudo interpretar")
    assert fila.indicadores == {}
    assert "analisis_requiere_revision" in api.get(f"/parcelas/{parcela.id}").json()["alertas"]
    # El personal la descarga como archivo, con la fuente y el código de la parcela en el nombre.
    url = api.get(f"/analisis/{fila.id}").json()["respuesta_url"]
    assert f"download=gfw-{parcela.codigo}-" in url and url.endswith(".json")


def test_el_productor_no_recibe_la_respuesta_completa(api, sesion, coop, operador):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _parcela(api, sesion, operador, productor)
    analisis_completado(sesion, parcela, "whisp")
    tarjetas = api.como(cuenta).get(f"/mi/parcelas/{parcela.id}/analisis").json()
    assert tarjetas and all(t["respuesta_documento_id"] is None for t in tarjetas)


def test_otra_cooperativa_no_ve_los_analisis(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    fila = _filas(sesion, parcela)[0]
    admin_b = factorias.perfil(sesion, "admin_cooperativa", factorias.cooperativa(sesion, "Coop B"))
    api.como(admin_b)
    assert api.get(f"/parcelas/{parcela.id}/analisis").status_code == 404
    assert api.get(f"/analisis/{fila.id}").status_code == 404
    assert api.post(f"/parcelas/{parcela.id}/analisis").status_code == 404


# --- Frases prohibidas ---

PROHIBIDAS = re.compile(
    r"constancia de no deforestaci|libre de deforestaci|certificad[oa]s?\b|aprobad[oa]s?\b|\bconforme\b",
    re.IGNORECASE,
)


def test_ninguna_frase_prohibida_en_el_codigo():
    archivos = [
        *(RAIZ / "frontend").rglob("*.js"),
        *(RAIZ / "frontend").rglob("*.html"),
        *(RAIZ / "frontend").rglob("*.css"),
        *(RAIZ / "backend" / "app").rglob("*.py"),
    ]
    encontradas = [
        f"{a.relative_to(RAIZ)}: {m.group(0)}"
        for a in archivos
        for m in PROHIBIDAS.finditer(a.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert encontradas == []
