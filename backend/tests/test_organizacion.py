"""Adenda 6: expediente de la organización por tipo, política, actuaciones de diligencia, cuadro de señales y
lista de productos.

Las pruebas de la sección 13 que no pasan por un lote; las del lote, la declaración aduanera, los hallazgos y
el DEX están en tests/test_dex.py.
"""

import json
import re
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import textos
from app.catalogos import actuaciones, requisitos_organizacion
from app.fechas import ahora, hoy_lima
from app.models import Auditoria, DeclaracionProducto, Parcela
from app.pdf import declaracion_productor as hoja_declaracion
from app.pdf import politica_organizacion as hoja_politica
from app.services import diligencia
from app.services.hallazgos import organizacion as reglas
from app.services.legalidad import sumar_meses
from tests import factorias
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import PDF, RESPUESTAS_FAMILIA, declarar_anual, incidencia
from tests.organizacion_util import DESCRIPCION, RESULTADO, actuacion, documento, politica
from tests.test_analisis import PROHIBIDAS

CALIFICA = re.compile(r"\b(cumple|incumple|cumplen|incumplen|complies|compliant)\b", re.IGNORECASE)
AGROQUIMICOS = {
    "quien_trabaja": "solo_familia",
    "menores_trabajan": "no",
    "usa_agroquimicos": "si",
    "productos": [{"nombre": "Herbicida X", "tipo": "herbicida"}],
    "quien_aplica": "yo_o_mi_familia",
    "destino_envases": "devuelve_o_centro_de_acopio",
    "ventas_superan_75_uit": "no",
}


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def otra(sesion):
    return factorias.cooperativa(sesion, "Otra Coop", codigo="OTR")


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
def admin_otra(sesion, otra):
    return factorias.perfil(sesion, "admin_cooperativa", otra)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _documento_api(api, tipo, fecha_emision, **extra):
    return api.post(
        "/cooperativa/documentos",
        data={
            "tipo": tipo,
            "numero": "N-1",
            "entidad_emisora": "SUNAT",
            "fecha_emision": fecha_emision,
            **extra,
        },
        files={
            "archivo": (f"{tipo}.pdf", PDF + tipo.encode() + str(fecha_emision).encode(), "application/pdf")
        },
    )


def _politica_api(api, temas, adoptada_en=None, organo="Consejo Directivo", n=0):
    return api.post(
        "/cooperativa/politicas",
        data={"temas": list(temas), "adoptada_en": str(adoptada_en or hoy_lima()), "organo": organo},
        files={"archivo": ("politica.pdf", PDF + f"politica {n}".encode(), "application/pdf")},
    )


def _actuacion_api(api, **datos):
    cuerpo = {
        "tipo": "capacitacion",
        "temas": ["integridad"],
        "fecha": str(hoy_lima()),
        "descripcion": DESCRIPCION,
        "resultado": RESULTADO,
        **datos,
    }
    return api.post("/actuaciones", json=cuerpo)


# ---------- Expediente de la organización (sección 4) ----------


def test_asociacion_ve_solo_lo_que_le_toca(api, sesion, coop, admin):
    coop.tipo_organizacion = "asociacion"
    sesion.flush()
    exp = api.como(admin).get("/cooperativa/expediente").json()
    assert [c["codigo"] for c in exp["casillas"]] == [
        "ficha_ruc",
        "partida_sunarp",
        "vigencia_poderes",
        "renta_anual",
    ]
    identidad = {c["codigo"]: c["frena_lote"] for c in exp["casillas"]}
    assert identidad == {
        "ficha_ruc": True,
        "partida_sunarp": True,
        "vigencia_poderes": True,
        "renta_anual": False,
    }
    requisitos = {r["codigo"]: r for r in exp["requisitos"]}
    assert set(requisitos) == {"identidad", "tributos", "registro_cooperativas", "integridad", "actuaciones"}
    assert requisitos["registro_cooperativas"]["estado"] == "no_aplica"
    assert requisitos["identidad"]["bloquea"] and not requisitos["tributos"]["bloquea"]
    assert exp["anteriores"] == [] and "rnca" not in json.dumps(exp["casillas"])
    assert exp["estado"] == "incompleto" and exp["faltan"] == [
        "ficha_ruc",
        "partida_sunarp",
        "vigencia_poderes",
    ]
    # El registro de cooperativas no se carga en una asociación.
    respuesta = _documento_api(api, "rnca", "2026-01-10")
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "tipo_no_aplica"


