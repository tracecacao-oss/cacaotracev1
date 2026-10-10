"""Parte 8: datos y expediente legal de la cooperativa, documentos de embarque, recomprobación del lote, stock
retenido, tarea diaria y pendientes."""

import itertools
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.catalogos import documentos_legales
from app.fechas import hoy_lima
from app.models import Auditoria, Documento, Lote, Parcela, Recomprobacion
from app.services import recomprobacion
from tests import factorias
from tests.exportacion_util import tanda_final
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import (
    PDF,
    documento_legal,
    fuentes_configuradas,
    legalidad_completa,
    productor_listo,
)
from tests.habilitacion_util import analisis_completado as analisis_hecho
from tests.proceso_util import calidad, lugar, tanda_validada

NOTA_HABILITAR = "Se habilita: expediente completo y análisis de las dos fuentes sin cambios desde 2021."
_contador = itertools.count(1)


@pytest.fixture
def fuentes():
    return fuentes_configuradas()


@pytest.fixture
def coop(sesion):
    coop = factorias.cooperativa(sesion, "Coop Recomprueba", codigo="CRC")
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
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def documento_cooperativa(sesion, coop, tipo, perfil, *, vence: date | None = None) -> Documento:
    n = next(_contador)
    doc = Documento(
        cooperativa_id=coop.id,
        entidad="cooperativa",
        entidad_id=coop.id,
        tipo=tipo,
        ruta=f"prueba/cooperativa/{n}.pdf",
        nombre_original=f"{tipo}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=100,
        sha256=f"{n + 5 * 10**6:064x}",
        subido_por=perfil.id,
        numero=f"C-{n}",
        entidad_emisora="Entidad de prueba",
        fecha_emision=date(2024, 1, 1),
        fecha_vencimiento=vence,
    )
    sesion.add(doc)
    sesion.flush()
    return doc


def documento_embarque(sesion, lote_id, tipo, perfil) -> Documento:
    n = next(_contador)
    doc = Documento(
        cooperativa_id=perfil.cooperativa_id,
        entidad="lote",
        entidad_id=lote_id,
        tipo=tipo,
        ruta=f"prueba/lote/{n}.pdf",
        nombre_original=f"{tipo}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=100,
        sha256=f"{n + 7 * 10**6:064x}",
        subido_por=perfil.id,
        numero=f"E-{n}",
        entidad_emisora="Emisor de prueba",
        fecha_emision=hoy_lima(),
    )
    sesion.add(doc)
    sesion.flush()
    return doc


@pytest.fixture
def expediente_cooperativa(sesion, coop, admin):
    return {t: documento_cooperativa(sesion, coop, t, admin) for t in documentos_legales.CODIGOS_COOPERATIVA}


def _habilitada(api, sesion, admin, operador, productor, este) -> Parcela:
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(100, 100, este_m=este), nombre=f"Parcela {este}"
    )
    assert respuesta.status_code == 201, respuesta.text
    parcela = sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))
    legalidad_completa(sesion, parcela, operador)
    productor_listo(sesion, productor, operador)
    analisis_hecho(sesion, parcela, "whisp")
    analisis_hecho(sesion, parcela, "gfw")
    respuesta = api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA_HABILITAR})
    assert respuesta.status_code == 200, respuesta.text
    sesion.refresh(parcela)
    return parcela


