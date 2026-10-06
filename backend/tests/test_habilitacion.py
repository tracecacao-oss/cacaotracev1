"""Parte 4: procedencia y compuerta de habilitación (con la revisión de imágenes de la adenda 2)."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.fechas import hoy_lima
from app.models import Auditoria, DecisionHabilitacion, Documento, Parcela
from tests import factorias
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import (
    PDF,
    analisis_completado,
    documento_legal,
    expediente_completo,
    fuentes_configuradas,
    productor_listo,
    visita,
)
from tests.imagenes_util import revision

NOTA = "Se habilita: la revisión de imágenes muestra cacao bajo sombra antes y después del corte."


@pytest.fixture
def fuentes():
    return fuentes_configuradas()


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def admin(sesion, coop):
    return factorias.perfil(sesion, "admin_cooperativa", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _parcela(api, sesion, operador, productor, geometria=None, nombre="Parcela Demo") -> Parcela:
    datos = crear_parcela(api.como(operador), productor.id, geometria or rectangulo(100, 100), nombre=nombre)
    assert datos.status_code == 201, datos.text
    return sesion.get(Parcela, uuid.UUID(datos.json()["id"]))


def _lista(sesion, parcela, operador, productor, *, whisp="low"):
    """Todos los requisitos cumplidos salvo, si se pide, la revisión que exige Whisp."""
    expediente_completo(sesion, parcela, operador)
    productor_listo(sesion, productor, operador)
    analisis_completado(sesion, parcela, "whisp", resultado=whisp)
    analisis_completado(sesion, parcela, "gfw")


def _requisitos(api, parcela) -> dict:
    datos = api.get(f"/parcelas/{parcela.id}/habilitacion").json()
    return {r["codigo"]: r["cumple"] for r in datos["requisitos"]}


# ---------- Procedencia ----------


def test_procedencia_recorrida_en_campo(api, sesion, operador, productor):
    """Las visitas ya registradas siguen contando para la procedencia; ya no se registran nuevas."""
    parcela = _parcela(api, sesion, operador, productor)
    api.como(operador)
    assert api.get(f"/parcelas/{parcela.id}").json()["procedencia"]["recorrida_en_campo"] is False
    visita(sesion, parcela, operador, motivo="verificacion_de_coordenadas")
    procedencia = api.get(f"/parcelas/{parcela.id}").json()["procedencia"]
    assert procedencia["recorrida_en_campo"] is True
    assert procedencia["fecha_recorrido"] == str(hoy_lima())
    assert procedencia["registrada_por_rol"] == "operador"

    # Cambia la geometría después de la visita: el recorrido ya no vale.
    cambio = api.patch(
        f"/parcelas/{parcela.id}",
        json={"geometria": rectangulo(100, 120), "motivo": "Se corrigió el lindero norte."},
    )
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["procedencia"]["recorrida_en_campo"] is False


# ---------- Requisitos y decisión ----------


def test_el_operador_no_decide(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    assert api.como(operador).post(f"/parcelas/{parcela.id}/habilitar", json={}).status_code == 403


def test_habilitar_con_requisitos_sin_cumplir(api, sesion, operador, admin, productor):
    parcela = _parcela(api, sesion, operador, productor)
    respuesta = api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={})
    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "requisitos_incompletos"
    assert set(error["faltan"]) == {"analisis_vigente", "expediente_completo", "productor_listo"}


def test_sin_fuentes_configuradas_no_hay_analisis_vigente(api, sesion, operador, admin, productor, fuentes):
    for f in fuentes.values():
        f._clave = None
    parcela = _parcela(api, sesion, operador, productor)
    expediente_completo(sesion, parcela, operador)
    productor_listo(sesion, productor, operador)
    requisitos = _requisitos(api.como(admin), parcela)
    assert requisitos["analisis_vigente"] is False
    assert api.post(f"/parcelas/{parcela.id}/habilitar", json={}).status_code == 400


def test_revision_de_whisp_exige_revision_de_imagenes_y_nota(api, sesion, operador, admin, productor):
    parcela = _parcela(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor, whisp="more_info_needed")
    api.como(admin)
    assert "analisis_requiere_revision" in api.get(f"/parcelas/{parcela.id}").json()["alertas"]
    assert _requisitos(api, parcela)["revision_atendida"] is False

    # Adenda 2: una visita de campo ya no atiende la alerta; la atiende la revisión de imágenes.
    visita(sesion, parcela, operador, motivo="analisis_requiere_revision")
    assert _requisitos(api, parcela)["revision_atendida"] is False
    revision(sesion, parcela, admin)
    assert _requisitos(api, parcela)["revision_atendida"] is True
    sin_nota = api.post(f"/parcelas/{parcela.id}/habilitar", json={})
    assert sin_nota.status_code == 422
    assert sin_nota.json()["error"]["codigo"] == "nota_requerida"

    respuesta = api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "habilitada"
    decision = sesion.query(DecisionHabilitacion).filter_by(parcela_id=parcela.id).one()
    assert decision.decision == "habilitar"
    assert decision.decidida_por == admin.id
    # Guarda la copia de requisitos y alertas del momento.
    assert {r["codigo"] for r in decision.requisitos["requisitos"]} >= {
        "parcela_activa",
        "expediente_completo",
    }
    assert "analisis_requiere_revision" in decision.requisitos["alertas"]
    assert sesion.query(Auditoria).filter_by(accion="parcela.habilitar").count() == 1


def test_habilitada_cuyo_documento_vence_pasa_a_observada_y_vuelve(api, sesion, operador, admin, productor):
    parcela = _parcela(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor)
    api.como(admin)
    assert api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA}).json()["estado"] == "habilitada"

    titulo = sesion.query(Documento).filter_by(entidad_id=parcela.id, tipo="titulo_sunarp").one()
    titulo.fecha_vencimiento = hoy_lima() - timedelta(days=1)
    sesion.flush()
    assert api.get(f"/parcelas/{parcela.id}").json()["habilitacion_estado"] == "observada"
    observar = sesion.query(DecisionHabilitacion).filter_by(parcela_id=parcela.id, decision="observar").one()
    assert observar.decidida_por is None
    assert "expediente" in observar.nota.lower()

    # Se corrige el requisito y el administrador decide de nuevo.
    documento_legal(sesion, parcela, "titulo_sunarp", operador, vence=hoy_lima() + timedelta(days=365))
    assert api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA}).json()["estado"] == "habilitada"


def test_habilitada_cuya_geometria_cambia_pasa_a_observada(api, sesion, operador, admin, productor):
    parcela = _parcela(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor)
    api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA})
    cambio = api.patch(
        f"/parcelas/{parcela.id}",
        json={"geometria": rectangulo(100, 110), "motivo": "Se corrigió el lindero sur."},
    )
    assert cambio.json()["habilitacion_estado"] == "observada"


# ---------- Exclusión ----------


def test_excluir(api, sesion, operador, admin, productor):
    parcela = _parcela(api, sesion, operador, productor)
    evidencia = revision(
        sesion, parcela, admin, observacion_2020="bosque", observacion_cambio="cambio_visible"
    )
    api.como(admin)
    descripcion = "Las imágenes muestran bosque en 2020 y tala con quema en 2023 dentro del polígono."
    sin_evidencia = api.post(
        f"/parcelas/{parcela.id}/excluir", json={"descripcion": descripcion, "confirmacion": "EXCLUIR"}
    )
    assert sin_evidencia.status_code == 422
    sin_palabra = api.post(
        f"/parcelas/{parcela.id}/excluir",
        json={
            "descripcion": descripcion,
            "evidencia_revision_id": str(evidencia.id),
            "confirmacion": "excluir",
        },
    )
    assert sin_palabra.status_code == 422

    respuesta = api.post(
        f"/parcelas/{parcela.id}/excluir",
        json={
            "descripcion": descripcion,
            "evidencia_revision_id": str(evidencia.id),
            "confirmacion": "EXCLUIR",
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "excluida"

    # Ninguna vía la revierte ni la edita.
    for llamada in (
        lambda: api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA}),
        lambda: api.patch(f"/parcelas/{parcela.id}", json={"nombre": "Otro nombre"}),
        lambda: api.post(
            f"/parcelas/{parcela.id}/documentos",
            data={"tipo": "sunat", "numero": "1", "entidad_emisora": "SUNAT", "fecha_emision": "2020-01-01"},
            files={"archivo": ("ruc.pdf", PDF)},
        ),
        lambda: api.post(
            f"/parcelas/{parcela.id}/excluir", json={"descripcion": descripcion, "confirmacion": "EXCLUIR"}
        ),
    ):
        r = llamada()
        assert r.status_code == 400, r.text
        assert r.json()["error"]["codigo"] == "parcela_excluida"


def test_parcela_nueva_superpuesta_con_una_excluida(api, sesion, coop, operador, admin, productor):
    parcela = _parcela(api, sesion, operador, productor)
    evidencia = analisis_completado(
        sesion, parcela, "gfw", indicadores={"alertas_desde_2021": 12, "perdida_ha_total": 0.8}
    )
    api.como(admin).post(
        f"/parcelas/{parcela.id}/excluir",
        json={
            "descripcion": "Pérdida de bosque en 2022 confirmada por GFW y por el técnico en campo.",
            "evidencia_analisis_id": str(evidencia.id),
            "confirmacion": "EXCLUIR",
        },
    )
    vecina = _parcela(
        api, sesion, operador, factorias.productor(sesion, coop), rectangulo(100, 100, este_m=50)
    )
    assert "superposicion_con_excluida" in api.get(f"/parcelas/{vecina.id}").json()["alertas"]


def test_las_decisiones_no_se_editan_ni_se_borran(api, sesion, operador, admin, productor):
    parcela = _parcela(api, sesion, operador, productor)
    _lista(sesion, parcela, operador, productor)
    api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA})
    for sql in ("UPDATE decisiones_habilitacion SET nota = 'x'", "DELETE FROM decisiones_habilitacion"):
        with pytest.raises(DBAPIError), sesion.begin_nested():
            sesion.execute(text(sql))


# ---------- Resumen y productor ----------


def test_resumen_por_estado_y_por_vencer(api, sesion, operador, admin, productor):
    a = _parcela(api, sesion, operador, productor)
    _parcela(api, sesion, operador, productor, rectangulo(100, 100, norte_m=500), nombre="Parcela Dos")
    _lista(sesion, a, operador, productor)
    api.como(admin).post(f"/parcelas/{a.id}/habilitar", json={"nota": NOTA})
    documento_legal(sesion, a, "sunat", operador, vence=hoy_lima() + timedelta(days=5))
    resumen = api.get("/habilitacion/resumen").json()
    assert resumen["por_estado"] == {"pendiente": 1, "habilitada": 1, "observada": 0, "excluida": 0}
    assert [(p["tipo"], p["estado"]) for p in resumen["por_vencer"]] == []  # el sunat original sigue vigente

    sunat = sesion.query(Documento).filter_by(entidad_id=a.id, tipo="sunat").all()
    for d in sunat:
        d.fecha_vencimiento = hoy_lima() + timedelta(days=5)
    sesion.flush()
    resumen = api.get("/habilitacion/resumen").json()
    assert [(p["parcela_codigo"], p["tipo"], p["estado"]) for p in resumen["por_vencer"]] == [
        (a.codigo, "sunat", "por_vencer")
    ]


def test_el_productor_ve_su_habilitacion(api, sesion, coop, operador):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _parcela(api, sesion, operador, productor)
    datos = api.como(cuenta).get(f"/mi/parcelas/{parcela.id}/habilitacion").json()
    assert datos["estado"] == "pendiente"
    assert api.post(f"/parcelas/{parcela.id}/habilitar", json={}).status_code == 403


def test_otra_cooperativa_no_ve_ni_decide(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    otra = factorias.cooperativa(sesion, "Coop B")
    admin_b = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(admin_b)
    assert api.get(f"/parcelas/{parcela.id}/habilitacion").status_code == 404
    assert api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA}).status_code == 404
    assert api.get(f"/parcelas/{parcela.id}/imagenes").status_code == 404
    assert api.get(f"/parcelas/{parcela.id}/revisiones-imagenes").status_code == 404
    assert api.get("/habilitacion/resumen").json()["por_estado"]["pendiente"] == 0