def test_cooperativa_agraria_y_los_que_salen(api, sesion, coop, admin, operador):
    api.como(admin)
    exp = api.get("/cooperativa/expediente").json()
    assert [c["codigo"] for c in exp["casillas"]] == [
        "ficha_ruc",
        "partida_sunarp",
        "vigencia_poderes",
        "renta_anual",
        "rnca",
    ]
    for tipo in ("ruc_comercio_exterior", "registro_aduanas"):
        respuesta = _documento_api(api, tipo, "2026-01-10")
        assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "tipo_anterior"
    # Uno cargado antes de la adenda se ve como documento anterior y no cuenta para nada.
    documento(sesion, coop.id, "cooperativa", coop.id, "ruc_comercio_exterior", admin, numero="CE-1")
    exp = api.get("/cooperativa/expediente").json()
    assert [a["codigo"] for a in exp["anteriores"]] == ["ruc_comercio_exterior"]
    assert exp["anteriores"][0]["anterior"] and not exp["anteriores"][0]["frena_lote"]
    assert "ruc_comercio_exterior" not in [c["codigo"] for c in exp["casillas"]]
    # Un rnca de una organización que deja de ser cooperativa agraria también pasa a anteriores.
    documento(sesion, coop.id, "cooperativa", coop.id, "rnca", admin, numero="R-1", fecha_emision=hoy_lima())
    coop.tipo_organizacion = "empresa"
    sesion.flush()
    exp = api.get("/cooperativa/expediente").json()
    assert {a["codigo"] for a in exp["anteriores"]} == {"rnca", "ruc_comercio_exterior"}
    # Solo el administrador carga.
    assert _documento_api(api.como(operador), "ficha_ruc", "2026-01-10").status_code == 403


def test_renta_anual_vence_sola(api, sesion, admin):
    api.como(admin)
    presentada = sumar_meses(hoy_lima(), -19)
    respuesta = _documento_api(api, "renta_anual", str(presentada))
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["fecha_vencimiento"] == str(sumar_meses(presentada, 18))
    exp = api.get("/cooperativa/expediente").json()
    renta = next(c for c in exp["casillas"] if c["codigo"] == "renta_anual")
    assert renta["estado"] == "vencido" and renta["vence_solo"]
    tributos = next(r for r in exp["requisitos"] if r["codigo"] == "tributos")
    assert tributos["estado"] == "sin_sustento"  # además falta la ficha RUC
    reciente = _documento_api(api, "renta_anual", str(hoy_lima() - timedelta(days=30)))
    assert reciente.status_code == 201
    renta = next(
        c for c in api.get("/cooperativa/expediente").json()["casillas"] if c["codigo"] == "renta_anual"
    )
    assert renta["estado"] == "vigente"


# ---------- Política (sección 5) ----------


