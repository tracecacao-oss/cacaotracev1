"""Adenda 2 de la Parte 4: imágenes satelitales de la parcela y revisión de imágenes.

Copernicus y Esri Wayback llegan simulados (tests/imagenes_util.py): ninguna prueba sale a internet.
"""

import io
import json
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.fechas import ahora, dia_lima, hoy_lima
from app.models import (
    Auditoria,
    ConfiguracionCooperativa,
    ConsumoImagenes,
    DecisionHabilitacion,
    Documento,
    Dop,
    ImagenParcela,
    Lugar,
    Parcela,
)
from app.services import imagenes as servicio
from app.services import sentinel, wayback
from app.services.imagenes import LINDERO
from tests import factorias
from tests.factorias import crear_parcela, punto, rectangulo
from tests.habilitacion_util import (
    PDF,
    analisis_completado,
    fuentes_configuradas,
    legalidad_completa,
    productor_listo,
    visita,
)
from tests.imagenes_util import DESCRIPCION, ServiciosFalsos, png, procesar, proveedores, revision

RAIZ = Path(__file__).resolve().parents[2]
HOY = hoy_lima()
NUBES = {
    date(2019, 8, 1): 0.5,
    date(2020, 10, 1): 0.1,
    date(2020, 11, 20): 0.5,
    date(2020, 12, 19): 1.2,  # la utilizable más cercana al corte
    date(2020, 12, 29): 60.0,  # más cercana, pero nublada
    date(2021, 1, 3): 0.0,  # sin nubes, pero después del corte
    date(2021, 7, 14): 2.0,
    date(2022, 3, 1): 1.0,
    date(2022, 11, 30): 1.0,  # empata con la de marzo: gana la más cercana a fin de año
    date(2023, 5, 5): 80.0,  # 2023 sin escena utilizable
    HOY - timedelta(days=40): 0.2,
    HOY - timedelta(days=12): 0.8,  # la reciente
}
CAPTURAS = [
    {"version": 100, "publicada": "2023-02-02", "captura": date(2023, 1, 29), "proveedor": "Vantor"},
    # Publicada en 2021, capturada en 2019: se muestra 2019.
    {"version": 90, "publicada": "2021-03-17", "captura": date(2019, 6, 10), "proveedor": "Maxar"},
]
NOTA = "Se habilita: la revisión de imágenes muestra cacao bajo sombra antes y después del corte."


@pytest.fixture
def servicios():
    return ServiciosFalsos(nubes=dict(NUBES), capturas=list(CAPTURAS))


@pytest.fixture
def imagenes(servicios):
    return proveedores(servicios)


@pytest.fixture
def fuentes():
    return fuentes_configuradas()


