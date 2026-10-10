"""Adenda 7: la declaración aduanera del lote con sus cuatro datos y su comparación, y el cuadro de legalidad
por requisito (sección 10). Usa los escenarios de tests/test_dex.py."""

import json
import re
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import textos
from app.catalogos import cuadro_legalidad as catalogo
from app.fechas import hoy_lima
from app.models import Auditoria, DeclaracionAduanera, Dex, Documento, Lote
from app.pdf import dex as pdf_dex
from app.services import sello
from tests import factorias
from tests.habilitacion_util import PDF, documento_legal, incidencia
from tests.organizacion_util import SUBPARTIDA, dam
from tests.test_analisis import DOCUMENTOS_CON_NOMBRE_PROPIO, PROHIBIDAS
from tests.test_dex import (  # noqa: F401  (fixtures)
    PROHIBIDAS_EN,
    _codigos,
    _emitir,
    _informe,
    _listo,
    _lote,
    _parcela,
    admin,
    basico,
    coop,
    expediente_cooperativa,
    fuentes,
    lector,
    operador,
    productor,
)

CALIFICA = re.compile(r"\b(cumple|incumple|cumplen|incumplen|complies|compliant)\b", re.IGNORECASE)
NOTA_COTEJO = "Consulta pública de SUNAT por número: coincide con el archivo."


def _cargar(api, lote, tipo="dam", **datos):
    return api.post(
        f"/lotes/{lote['id']}/documentos",
        data={"tipo": tipo, **{k: str(v) for k, v in datos.items()}},
        files={"archivo": (f"{tipo}.pdf", PDF + str(datos).encode(), "application/pdf")},
    )


def _dam(api, lote, *, numero="DAM-PRUEBA-0002", peso="300.00", subpartida="1801.00.00.00", **extra):
    return _cargar(
        api,
        lote,
        numero=numero,
        fecha_emision=str(hoy_lima()),
        peso_neto_kg=peso,
        subpartida=subpartida,
        **extra,
    )


# ---------- Declaración aduanera (sección 4) ----------