def test_politica_por_temas(api, sesion, coop, admin, operador, lector):
    api.como(admin)
    tres = _politica_api(api, ["integridad", "no_fraude", "trabajo_digno"], n=1)
    assert tres.status_code == 201, tres.text
    salida = tres.json()
    estados = {t["codigo"]: t["estado"] for t in salida["temas"]}
    assert estados == {
        "integridad": "sustentado",
        "no_fraude": "sustentado",
        "canal_denuncias": "sin_sustento",
        "trabajo_digno": "sustentado",
        "revision_de_documentos": "sin_sustento",
    }
    assert salida["requisito"]["estado"] == "sin_sustento"
    assert salida["requisito"]["falta_codigos"] == ["canal_denuncias", "revision_de_documentos"]
    # El hallazgo lista los dos que faltan.
    d = SimpleNamespace(sesion=sesion, cooperativa=coop, hoy=hoy_lima())
    [hallazgo] = reglas.politica_incompleta(d)
    assert hallazgo.datos["codigos_temas"] == ["canal_denuncias", "revision_de_documentos"]
    assert "Canal de quejas y denuncias" in hallazgo.hecho()["es"]
    # Dos políticas que juntas cubren los cinco temas, pero sin el contacto del canal.
    otra = _politica_api(api, ["canal_denuncias", "revision_de_documentos"], n=2).json()
    canal = next(t for t in otra["temas"] if t["codigo"] == "canal_denuncias")
    assert canal["estado"] == "sin_sustento" and "contacto" in canal["falta"]
    [hallazgo] = reglas.politica_incompleta(d)
    assert "falta el contacto del canal" in hallazgo.hecho()["es"]
    assert (
        api.patch("/cooperativa", json={"canal_denuncias_contacto": "Buzón en la oficina"}).status_code == 200
    )
    salida = api.get("/cooperativa/politicas").json()
    assert salida["requisito"]["estado"] == "sustentado" and reglas.politica_incompleta(d) == []
    assert salida["canal_denuncias_contacto"] == "Buzón en la oficina"
    # Una política anulada deja de contar y se conserva.
    segunda = next(p for p in salida["politicas"] if "canal_denuncias" in p["temas"])
    anular = api.post(
        f"/cooperativa/politicas/{segunda['id']}/anular", json={"motivo": "Se cargó por error."}
    )
    assert anular.status_code == 200
    salida = anular.json()
    assert salida["requisito"]["estado"] == "sin_sustento" and len(salida["politicas"]) == 2
    assert not next(p for p in salida["politicas"] if p["id"] == segunda["id"])["vigente"]
    repetida = api.post(
        f"/cooperativa/politicas/{segunda['id']}/anular", json={"motivo": "Otra vez lo mismo."}
    )
    assert repetida.status_code == 400
    # El archivo de la política no se anula por su cuenta.
    doc_id = salida["politicas"][0]["documento"]["id"]
    assert api.post(f"/documentos/{doc_id}/anular", json={"motivo": "Prueba de anulación"}).status_code == 400
    # Validaciones, permisos y auditoría.
    assert _politica_api(api, [], n=3).status_code == 422
    assert (
        _politica_api(api, ["integridad"], adoptada_en=hoy_lima() + timedelta(days=1), n=4).status_code == 422
    )
    assert _politica_api(api.como(operador), ["integridad"], n=5).status_code == 403
    assert api.como(lector).get("/cooperativa/politicas").status_code == 200
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert acciones.count("politica.cargar") == 2 and "politica.anular" in acciones


@pytest.mark.parametrize(
    ("tipo", "organo"),
    [
        ("cooperativa_agraria", "el Consejo de Administración"),
        ("asociacion", "el Consejo Directivo"),
        ("empresa", "el Directorio o la Gerencia General"),
    ],
)
def test_plantilla_de_la_politica(api, sesion, coop, admin, operador, tipo, organo):
    coop.tipo_organizacion = tipo
    coop.canal_denuncias_contacto = "WhatsApp 900 000 000"
    sesion.flush()
    respuesta = api.como(admin).get("/cooperativa/politica/hoja")
    assert respuesta.status_code == 200 and respuesta.content.startswith(b"%PDF")
    escrito = " ".join(hoja_politica.documento(diligencia.datos_politica(coop)).textos)
    assert coop.razon_social in escrito and coop.ruc in escrito and organo in escrito
    assert "WhatsApp 900 000 000" in escrito and "Versión 1" in escrito
    assert not PROHIBIDAS.search(escrito) and not CALIFICA.search(escrito)
    assert api.como(operador).get("/cooperativa/politica/hoja").status_code == 403