@pytest.fixture
def coop(sesion):
    coop = factorias.cooperativa(sesion, "Coop Imágenes", codigo="CIM")
    sesion.add(ConfiguracionCooperativa(cooperativa_id=coop.id, tope_kg_seco_ha_anio=Decimal("2000")))
    sesion.flush()
    return coop


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def admin(sesion, coop):
    return factorias.perfil(sesion, "admin_cooperativa", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


def _parcela(api, sesion, operador, productor, geometria=None, nombre="Parcela Imágenes", **extra) -> Parcela:
    datos = crear_parcela(
        api.como(operador), productor.id, geometria or rectangulo(100, 100), nombre=nombre, **extra
    )
    assert datos.status_code == 201, datos.text
    return sesion.get(Parcela, uuid.UUID(datos.json()["id"]))


def _con_alerta(sesion, parcela, hace=timedelta(days=1)):
    analisis_completado(sesion, parcela, "whisp", resultado="more_info_needed", hace=hace)
    analisis_completado(sesion, parcela, "gfw", hace=hace)


@pytest.fixture
def parcela(api, sesion, operador, productor):
    parcela = _parcela(api, sesion, operador, productor)
    _con_alerta(sesion, parcela)
    return parcela


def _generar(sesion, parcela, storage) -> dict:
    assert servicio.asegurar_juego(sesion, parcela) is True
    procesar(sesion, storage)
    return servicio.salida(sesion, storage, parcela).model_dump(mode="json")


def _por_papel(salida: dict, papel: str, fuente: str = "sentinel2") -> list[dict]:
    return [i for i in salida["imagenes"] if i["papel"] == papel and i["fuente"] == fuente]


def _requisitos(api, parcela) -> dict:
    datos = api.get(f"/parcelas/{parcela.id}/habilitacion").json()
    return {r["codigo"]: r["cumple"] for r in datos["requisitos"]}


def _nueva_revision(api, parcela, **cambios):
    datos = {
        "observacion_2020": "cultivo_o_uso_agricola",
        "observacion_cambio": "sin_cambio_visible",
        "descripcion": DESCRIPCION,
    } | cambios
    return api.post(f"/parcelas/{parcela.id}/revisiones-imagenes", json=datos)


# ---------- Cuándo se generan ----------


def test_sin_alerta_no_se_genera_ninguna_imagen(api, sesion, operador, productor, servicios, storage_falso):
    parcela = _parcela(api, sesion, operador, productor)
    analisis_completado(sesion, parcela, "whisp", resultado="low")
    analisis_completado(sesion, parcela, "gfw")
    assert servicio.asegurar_juego(sesion, parcela) is False
    assert servicio.encolar_pendientes(sesion) == 0
    assert procesar(sesion, storage_falso) == 0
    assert sesion.query(ImagenParcela).filter_by(parcela_id=parcela.id).count() == 0
    assert servicios.peticiones == []

    api.como(operador)
    salida = api.get(f"/parcelas/{parcela.id}/imagenes").json()
    assert (salida["estado"], salida["tiene_alerta"], salida["imagenes"]) == ("sin_alerta", False, [])
    respuesta = api.post(f"/parcelas/{parcela.id}/imagenes")
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "sin_alerta"


def test_la_alerta_genera_el_juego(api, sesion, operador, productor, parcela, servicios, storage_falso):
    api.como(operador)
    assert servicio.encolar_pendientes(sesion) == 1
    assert api.get(f"/parcelas/{parcela.id}/imagenes").json()["estado"] == "pendiente"
    assert (
        sesion.query(Auditoria).filter_by(accion="imagenes.generar", entidad_id=str(parcela.id)).count() == 1
    )
    procesar(sesion, storage_falso)

    salida = api.get(f"/parcelas/{parcela.id}/imagenes").json()
    assert (salida["estado"], salida["tiene_alerta"]) == ("generada", True)
    [previa] = _por_papel(salida, "anterior_al_corte")
    assert previa["fecha_captura"] == "2020-12-19"
    assert previa["dias_respecto_al_corte"] == -12
    assert Decimal(previa["resolucion_m"]) == 10
    assert Decimal(previa["nubes_parcela_pct"]) == Decimal("1.2")
    assert (previa["identificador_fuente"], previa["proveedor"]) == ("S2B_MSIL2A_20201219", "Sentinel-2B")
    assert previa["url_natural"] and previa["url_infrarrojo"] and previa["sha256_natural"]

    anuales = {i["periodo"]: i for i in _por_papel(salida, "anual")}
    assert set(anuales) == set(range(2021, HOY.year))
    assert anuales[2021]["fecha_captura"] == "2021-01-03"
    assert anuales[2022]["fecha_captura"] == "2022-11-30"
    # Un año sin escena utilizable queda como espacio marcado en la tira.
    assert (anuales[2023]["estado"], anuales[2023]["fecha_captura"]) == ("sin_imagen_utilizable", None)
    [reciente] = _por_papel(salida, "reciente")
    assert reciente["fecha_captura"] == str(HOY - timedelta(days=12))

    # Wayback: la fecha de captura real, no la de publicación; sin imagen guardada.
    altas = _por_papel(salida, "alta_resolucion", "esri_wayback")
    assert [(a["fecha_captura"], a["proveedor"]) for a in altas] == [
        ("2019-06-10", "Maxar · WV02"),
        ("2023-01-29", "Vantor · WV02"),
    ]
    assert all(a["url_natural"] is None for a in altas)
    assert salida["atribucion_wayback"] == wayback.ATRIBUCION

    # Dos PNG por imagen de Sentinel-2 generada, con el lindero dibujado.
    generadas = [i for i in salida["imagenes"] if i["fuente"] == "sentinel2" and i["estado"] == "generada"]
    pngs = [r for r in storage_falso.archivos if "/imagen/" in r]
    assert len(pngs) == 2 * len(generadas)
    natural = sesion.get(ImagenParcela, uuid.UUID(previa["id"])).documento_natural_id
    dibujo = Image.open(io.BytesIO(storage_falso.archivos[sesion.get(Documento, natural).ruta]))
    assert min(dibujo.size) == servicio.LADO_MINIMO_PX
    assert LINDERO in {color for _, color in dibujo.getcolors(maxcolors=100_000)}

    consumo = sesion.query(ConsumoImagenes).filter_by(parcela_id=parcela.id).one()
    assert consumo.pu > 0 and consumo.peticiones > 0
    # Ya tiene juego: no se encola otro.
    assert servicio.asegurar_juego(sesion, parcela) is False


def test_a_copernicus_solo_va_la_geometria(api, sesion, coop, operador, servicios, storage_falso):
    productor = factorias.productor(sesion, coop, nombres="Rosa Elvira", apellidos="Quispe Huamán")
    parcela = _parcela(api, sesion, operador, productor, nombre="Chacra Secreta")
    _con_alerta(sesion, parcela)
    _generar(sesion, parcela, storage_falso)
    cuerpos = " ".join(p.content.decode() for p in servicios.peticiones if p.method == "POST")
    for dato in ("Rosa", "Quispe", productor.dni, "Chacra Secreta", parcela.codigo):
        assert dato not in cuerpos


def test_un_punto_se_recorta_como_circulo(api, sesion, operador, productor, servicios, storage_falso):
    parcela = _parcela(api, sesion, operador, productor, punto(), area_declarada_ha="3")
    _con_alerta(sesion, parcela)
    _generar(sesion, parcela, storage_falso)
    [estadistica, *_] = servicios.de(sentinel.ESTADISTICA)
    geometria = json.loads(estadistica.content)["input"]["bounds"]["geometry"]
    assert geometria["type"] == "Polygon" and len(geometria["coordinates"][0]) > 30


# ---------- Selección de escenas ----------


def test_2020_nublado_retrocede_a_2019(api, sesion, parcela, servicios, storage_falso):
    servicios.nubes = {d: (40.0 if d.year == 2020 else p) for d, p in NUBES.items()}
    [previa] = _por_papel(_generar(sesion, parcela, storage_falso), "anterior_al_corte")
    assert previa["fecha_captura"] == "2019-08-01"


def test_sin_escena_antes_del_corte(api, sesion, parcela, servicios, storage_falso):
    servicios.nubes = {d: p for d, p in NUBES.items() if d > servicio.CORTE}
    [previa] = _por_papel(_generar(sesion, parcela, storage_falso), "anterior_al_corte")
    assert (previa["estado"], previa["fecha_captura"]) == ("sin_imagen_utilizable", None)


def test_escena_que_no_cubre_la_parcela_no_sirve(api, sesion, parcela, servicios, storage_falso):
    servicios.sin_dato = {date(2020, 12, 19): 300}
    [previa] = _por_papel(_generar(sesion, parcela, storage_falso), "anterior_al_corte")
    assert previa["fecha_captura"] == "2020-11-20"


def test_copernicus_falla(api, sesion, parcela, servicios, storage_falso):
    servicios.falla_proceso = True
    salida = _generar(sesion, parcela, storage_falso)
    errores = [i for i in salida["imagenes"] if i["fuente"] == "sentinel2" and i["estado"] == "error"]
    assert errores and all("HTTP 500" in i["error_detalle"] for i in errores)
    assert not any("/imagen/" in r for r in storage_falso.archivos)


def test_un_juego_que_fallo_entero_se_vuelve_a_pedir(api, sesion, parcela, servicios, storage_falso):
    servicios.nubes = {}
    servicios.falla_proceso = True
    _generar(sesion, parcela, storage_falso)
    # Falla todo (también Wayback, sin versiones simuladas): la tarea diaria lo vuelve a pedir.
    for fila in servicio.juego_actual(sesion, parcela):
        fila.estado = "error"
    sesion.flush()
    servicios.nubes, servicios.falla_proceso = dict(NUBES), False
    assert servicio.asegurar_juego(sesion, parcela) is True
    procesar(sesion, storage_falso)
    [previa] = _por_papel(
        servicio.salida(sesion, storage_falso, parcela).model_dump(mode="json"), "anterior_al_corte"
    )
    assert previa["estado"] == "generada"
    # Un juego con alguna imagen generada no se repite solo.
    assert servicio.asegurar_juego(sesion, parcela) is False


def test_no_configurada(api, sesion, admin, parcela, imagenes):
    imagenes.sentinel.client_id = None
    api.como(admin)
    assert api.get(f"/parcelas/{parcela.id}/imagenes").json()["estado"] == "no_configurada"
    assert servicio.asegurar_juego(sesion, parcela) is False
    assert (
        api.post(f"/parcelas/{parcela.id}/imagenes").json()["error"]["codigo"] == "imagenes_no_configuradas"
    )


# ---------- Acciones del personal ----------


def test_regenerar_y_buscar_mas(api, sesion, operador, admin, parcela, storage_falso):
    primera = _generar(sesion, parcela, storage_falso)
    api.como(operador)
    assert api.post(f"/parcelas/{parcela.id}/imagenes/buscar-mas").status_code == 403

    api.como(admin)
    assert api.post(f"/parcelas/{parcela.id}/imagenes/buscar-mas").status_code == 202
    en_curso = api.post(f"/parcelas/{parcela.id}/imagenes/buscar-mas")
    assert en_curso.status_code == 409
    procesar(sesion, storage_falso)
    salida = api.get(f"/parcelas/{parcela.id}/imagenes").json()
    # Las más cercanas al corte que no estaban; las que no encuentra no dejan huecos.
    assert [i["fecha_captura"] for i in _por_papel(salida, "anterior_al_corte")] == [
        "2019-08-01",
        "2020-10-01",
        "2020-11-20",
        "2020-12-19",
    ]
    # No hay una reciente más nueva: queda la misma.
    assert [i["id"] for i in _por_papel(salida, "reciente")] == [
        i["id"] for i in _por_papel(primera, "reciente")
    ]

    # Regenerar deja el juego anterior como historial y pide uno nuevo.
    api.como(operador)
    assert api.post(f"/parcelas/{parcela.id}/imagenes").status_code == 202
    assert api.post(f"/parcelas/{parcela.id}/imagenes").status_code == 409
    viejas = sesion.query(ImagenParcela).filter(
        ImagenParcela.parcela_id == parcela.id, ImagenParcela.reemplazada_en.isnot(None)
    )
    assert viejas.count() >= len(primera["imagenes"])
    procesar(sesion, storage_falso)
    assert api.get(f"/parcelas/{parcela.id}/imagenes").json()["estado"] == "generada"
    origenes = [
        a.detalle["origen"]
        for a in sesion.query(Auditoria).filter_by(accion="imagenes.generar", entidad_id=str(parcela.id))
    ]
    assert sorted(origenes) == ["alerta", "buscar_mas", "regenerar"]


def test_cargar_imagen_externa(api, sesion, operador, admin, parcela, storage_falso):
    datos = {"fuente": "Planet (cuenta de la cooperativa)", "fecha_captura": "2020-11-02"}
    archivo = {"archivo": ("planet.png", png(), "image/png")}
    ruta = f"/parcelas/{parcela.id}/imagenes/externa"
    assert api.como(operador).post(ruta, data=datos, files=archivo).status_code == 403
    api.como(admin)
    futura = api.post(ruta, data=datos | {"fecha_captura": str(HOY + timedelta(days=1))}, files=archivo)
    assert futura.status_code == 422
    pdf = api.post(ruta, data=datos, files={"archivo": ("planet.pdf", PDF, "application/pdf")})
    assert pdf.status_code == 422 and pdf.json()["error"]["codigo"] == "formato_no_admitido"
    respuesta = api.post(ruta, data=datos, files=archivo)
    assert respuesta.status_code == 201, respuesta.text
    [externa] = _por_papel(respuesta.json(), "externa", "externa")
    assert (externa["fecha_captura"], externa["proveedor"]) == ("2020-11-02", datos["fuente"])
    assert externa["url_natural"]
    assert sesion.query(Auditoria).filter_by(accion="imagenes.cargar_externa").count() == 1


# ---------- La revisión ----------


def test_registrar_revision(api, sesion, operador, admin, productor, parcela, storage_falso):
    api.como(admin)
    sin_imagenes = _nueva_revision(api, parcela)
    assert sin_imagenes.status_code == 400
    assert sin_imagenes.json()["error"]["codigo"] == "imagenes_insuficientes"

    _generar(sesion, parcela, storage_falso)
    assert _nueva_revision(api.como(operador), parcela).status_code == 403
    api.como(admin)
    corta = _nueva_revision(api, parcela, descripcion="Cacao bajo sombra ok")
    assert corta.status_code == 422
    respuesta = _nueva_revision(api, parcela)
    assert respuesta.status_code == 201, respuesta.text
    [creada] = respuesta.json()
    assert creada["vigente"] is True
    assert creada["revisada_por_nombre"]
    assert len(creada["imagenes"]) == sum(
        f.estado == "generada" for f in servicio.juego_actual(sesion, parcela)
    )
    assert sesion.query(Auditoria).filter_by(accion="revision_imagenes.registrar").count() == 1
    assert _requisitos(api, parcela)["revision_atendida"] is True

    # No se edita ni se borra; solo se anula, una vez.
    for sql in (
        "UPDATE revisiones_imagenes SET descripcion = 'x'",
        "DELETE FROM revisiones_imagenes",
    ):
        with pytest.raises(DBAPIError), sesion.begin_nested():
            sesion.execute(text(sql))
    ruta = f"/revisiones-imagenes/{creada['id']}/anular"
    assert api.como(operador).post(ruta, json={"motivo": "Revisé otra parcela"}).status_code == 403
    anulada = api.como(admin).post(ruta, json={"motivo": "Revisé otra parcela"})
    assert anulada.json()[0]["vigente"] is False
    assert api.post(ruta, json={"motivo": "otra vez"}).status_code == 400
    assert _requisitos(api, parcela)["revision_atendida"] is False


def test_revision_sin_imagen_anterior_al_corte(api, sesion, admin, parcela, servicios, storage_falso):
    servicios.nubes = {d: p for d, p in NUBES.items() if d > servicio.CORTE}
    _generar(sesion, parcela, storage_falso)
    respuesta = _nueva_revision(api.como(admin), parcela)
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "imagenes_insuficientes"


@pytest.mark.parametrize(
    ("observacion_2020", "observacion_cambio", "atendida"),
    [
        ("cultivo_o_uso_agricola", "sin_cambio_visible", True),
        ("bosque", "cambio_visible", True),
        ("no_se_distingue", "sin_cambio_visible", False),
        ("bosque", "no_se_distingue", False),
    ],
)
def test_revision_atendida_segun_lo_observado(
    api, sesion, admin, parcela, observacion_2020, observacion_cambio, atendida
):
    revision(sesion, parcela, admin, observacion_2020=observacion_2020, observacion_cambio=observacion_cambio)
    assert _requisitos(api.como(admin), parcela)["revision_atendida"] is atendida


def test_una_visita_ya_no_atiende_la_alerta(api, sesion, operador, admin, parcela):
    visita(sesion, parcela, operador, motivo="analisis_requiere_revision")
    requisito = next(
        r
        for r in api.como(admin).get(f"/parcelas/{parcela.id}/habilitacion").json()["requisitos"]
        if r["codigo"] == "revision_atendida"
    )
    assert requisito["cumple"] is False
    assert "Imágenes" in requisito["detalle"]


def test_cambia_la_geometria_despues_de_la_revision(api, sesion, admin, parcela, storage_falso):
    _generar(sesion, parcela, storage_falso)
    assert _nueva_revision(api.como(admin), parcela).status_code == 201
    cambio = api.patch(
        f"/parcelas/{parcela.id}",
        json={"geometria": rectangulo(100, 120), "motivo": "Se corrigió el lindero norte."},
    )
    assert cambio.status_code == 200, cambio.text
    sesion.refresh(parcela)
    assert api.get(f"/parcelas/{parcela.id}/revisiones-imagenes").json()[0]["vigente"] is False
    assert api.get(f"/parcelas/{parcela.id}/imagenes").json()["imagenes"] == []

    # Con el análisis de la geometría nueva vuelve la alerta y se genera un juego nuevo.
    _con_alerta(sesion, parcela, hace=timedelta(minutes=5))
    assert _requisitos(api, parcela)["revision_atendida"] is False
    assert servicio.asegurar_juego(sesion, parcela) is True


def test_un_analisis_posterior_no_vence_la_revision(api, sesion, admin, parcela):
    """Decisión del equipo del 2026-10-05: la parcela revisada queda así aunque se renueve el análisis."""
    revision(sesion, parcela, admin, revisada_en=ahora() - timedelta(hours=2))
    assert _requisitos(api.como(admin), parcela)["revision_atendida"] is True
    _con_alerta(sesion, parcela, hace=timedelta(hours=1))
    assert _requisitos(api, parcela)["revision_atendida"] is True
    assert api.get(f"/parcelas/{parcela.id}/revisiones-imagenes").json()[0]["vigente"] is True


def test_habilitar_con_cambio_visible_exige_nota(api, sesion, operador, admin, productor, parcela):
    legalidad_completa(sesion, parcela, operador)
    productor_listo(sesion, productor, operador)
    revision(sesion, parcela, admin, observacion_2020="bosque", observacion_cambio="cambio_visible")
    api.como(admin)
    sin_nota = api.post(f"/parcelas/{parcela.id}/habilitar", json={})
    assert sin_nota.status_code == 422
    assert sin_nota.json()["error"]["codigo"] == "nota_requerida"
    respuesta = api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA})
    assert respuesta.json()["estado"] == "habilitada"
    decision = sesion.query(DecisionHabilitacion).filter_by(parcela_id=parcela.id).one()
    assert decision.requisitos["revision_imagenes"]["observacion_cambio"] == "cambio_visible"


