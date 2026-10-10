"""Adenda 5: la declaración anual del productor, sus requisitos, la compuerta y sus pantallas.

Las pruebas de la sección 13 que no pasan por un lote; los hallazgos del productor y el DEX están en
tests/test_dex.py.
"""

import re
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.catalogos import declaracion_productor as cuestionario
from app.catalogos import requisitos_productor
from app.fechas import hoy_lima
from app.models import Auditoria, DeclaracionProducto, DeclaracionProductor, Parcela
from app.pdf import declaracion_productor as hoja_pdf
from app.pdf import dop as dop_pdf
from app.services import declaracion_productor as servicio
from tests import factorias
from tests.factorias import crear_parcela, rectangulo
from tests.habilitacion_util import (
    PDF,
    PERFIL_BASE,
    RESPUESTAS_FAMILIA,
    analisis_completado,
    declaracion_vigente,
    declarar,
    declarar_anual,
    documento_legal,
    fuentes_configuradas,
    productor_listo,
)

NOTA = "Se habilita con lo declarado por el productor y la visita del técnico de la organización a la chacra."
SEGUIMIENTO = (
    "Se visitó al productor el 5 de octubre, se le explicó la jornada legal y se acordó revisar en enero."
)
EVENTUALES = {
    "quien_trabaja": "eventuales",
    "trabajadores_numero": 4,
    "acuerdo_por_escrito": "no",
    "jornal_soles": 50,
    "horas_por_dia": 8,
    "seguro_salud": "todos",
    "equipo_proteccion": "si",
    "pueden_dejar_el_trabajo": "si",
    "menores_trabajan": "no",
    "usa_agroquimicos": "no",
    "ventas_superan_75_uit": "no",
}


@pytest.fixture
def fuentes():
    return fuentes_configuradas()


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
def productor_y_cuenta(sesion, coop):
    return factorias.productor_con_acceso(sesion, coop)


@pytest.fixture
def productor(productor_y_cuenta):
    return productor_y_cuenta[0]


@pytest.fixture
def cuenta(sesion, productor_y_cuenta):
    perfil = productor_y_cuenta[1]
    perfil.debe_cambiar_clave = False
    productor_y_cuenta[0].consentimiento_datos_en = perfil.creado_en or hoy_lima()
    productor_y_cuenta[0].consentimiento_origen = "productor"
    sesion.flush()
    return perfil


def _parcela(api, sesion, operador, productor, este=0, ancho=100) -> Parcela:
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(ancho, 100, este_m=este), nombre=f"Parcela {este}"
    )
    assert respuesta.status_code == 201, respuesta.text
    parcela = sesion.get(Parcela, uuid.UUID(respuesta.json()["id"]))
    declarar(sesion, parcela, operador, **PERFIL_BASE)
    documento_legal(sesion, parcela, "titulo_sunarp", operador)
    analisis_completado(sesion, parcela, "whisp")
    analisis_completado(sesion, parcela, "gfw")
    return parcela


def _lista(api, sesion, operador, productor, **kw) -> Parcela:
    """Todo listo para habilitar, salvo la declaración anual."""
    parcela = _parcela(api, sesion, operador, productor, **kw)
    productor_listo(sesion, productor, operador, declaracion=False)
    return parcela


def _productor_listo(api, parcela) -> dict:
    respuesta = api.get(f"/parcelas/{parcela.id}/habilitacion")
    assert respuesta.status_code == 200, respuesta.text
    return next(r for r in respuesta.json()["requisitos"] if r["codigo"] == "productor_listo")


def _habilitar(api, admin, parcela, nota=NOTA):
    return api.como(admin).post(f"/parcelas/{parcela.id}/habilitar", json={"nota": nota})


def _registrar(api, productor, respuestas=None):
    return api.post(
        f"/productores/{productor.id}/declaraciones", json={"respuestas": respuestas or RESPUESTAS_FAMILIA}
    )