def test_el_contacto_del_canal_llega_al_productor(api, sesion, coop, admin):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    cuenta.debe_cambiar_clave = False
    productor.consentimiento_datos_en = hoy_lima()
    productor.consentimiento_origen = "productor"
    sesion.flush()
    assert api.como(cuenta).get("/mi/productor").json()["canal_denuncias_contacto"] is None
    api.como(admin).patch("/cooperativa", json={"canal_denuncias_contacto": "Correo quejas@prueba.test"})
    assert (
        api.como(cuenta).get("/mi/productor").json()["canal_denuncias_contacto"]
        == "Correo quejas@prueba.test"
    )
    # La hoja de la declaración anual lo imprime antes de la firma.
    datos = {
        "productor": "Demo Productor",
        "organizacion": coop.razon_social,
        "canal": "Correo quejas@prueba.test",
    }
    escrito = hoja_declaracion.documento(datos, [], version_cuestionario=1).textos
    canal = next(i for i, t in enumerate(escrito) if "Correo quejas@prueba.test" in t)
    firma = next(i for i, t in enumerate(escrito) if t.startswith("Firma:"))
    assert canal < firma
    assert not any("quejas" in t for t in hoja_declaracion.documento({}, [], version_cuestionario=1).textos)
    # El contacto se valida: de 3 a 200 caracteres.
    assert (
        api.como(admin).patch("/cooperativa", json={"canal_denuncias_contacto": "x" * 201}).status_code == 422
    )


# ---------- Actuaciones y señales (sección 6) ----------


def test_cuadro_de_senales(api, sesion, coop, admin, operador, productor):
    vecino = factorias.productor(sesion, coop)
    declarar_anual(sesion, productor, operador, AGROQUIMICOS)
    declarar_anual(sesion, vecino, operador, RESPUESTAS_FAMILIA)
    cuadro = api.como(operador).get("/cooperativa/diligencia").json()
    senales = {s["codigo"]: s for s in cuadro["senales"]}
    assert list(senales) == list(actuaciones.CODIGOS_TEMAS)
    assert senales["integridad"]["esperada"] and senales["integridad"]["cuenta"] is None
    agro = senales["agroquimicos_y_envases"]
    assert (
        agro["esperada"] and agro["cuenta"] == 1 and agro["texto"] == "1 productor declara usar agroquímicos"
    )
    # Nadie contrata, ninguna parcela en área protegida, nada de menores: no se espera.
    for tema in ("trabajo", "areas_protegidas", "derechos_humanos", "tenencia", "tierra_forestal", "agua"):
        assert not senales[tema]["esperada"] and senales[tema]["estado"] == "no_se_espera", tema
    assert cuadro["requisito"]["estado"] == "sin_sustento"
    assert cuadro["requisito"]["falta_codigos"] == ["integridad", "agroquimicos_y_envases"]
    d = SimpleNamespace(sesion=sesion, cooperativa=coop, hoy=hoy_lima())
    [hallazgo] = reglas.sin_actuaciones_de_diligencia(d)
    assert "Agroquímicos y envases (1 productor declara usar agroquímicos)" in hallazgo.hecho()["es"]
    assert hallazgo.entrada.grupo == "no_verificado" and hallazgo.entrada.etapa == 3
    # Un productor que declara menores: se espera una actuación de derechos humanos.
    declarar_anual(
        sesion,
        vecino,
        operador,
        {
            **RESPUESTAS_FAMILIA,
            "menores_trabajan": "si_de_la_familia",
            "menor_edad_minima": 14,
            "menores_van_a_la_escuela": "si",
        },
    )
    senales = {s["codigo"]: s for s in api.get("/cooperativa/diligencia").json()["senales"]}
    assert senales["derechos_humanos"]["esperada"] and senales["derechos_humanos"]["cuenta"] == 1
    # Una incidencia de tenencia en el último año hace esperar una actuación de tenencia.
    parcela = crear_parcela(api.como(operador), productor.id, rectangulo(100, 100)).json()
    incidencia(sesion, sesion.get(Parcela, uuid.UUID(parcela["id"])), operador)
    senales = {s["codigo"]: s for s in api.get("/cooperativa/diligencia").json()["senales"]}
    assert senales["tenencia"]["cuenta"] == 1 and senales["tenencia"]["esperada"]
    # Una capacitación registrada hoy atiende sus temas.
    registrada = _actuacion_api(api, temas=["integridad", "agroquimicos_y_envases"])
    assert registrada.status_code == 201, registrada.text
    senales = {s["codigo"]: s for s in api.get("/cooperativa/diligencia").json()["senales"]}
    assert senales["agroquimicos_y_envases"]["estado"] == "sustentado"
    assert senales["agroquimicos_y_envases"]["actuaciones_vigentes"] == 1
    assert senales["agroquimicos_y_envases"]["ultima"] == str(hoy_lima())
    # Una de hace 13 meses no cuenta.
    actuacion(sesion, coop, admin, temas=("tenencia",), fecha=sumar_meses(hoy_lima(), -13))
    senales = {s["codigo"]: s for s in api.get("/cooperativa/diligencia").json()["senales"]}
    assert senales["tenencia"]["estado"] == "sin_sustento"


