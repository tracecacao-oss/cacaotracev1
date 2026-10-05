"""Aislamiento entre cooperativas: prueba obligatoria con A y B en todo endpoint de datos.

Un usuario de A que pide un recurso de B recibe 404, y sus listados solo traen datos de A.
"""

import pytest

from tests import factorias


@pytest.fixture
def mundo(sesion):
    a = factorias.cooperativa(sesion, nombre="Coop A")
    b = factorias.cooperativa(sesion, nombre="Coop B")
    return {
        "a": a,
        "b": b,
        "admin_a": factorias.perfil(sesion, "admin_cooperativa", a),
        "operador_a": factorias.perfil(sesion, "operador", a),
        "productor_a": factorias.productor_con_acceso(sesion, a)[0],
        "productor_b": factorias.productor_con_acceso(sesion, b)[0],
        "personal_b": factorias.perfil(sesion, "lector", b),
        "admin_b": factorias.perfil(sesion, "admin_cooperativa", b),
    }


RECURSOS_DE_B = [
    ("get", "/productores/{productor_b}"),
    ("post", "/productores/{productor_b}/acceso"),
    ("post", "/productores/{productor_b}/acceso/restablecer-clave"),
    ("delete", "/productores/{productor_b}/acceso"),
    ("patch", "/usuarios/{personal_b}"),
    ("post", "/usuarios/{personal_b}/restablecer-clave"),
]


@pytest.mark.parametrize(("metodo", "ruta"), RECURSOS_DE_B)
def test_recurso_de_b_responde_404_a_un_usuario_de_a(api, mundo, auth_falso, metodo, ruta):
    actor = mundo["admin_a"]
    url = ruta.format(productor_b=mundo["productor_b"].id, personal_b=mundo["personal_b"].id)
    kwargs = {"json": {"nombres": "Intruso"}} if metodo == "patch" else {}
    respuesta = getattr(api.como(actor), metodo)(url, **kwargs)
    assert respuesta.status_code == 404
    assert auth_falso.llamadas == []  # nada se tocó en Supabase Auth


def test_listados_solo_traen_datos_de_a(api, mundo):
    api.como(mundo["admin_a"])
    productores = api.get("/productores").json()
    assert [p["id"] for p in productores["items"]] == [str(mundo["productor_a"].id)]
    usuarios = api.get("/usuarios").json()
    assert {u["id"] for u in usuarios["items"]} == {str(mundo["admin_a"].id), str(mundo["operador_a"].id)}
    assert str(mundo["b"].id) not in str(api.get("/auditoria").json())


def test_productor_creado_por_a_queda_en_a(api, sesion, mundo):
    nuevo = (
        api.como(mundo["operador_a"])
        .post("/productores", json={"dni": "90000099", "nombres": "Demo", "apellidos": "A"})
        .json()
    )
    assert api.como(mundo["admin_b"]).get(f"/productores/{nuevo['id']}").status_code == 404


def test_operador_que_envia_cabecera_de_otra_cooperativa_la_ve_ignorada(api, mundo):
    respuesta = api.como(mundo["operador_a"], cooperativa_id=mundo["b"].id).get("/productores")
    assert respuesta.status_code == 200
    assert [p["id"] for p in respuesta.json()["items"]] == [str(mundo["productor_a"].id)]


def test_cabecera_ignorada_tambien_en_escrituras(api, mundo):
    respuesta = api.como(mundo["operador_a"], cooperativa_id=mundo["b"].id).post(
        "/productores", json={"dni": "90000098", "nombres": "Demo", "apellidos": "A"}
    )
    assert respuesta.status_code == 201
    assert api.como(mundo["admin_a"]).get(f"/productores/{respuesta.json()['id']}").status_code == 200


def test_identificador_inventado_responde_404(api, mundo):
    api.como(mundo["admin_a"])
    assert api.get("/productores/00000000-0000-4000-8000-000000000000").status_code == 404
    assert api.get("/productores/no-es-uuid").status_code == 422