def test_excluir_citando_una_revision_ajena_o_anulada(api, sesion, operador, admin, productor, parcela):
    otra = _parcela(api, sesion, operador, productor, rectangulo(100, 100, norte_m=500), nombre="Otra")
    ajena = revision(sesion, otra, admin)
    datos = {
        "descripcion": "Las imágenes muestran bosque en 2020 y tala con quema en 2023 dentro del polígono.",
        "evidencia_revision_id": str(ajena.id),
        "confirmacion": "EXCLUIR",
    }
    respuesta = api.como(admin).post(f"/parcelas/{parcela.id}/excluir", json=datos)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "evidencia_invalida"


# ---------- Cuota ----------


def test_cuota_al_80_por_ciento(api, sesion, coop, admin, parcela, servicios, storage_falso):
    sesion.add(
        ConsumoImagenes(
            mes=servicio._primer_dia_del_mes(),
            parcela_id=parcela.id,
            cooperativa_id=coop.id,
            pu=Decimal("24000"),
            peticiones=1000,
        )
    )
    sesion.flush()
    assert servicio.asegurar_juego(sesion, parcela) is True
    assert procesar(sesion, storage_falso) == 0
    assert servicios.peticiones == []
    assert api.como(admin).get(f"/parcelas/{parcela.id}/imagenes").json()["estado"] == "pausada"

    assert api.get("/admin/imagenes/consumo").status_code == 403
    consumo = api.como(factorias.perfil(sesion, "superadmin")).get("/admin/imagenes/consumo").json()
    assert (consumo["usadas_pu"], consumo["cuota_pu"], consumo["umbral_pu"]) == (24000, 30000, 24000)
    assert consumo["en_pausa"] is True and consumo["configurada"] is True
    assert consumo["pendientes"] > 0