def test_registrar_una_actuacion(api, sesion, coop, admin, operador, lector, productor, storage_falso):
    api.como(operador)
    # La consulta a partes interesadas pide con quién se habló.
    sin_contraparte = _actuacion_api(api, tipo="consulta_a_partes_interesadas")
    assert sin_contraparte.status_code == 422
    assert sin_contraparte.json()["error"]["codigo"] == "contraparte_requerida"
    assert _actuacion_api(api, fecha=str(hoy_lima() + timedelta(days=1))).status_code == 422
    assert _actuacion_api(api, descripcion="Muy corta").status_code == 422
    assert _actuacion_api(api, temas=[]).status_code == 422
    assert _actuacion_api(api, departamento="SAN MARTIN").status_code == 422
    ajeno = factorias.productor(sesion, factorias.cooperativa(sesion, "Ajena"))
    respuesta = _actuacion_api(api, productor_ids=[str(ajeno.id)])
    assert respuesta.status_code == 422 and respuesta.json()["error"]["codigo"] == "productor_no_afiliado"
    # Una revisión de fuente pública, con su fuente, su lugar y el productor que alcanzó.
    respuesta = _actuacion_api(
        api,
        tipo="revision_de_fuente_publica",
        temas=["agroquimicos_y_envases", "agua"],
        contraparte="OEFA, administrados sancionados",
        departamento="san martin",
        provincia="picota",
        distrito="picota",
        participantes=12,
        productor_ids=[str(productor.id)],
    )
    assert respuesta.status_code == 201, respuesta.text
    ficha = respuesta.json()
    assert ficha["nivel"] == "declarado" and ficha["vigente"] and ficha["departamento"] == "SAN MARTIN"
    assert [p["id"] for p in ficha["productores_alcanzados"]] == [str(productor.id)]
    assert ficha["vigente_hasta"] == str(sumar_meses(hoy_lima(), 12))
    # Con evidencia, documentado.
    evidencia = api.post(
        f"/actuaciones/{ficha['id']}/evidencias",
        files={"archivo": ("asistencia.pdf", PDF + b"asistencia", "application/pdf")},
    )
    assert evidencia.status_code == 201, evidencia.text
    assert evidencia.json()["nivel"] == "documentado" and len(evidencia.json()["documentos"]) == 1
    # Aparece en la ficha del productor, y en la lista con sus filtros.
    del_productor = api.get("/actuaciones", params={"productor_id": str(productor.id)}).json()
    assert [a["id"] for a in del_productor] == [ficha["id"]]
    assert api.get("/actuaciones", params={"tema": "agua"}).json()[0]["id"] == ficha["id"]
    assert api.get("/actuaciones", params={"tema": "trabajo"}).json() == []
    assert api.get("/actuaciones", params={"tipo": "capacitacion"}).json() == []
    assert api.get("/actuaciones", params={"desde": str(hoy_lima() + timedelta(days=1))}).json() == []
    # El lector solo ve; el operador no anula.
    assert api.como(lector).get(f"/actuaciones/{ficha['id']}").status_code == 200
    assert _actuacion_api(api.como(lector)).status_code == 403
    motivo = {"motivo": "Se registró dos veces."}
    assert api.como(operador).post(f"/actuaciones/{ficha['id']}/anular", json=motivo).status_code == 403
    anulada = api.como(admin).post(f"/actuaciones/{ficha['id']}/anular", json=motivo)
    assert anulada.status_code == 200 and anulada.json()["anulada_en"] and not anulada.json()["vigente"]
    # Se conserva, y deja de contar.
    assert len(api.get("/actuaciones").json()) == 1
    assert diligencia.actuaciones_vigentes(sesion, coop.id) == []
    assert api.post(f"/actuaciones/{ficha['id']}/anular", json=motivo).status_code == 400
    sin_evidencia = api.post(
        f"/actuaciones/{ficha['id']}/evidencias",
        files={"archivo": ("foto.pdf", PDF + b"foto", "application/pdf")},
    )
    assert sin_evidencia.status_code == 400
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert {"actuacion.registrar", "actuacion.anular", "documento.cargar"} <= set(acciones)