def _hoja_firmada(api, productor, declaracion_id, fecha=None):
    return api.post(
        f"/productores/{productor.id}/declaraciones/{declaracion_id}/hoja-firmada",
        data={"fecha_firma": (fecha or hoy_lima()).isoformat()},
        files={"archivo": ("hoja.pdf", PDF)},
    )


def _req(salida: dict, codigo: str) -> dict:
    return next(r for r in salida["requisitos"] if r["codigo"] == codigo)


def _estado(sesion, productor, coop) -> servicio.EstadoProductor:
    return servicio.estado_de(sesion, productor.id, coop.id)


# ---------- Compuerta y estados ----------


def test_sin_declaracion_las_parcelas_no_se_habilitan(api, sesion, operador, admin, productor):
    parcela = _lista(api, sesion, operador, productor)
    requisito = _productor_listo(api.como(operador), parcela)
    assert requisito["cumple"] is False and "declaración anual" in requisito["detalle"]
    respuesta = _habilitar(api, admin, parcela)
    assert respuesta.status_code == 400 and "productor_listo" in respuesta.json()["error"]["faltan"]


def test_registrada_por_el_personal_queda_por_firmar_hasta_la_hoja(api, sesion, operador, admin, productor):
    parcela = _lista(api, sesion, operador, productor)
    respuesta = _registrar(api.como(operador), productor)
    assert respuesta.status_code == 201, respuesta.text
    salida = respuesta.json()
    assert salida["estado"] == "por_firmar" and salida["vigente"] is None
    assert salida["por_firmar"]["origen"] == "personal" and salida["pendientes"] == ["declaracion_por_firmar"]
    requisito = _productor_listo(api, parcela)
    assert requisito["cumple"] is False and "hoja firmada de la declaración" in requisito["detalle"]
    declaracion_id = salida["por_firmar"]["id"]
    # La fecha de firma no puede ser futura ni anterior al registro.
    futura = _hoja_firmada(api, productor, declaracion_id, hoy_lima() + timedelta(days=1))
    assert futura.status_code == 422
    anterior = _hoja_firmada(api, productor, declaracion_id, hoy_lima() - timedelta(days=1))
    assert anterior.status_code == 422 and anterior.json()["error"]["codigo"] == "fecha_anterior_al_registro"
    firmada = _hoja_firmada(api, productor, declaracion_id)
    assert firmada.status_code == 200, firmada.text
    vigente = firmada.json()["vigente"]
    assert firmada.json()["estado"] == "vigente" and vigente["declarada_en"] == hoy_lima().isoformat()
    assert [d["tipo"] for d in vigente["documentos"]] == ["hoja_declaracion_productor"]
    assert _productor_listo(api, parcela)["cumple"] is True
    assert _habilitar(api, admin, parcela).status_code == 200
    # La hoja firmada no se anula a mano.
    hoja = vigente["documentos"][0]["id"]
    assert api.como(admin).post(f"/documentos/{hoja}/anular", json={"motivo": "Prueba"}).status_code == 400


def test_el_productor_declara_desde_su_cuenta(api, sesion, operador, productor, cuenta):
    por_firmar = _registrar(api.como(operador), productor).json()["por_firmar"]
    sin_declaro = api.como(cuenta).post(
        "/mi/declaracion", json={"respuestas": RESPUESTAS_FAMILIA, "declaro": False}
    )
    assert sin_declaro.status_code == 422
    respuesta = api.como(cuenta).post(
        "/mi/declaracion", json={"respuestas": RESPUESTAS_FAMILIA, "declaro": True}
    )
    assert respuesta.status_code == 201, respuesta.text
    salida = respuesta.json()
    assert salida["estado"] == "vigente" and salida["vigente"]["origen"] == "productor"
    assert salida["vigente"]["declarada_en"] == hoy_lima().isoformat() and salida["por_firmar"] is None
    # Reemplaza a la que esperaba la firma, que se conserva.
    assert sesion.get(DeclaracionProductor, uuid.UUID(por_firmar["id"])).estado == "reemplazada"
    # El productor lee de tú; el personal, en tercera persona.
    assert salida["vigente"]["respuestas"][0]["pregunta"] == "¿Quién trabaja en tus parcelas?"
    copia = api.como(cuenta).get("/mi/declaracion/hoja")
    assert copia.status_code == 200 and copia.content.startswith(b"%PDF")