@pytest.fixture
def armado(api, sesion, coop, admin, operador, productor, expediente_cooperativa):
    """Un lote armado de 300 kg con dos parcelas habilitadas; su tanda final de 400 kg queda con 100 kg de
    saldo."""
    cancha = lugar(sesion, coop.id, "Cancha central")
    almacen = lugar(sesion, coop.id, "Almacén", tipo="almacen")
    grado = calidad(sesion, coop.id)
    p1 = _habilitada(api, sesion, admin, operador, productor, 0)
    p2 = _habilitada(api, sesion, admin, operador, productor, 600)
    tandas = [
        tanda_validada(sesion, operador, productor, p1, cancha, peso="600.00"),
        tanda_validada(sesion, operador, productor, p2, cancha, peso="400.00"),
    ]
    tf = tanda_final(sesion, operador, grado, almacen, tandas, peso="400.00")
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
            "cantidad_kg": "300.00",
            "calidad_id": str(grado.id),
            "pais_destino": "Alemania",
            "lugar_destino": "Hamburgo",
            "fecha_entrega": (hoy_lima() + timedelta(days=60)).isoformat(),
        },
    ).json()
    lote = api.post(f"/ordenes/{orden['id']}/lote").json()
    confirmado = api.post(f"/lotes/{lote['id']}/confirmar", json={})
    assert confirmado.status_code == 200, confirmado.text
    return {
        "lote": confirmado.json(),
        "parcelas": (p1, p2),
        "tf": tf,
        "grado": grado,
        "importador": importador,
    }


def _con_embarque(sesion, lote, perfil):
    for tipo in ("factura_comercial", "packing_list", "certificado_origen", "certificado_fitosanitario"):
        documento_embarque(sesion, uuid.UUID(lote["id"]), tipo, perfil)


def _recomprobar(api, lote):
    respuesta = api.post(f"/lotes/{lote['id']}/recomprobar")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _fallan(resultado) -> dict:
    return {
        c["codigo"]: c["casos"] for c in resultado["comprobaciones"] if c["resultado"] == "con_observaciones"
    }


# ---------- Recomprobación ----------


def test_lote_con_todo_en_orden(api, sesion, operador, armado):
    lote = armado["lote"]
    _con_embarque(sesion, lote, operador)
    resultado = _recomprobar(api.como(operador), lote)
    assert resultado["resultado"] == "sin_observaciones" and resultado["estado_lote"] == "listo"
    assert len(resultado["comprobaciones"]) == 9 and _fallan(resultado) == {}
    detalle = api.get(f"/lotes/{lote['id']}").json()
    assert detalle["estado"] == "listo" and detalle["recomprobacion"]["resultado"] == "sin_observaciones"
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert "lote.recomprobar" in acciones and "lote.cambiar_estado" in acciones


def test_parcela_observada_bloquea_y_se_desbloquea(api, sesion, admin, operador, armado):
    lote = armado["lote"]
    _con_embarque(sesion, lote, operador)
    p1 = armado["parcelas"][0]
    titulo = sesion.scalar(
        select(Documento).where(Documento.entidad_id == p1.id, Documento.tipo == "titulo_sunarp")
    )
    titulo.fecha_vencimiento = hoy_lima() - timedelta(days=1)
    sesion.flush()
    resultado = _recomprobar(api.como(operador), lote)
    assert resultado["estado_lote"] == "bloqueado"
    casos = _fallan(resultado)["parcelas_habilitadas"]
    assert len(casos) == 1 and casos[0]["codigo"] == p1.codigo and "observada" in casos[0]["texto"]
    assert casos[0]["detalle"] and casos[0]["tipo"] == "parcela" and casos[0]["id"] == str(p1.id)
    # Mientras está bloqueado, nadie cambia su selección de stock.
    respuesta = api.put(f"/lotes/{lote['id']}/asignaciones", json={"asignaciones": []})
    assert respuesta.status_code == 400
    # Se renueva el documento, el administrador habilita de nuevo y se recomprueba.
    documento_legal(sesion, p1, "titulo_sunarp", operador, vence=hoy_lima() + timedelta(days=365))
    assert (
        api.como(admin).post(f"/parcelas/{p1.id}/habilitar", json={"nota": NOTA_HABILITAR}).status_code == 200
    )
    assert _recomprobar(api.como(operador), lote)["estado_lote"] == "listo"