# ---------- Quién ve qué ----------


def test_el_productor_solo_lee(api, sesion, coop, operador, storage_falso):
    productor, cuenta = factorias.productor_con_acceso(sesion, coop)
    parcela = _parcela(api, sesion, operador, productor)
    _con_alerta(sesion, parcela)
    _generar(sesion, parcela, storage_falso)
    api.como(cuenta)
    assert api.get(f"/mi/parcelas/{parcela.id}/imagenes").json()["estado"] == "generada"
    assert api.get(f"/mi/parcelas/{parcela.id}/revisiones-imagenes").json() == []
    assert api.get(f"/parcelas/{parcela.id}/imagenes").status_code == 403
    assert api.post(f"/parcelas/{parcela.id}/imagenes").status_code == 403
    assert _nueva_revision(api, parcela).status_code == 403


def test_otra_cooperativa_no_ve_las_imagenes(api, sesion, parcela, storage_falso):
    _generar(sesion, parcela, storage_falso)
    admin_b = factorias.perfil(sesion, "admin_cooperativa", factorias.cooperativa(sesion, "Coop B"))
    api.como(admin_b)
    assert api.get(f"/parcelas/{parcela.id}/imagenes").status_code == 404
    assert api.post(f"/parcelas/{parcela.id}/imagenes/buscar-mas").status_code == 404
    assert _nueva_revision(api, parcela).status_code == 404


