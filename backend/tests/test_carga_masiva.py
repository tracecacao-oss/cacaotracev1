"""Carga masiva de productores desde .csv o .xlsx: revisar sin guardar y registrar las filas listas."""

import io

import openpyxl
import pytest

from app.models import Afiliacion, Auditoria, Productor
from tests import factorias

ENCABEZADOS = "DNI;Nombres;Apellidos;Dirección;Teléfono;PPA;Código PPA;Código socio"


@pytest.fixture
def coop(sesion):
    return factorias.cooperativa(sesion)


@pytest.fixture
def operador(sesion, coop):
    return factorias.perfil(sesion, "operador", coop)


def _csv(*filas: str, encabezados: str = ENCABEZADOS) -> tuple[str, bytes]:
    return ("productores.csv", "\r\n".join([encabezados, *filas]).encode("cp1252"))


def _analizar(api, archivo):
    return api.post("/productores/carga-masiva/analizar", files={"archivo": archivo})


def _registrar(api, archivo):
    return api.post("/productores/carga-masiva", files={"archivo": archivo})


def test_revisar_no_guarda_nada(api, sesion, operador):
    archivo = _csv(
        "80000001;Ana;Demo Uno;Caserío Demo s/n;;sí;PPA-1;S-1", "80000002;Luis;Demo Dos;Caserío Demo;;;;"
    )
    respuesta = _analizar(api.como(operador), archivo)
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert (datos["total"], datos["listas"], datos["con_problemas"]) == (2, 2, 0)
    assert [f["estado"] for f in datos["filas"]] == ["lista", "lista"]
    assert sesion.query(Productor).filter(Productor.dni.in_(["80000001", "80000002"])).count() == 0


def test_registrar_las_filas_listas_y_omitir_las_demas(api, sesion, coop, operador):
    ya = factorias.productor(sesion, coop, dni="80000010")
    otra = factorias.cooperativa(sesion, "Coop Otra")
    factorias.productor(sesion, otra, dni="80000011")
    archivo = _csv(
        "80000001;Ana;Demo Uno;Caserío Demo s/n;900000001;sí;PPA-1;S-1",
        "800001;Sin;Ceros;Caserío Demo;;;;",  # Excel borró los ceros: 6 cifras se completan a 00800001
        "80000001;Ana;Repetida;Caserío Demo;;;;",
        f"{ya.dni};Ya;Registrado;Caserío Demo;;;;",
        "80000011;De;Otra;Caserío Demo;;;;",
        "1234;Dni;Corto;Caserío Demo;;;;",
        "80000003;;Sin Nombres;;;quizás;;",
    )
    respuesta = _registrar(api.como(operador), archivo)
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    estados = {f["fila"]: (f["estado"], f["mensajes"]) for f in datos["filas"]}
    assert estados[2][0] == estados[3][0] == "creada"
    assert estados[4] == ("repetida", ["El DNI ya aparece en la fila 2."])
    assert estados[5] == ("ya_registrado", ["Ya está registrado en tu cooperativa."])
    assert estados[6] == ("otra_cooperativa", ["Este DNI ya está afiliado a otra cooperativa."])
    assert estados[7] == ("error", ["El DNI debe tener 8 dígitos."])
    assert estados[8][0] == "error"
    assert set(estados[8][1]) == {
        "En «PPA» escribe sí o no.",
        "Faltan los nombres.",
        "Falta la dirección postal.",
    }
    assert (datos["creadas"], datos["con_problemas"]) == (2, 5)

    ana = sesion.query(Productor).filter_by(dni="80000001").one()
    assert (ana.ppa_registrado, ana.ppa_codigo, ana.telefono) == (True, "PPA-1", "900000001")
    assert sesion.query(Afiliacion).filter_by(productor_id=ana.id).one().codigo_socio == "S-1"
    assert sesion.query(Productor).filter_by(dni="00800001").one().nombres == "Sin"

    acciones = [a.accion for a in sesion.query(Auditoria).order_by(Auditoria.id)]
    assert acciones == ["productor.crear", "productor.crear", "productor.carga_masiva"]
    resumen = sesion.query(Auditoria).filter_by(accion="productor.carga_masiva").one()
    assert resumen.detalle == {"archivo": "productores.csv", "filas": 7, "creados": 2}


def test_excel_con_otros_titulos_y_columnas_de_mas(api, sesion, operador):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["Padrón de socios 2026"])  # una fila de título antes de los encabezados
    hoja.append([])
    hoja.append(
        ["N°", "Documento", "Nombre", "Apellido", "Domicilio", "Correo", "Agro Digital", "Observación"]
    )
    hoja.append([1, 80000021, "Rosa", "Demo", "Sector Demo", "rosa@ejemplo.test", "AD-77", "nada"])
    salida = io.BytesIO()
    libro.save(salida)
    respuesta = _registrar(api.como(operador), ("socios.xlsx", salida.getvalue()))
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["filas"][0]["fila"] == 4
    datos = respuesta.json()
    assert datos["columnas_ignoradas"] == ["N°", "Observación"]
    rosa = sesion.query(Productor).filter_by(dni="80000021").one()
    assert (rosa.correo_contacto, rosa.codigo_agrodigital) == ("rosa@ejemplo.test", "AD-77")


def test_faltan_columnas_obligatorias(api, operador):
    respuesta = _analizar(api.como(operador), _csv("80000001;Ana", encabezados="DNI;Nombres"))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["mensaje"].startswith(
        "Faltan estas columnas: apellidos, dirección postal."
    )


def test_nada_que_registrar(api, operador):
    respuesta = _registrar(api.como(operador), _csv("1234;Dni;Corto;Caserío;;;;"))
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "nada_que_registrar"


@pytest.mark.parametrize(
    ("nombre", "codigo"), [("socios.xls", "formato_no_admitido"), ("socios.csv", "archivo_vacio")]
)
def test_archivos_que_no_sirven(api, operador, nombre, codigo):
    respuesta = _analizar(api.como(operador), (nombre, b""))
    assert respuesta.json()["error"]["codigo"] == codigo


def test_lector_y_superadmin_no_cargan(api, sesion, coop):
    lector = factorias.perfil(sesion, "lector", coop)
    assert _analizar(api.como(lector), _csv("80000001;Ana;Demo;Caserío;;;;")).status_code == 403
    superadmin = factorias.perfil(sesion, "superadmin")
    assert _registrar(api.como(superadmin), _csv("80000001;Ana;Demo;Caserío;;;;")).status_code == 403


def test_cada_cooperativa_carga_en_la_suya(api, sesion):
    a, b = factorias.cooperativa(sesion, "Coop A"), factorias.cooperativa(sesion, "Coop B")
    admin_a, admin_b = (
        factorias.perfil(sesion, "admin_cooperativa", a),
        factorias.perfil(sesion, "admin_cooperativa", b),
    )
    assert _registrar(api.como(admin_a), _csv("80000031;Ana;Demo;Caserío;;;;")).status_code == 201
    # B ve que el DNI está en otra cooperativa, sin saber cuál, y no puede afiliarlo.
    fila = _analizar(api.como(admin_b), _csv("80000031;Ana;Demo;Caserío;;;;")).json()["filas"][0]
    assert fila["estado"] == "otra_cooperativa"
    assert "Coop A" not in str(fila)
    productor = sesion.query(Productor).filter_by(dni="80000031").one()
    assert sesion.query(Afiliacion).filter_by(productor_id=productor.id).one().cooperativa_id == a.id