def test_parcela_excluida_y_stock_retenido(api, sesion, admin, operador, armado):
    lote = armado["lote"]
    _con_embarque(sesion, lote, operador)
    p2 = armado["parcelas"][1]
    p2.habilitacion_estado = "excluida"
    sesion.flush()
    resultado = _recomprobar(api.como(operador), lote)
    assert "sin_parcelas_excluidas" in _fallan(resultado) and resultado["estado_lote"] == "bloqueado"
    # Ninguna acción lo devuelve a listo.
    assert _recomprobar(api, lote)["estado_lote"] == "bloqueado"
    # La tanda final con cacao de la parcela excluida queda retenida.
    finales = {f["id"]: f for f in api.get("/tandas-finales").json()}
    assert finales[str(armado["tf"].id)]["retenida"] is True
    orden = api.post(
        "/ordenes",
        json={
            "importador_id": armado["importador"]["id"],
            "cantidad_kg": "50.00",
            "calidad_id": str(armado["grado"].id),
            "pais_destino": "Alemania",
            "lugar_destino": "Hamburgo",
            "fecha_entrega": "2026-12-20",
        },
    ).json()
    otro = api.post(f"/ordenes/{orden['id']}/lote").json()
    assert otro["asignaciones"] == []
    sugerencia = api.get(f"/lotes/{otro['id']}/sugerencia-fifo").json()
    assert sugerencia["candidatas"] == []
    respuesta = api.put(
        f"/lotes/{otro['id']}/asignaciones",
        json={"asignaciones": [{"tanda_final_id": str(armado["tf"].id), "kg_asignados": "50.00"}]},
    )
    assert respuesta.status_code == 400 and respuesta.json()["error"]["codigo"] == "stock_retenido"
    # Solo el administrador anula un lote bloqueado.
    anular = api.post(f"/lotes/{lote['id']}/anular", json={"motivo": "Parcela excluida"})
    assert anular.status_code == 403
    assert (
        api.como(admin).post(f"/lotes/{lote['id']}/anular", json={"motivo": "Parcela excluida"}).status_code
        == 200
    )


def test_expediente_y_datos_de_la_cooperativa(
    api, sesion, coop, admin, operador, armado, expediente_cooperativa
):
    lote = armado["lote"]
    _con_embarque(sesion, lote, operador)
    # Un documento que venció ayer deja la casilla vencida y el lote bloqueado.
    expediente_cooperativa["ficha_ruc"].fecha_vencimiento = hoy_lima() - timedelta(days=1)
    # Otro falta.
    expediente_cooperativa["vigencia_poderes"].anulado_en = hoy_lima()
    coop.representante_nombre = None
    sesion.flush()
    exp = api.como(operador).get("/cooperativa/expediente").json()
    estados = {c["codigo"]: c["estado"] for c in exp["casillas"]}
    assert exp["estado"] == "incompleto" and estados["ficha_ruc"] == "vencido"
    assert estados["vigencia_poderes"] == "faltante" and estados["rnca"] == "vigente"
    resultado = _recomprobar(api, lote)
    fallan = _fallan(resultado)
    assert {c["codigo"] for c in fallan["expediente_cooperativa_completo"]} == {
        "ficha_ruc",
        "vigencia_poderes",
    }
    assert [c["texto"] for c in fallan["datos_cooperativa_completos"]] == [
        "Falta el dato: nombre del representante legal"
    ]
    assert resultado["estado_lote"] == "bloqueado"