def test_los_textos_no_proponen_una_visita(api, sesion, admin, parcela):
    api.como(admin)
    for ruta in (f"/parcelas/{parcela.id}", f"/parcelas/{parcela.id}/habilitacion"):
        assert "visita" not in api.get(ruta).text.lower()
    # En la interfaz, ninguna pantalla propone una visita ni una revisión en campo ante un análisis.
    propuestas = re.compile(
        r"registrar visita|visita la parcela|piden? visita|revisi[oó]n en campo|en campo que no|"
        r"revisar[aá] tu parcela en campo|pesta[nñ]a visitas",
        re.IGNORECASE,
    )
    encontradas = [
        f"{a.name}: {m.group(0)}"
        for a in (RAIZ / "frontend").rglob("*.js")
        for m in propuestas.finditer(a.read_text(encoding="utf-8"))
    ]
    assert encontradas == []


# ---------- DOP ----------


def test_el_dop_lleva_las_imagenes_y_la_revision(
    api, sesion, coop, operador, admin, productor, parcela, storage_falso
):
    _generar(sesion, parcela, storage_falso)
    legalidad_completa(sesion, parcela, operador)
    productor_listo(sesion, productor, operador)
    api.como(admin)
    assert _nueva_revision(api, parcela).status_code == 201
    assert api.post(f"/parcelas/{parcela.id}/habilitar", json={"nota": NOTA}).status_code == 200

    lugar = Lugar(
        cooperativa_id=coop.id,
        nombre="Cancha central",
        tipo="cancha_acopio",
        departamento="SAN MARTIN",
        provincia="PICOTA",
        distrito="PICOTA",
    )
    sesion.add(lugar)
    sesion.flush()
    recibida = ahora() - timedelta(hours=1)
    dia = dia_lima(recibida)
    tanda = (
        api.como(operador)
        .post(
            "/tandas",
            json={
                "productor_id": str(productor.id),
                "parcela_id": str(parcela.id),
                "lugar_id": str(lugar.id),
                "recibida_en": recibida.isoformat(),
                "estado_producto": "seco",
                "peso_kg": "100.00",
                "variedad": "ccn_51",
                "cosecha_desde": str(dia - timedelta(days=10)),
                "cosecha_hasta": str(dia - timedelta(days=3)),
                "doc_entrega_tipo": "guia_remision",
                "doc_entrega_numero": "T001-123",
                "doc_entrega_fecha_emision": str(dia),
                "doc_entrega_ruc_emisor": "20123456789",
            },
        )
        .json()
    )
    api.post(f"/tandas/{tanda['id']}/documentos", files={"archivo": ("guia.pdf", PDF, "application/pdf")})
    nota = "Se valida: la alerta de análisis de la parcela quedó atendida con la revisión de imágenes."
    respuesta = api.post(f"/tandas/{tanda['id']}/validar", json={"nota": nota})
    assert respuesta.status_code == 200, respuesta.text

    dop = sesion.query(Dop).filter_by(tanda_id=uuid.UUID(tanda["id"])).one()
    bloque = dop.contenido["imagenes"]
    assert bloque["anterior_al_corte"]["fecha_captura"] == "2020-12-19"
    assert bloque["reciente"]["fecha_captura"] == str(HOY - timedelta(days=12))
    assert bloque["anterior_al_corte"]["atribucion"] == "Contains modified Copernicus Sentinel data 2020"
    assert [a["fecha_captura"] for a in bloque["alta_resolucion"]] == ["2019-06-10", "2023-01-29"]
    assert bloque["revision"]["observacion_cambio"] == "sin_cambio_visible"
    pdf = storage_falso.archivos[sesion.get(Documento, dop.pdf_documento_id).ruta]
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Subtype /Image") >= 2


def test_el_dop_sin_alerta_no_lleva_imagenes(api, sesion, operador, productor):
    from app.services import dops

    parcela = _parcela(api, sesion, operador, productor)
    analisis_completado(sesion, parcela, "whisp", resultado="low")
    assert servicio.para_dop(sesion, parcela, None) == (None, {})
    assert dops.VERSION_CONTENIDO >= 2
