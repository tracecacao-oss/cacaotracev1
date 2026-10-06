"""Catálogo oficial de ubicaciones (INEI): validación de departamento, provincia y distrito."""

import pytest

from app import ubigeo
from app.models import Auditoria
from tests import factorias
from tests.factorias import crear_parcela, rectangulo


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


@pytest.fixture
def productor(sesion, coop):
    return factorias.productor(sesion, coop)


@pytest.fixture
def superadmin(sesion):
    return factorias.perfil(sesion, "superadmin")


def _error(respuesta) -> dict:
    return respuesta.json()["error"]


# --- El catálogo ---


def test_catalogo_completo_del_inei():
    c = ubigeo.catalogo()
    assert len(c.departamentos) == 25
    assert len(c.provincias) == 196
    assert len(c.distritos) == 1891
    assert c.arbol["SAN MARTIN"]["PICOTA"][0] == "PICOTA"
    assert "CAÑETE" in c.arbol["LIMA"]


def test_nombres_oficiales_sin_importar_tildes_ni_mayusculas():
    assert ubigeo.oficial("San Martín", "picota ", "Tres  Unidos") == ("SAN MARTIN", "PICOTA", "TRES UNIDOS")
    assert ubigeo.oficial("lima", "Canete", "san vicente de canete") == (
        "LIMA",
        "CAÑETE",
        "SAN VICENTE DE CAÑETE",
    )
    assert ubigeo.oficial("JUNIN", "SATIPO", "Vizcatan del Ene")[2] == "VIZCATÁN DEL ENE"


@pytest.mark.parametrize(
    ("terna", "texto"),
    [
        (("Narnia", "PICOTA", "PICOTA"), "departamento «Narnia»"),
        (("SAN MARTIN", "SATIPO", "SATIPO"), "provincia «SATIPO» no pertenece a SAN MARTIN"),
        (("SAN MARTIN", "PICOTA", "TARAPOTO"), "distrito «TARAPOTO» no pertenece a PICOTA, SAN MARTIN"),
    ],
)
def test_combinacion_que_no_existe(terna, texto):
    with pytest.raises(Exception) as exc:
        ubigeo.oficial(*terna)
    assert exc.value.status_code == 422
    assert exc.value.detail["codigo"] == "ubigeo_invalido"
    assert texto in exc.value.detail["mensaje"]


def test_endpoint_del_catalogo(api, operador):
    respuesta = api.como(operador).get("/ubigeos")
    assert respuesta.status_code == 200
    assert "max-age" in respuesta.headers["cache-control"]
    datos = respuesta.json()
    assert datos["fuente"].startswith("INEI")
    assert len(datos["departamentos"]) == 25
    amazonas = datos["departamentos"][0]
    assert amazonas["nombre"] == "AMAZONAS"
    assert amazonas["provincias"][0] == {
        "nombre": "CHACHAPOYAS",
        "distritos": amazonas["provincias"][0]["distritos"],
    }
    assert sum(len(p["distritos"]) for d in datos["departamentos"] for p in d["provincias"]) == 1891


def test_endpoint_del_catalogo_exige_sesion(api):
    assert api.get("/ubigeos").status_code == 401


# --- Parcelas ---


def test_parcela_guarda_los_nombres_oficiales(api, operador, productor):
    respuesta = crear_parcela(
        api.como(operador),
        productor.id,
        rectangulo(100, 100),
        departamento="San Martín",
        provincia="Picota",
        distrito="Tres Unidos",
    )
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert (datos["departamento"], datos["provincia"], datos["distrito"]) == (
        "SAN MARTIN",
        "PICOTA",
        "TRES UNIDOS",
    )


def test_parcela_con_distrito_de_otra_provincia(api, operador, productor):
    respuesta = crear_parcela(
        api.como(operador), productor.id, rectangulo(100, 100), provincia="PICOTA", distrito="TARAPOTO"
    )
    assert respuesta.status_code == 422
    assert _error(respuesta)["codigo"] == "ubigeo_invalido"


def test_editar_solo_el_distrito_valida_la_terna(api, operador, productor):
    api.como(operador)
    parcela = crear_parcela(api, productor.id, rectangulo(100, 100)).json()
    malo = api.patch(f"/parcelas/{parcela['id']}", json={"distrito": "Tarapoto"})
    assert _error(malo)["codigo"] == "ubigeo_invalido"
    bueno = api.patch(f"/parcelas/{parcela['id']}", json={"distrito": "pucacaca"})
    assert bueno.status_code == 200, bueno.text
    assert bueno.json()["distrito"] == "PUCACACA"


# --- Cooperativas ---


def test_cooperativa_nueva_con_nombres_oficiales(api, sesion, superadmin):
    respuesta = api.como(superadmin).post(
        "/admin/cooperativas",
        json={
            "razon_social": "Coop Ubicada",
            "codigo": "CUB",
            "tipo_organizacion": "cooperativa_agraria",
            "ruc": "20999999931",
            "departamento": "Cusco",
            "provincia": "La Convención",
            "distrito": "Echarate",
            "administrador": {"nombres": "A", "apellidos": "B", "correo": "ubicada@prueba.test"},
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    coop = respuesta.json()["cooperativa"]
    assert (coop["departamento"], coop["provincia"], coop["distrito"]) == (
        "CUSCO",
        "LA CONVENCION",
        "ECHARATE",
    )
    fila = sesion.query(Auditoria).filter_by(accion="cooperativa.crear").one()
    assert fila.detalle["provincia"] == "LA CONVENCION"


def test_cooperativa_con_ubicacion_inventada_no_se_crea(api, sesion, superadmin, auth_falso):
    respuesta = api.como(superadmin).post(
        "/admin/cooperativas",
        json={
            "razon_social": "Coop Sin Lugar",
            "codigo": "CSL",
            "tipo_organizacion": "empresa",
            "ruc": "20999999932",
            "departamento": "Departamento X",
            "provincia": "Provincia X",
            "distrito": "Distrito X",
            "administrador": {"nombres": "A", "apellidos": "B", "correo": "sinlugar@prueba.test"},
        },
    )
    assert respuesta.status_code == 422
    assert _error(respuesta)["codigo"] == "ubigeo_invalido"
    assert not auth_falso.usuarios


def test_cooperativa_previa_al_catalogo_se_edita_sin_tocar_su_ubicacion(api, sesion, superadmin):
    coop = factorias.cooperativa(sesion)
    coop.departamento, coop.provincia, coop.distrito = "San Martín", "Provincia X", "Distrito X"
    sesion.flush()
    api.como(superadmin)
    assert (
        api.patch(f"/admin/cooperativas/{coop.id}", json={"razon_social": "Coop Antigua"}).status_code == 200
    )
    # Al cambiar la ubicación se exige la terna completa del catálogo.
    malo = api.patch(f"/admin/cooperativas/{coop.id}", json={"distrito": "Picota"})
    assert _error(malo)["codigo"] == "ubigeo_invalido"
    bueno = api.patch(
        f"/admin/cooperativas/{coop.id}",
        json={"departamento": "San Martín", "provincia": "Picota", "distrito": "Picota"},
    )
    assert bueno.status_code == 200
    assert bueno.json()["departamento"] == "SAN MARTIN"