def test_documentos_de_embarque(api, sesion, admin, operador, armado):
    lote = armado["lote"]
    api.como(operador)
    faltan = _fallan(_recomprobar(api, lote))["documentos_embarque_completos"]
    assert len(faltan) == 4 and "Falta: Factura comercial" in [c["texto"] for c in faltan]
    for tipo in ("factura_comercial", "packing_list", "certificado_origen", "certificado_fitosanitario"):
        respuesta = api.post(
            f"/lotes/{lote['id']}/documentos",
            data={
                "tipo": tipo,
                "numero": "F001-1",
                "entidad_emisora": "Emisor",
                "fecha_emision": "2026-10-01",
            },
            files={"archivo": (f"{tipo}.pdf", PDF + tipo.encode(), "application/pdf")},
        )
        assert respuesta.status_code == 201, respuesta.text
    embarque = api.get(f"/lotes/{lote['id']}/documentos").json()
    assert embarque["completo"] is True and embarque["faltan"] == []
    # Pedido del equipo del 2026-10-10: cada tipo dice qué es, quién lo emite y dónde se tramita.
    tipos = {t["codigo"]: t for t in embarque["tipos"]}
    assert all(t["que_es"] and t["quien_lo_emite"] for t in tipos.values())
    origen = tipos["certificado_origen"]
    assert "MINCETUR" in origen["quien_lo_emite"] and "Unión Europea" in origen["nota"]
    assert {c["url"] for c in origen["tramite"]} == {
        "https://www.vuce.gob.pe/",
        "https://www.vuce.gob.pe/archivos_entidades/origen/Entidades_Delegadas.pdf",
    }
    assert _recomprobar(api, lote)["estado_lote"] == "listo"
    factura = next(t for t in embarque["tipos"] if t["codigo"] == "factura_comercial")["documentos"][0]
    assert (
        api.post(f"/documentos/{factura['id']}/anular", json={"motivo": "Número mal escrito"}).status_code
        == 200
    )
    assert _recomprobar(api, lote)["estado_lote"] == "bloqueado"
    sin_numero = api.post(
        f"/lotes/{lote['id']}/documentos",
        data={"tipo": "factura_comercial", "entidad_emisora": "Emisor", "fecha_emision": "2026-10-01"},
        files={"archivo": ("f.pdf", PDF + b"x", "application/pdf")},
    )
    assert sin_numero.status_code == 422


def test_documentos_legales_de_la_cooperativa(api, sesion, coop, admin, operador):
    datos = {
        "tipo": "ficha_ruc",
        "numero": "20123456789",
        "entidad_emisora": "SUNAT",
        "fecha_emision": "2026-01-10",
    }
    archivo = {"archivo": ("ficha.pdf", PDF + b"ficha", "application/pdf")}
    assert api.como(operador).post("/cooperativa/documentos", data=datos, files=archivo).status_code == 403
    respuesta = api.como(admin).post("/cooperativa/documentos", data=datos, files=archivo)
    assert respuesta.status_code == 201, respuesta.text
    doc = respuesta.json()
    # El cotejo sigue las reglas de la Parte 4: la ficha RUC tiene registro público consultable.
    assert (
        api.post(
            f"/documentos/{doc['id']}/cotejo", json={"nota": "Consulta RUC de SUNAT: activo"}
        ).status_code
        == 200
    )
    rnca = api.post(
        "/cooperativa/documentos",
        data={"tipo": "rnca", "numero": "R-1", "entidad_emisora": "MIDAGRI", "fecha_emision": "2025-05-01"},
        files={"archivo": ("rnca.pdf", PDF + b"rnca", "application/pdf")},
    ).json()
    sin_registro = api.post(f"/documentos/{rnca['id']}/cotejo", json={"nota": "No hay registro en línea"})
    assert sin_registro.status_code == 400
    # Solo el administrador anula.
    assert (
        api.como(operador).post(f"/documentos/{rnca['id']}/anular", json={"motivo": "Error"}).status_code
        == 403
    )
    assert (
        api.como(admin).post(f"/documentos/{rnca['id']}/anular", json={"motivo": "Error"}).status_code == 200
    )
    exp = api.get("/cooperativa/expediente").json()
    casilla = next(c for c in exp["casillas"] if c["codigo"] == "ficha_ruc")
    assert casilla["estado"] == "vigente" and casilla["nivel"] == "verificado_en_fuente"