def test_declaracion_de_hace_13_meses_vence_y_observa_las_parcelas(api, sesion, operador, admin, productor):
    parcela = _lista(api, sesion, operador, productor)
    declaracion_vigente(sesion, productor, operador)
    assert _habilitar(api, admin, parcela).status_code == 200
    declaracion = sesion.scalar(
        select(DeclaracionProductor).where(DeclaracionProductor.productor_id == productor.id)
    )
    # Los triggers no dejan cambiar las fechas: se registra otra, de hace 13 meses, en su lugar.
    declaracion.estado = "reemplazada"
    sesion.flush()
    declaracion_vigente(sesion, productor, operador, declarada_en=hoy_lima() - timedelta(days=400))
    requisito = _productor_listo(api.como(operador), parcela)
    assert requisito["cumple"] is False and "declaración anual vencida" in requisito["detalle"]
    sesion.refresh(parcela)
    assert parcela.habilitacion_estado == "observada"
    salida = api.get(f"/productores/{productor.id}/declaracion").json()
    assert salida["estado"] == "vencida" and salida["pendientes"] == ["sin_declaracion_anual"]


def test_la_nueva_vigente_reemplaza_a_la_anterior_y_la_conserva(api, sesion, operador, productor):
    primera = declaracion_vigente(sesion, productor, operador, declarada_en=hoy_lima() - timedelta(days=200))
    por_firmar = _registrar(api.como(operador), productor).json()["por_firmar"]
    # Mientras está por firmar, no reemplaza a la vigente.
    assert sesion.get(DeclaracionProductor, primera.id).estado == "vigente"
    otra = _registrar(api, productor, EVENTUALES).json()["por_firmar"]
    assert sesion.get(DeclaracionProductor, uuid.UUID(por_firmar["id"])).estado == "reemplazada"
    _hoja_firmada(api, productor, otra["id"])
    sesion.expire_all()
    assert sesion.get(DeclaracionProductor, primera.id).estado == "reemplazada"
    historial = api.get(f"/productores/{productor.id}/declaracion").json()["historial"]
    assert [h["estado"] for h in historial] == ["vigente", "reemplazada", "reemplazada"]


# ---------- Cuestionario ----------


def test_solo_familia_responde_cuatro_preguntas(api, operador, productor):
    salida = _registrar(api.como(operador), productor).json()
    assert [r["codigo"] for r in salida["por_firmar"]["respuestas"]] == list(RESPUESTAS_FAMILIA)
    assert cuestionario.mostradas(RESPUESTAS_FAMILIA, {"area_total_ha": 10}) == list(RESPUESTAS_FAMILIA)


def test_preguntas_de_mas_o_de_menos_responden_422(api, operador, productor):
    api.como(operador)
    sobra = _registrar(api, productor, RESPUESTAS_FAMILIA | {"jornal_soles": 40})
    assert sobra.status_code == 422 and "no corresponden" in sobra.json()["error"]["mensaje"]
    falta = _registrar(api, productor, {k: v for k, v in EVENTUALES.items() if k != "horas_por_dia"})
    assert falta.status_code == 422 and "horas" in falta.json()["error"]["mensaje"]
    menores = _registrar(api, productor, RESPUESTAS_FAMILIA | {"menores_trabajan": "si_de_la_familia"})
    assert menores.status_code == 422  # pide la edad y la escuela
    desconocida = _registrar(api, productor, RESPUESTAS_FAMILIA | {"color_favorito": "verde"})
    assert desconocida.status_code == 422