def test_aislamiento(api, sesion, coop, admin, admin_otra, storage_falso):
    propia = politica(sesion, coop, admin)
    act = actuacion(sesion, coop, admin)
    evidencia = documento(sesion, coop.id, "actuacion", act.id, "evidencia_actuacion", admin)
    api.como(admin_otra)
    assert api.get(f"/actuaciones/{act.id}").status_code == 404
    assert api.post(f"/actuaciones/{act.id}/anular", json={"motivo": "Intento de otra"}).status_code == 404
    archivo = {"archivo": ("x.pdf", PDF + b"x", "application/pdf")}
    assert api.post(f"/actuaciones/{act.id}/evidencias", files=archivo).status_code == 404
    assert (
        api.post(f"/cooperativa/politicas/{propia.id}/anular", json={"motivo": "Intento de otra"}).status_code
        == 404
    )
    assert api.get(f"/documentos/{evidencia.id}/url").status_code == 404
    assert api.get("/actuaciones").json() == []
    assert api.get("/cooperativa/politicas").json()["politicas"] == []


def test_politicas_y_actuaciones_no_se_editan_ni_se_borran(sesion, coop, admin, productor):
    fila = politica(sesion, coop, admin)
    act = actuacion(sesion, coop, admin, productores=(productor.id,))
    for sentencia in (
        "UPDATE politicas_organizacion SET temas = ARRAY['integridad'] WHERE id = :id",
        "DELETE FROM politicas_organizacion WHERE id = :id",
    ):
        with pytest.raises(DBAPIError), sesion.begin_nested():
            sesion.execute(text(sentencia), {"id": fila.id})
    for sentencia in (
        "UPDATE actuaciones_diligencia SET resultado = 'Otro resultado distinto del original' WHERE id = :id",
        "DELETE FROM actuaciones_diligencia WHERE id = :id",
        "DELETE FROM actuacion_productores WHERE actuacion_id = :id",
    ):
        with pytest.raises(DBAPIError), sesion.begin_nested():
            sesion.execute(text(sentencia), {"id": act.id})
    # Anular sí, una vez.
    with sesion.begin_nested():
        sesion.execute(
            text(
                "UPDATE actuaciones_diligencia SET anulada_en = now(), anulada_por = :p, "
                "motivo_anulacion = 'x' WHERE id = :id"
            ),
            {"id": act.id, "p": admin.id},
        )
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(
            text("UPDATE actuaciones_diligencia SET motivo_anulacion = 'otro' WHERE id = :id"), {"id": act.id}
        )