def test_editar_los_datos_de_la_cooperativa(api, sesion, coop, admin, operador):
    cambios = {
        "representante_nombre": "Ana Pérez",
        "representante_dni": "41234567",
        "correo": "Coop@Prueba.test",
    }
    assert api.como(operador).patch("/cooperativa", json=cambios).status_code == 403
    datos = api.como(admin).patch("/cooperativa", json=cambios).json()
    assert datos["representante_nombre"] == "Ana Pérez" and datos["correo"] == "coop@prueba.test"
    assert datos["faltan_datos"] == []
    assert api.patch("/cooperativa", json={"representante_dni": "123"}).status_code == 422
    assert sesion.scalar(select(Auditoria).where(Auditoria.accion == "cooperativa.editar")) is not None
    assert api.como(operador).get("/cooperativa").json()["ruc"] == coop.ruc


# ---------- Tarea diaria, exclusión posterior y trigger ----------


def test_tarea_diaria(api, sesion, admin, operador, armado):
    lote = armado["lote"]
    _con_embarque(sesion, lote, operador)
    p1 = armado["parcelas"][0]
    p1.habilitacion_estado = "observada"
    sesion.flush()
    assert _recomprobar(api.como(operador), lote)["estado_lote"] == "bloqueado"
    assert recomprobacion.tarea_diaria(sesion) == 0  # sin cambios: no crea fila
    filas = lambda: list(  # noqa: E731
        sesion.scalars(select(Recomprobacion).where(Recomprobacion.lote_id == uuid.UUID(lote["id"])))
    )
    assert len(filas()) == 1
    assert (
        api.como(admin).post(f"/parcelas/{p1.id}/habilitar", json={"nota": NOTA_HABILITAR}).status_code == 200
    )
    assert recomprobacion.tarea_diaria(sesion) == 1
    assert sesion.get(Lote, uuid.UUID(lote["id"])).estado == "listo"
    ultima = recomprobacion.ultima(sesion, uuid.UUID(lote["id"]))
    assert ultima.ejecutada_por is None and ultima.resultado == "sin_observaciones"
    assert recomprobacion.tarea_diaria(sesion) == 0 and len(filas()) == 2