def test_declaracion_aduanera_y_su_comparacion(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    api.como(operador)
    # Validaciones: sin peso, 422; un número muy corto, 422; una subpartida sin dígitos suficientes, 422.
    sin_peso = _cargar(api, lote, numero="DAM-PRUEBA-0002", fecha_emision=str(hoy_lima()), subpartida="1801")
    assert sin_peso.status_code == 422 and "peso neto" in sin_peso.json()["error"]["mensaje"]
    assert _dam(api, lote, numero="1234").status_code == 422
    assert _dam(api, lote, subpartida="18").status_code == 422
    assert _dam(api, lote, peso="0").status_code == 422
    # Peso igual a la masa del lote y subpartida que empieza con 1801: sin diferencias.
    cargada = _dam(api, lote)
    assert cargada.status_code == 201, cargada.text
    embarque = api.get(f"/lotes/{lote['id']}/documentos").json()
    d = embarque["declaracion"]
    assert d["subpartida"] == "1801000000" and d["peso_neto_kg"] == "300.00" and not d["posterior_al_dex"]
    c = d["comparacion"]
    assert (c["diferencia_kg"], c["diferencia_pct"], c["difiere"]) == ("0.00", "0.00", False)
    assert c["tolerancia_pct"] == "1" and c["partida_orden"] == "1801"
    assert not _codigos(_informe(api, lote)).get("dam_difiere_del_lote")
    # Una segunda sin anular la primera: 400.
    segunda = _dam(api, lote, numero="DAM-PRUEBA-0003")
    assert segunda.status_code == 400 and segunda.json()["error"]["codigo"] == "declaracion_existente"
    # El archivo no se anula solo: se anula la declaración, y solo el administrador.
    doc_id = d["documento"]["id"]
    assert api.post(f"/documentos/{doc_id}/anular", json={"motivo": "Prueba"}).status_code == 400
    motivo = {"motivo": "Se cargó con el peso equivocado."}
    assert api.post(f"/lotes/{lote['id']}/declaracion-aduanera/anular", json=motivo).status_code == 403
    anulada = api.como(admin).post(f"/lotes/{lote['id']}/declaracion-aduanera/anular", json=motivo)
    assert anulada.status_code == 200 and anulada.json()["declaracion"] is None
    assert sesion.get(Documento, uuid.UUID(doc_id)).anulado_en is not None
    # Con 0,5 % más: no difiere, y la diferencia se muestra igual.
    api.como(operador)
    assert _dam(api, lote, numero="DAM-PRUEBA-0004", peso="301.50").status_code == 201
    c = api.get(f"/lotes/{lote['id']}/documentos").json()["declaracion"]["comparacion"]
    assert (c["diferencia_kg"], c["diferencia_pct"], c["peso_difiere"]) == ("1.50", "0.50", False)
    # Con 3 % más y subpartida 0901: difiere en las dos, con los dos valores en el hallazgo, y no bloquea.
    api.como(admin).post(f"/lotes/{lote['id']}/declaracion-aduanera/anular", json=motivo)
    api.como(operador)
    assert (
        _dam(api, lote, numero="DAM-PRUEBA-0005", peso="309.00", subpartida="0901110000").status_code == 201
    )
    c = api.get(f"/lotes/{lote['id']}/documentos").json()["declaracion"]["comparacion"]
    assert c["peso_difiere"] and c["subpartida_difiere"] and c["diferencia_pct"] == "3.00"
    hallazgo = _codigos(_informe(api, lote))["dam_difiere_del_lote"][0]
    assert (hallazgo["grupo"], hallazgo["etapa"], hallazgo["criterio"]) == ("requiere_atencion", 3, 3)
    assert "309.00 kg" in hallazgo["hecho"]["es"] and "300.00 kg" in hallazgo["hecho"]["es"]
    assert "0901110000" in hallazgo["hecho"]["es"] and "1801" in hallazgo["hecho"]["en"]
    assert api.post(f"/lotes/{lote['id']}/recomprobar").json()["estado_lote"] == "listo"
    acciones = [a.accion for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert acciones.count("declaracion_aduanera.registrar") == 3 and "declaracion_aduanera.anular" in acciones


def test_declaracion_aduanera_despues_del_dex(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    emitido = _emitir(api, admin, lote)
    assert emitido.status_code == 201, emitido.text
    dex = emitido.json()
    assert "lote_sin_dam" in {h["codigo"] for h in dex["contenido"]["informe"]["hallazgos"]}
    api.como(operador)
    # Con el lote cerrado, la factura no se carga, como antes; la declaración aduanera sí.
    factura = _cargar(
        api, lote, "factura_comercial", numero="F001-9", entidad_emisora="E", fecha_emision="2026-10-01"
    )
    assert factura.status_code == 400
    cargada = _dam(api, lote, peso="320.00")
    assert cargada.status_code == 201, cargada.text
    fila = sesion.scalar(
        select(DeclaracionAduanera).where(DeclaracionAduanera.lote_id == uuid.UUID(lote["id"]))
    )
    assert fila.posterior_al_dex
    # La diferencia de peso (6,67 %) deja la alerta en el lote.
    sesion.expire_all()
    alertas = sesion.get(Lote, uuid.UUID(lote["id"])).alertas
    assert [a["codigo"] for a in alertas] == ["dam_difiere_del_lote"] and alertas[0]["peso_difiere"]
    # El DEX no cambia.
    sellado = sesion.get(Dex, uuid.UUID(dex["id"]))
    sesion.refresh(sellado)
    assert sellado.contenido_sha256 == dex["contenido_sha256"] == sello.huella(sellado.contenido)
    detalle = api.get(f"/dex/{dex['id']}").json()
    [agregado] = detalle["agregado"]
    assert agregado["peso_neto_kg"] == "320.00" and agregado["comparacion"]["peso_difiere"]
    # Admite cotejo con el lote cerrado.
    documento_id = api.get(f"/lotes/{lote['id']}/documentos").json()["declaracion"]["documento"]["id"]
    assert api.post(f"/documentos/{documento_id}/cotejo", json={"nota": NOTA_COTEJO}).status_code == 200
    # La verificación pública muestra tres datos, sin pesos.
    api.headers.pop("Authorization", None)
    publico = api.get(f"/publico/dex/{dex['codigo']}").json()
    [visible] = publico["agregado"]
    assert set(visible) == {"nombre", "numero", "fecha_numeracion", "agregado_en"}
    assert visible["numero"] == "DAM-PRUEBA-0002" and visible["fecha_numeracion"] == str(hoy_lima())
    assert "320" not in json.dumps(publico)


def test_la_declaracion_al_emitir_va_con_el_embarque(api, sesion, admin, operador, basico):
    lote = _listo(api, sesion, basico, operador)
    dam(sesion, uuid.UUID(lote["id"]), operador, peso=Decimal("300.00"))
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 201, respuesta.text
    contenido = respuesta.json()["contenido"]
    [declaracion] = [x for x in contenido["embarque"] if x["tipo"] == "dam"]
    assert declaracion["peso_neto_kg"] == "300.00" and declaracion["subpartida"] == SUBPARTIDA
    assert declaracion["comparacion"]["difiere"] is False
    assert "lote_sin_dam" not in {h["codigo"] for h in contenido["informe"]["hallazgos"]}
    assert respuesta.json()["agregado"] == []
    for idioma, texto in (
        ("es", "Declaración aduanera: N.º DAM-PRUEBA-0001"),
        ("en", "Customs declaration: No."),
    ):
        escrito = " ".join(pdf_dex.documento(contenido, "x" * 64, "https://x.test", idioma).textos)
        assert texto in escrito


# ---------- Cuadro de legalidad por requisito (sección 5) ----------


@pytest.fixture
def tres_parcelas(api, sesion, coop, admin, operador, productor, expediente_cooperativa):
    """Un lote de tres parcelas de dos productores: dos con título y una con declaración jurada."""
    vecino = factorias.productor(sesion, coop, nombres="Vecino", apellidos="Familiar")

    def solo_declaracion(p):
        sesion.query(Documento).filter_by(entidad_id=p.id, tipo="constancia_posesion").delete()
        documento_legal(sesion, p, "declaracion_jurada_tenencia", operador, emitido=hoy_lima())

    p1 = _parcela(api, sesion, admin, operador, productor, 0)
    p2 = _parcela(api, sesion, admin, operador, productor, 600)
    p3 = _parcela(api, sesion, admin, operador, vecino, 1200, posesion=True, preparar=solo_declaracion)
    datos = _lote(api, sesion, coop, operador, [p1, p2, p3])
    return datos | {"parcelas": (p1, p2, p3), "vecino": vecino}


def test_cuadro_de_un_lote_armado(api, sesion, operador, productor, tres_parcelas):
    lote = tres_parcelas["lote"]
    p1, p2, p3 = tres_parcelas["parcelas"]
    incidencia(sesion, p3, operador, tipo="ambiental")
    cuadro = api.como(operador).get(f"/lotes/{lote['id']}/legalidad").json()
    assert cuadro["estado"] == "preliminar" and len(cuadro["filas"]) == 21
    assert [f["codigo"] for f in cuadro["filas"]] == list(catalogo.CODIGOS)
    assert len(cuadro["no_se_piden"]) == 9 and {x["referencia"] for x in cuadro["no_se_piden"]} >= {
        "2.6",
        "6.1",
    }
    filas = {f["codigo"]: f for f in cuadro["filas"]}
    # Las 21 filas nombran los 31 requisitos pertinentes.
    referencias = {r for f in cuadro["filas"] for r in f["referencias"]}
    assert len(referencias) == 31
    for f in cuadro["filas"]:
        if f["de"] == "parcela":
            suma = f["con_sustento"]["n"] + f["por_atender"]["n"] + f["sin_sustento"]["n"]
            assert suma == f["aplica"]["n"] and f["sujetos_lote"] == 3, f["codigo"]
    # Tenencia: con sustento las tres; una declarada (declaración jurada) y dos documentadas (título).
    tenencia = filas["tenencia"]
    assert tenencia["aplica"]["n"] == 3 and tenencia["con_sustento"]["n"] == 3
    assert tenencia["con_sustento"]["niveles"] == {
        "declarado": 1,
        "documentado": 2,
        "verificado_en_fuente": 0,
    }
    pcts = [Decimal(tenencia[k]["pct"]) for k in ("con_sustento", "por_atender", "sin_sustento")]
    assert sum(pcts) == Decimal("100.00") == Decimal(tenencia["aplica"]["pct"])
    # Daños ambientales: la incidencia abierta queda por atender.
    danos = filas["danos_ambientales"]
    assert (danos["aplica"]["n"], danos["por_atender"]["n"]) == (1, 1)
    # Envases: nadie usa agroquímicos, no aplica a este lote.
    assert filas["envases"]["aplica"]["n"] == 0
    # El productor con dos parcelas pesa la suma de las dos.
    sujetos = {s["id"]: s for s in filas["menores_de_edad"]["sujetos"]}
    pesos = {s["codigo"]: Decimal(s["peso"]) for s in filas["tenencia"]["sujetos"]}
    assert Decimal(sujetos[str(productor.id)]["peso"]) == pesos[p1.codigo] + pesos[p2.codigo]
    # Organización y lote: un solo sujeto, con su estado y lo que falta.
    assert filas["aduanas"]["estado"] == "sin_sustento" and filas["aduanas"]["falta"]
    assert filas["tributos_organizacion"]["conteo"] is False
    # Sin totales ni nada que resuma el lote.
    plano = json.dumps(cuadro)
    assert not re.search(r'"(total|puntaje|calificacion|resultado)"', plano)
    # La fila, con sus sujetos.
    detalle = api.get(f"/lotes/{lote['id']}/legalidad/tenencia").json()
    assert {s["codigo"] for s in detalle["fila"]["sujetos"]} == {p1.codigo, p2.codigo, p3.codigo}
    assert any("Declaración jurada" in s["sustento"] for s in detalle["fila"]["sujetos"])
    assert api.get(f"/lotes/{lote['id']}/legalidad/no_existe").status_code == 404


def test_cuadro_preliminar_y_sellado(api, sesion, admin, operador, tres_parcelas):
    lote = _listo(api, sesion, tres_parcelas, operador)
    antes = api.get(f"/lotes/{lote['id']}/legalidad").json()
    assert antes["estado"] == "preliminar"
    respuesta = _emitir(api, admin, lote)
    assert respuesta.status_code == 201, respuesta.text
    dex = sesion.get(Dex, uuid.UUID(respuesta.json()["id"]))
    sellado = dex.contenido["legalidad_por_requisito"]
    assert sellado["estado"] == "sellado" and sellado["dex"] == dex.codigo
    # Después de emitir, aunque cambie una parcela, se muestra el sellado.
    p1 = tres_parcelas["parcelas"][0]
    titulo = sesion.scalar(
        select(Documento).where(Documento.entidad_id == p1.id, Documento.tipo == "titulo_sunarp")
    )
    titulo.anulado_en = hoy_lima()
    sesion.flush()
    despues = api.get(f"/lotes/{lote['id']}/legalidad").json()
    assert despues == json.loads(json.dumps(sellado))
    # El archivo de hallazgos lo trae, y el PDF tiene la sección en los dos idiomas con las mismas cifras.
    hallazgos_json = json.loads(json.dumps(sellado))
    assert hallazgos_json["filas"][0]["aplica"]["n"] == 3
    for idioma, titulo_seccion in (("es", "Legalidad por requisito"), ("en", "Legality by requirement")):
        documento = pdf_dex.documento(dex.contenido, dex.contenido_sha256, "https://x.test", idioma)
        texto = " ".join(documento.textos)
        assert titulo_seccion in texto and "3 (100.0 %)" in texto
        assert texto.index(titulo_seccion) < texto.index(textos.obtener(idioma, "pdf.respaldo"))
        limpio = texto
        for nombre in DOCUMENTOS_CON_NOMBRE_PROPIO:
            limpio = limpio.replace(nombre, "")
        assert (
            not PROHIBIDAS.search(limpio) and not PROHIBIDAS_EN.search(limpio) and not CALIFICA.search(limpio)
        )
        # Un DEX emitido antes de la adenda 7 se sigue leyendo, sin la sección.
        anterior = {k: v for k, v in dex.contenido.items() if k != "legalidad_por_requisito"}
        assert titulo_seccion not in " ".join(
            pdf_dex.documento(anterior, dex.contenido_sha256, "https://x.test", idioma).textos
        )


def test_el_caso_de_una_parcela_nombra_a_su_productor(api, sesion, admin, operador, productor, tres_parcelas):
    lote = tres_parcelas["lote"]
    p1 = tres_parcelas["parcelas"][0]
    titulo = sesion.scalar(
        select(Documento).where(Documento.entidad_id == p1.id, Documento.tipo == "titulo_sunarp")
    )
    titulo.fecha_vencimiento = hoy_lima() - timedelta(days=1)
    sesion.flush()
    resultado = api.como(operador).post(f"/lotes/{lote['id']}/recomprobar").json()
    [caso] = next(c["casos"] for c in resultado["comprobaciones"] if c["codigo"] == "parcelas_habilitadas")
    nombre = f"{productor.nombres} {productor.apellidos}"
    assert nombre in caso["texto"] and caso["productor_id"] == str(productor.id)
    hallazgo = next(
        h
        for h in _informe(api, lote)["hallazgos"]
        if h["datos"].get("codigo_comprobacion") == "parcelas_habilitadas"
    )
    assert nombre in hallazgo["hecho"]["es"] and nombre in hallazgo["hecho"]["en"]


def test_aislamiento(api, sesion, operador, basico):
    lote = basico["lote"]
    otra = factorias.cooperativa(sesion, "Otra Coop", codigo="OTR")
    ajeno = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(ajeno)
    assert api.get(f"/lotes/{lote['id']}/legalidad").status_code == 404
    assert api.get(f"/lotes/{lote['id']}/legalidad/tenencia").status_code == 404
    motivo = {"motivo": "Intento de otra organización."}
    assert api.post(f"/lotes/{lote['id']}/declaracion-aduanera/anular", json=motivo).status_code == 404
    assert _dam(api, lote).status_code == 404


def test_los_textos_nuevos_no_califican():
    piezas = []
    for idioma in textos.IDIOMAS:
        datos = textos.cargar(idioma)
        piezas.append(json.dumps(datos["cuadro"], ensure_ascii=False))
        piezas.append(json.dumps(datos["aduanas"], ensure_ascii=False))
        piezas += [datos["hallazgo"]["dam_difiere_del_lote"], datos["mensaje"]["dam_difiere_del_lote"]]
        piezas += [datos["pdf"][k] for k in ("embarque_dam", "dam_coincide", "dam_difiere")]
    for pieza in piezas:
        assert not PROHIBIDAS.search(pieza) and not PROHIBIDAS_EN.search(pieza), pieza
        assert not CALIFICA.search(pieza), pieza