@pytest.mark.parametrize(
    ("quien", "area", "mismo_pago", "descanso"),
    [("eventuales", 3, False, False), ("eventuales", 6, True, False), ("permanentes", 6, True, True)],
)
def test_las_preguntas_de_5_ha(quien, area, mismo_pago, descanso):
    mostradas = cuestionario.mostradas({"quien_trabaja": quien}, {"area_total_ha": area})
    assert ("mismo_pago" in mostradas) is mismo_pago
    assert ("descanso_maternidad_paternidad" in mostradas) is descanso


def test_el_cuestionario_y_los_valores_de_referencia(api, sesion, operador, productor):
    superadmin = factorias.perfil(sesion, "superadmin")
    cuest = api.como(operador).get("/declaraciones-productor/cuestionario").json()
    assert cuest["version"] == cuestionario.VERSION and len(cuest["preguntas"]) == 18
    assert cuest["uit_soles"] is None and cuest["jornal_minimo_referencia"] is None
    assert [b for b in cuest["anexo"] if b["en_pantalla"]][0]["texto"].startswith("**SEGUNDO.")
    # El valor de la UIT va con su año, y el jornal con su nota.
    api.como(superadmin)
    assert api.put("/admin/configuracion", json={"uit_soles": "5500"}).status_code == 422
    respuesta = api.put(
        "/admin/configuracion",
        json={
            "uit_soles": "5500",
            "uit_anio": 2026,
            "jornal_minimo_referencia": "45",
            "jornal_referencia_nota": "x",
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    # Cambiar la clasificación no borra la UIT.
    api.put("/admin/configuracion", json={"clasificacion_pais": None})
    cuest = api.como(operador).get("/declaraciones-productor/cuestionario").json()
    assert (cuest["uit_soles"], cuest["uit_anio"], cuest["jornal_minimo_referencia"]) == (5500.0, 2026, 45.0)
    # La declaración guarda los valores con que se evaluó.
    salida = _registrar(api.como(operador), productor).json()
    assert salida["por_firmar"]["contexto"]["uit_soles"] == 5500.0


# ---------- Requisitos ----------


def test_horas_de_mas_dejan_condiciones_por_atender(api, sesion, operador, productor, coop):
    declarar_anual(sesion, productor, operador, EVENTUALES | {"horas_por_dia": 10})
    salida = api.como(operador).get(f"/productores/{productor.id}/declaracion").json()
    condiciones = _req(salida, "condiciones_de_trabajo")
    assert condiciones["estado"] == "por_atender"
    assert condiciones["hechos"] == [
        {
            "pregunta": "horas_por_dia",
            "texto": "¿Cuántas horas se trabaja en un día normal?",
            "valor": "10 horas",
        }
    ]
    assert _estado(sesion, productor, coop).alertas == ["productor_por_atender"]


def test_el_jornal_se_compara_solo_con_una_referencia_registrada(api, sesion, operador, productor, coop):
    declarar_anual(sesion, productor, operador, EVENTUALES | {"jornal_soles": 30})
    assert _estado(sesion, productor, coop).requisitos["condiciones_de_trabajo"].estado == "declarado"
    declarar_anual(sesion, productor, operador, EVENTUALES | {"jornal_soles": 30}, jornal_referencia=45)
    r = _estado(sesion, productor, coop).requisitos["condiciones_de_trabajo"]
    assert r.estado == "por_atender" and r.hechos[0].pregunta == "jornal_soles"


def test_permanentes_sin_relacion_quedan_sin_sustento(api, sesion, operador, productor, coop):
    respuestas = EVENTUALES | {"quien_trabaja": "permanentes"}
    declaracion = declarar_anual(sesion, productor, operador, respuestas)
    r = _estado(sesion, productor, coop).requisitos["condiciones_de_trabajo"]
    assert (r.estado, r.falta) == ("sin_sustento", ["relacion_trabajadores"])
    respuesta = api.como(operador).post(
        f"/productores/{productor.id}/declaraciones/{declaracion.id}/documentos",
        data={"tipo": "relacion_trabajadores"},
        files={"archivo": ("relacion.pdf", PDF)},
    )
    assert respuesta.status_code == 201, respuesta.text
    r = _estado(sesion, productor, coop).requisitos["condiciones_de_trabajo"]
    assert (r.estado, r.nivel_verificacion) == ("sustentado", "documentado")
    # La declaración de renta no se pide con ventas de hasta 75 UIT.
    renta = api.post(
        f"/productores/{productor.id}/declaraciones/{declaracion.id}/documentos",
        data={"tipo": "declaracion_renta"},
        files={"archivo": ("renta.pdf", PDF)},
    )
    assert renta.status_code == 400


def test_menores_de_la_familia_no_bloquean(api, sesion, operador, admin, productor, coop):
    parcela = _lista(api, sesion, operador, productor)
    respuestas = RESPUESTAS_FAMILIA | {
        "menores_trabajan": "si_de_la_familia",
        "menor_edad_minima": 14,
        "menores_van_a_la_escuela": "si",
    }
    declarar_anual(sesion, productor, operador, respuestas)
    assert _estado(sesion, productor, coop).requisitos["menores_de_edad"].estado == "por_atender"
    habilitacion = api.como(operador).get(f"/parcelas/{parcela.id}/habilitacion").json()
    assert "productor_por_atender" in habilitacion["alertas"]
    assert _habilitar(api, admin, parcela, nota="Corta").status_code == 422
    assert _habilitar(api, admin, parcela).status_code == 200


def test_trabajo_no_libre_no_bloquea(api, sesion, operador, admin, productor, coop):
    parcela = _lista(api, sesion, operador, productor)
    declarar_anual(sesion, productor, operador, EVENTUALES | {"pueden_dejar_el_trabajo": "no"})
    assert _estado(sesion, productor, coop).requisitos["trabajo_libre"].estado == "por_atender"
    assert _habilitar(api, admin, parcela).status_code == 200


def test_agroquimicos_revision_y_copia(api, sesion, operador, productor, coop):
    respuestas = RESPUESTAS_FAMILIA | {
        "usa_agroquimicos": "si",
        "productos": [{"nombre": "Cobre Agrícola 50", "tipo": "fungicida"}],
        "quien_aplica": "yo_o_mi_familia",
        "destino_envases": "devuelve_o_centro_de_acopio",
    }
    salida = _registrar(api.como(operador), productor, respuestas).json()
    declaracion = salida["por_firmar"]
    _hoja_firmada(api, productor, declaracion["id"])
    r = _estado(sesion, productor, coop).requisitos
    assert (r["agroquimicos"].estado, r["envases"].estado) == ("sin_sustento", "declarado")
    producto = declaracion["productos"][0]
    ruta = f"/productores/{productor.id}/declaraciones/{declaracion['id']}/productos/{producto['id']}"
    respuesta = api.patch(ruta, json={"revision": "no_figura"})
    assert respuesta.status_code == 200, respuesta.text
    assert _estado(sesion, productor, coop).requisitos["agroquimicos"].estado == "por_atender"
    respuesta = api.patch(ruta, json={"revision": "figura", "registro": "PQUA N.° 123-SENASA"})
    assert _estado(sesion, productor, coop).requisitos["agroquimicos"].estado == "sustentado"
    revisado = respuesta.json()["vigente"]["productos"][0]
    assert revisado["registro"] == "PQUA N.° 123-SENASA" and revisado["copiada"] is False
    # Otro productor de la organización declara el mismo producto: la revisión se copia.
    vecino = factorias.productor(sesion, coop)
    otro = _registrar(
        api, vecino, respuestas | {"productos": [{"nombre": " cobre  agricola 50", "tipo": "fungicida"}]}
    )
    copiado = otro.json()["por_firmar"]["productos"][0]
    assert copiado["revision"] == "figura" and copiado["copiada"] is True
    fila = sesion.get(DeclaracionProducto, uuid.UUID(copiado["id"]))
    assert fila.copiada_de == uuid.UUID(producto["id"])
    # El mismo nombre con otro tipo no se copia.
    tercero = factorias.productor(sesion, coop)
    distinto = _registrar(
        api, tercero, respuestas | {"productos": [{"nombre": "Cobre Agrícola 50", "tipo": "otro"}]}
    )
    assert distinto.json()["por_firmar"]["productos"][0]["revision"] == "sin_revisar"
    # Los nombres declarados se sugieren.
    assert (
        "Cobre Agrícola 50"
        in api.get(f"/productores/{tercero.id}/declaracion").json()["sugerencias_productos"]
    )


def test_envases_quemados_dejan_envases_por_atender(sesion, operador, productor, coop):
    respuestas = RESPUESTAS_FAMILIA | {
        "usa_agroquimicos": "si",
        "productos": [{"nombre": "Abono foliar", "tipo": "fertilizante"}],
        "quien_aplica": "trabajadores",
        "destino_envases": "quema",
    }
    declarar_anual(sesion, productor, operador, respuestas, revisiones={"Abono foliar": "figura"})
    r = _estado(sesion, productor, coop).requisitos
    assert (r["envases"].estado, r["agroquimicos"].estado) == ("por_atender", "sustentado")


def test_tributos(api, sesion, operador, productor, coop):
    declaracion = declarar_anual(
        sesion, productor, operador, RESPUESTAS_FAMILIA | {"ventas_superan_75_uit": "si"}
    )
    r = _estado(sesion, productor, coop).requisitos["tributos"]
    assert (r.estado, r.falta) == ("sin_sustento", ["ruc", "declaracion_renta"])
    productor.ruc = "10456789012"
    sesion.flush()
    api.como(operador).post(
        f"/productores/{productor.id}/declaraciones/{declaracion.id}/documentos",
        data={"tipo": "declaracion_renta"},
        files={"archivo": ("renta.pdf", PDF)},
    )
    assert _estado(sesion, productor, coop).requisitos["tributos"].estado == "sustentado"
    declarar_anual(sesion, productor, operador, RESPUESTAS_FAMILIA | {"ventas_superan_75_uit": "no_sabe"})
    r = _estado(sesion, productor, coop).requisitos["tributos"]
    assert (r.estado, r.falta) == ("sin_sustento", ["ventas_no_sabe"])
    declarar_anual(sesion, productor, operador, RESPUESTAS_FAMILIA)
    assert _estado(sesion, productor, coop).requisitos["tributos"].estado == "no_aplica"


def test_sin_declaracion_todos_sin_dato_y_ninguno_dice_cumple(sesion, productor, coop):
    estado = _estado(sesion, productor, coop)
    assert {r.estado for r in estado.requisitos.values()} == {"sin_dato"}
    assert set(estado.requisitos) == set(requisitos_productor.CODIGOS)


def test_el_area_que_cruza_5_ha_avisa_sin_bloquear(api, sesion, operador, productor):
    _parcela(api, sesion, operador, productor, ancho=100)  # 1 ha
    declarar_anual(sesion, productor, operador, RESPUESTAS_FAMILIA, area_total_ha=1.0)
    assert api.get(f"/productores/{productor.id}/declaracion").json()["aviso_area"] is None
    _parcela(api, sesion, operador, productor, este=600, ancho=500)  # 5 ha más
    salida = api.get(f"/productores/{productor.id}/declaracion").json()
    assert salida["aviso_area"] and "5 ha" in salida["aviso_area"] and salida["estado"] == "vigente"


# ---------- Hoja, seguimiento, pendientes y lista ----------


def test_la_hoja_para_firmar(api, sesion, operador, productor, coop):
    respuestas = EVENTUALES | {"horas_por_dia": 10}
    por_firmar = _registrar(api.como(operador), productor, respuestas).json()["por_firmar"]
    respuesta = api.get(f"/productores/{productor.id}/declaraciones/{por_firmar['id']}/hoja")
    assert respuesta.status_code == 200 and respuesta.content.startswith(b"%PDF")
    declaracion = sesion.get(DeclaracionProductor, uuid.UUID(por_firmar["id"]))
    datos = {
        "productor": f"{productor.nombres} {productor.apellidos}",
        "dni": productor.dni,
        "organizacion": coop.razon_social,
    }
    documento = hoja_pdf.documento(datos, servicio.respuestas_salida(declaracion), version_cuestionario=1)
    texto = " ".join(documento.textos)
    assert productor.dni in texto and coop.razon_social in texto
    for r in servicio.respuestas_salida(declaracion):
        assert r["pregunta"] in texto and r["etiqueta"] in texto
    assert "DECLARACIÓN JURADA ANUAL DEL PRODUCTOR" in texto and "SEXTO. De la veracidad." in texto
    assert "Firma:" in texto and "Huella dactilar" in texto
    # De una declaración ya declarada sale la copia, sin las líneas para firmar.
    copia = hoja_pdf.documento(datos, [], copia="Copia de la declaración.", version_cuestionario=1)
    assert "Huella dactilar" not in " ".join(copia.textos)


def test_seguimiento_permisos_y_aislamiento(
    api, sesion, coop, otra, admin, operador, lector, productor, cuenta
):
    declaracion = declarar_anual(sesion, productor, operador, EVENTUALES | {"horas_por_dia": 10})
    ruta = f"/productores/{productor.id}/declaraciones/{declaracion.id}/seguimiento"
    assert api.como(operador).put(ruta, json={"nota": SEGUIMIENTO}).status_code == 403
    assert api.como(admin).put(ruta, json={"nota": "Muy corta"}).status_code == 422
    respuesta = api.put(ruta, json={"nota": SEGUIMIENTO})
    assert respuesta.status_code == 200 and respuesta.json()["vigente"]["seguimiento"]["nota"] == SEGUIMIENTO
    # El lector ve y no registra; el productor no ve el seguimiento.
    assert api.como(lector).get(f"/productores/{productor.id}/declaracion").status_code == 200
    assert _registrar(api, productor).status_code == 403
    assert api.como(cuenta).get("/mi/declaracion").json()["vigente"]["seguimiento"] is None
    # Otra organización recibe 404 en la declaración, la hoja, los productos y el seguimiento.
    ajeno = factorias.perfil(sesion, "admin_cooperativa", otra)
    api.como(ajeno)
    base = f"/productores/{productor.id}"
    assert api.get(f"{base}/declaracion").status_code == 404
    assert api.get(f"{base}/declaraciones/{declaracion.id}/hoja").status_code == 404
    assert api.put(ruta, json={"nota": SEGUIMIENTO}).status_code == 404
    assert (
        api.patch(
            f"{base}/declaraciones/{declaracion.id}/productos/{uuid.uuid4()}", json={"revision": "figura"}
        ).status_code
        == 404
    )
    assert _registrar(api, productor).status_code == 404
    # Cada acción queda en la auditoría.
    acciones = set(
        sesion.scalars(select(Auditoria.accion).where(Auditoria.entidad == "declaracion_productor"))
    )
    assert "declaracion_productor.seguimiento" in acciones


def test_auditoria_de_cada_accion(api, sesion, operador, productor):
    por_firmar = _registrar(api.como(operador), productor).json()["por_firmar"]
    _hoja_firmada(api, productor, por_firmar["id"])
    acciones = list(
        sesion.scalars(select(Auditoria.accion).where(Auditoria.entidad == "declaracion_productor"))
    )
    assert acciones.count("declaracion_productor.registrar") == 1
    assert acciones.count("declaracion_productor.hoja_firmada") == 1


def test_pendientes_del_inicio_y_filtro_de_la_lista(api, sesion, coop, operador, productor):
    vencido = factorias.productor(sesion, coop, apellidos="Vencido")
    por_vencer = factorias.productor(sesion, coop, apellidos="PorVencer")
    vigente = factorias.productor(sesion, coop, apellidos="Vigente")
    firmar = factorias.productor(sesion, coop, apellidos="Firmar")
    declaracion_vigente(sesion, vencido, operador, declarada_en=hoy_lima() - timedelta(days=400))
    declaracion_vigente(sesion, por_vencer, operador, declarada_en=hoy_lima() - timedelta(days=350))
    declaracion_vigente(sesion, vigente, operador)
    _registrar(api.como(operador), firmar)

    def filtro(caso):
        return {p["id"] for p in api.get("/productores", params={"declaracion": caso}).json()["items"]}

    assert filtro("vencida") == {str(vencido.id)}
    assert filtro("por_vencer") == {str(por_vencer.id)}
    assert filtro("por_firmar") == {str(firmar.id)}
    assert filtro("sin_declaracion") == {str(productor.id)}
    lista = {p["id"]: p for p in api.get("/productores").json()["items"]}
    assert lista[str(vigente.id)]["declaracion"] == "vigente"
    assert "declaracion_por_vencer" in lista[str(por_vencer.id)]["pendientes"]
    grupos = {g["clave"]: g for g in api.get("/pendientes").json()["grupos"]}
    grupo = grupos["declaraciones_productores"]
    assert grupo["prioridad"] == "vencido" and grupo["cantidad"] == 4
    assert [i["detalle"].split(" ")[0] for i in grupo["items"]] == ["Venció", "Vence", "Falta", "Sin"]
    assert grupo["items"][0]["enlace"] == f"#/productores/{vencido.id}/declaracion"


# ---------- Textos ----------


def test_textos_sin_palabras_que_califican():
    """Sección 13: ni "cumple" ni "incumple", ni "autorizado" ni "prohibido", ni las prohibidas de la
    Parte 4."""
    from app.pdf.declaracion_tenencia import textos as plantillas
    from app.textos import cargar
    from tests.test_analisis import PROHIBIDAS

    califican = re.compile(
        r"\b(cumple|incumple|cumplen|incumplen|autorizad[oa]s?|prohibid[oa]s?|complies|authori[sz]ed|prohibited)\b",
        re.I,
    )
    textos = [p.texto for p in cuestionario.PREGUNTAS] + [p.texto_personal for p in cuestionario.PREGUNTAS]
    textos += [p.ayuda for p in cuestionario.PREGUNTAS] + [
        e for p in cuestionario.PREGUNTAS for _, e in p.valores
    ]
    textos += [r.nombre for r in requisitos_productor.REQUISITOS] + [
        r.que_pide for r in requisitos_productor.REQUISITOS
    ]
    textos += list(requisitos_productor.ETIQUETAS_ESTADO.values()) + list(servicio.TEXTO_FALTA.values())
    textos += [b["texto"] for b in plantillas()["declaracion_productor"]["bloques"]]
    textos += [
        dop_pdf.revision_producto({"revision": r, "revisado_en": "2026-10-01", "registro": None})
        for r in ("figura", "no_figura", "sin_revisar")
    ]

    def cadenas(valor):
        if isinstance(valor, dict):
            for v in valor.values():
                yield from cadenas(v)
        elif isinstance(valor, str):
            yield valor

    for idioma in ("es", "en"):
        datos = cargar(idioma)
        textos += list(cadenas(datos["declaracion"]))
        textos += [datos["hallazgo"][c] for c in ESPERADOS] + [datos["mensaje"][c] for c in ESPERADOS]
    for texto in textos:
        assert not califican.search(texto), texto
        assert not PROHIBIDAS.search(texto), texto


ESPERADOS = (
    "condiciones_de_trabajo_por_atender",
    "menores_en_la_parcela",
    "trabajo_no_libre",
    "agroquimico_no_figura",
    "envases_por_atender",
    "agroquimicos_sin_revisar",
    "permanentes_sin_relacion",
    "tributos_sin_sustento",
)