def test_exclusion_posterior_al_cierre(api, sesion, admin, operador, armado):
    lote = sesion.get(Lote, uuid.UUID(armado["lote"]["id"]))
    lote.estado = "cerrado"
    sesion.flush()
    p1 = armado["parcelas"][0]
    evidencia = analisis_hecho(
        sesion, p1, "gfw", indicadores={"alertas_desde_2021": 3, "perdida_ha_total": 0.4}
    )
    respuesta = api.como(admin).post(
        f"/parcelas/{p1.id}/excluir",
        json={
            "descripcion": "El análisis de GFW muestra pérdida de cobertura en 2023 dentro del polígono "
            "declarado.",
            "evidencia_analisis_id": str(evidencia.id),
            "confirmacion": "EXCLUIR",
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    sesion.refresh(lote)
    assert lote.estado == "cerrado"
    assert [a["codigo"] for a in lote.alertas] == ["exclusion_posterior_al_cierre"]
    assert lote.alertas[0]["parcela_codigo"] == p1.codigo
    assert sesion.scalar(select(Auditoria).where(Auditoria.accion == "lote.alerta")) is not None
    grupos = {g["clave"]: g for g in api.get("/pendientes").json()["grupos"]}
    assert grupos["exclusion_posterior_al_cierre"]["items"][0]["enlace"] == f"#/lotes-exportacion/{lote.id}"


def test_las_recomprobaciones_no_cambian(api, sesion, operador, armado):
    resultado = _recomprobar(api.como(operador), armado["lote"])
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(
            text("UPDATE recomprobaciones SET resultado = 'sin_observaciones' WHERE id = :i"),
            {"i": resultado["id"]},
        )
    with pytest.raises(DBAPIError), sesion.begin_nested():
        sesion.execute(text("DELETE FROM recomprobaciones WHERE id = :i"), {"i": resultado["id"]})
    historial = api.get(f"/lotes/{armado['lote']['id']}/recomprobaciones").json()
    assert len(historial) == 1 and historial[0]["ejecutada_por_nombre"]


# ---------- Pendientes ----------


def test_pendientes(api, sesion, coop, admin, operador, armado, expediente_cooperativa):
    lote = armado["lote"]
    p1 = armado["parcelas"][0]
    titulo = sesion.scalar(
        select(Documento).where(Documento.entidad_id == p1.id, Documento.tipo == "titulo_sunarp")
    )
    titulo.fecha_vencimiento = hoy_lima() - timedelta(days=2)
    expediente_cooperativa["vigencia_poderes"].fecha_vencimiento = hoy_lima() + timedelta(days=10)
    sesion.flush()
    _recomprobar(api.como(operador), lote)
    salida = api.get("/pendientes").json()
    grupos = {g["clave"]: g for g in salida["grupos"]}
    assert grupos["documentos_parcelas_vencidos"]["items"][0]["enlace"] == f"#/parcelas/{p1.id}"
    assert grupos["documentos_cooperativa_por_vencer"]["items"][0]["enlace"] == "#/cooperativa/legal"
    assert grupos["lotes_bloqueados"]["items"][0]["enlace"] == f"#/lotes-exportacion/{lote['id']}"
    assert "Parcelas habilitadas" in grupos["lotes_bloqueados"]["items"][0]["detalle"]
    assert grupos["parcelas_observadas"]["cantidad"] == 1
    # Primero lo vencido, luego lo que está por vencer y al final lo demás.
    prioridades = [g["prioridad"] for g in salida["grupos"]]
    assert prioridades == sorted(prioridades, key=["vencido", "por_vencer", "otro"].index)
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    assert api.como(cuenta).get("/pendientes").status_code == 403


def test_lote_por_entregar(api, sesion, operador, armado):
    orden_id = armado["lote"]["orden"]["id"]
    api.como(operador)
    # La orden ya tiene lote: se acerca su fecha directamente.
    from app.models import OrdenCompra

    sesion.get(OrdenCompra, uuid.UUID(orden_id)).fecha_entrega = hoy_lima() + timedelta(days=10)
    sesion.flush()
    grupos = {g["clave"]: g for g in api.get("/pendientes").json()["grupos"]}
    assert grupos["lotes_por_entregar"]["items"][0]["titulo"] == armado["lote"]["codigo"]


# ---------- Dos cooperativas ----------


def test_otra_cooperativa_no_ve_ni_opera(api, sesion, operador, armado, expediente_cooperativa):
    lote = armado["lote"]
    otra = factorias.cooperativa(sesion, "Coop B", codigo="CBB")
    admin_b = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(admin_b)
    assert api.get(f"/lotes/{lote['id']}/documentos").status_code == 404
    assert api.post(f"/lotes/{lote['id']}/recomprobar").status_code == 404
    assert api.get(f"/lotes/{lote['id']}/recomprobaciones").status_code == 404
    respuesta = api.post(
        f"/lotes/{lote['id']}/documentos",
        data={
            "tipo": "packing_list",
            "numero": "P-1",
            "entidad_emisora": "Emisor",
            "fecha_emision": "2026-10-01",
        },
        files={"archivo": ("p.pdf", PDF + b"p", "application/pdf")},
    )
    assert respuesta.status_code == 404
    assert api.get("/cooperativa").json()["id"] == str(otra.id)
    assert api.get("/cooperativa/expediente").json()["estado"] == "incompleto"
    assert api.get("/pendientes").json()["total"] == 0
    ajeno = expediente_cooperativa["ficha_ruc"]
    assert api.get(f"/documentos/{ajeno.id}/url").status_code == 404
    assert api.post(f"/documentos/{ajeno.id}/anular", json={"motivo": "x"}).status_code == 404
    assert api.get(f"/lotes/{lote['id']}").status_code == 404
    assert Decimal(api.como(operador).get(f"/lotes/{lote['id']}").json()["masa_neta_kg"]) == Decimal("300.00")