# ---------- Lista de productos (sección 6.6) ----------


def test_lista_de_productos(api, sesion, coop, admin, operador, productor):
    vecino = factorias.productor(sesion, coop)
    declarar_anual(sesion, productor, operador, AGROQUIMICOS, revisiones={"Herbicida X": "figura"})
    declarar_anual(
        sesion,
        vecino,
        operador,
        {
            **AGROQUIMICOS,
            "productos": [
                {"nombre": "HERBICIDA X", "tipo": "herbicida"},
                {"nombre": "Abono Y", "tipo": "fertilizante"},
            ],
        },
        revisiones={"HERBICIDA X": "no_figura"},
    )
    # La revisión del vecino es la más reciente.
    reciente = sesion.scalar(select(DeclaracionProducto).where(DeclaracionProducto.nombre == "HERBICIDA X"))
    reciente.revisado_en = ahora() + timedelta(minutes=5)
    sesion.flush()
    lista = api.como(operador).get("/cooperativa/productos-revisados").json()
    por_nombre = {cuestionario_normalizar(p["nombre"]): p for p in lista["productos"]}
    assert set(por_nombre) == {"herbicida x", "abono y"}
    herbicida = por_nombre["herbicida x"]
    # Una vez, con su revisión más reciente y los dos productores que lo declaran.
    assert herbicida["productores"] == 2 and herbicida["revision"] == "no_figura"
    assert por_nombre["abono y"]["revision"] == "sin_revisar" and por_nombre["abono y"]["revisado_en"] is None
    assert len(lista["consultas"]) == 2
    hoja = api.get("/cooperativa/productos-revisados/hoja")
    assert hoja.status_code == 200 and hoja.content.startswith(b"%PDF")
    figuran = [
        {
            "nombre": "Herbicida X",
            "tipo": "Herbicida",
            "registro": "PQUA N.° 1",
            "fecha": "01/10/2026",
            "productores": 1,
        }
    ]
    escrito = " ".join(
        hoja_politica.documento_productos(
            "Coop", hoy_lima(), figuran, [], (("https://x.test", "Registro"),)
        ).textos
    )
    assert "Esta lista no reemplaza la consulta del registro" in escrito and "Herbicida X" in escrito
    assert not re.search(r"autorizad|prohibid", escrito, re.IGNORECASE)


def cuestionario_normalizar(nombre: str) -> str:
    from app.catalogos.declaracion_productor import normalizar_nombre

    return normalizar_nombre(nombre)


# ---------- Textos (sección 13) ----------


def test_los_textos_nuevos_no_califican():
    piezas = []
    for idioma in textos.IDIOMAS:
        datos = textos.cargar(idioma)
        piezas.append(json.dumps(datos["organizacion"], ensure_ascii=False))
        for codigo in reglas.REGLAS:
            nombre = codigo.__name__
            piezas += [datos["hallazgo"][nombre], datos["mensaje"][nombre]]
        piezas += [
            v
            for k, v in datos["pdf"].items()
            if k in ("organizacion", "organizacion_sub", "senales", "canal")
        ]
    from app.pdf.declaracion_tenencia import textos as plantillas

    piezas.append(json.dumps(plantillas()["politica_organizacion"], ensure_ascii=False))
    piezas += [r.nombre + r.que_pide for r in requisitos_organizacion.REQUISITOS]
    piezas += [t.nombre + t.que_dice for t in requisitos_organizacion.TEMAS_POLITICA]
    piezas += [t.nombre + t.que_es + t.ejemplos for t in actuaciones.TIPOS]
    for pieza in piezas:
        assert not PROHIBIDAS.search(pieza), pieza
        assert not CALIFICA.search(pieza), pieza
