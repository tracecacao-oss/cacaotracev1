"""CacaoTrace: trazabilidad de cacao para cooperativas (DOP -> DPP -> DEX).

Arranque local:   python app.py
Producción:       gunicorn app:app --workers 1 --threads 8
"""
import hashlib
import hmac
import json
import math
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, Response, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

import db as datos
import motor
import satelite
import semilla

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

COOKIE = "ct_sesion"
DIAS_SESION = 7
EN_PRODUCCION = bool(os.environ.get("RENDER"))
DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@cacaotrace.pe").lower()
DEMO_CLAVE = os.environ.get("DEMO_PASSWORD", "cacao-demo-2026")
CODIGO_REGISTRO = os.environ.get("REGISTRO_CODIGO", "").strip()
MAX_ARCHIVO_B64 = 2_800_000  # ~2 MB de archivo


class Fallo(Exception):
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.mensaje, self.codigo = mensaje, codigo


# ---------- Utilidades ----------

def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hoy():
    """Fecha de Perú (UTC-5)."""
    return (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")


def bd():
    if g.get("db") is None:
        g.db = datos.DB()
    return g.db


@app.teardown_request
def _cerrar(exc):
    d = g.pop("db", None)
    if d is not None:
        d.cerrar(ok=exc is None and not g.get("fallo"))


@app.errorhandler(Fallo)
def _fallo(e):
    g.fallo = True
    return jsonify(error=e.mensaje), e.codigo


@app.errorhandler(Exception)
def _error(e):
    if isinstance(e, HTTPException):
        return jsonify(error=e.description), e.code
    g.fallo = True
    app.logger.exception("Error no controlado")
    return jsonify(error="Ocurrió un error en el servidor. Intenta de nuevo."), 500


def cifrar(clave, sal=None):
    sal = sal or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), 200_000).hex()
    return "pbkdf2${}${}".format(sal, h)


def clave_valida(clave, guardada):
    try:
        _, sal, _ = guardada.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(cifrar(clave, sal), guardada)


def leer(campos, cuerpo=None):
    """Valida el JSON recibido. campos = {nombre: (tipo, obligatorio, etiqueta)}"""
    d = cuerpo if cuerpo is not None else (request.get_json(silent=True) or {})
    if not isinstance(d, dict):
        raise Fallo("La solicitud no tiene un formato válido")
    out = {}
    for nombre, (tipo, obligatorio, etiqueta) in campos.items():
        v = d.get(nombre)
        if isinstance(v, str):
            v = v.strip()
        if v is None or v == "":
            if obligatorio:
                raise Fallo("Falta completar: {}".format(etiqueta))
            out[nombre] = None
            continue
        try:
            if tipo is float:
                v = float(str(v).replace(",", "."))
                if not math.isfinite(v):
                    raise ValueError
            elif tipo is int:
                v = int(v)
            else:
                v = str(v)[:2000]
        except (TypeError, ValueError):
            raise Fallo("El valor de «{}» no es válido".format(etiqueta))
        out[nombre] = v
    return out


def fecha_valida(v, etiqueta):
    if v is None:
        return None
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise Fallo("La fecha de «{}» no es válida".format(etiqueta))
    return v


def propio(tabla, id_, que="El registro"):
    f = bd().uno("SELECT * FROM {} WHERE id = ? AND coop_id = ?".format(tabla), (id_, g.u["coop_id"]))
    if not f:
        raise Fallo("{} no existe".format(que), 404)
    return f


def siguiente(tabla, columna, prefijo, ancho):
    """Siguiente correlativo por cooperativa: PREFIJO-AAAA-NNN."""
    base = "{}-{}-".format(prefijo, hoy()[:4])
    filas = bd().todos("SELECT {} AS c FROM {} WHERE coop_id = ?".format(columna, tabla), (g.u["coop_id"],))
    usados = [int(f["c"][len(base):]) for f in filas
              if f["c"] and f["c"].startswith(base) and f["c"][len(base):].isdigit()]
    return "{}{:0{}d}".format(base, max(usados or [0]) + 1, ancho)


# ---------- Sesiones ----------

_intentos = {}


def _frenar(clave):
    t = time.time()
    lista = [x for x in _intentos.get(clave, []) if t - x < 600]
    _intentos[clave] = lista
    if len(lista) >= 8:
        raise Fallo("Demasiados intentos. Espera unos minutos y vuelve a probar.", 429)


def _abrir_sesion(usuario_id):
    token = secrets.token_urlsafe(32)
    expira = (datetime.now(timezone.utc) + timedelta(days=DIAS_SESION)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bd().ej("DELETE FROM sesiones WHERE expira < ?", (ahora(),))
    bd().ej("INSERT INTO sesiones (token, usuario_id, expira) VALUES (?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), usuario_id, expira))
    r = jsonify(ok=True)
    r.set_cookie(COOKIE, token, max_age=DIAS_SESION * 86400, httponly=True, samesite="Lax",
                 secure=EN_PRODUCCION, path="/")
    return r


def _usuario_actual():
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return bd().uno(
        "SELECT u.id, u.coop_id, u.nombre, u.email, u.rol FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token = ? AND s.expira > ?", (hashlib.sha256(token.encode()).hexdigest(), ahora()))


def sesion(f):
    @wraps(f)
    def envoltura(*a, **k):
        g.u = _usuario_actual()
        if not g.u:
            raise Fallo("Tu sesión terminó. Vuelve a ingresar.", 401)
        return f(*a, **k)
    return envoltura


def solo_admin():
    if g.u["rol"] != "admin":
        raise Fallo("Solo un administrador de la cooperativa puede hacer esto", 403)


@app.post("/api/auth/registro")
def registro():
    d = leer({"cooperativa": (str, 1, "Nombre de la cooperativa"), "ruc": (str, 0, "RUC"),
              "region": (str, 0, "Región"), "nombre": (str, 1, "Tu nombre"),
              "email": (str, 1, "Correo"), "clave": (str, 1, "Contraseña"), "codigo": (str, 0, "Código")})
    if CODIGO_REGISTRO and not hmac.compare_digest((d["codigo"] or "").encode(), CODIGO_REGISTRO.encode()):
        raise Fallo("El código de registro no es correcto", 403)
    email = d["email"].lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise Fallo("Escribe un correo válido")
    if len(d["clave"]) < 8:
        raise Fallo("La contraseña debe tener al menos 8 caracteres")
    if d["ruc"] and not (d["ruc"].isdigit() and len(d["ruc"]) == 11):
        raise Fallo("El RUC debe tener 11 dígitos")
    if bd().uno("SELECT id FROM usuarios WHERE email = ?", (email,)):
        raise Fallo("Ya existe una cuenta con ese correo", 409)
    coop = bd().insertar("cooperativas", dict(nombre=d["cooperativa"], ruc=d["ruc"], region=d["region"] or "San Martín",
                                              campania=hoy()[:4], creado=ahora()))
    uid = bd().insertar("usuarios", dict(coop_id=coop, nombre=d["nombre"], email=email, clave=cifrar(d["clave"]),
                                         rol="admin", creado=ahora()))
    return _abrir_sesion(uid)


@app.post("/api/auth/login")
def login():
    d = leer({"email": (str, 1, "Correo"), "clave": (str, 1, "Contraseña")})
    email = d["email"].lower()
    llave = "{}|{}".format(email, request.headers.get("X-Forwarded-For", request.remote_addr or ""))
    _frenar(llave)
    u = bd().uno("SELECT id, clave FROM usuarios WHERE email = ?", (email,))
    if not u or not clave_valida(d["clave"], u["clave"]):
        _intentos.setdefault(llave, []).append(time.time())
        raise Fallo("El correo o la contraseña no coinciden", 401)
    return _abrir_sesion(u["id"])


@app.post("/api/auth/salir")
def salir():
    token = request.cookies.get(COOKIE)
    if token:
        bd().ej("DELETE FROM sesiones WHERE token = ?", (hashlib.sha256(token.encode()).hexdigest(),))
    r = jsonify(ok=True)
    r.delete_cookie(COOKIE, path="/")
    return r


# ---------- Estado completo de la cooperativa ----------

def cargar_estado(coop_id, con_calculo=True):
    d = bd()
    S = {"cooperativa": d.uno("SELECT * FROM cooperativas WHERE id = ?", (coop_id,))}
    for tabla, orden in (("productores", "nombre"), ("parcelas", "codigo"), ("entregas", "fecha, id"),
                         ("lotes", "codigo"), ("etapas", "id"), ("asignaciones", "id")):
        S[tabla] = d.todos("SELECT * FROM {} WHERE coop_id = ? ORDER BY {}".format(tabla, orden), (coop_id,))
    S["ordenes"] = d.todos(
        "SELECT id, coop_id, codigo, comprador, comprador_id, pais, kg, fecha, contrato, dex_codigo, dex_fecha, "
        "dex_hash, dex_usuario FROM ordenes WHERE coop_id = ? ORDER BY codigo", (coop_id,))
    S["documentos"] = d.todos(
        "SELECT id, ambito, ref_id, tipo, numero, nivel, fecha, nota, archivo_nombre FROM documentos "
        "WHERE coop_id = ? ORDER BY id", (coop_id,))
    return motor.calcular(S, hoy()) if con_calculo else S


@app.get("/api/estado")
@sesion
def estado():
    S = cargar_estado(g.u["coop_id"])
    S["usuario"] = g.u
    S["usuarios"] = bd().todos("SELECT id, nombre, email, rol FROM usuarios WHERE coop_id = ? ORDER BY id",
                               (g.u["coop_id"],))
    S["hoy"] = hoy()
    S["catalogo"] = motor.CATALOGO
    S["etapas_tipo"] = motor.ETAPAS
    S["fuentes_geo"] = motor.FUENTES_GEO
    S["niveles"] = motor.NIVEL_TXT
    S["modo_satelite"] = satelite.MODO
    return jsonify(S)


# ---------- Cooperativa y usuarios ----------

@app.put("/api/cooperativa")
@sesion
def cooperativa_editar():
    solo_admin()
    d = leer({"nombre": (str, 1, "Nombre"), "ruc": (str, 0, "RUC"), "region": (str, 0, "Región"),
              "campania": (str, 0, "Campaña"), "factor_baba": (float, 1, "Rendimiento baba a seco"),
              "tolerancia": (float, 1, "Tolerancia")})
    if not 0.2 <= d["factor_baba"] <= 0.6:
        raise Fallo("El rendimiento de baba a grano seco debe estar entre 20% y 60%")
    if not 0 <= d["tolerancia"] <= 0.3:
        raise Fallo("La tolerancia debe estar entre 0% y 30%")
    bd().ej("UPDATE cooperativas SET nombre = ?, ruc = ?, region = ?, campania = ?, factor_baba = ?, tolerancia = ? "
            "WHERE id = ?", (d["nombre"], d["ruc"], d["region"], d["campania"], d["factor_baba"], d["tolerancia"],
                             g.u["coop_id"]))
    return jsonify(ok=True)


@app.post("/api/usuarios")
@sesion
def usuario_crear():
    solo_admin()
    d = leer({"nombre": (str, 1, "Nombre"), "email": (str, 1, "Correo"), "clave": (str, 1, "Contraseña"),
              "rol": (str, 1, "Rol")})
    email = d["email"].lower()
    if "@" not in email:
        raise Fallo("Escribe un correo válido")
    if len(d["clave"]) < 8:
        raise Fallo("La contraseña debe tener al menos 8 caracteres")
    if d["rol"] not in ("admin", "operador"):
        raise Fallo("El rol no es válido")
    if bd().uno("SELECT id FROM usuarios WHERE email = ?", (email,)):
        raise Fallo("Ya existe una cuenta con ese correo", 409)
    bd().insertar("usuarios", dict(coop_id=g.u["coop_id"], nombre=d["nombre"], email=email,
                                   clave=cifrar(d["clave"]), rol=d["rol"], creado=ahora()))
    return jsonify(ok=True)


@app.delete("/api/usuarios/<int:id_>")
@sesion
def usuario_borrar(id_):
    solo_admin()
    if id_ == g.u["id"]:
        raise Fallo("No puedes eliminar tu propia cuenta")
    propio("usuarios", id_, "El usuario")
    bd().ej("DELETE FROM sesiones WHERE usuario_id = ?", (id_,))
    bd().ej("DELETE FROM usuarios WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


@app.post("/api/ejemplo")
@sesion
def ejemplo():
    solo_admin()
    if bd().uno("SELECT id FROM productores WHERE coop_id = ?", (g.u["coop_id"],)):
        raise Fallo("Los datos de ejemplo solo se cargan en una cooperativa sin productores")
    semilla.cargar(bd(), g.u["coop_id"], g.u["nombre"], ahora())
    return jsonify(ok=True)


# ---------- Productores ----------

CAMPOS_PRODUCTOR = {"nombre": (str, 1, "Nombre completo"), "dni": (str, 1, "DNI"),
                    "comunidad": (str, 0, "Comunidad"), "distrito": (str, 0, "Distrito"),
                    "provincia": (str, 0, "Provincia"), "telefono": (str, 0, "Teléfono")}


def _productor():
    d = leer(CAMPOS_PRODUCTOR)
    if not (d["dni"].isdigit() and len(d["dni"]) == 8):
        raise Fallo("El DNI debe tener 8 dígitos")
    return d


@app.post("/api/productores")
@sesion
def productor_crear():
    d = _productor()
    if bd().uno("SELECT id FROM productores WHERE coop_id = ? AND dni = ?", (g.u["coop_id"], d["dni"])):
        raise Fallo("Ya hay un productor registrado con ese DNI", 409)
    return jsonify(id=bd().insertar("productores", dict(d, coop_id=g.u["coop_id"], creado=ahora())))


@app.put("/api/productores/<int:id_>")
@sesion
def productor_editar(id_):
    propio("productores", id_, "El productor")
    bd().actualizar("productores", id_, g.u["coop_id"], _productor())
    return jsonify(ok=True)


@app.delete("/api/productores/<int:id_>")
@sesion
def productor_borrar(id_):
    propio("productores", id_, "El productor")
    if bd().uno("SELECT id FROM parcelas WHERE productor_id = ? AND coop_id = ?", (id_, g.u["coop_id"])):
        raise Fallo("Este productor tiene parcelas. Elimínalas primero.", 409)
    bd().ej("DELETE FROM productores WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


# ---------- Parcelas (DOP) ----------

def _parcela():
    crudo = request.get_json(silent=True) or {}
    d = leer({"productor_id": (int, 1, "Productor"), "nombre": (str, 1, "Nombre de la parcela"),
              "area_ha": (float, 0, "Área"), "fuente_geo": (str, 1, "Fuente de la geolocalización"),
              "vigente_hasta": (str, 0, "Vigencia")}, crudo)
    propio("productores", d["productor_id"], "El productor")
    if d["fuente_geo"] not in motor.FUENTES_GEO:
        raise Fallo("La fuente de la geolocalización no es válida")
    fecha_valida(d["vigente_hasta"], "Vigencia")
    if not crudo.get("geometria"):
        raise Fallo("Falta completar: Geolocalización de la parcela")
    try:
        geom = motor.validar_geometria(crudo["geometria"])
    except ValueError as e:
        raise Fallo(str(e))
    if geom["type"] == "Polygon":
        d["area_ha"] = motor.area_ha(geom)
        if not d["area_ha"] or d["area_ha"] <= 0:
            raise Fallo("El polígono no encierra un área válida")
    else:
        if not d["area_ha"] or d["area_ha"] <= 0:
            raise Fallo("Con un solo punto debes indicar el área de la parcela")
        if d["area_ha"] > motor.LIMITE_PUNTO_HA:
            raise Fallo("Las parcelas de más de 4 ha necesitan polígono, no un punto")
    d["geometria"] = json.dumps(geom)
    return d


@app.post("/api/parcelas")
@sesion
def parcela_crear():
    d = _parcela()
    d.update(coop_id=g.u["coop_id"], codigo=siguiente("parcelas", "codigo", "DOP", 4), creado=ahora())
    return jsonify(id=bd().insertar("parcelas", d))


@app.put("/api/parcelas/<int:id_>")
@sesion
def parcela_editar(id_):
    antes = propio("parcelas", id_, "La parcela")
    d = _parcela()
    if json.loads(antes["geometria"] or "null") != json.loads(d["geometria"]):
        # Revalidación por inconsistencia: si cambia la geometría, la verificación anterior deja de valer.
        d.update(sat_estado="pendiente", sat_detalle=None, sat_fuente=None, sat_fecha=None,
                 rev_resultado=None, rev_nota=None, rev_usuario=None, rev_fecha=None)
    bd().actualizar("parcelas", id_, g.u["coop_id"], d)
    return jsonify(ok=True)


@app.delete("/api/parcelas/<int:id_>")
@sesion
def parcela_borrar(id_):
    propio("parcelas", id_, "La parcela")
    if bd().uno("SELECT id FROM entregas WHERE parcela_id = ? AND coop_id = ?", (id_, g.u["coop_id"])):
        raise Fallo("Esta parcela ya tiene entregas registradas y no se puede eliminar", 409)
    bd().ej("DELETE FROM documentos WHERE ambito = 'parcela' AND ref_id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    bd().ej("DELETE FROM parcelas WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


@app.post("/api/parcelas/<int:id_>/verificar")
@sesion
def parcela_verificar(id_):
    p = propio("parcelas", id_, "La parcela")
    if not p["geometria"]:
        raise Fallo("La parcela no tiene geolocalización")
    est, detalle, fuente = satelite.verificar(json.loads(p["geometria"]), p["area_ha"])
    bd().actualizar("parcelas", id_, g.u["coop_id"], dict(
        sat_estado=est, sat_detalle=detalle, sat_fuente=fuente, sat_fecha=hoy(),
        rev_resultado=None, rev_nota=None, rev_usuario=None, rev_fecha=None))
    return jsonify(estado=est, detalle=detalle)


@app.post("/api/parcelas/<int:id_>/revision")
@sesion
def parcela_revision(id_):
    p = propio("parcelas", id_, "La parcela")
    d = leer({"resultado": (str, 1, "Resultado"), "nota": (str, 1, "Sustento de la revisión")})
    if p["sat_estado"] != "ambar":
        raise Fallo("La revisión humana solo aplica a resultados no concluyentes (ámbar)")
    if d["resultado"] not in ("conforme", "no_conforme"):
        raise Fallo("El resultado no es válido")
    bd().actualizar("parcelas", id_, g.u["coop_id"], dict(
        rev_resultado=d["resultado"], rev_nota=d["nota"], rev_usuario=g.u["nombre"], rev_fecha=hoy()))
    return jsonify(ok=True)


@app.post("/api/parcelas/<int:id_>/revalidar")
@sesion
def parcela_revalidar(id_):
    """Revalidación por campaña: extiende la vigencia y exige una verificación satelital nueva."""
    propio("parcelas", id_, "La parcela")
    d = leer({"vigente_hasta": (str, 1, "Nueva vigencia")})
    fecha_valida(d["vigente_hasta"], "Nueva vigencia")
    if d["vigente_hasta"] < hoy():
        raise Fallo("La nueva vigencia debe ser una fecha futura")
    bd().actualizar("parcelas", id_, g.u["coop_id"], dict(
        vigente_hasta=d["vigente_hasta"], sat_estado="pendiente", sat_detalle=None, sat_fuente=None,
        sat_fecha=None, rev_resultado=None, rev_nota=None, rev_usuario=None, rev_fecha=None))
    return jsonify(ok=True)


# ---------- Documentos ----------

@app.post("/api/documentos")
@sesion
def documento_crear():
    crudo = request.get_json(silent=True) or {}
    d = leer({"ambito": (str, 1, "Ámbito"), "ref_id": (int, 1, "Referencia"), "tipo": (str, 1, "Documento"),
              "numero": (str, 0, "Número"), "nivel": (str, 1, "Nivel de verificación"),
              "fecha": (str, 0, "Fecha"), "nota": (str, 0, "Nota")}, crudo)
    if d["ambito"] not in motor.CATALOGO or d["tipo"] not in [c["tipo"] for c in motor.CATALOGO[d["ambito"]]]:
        raise Fallo("El tipo de documento no es válido")
    if d["nivel"] not in motor.NIVELES:
        raise Fallo("El nivel de verificación no es válido")
    if d["nivel"] == "verificado" and d["tipo"] not in motor.VERIFICABLES_EN_FUENTE:
        raise Fallo("Solo la DAM puede marcarse como verificada en fuente (consulta pública de SUNAT)")
    if d["nivel"] != "declarado" and not d["numero"]:
        raise Fallo("Indica el número o la referencia del documento")
    fecha_valida(d["fecha"], "Fecha")
    if d["ambito"] == "cooperativa":
        d["ref_id"] = g.u["coop_id"]
    elif d["ambito"] == "orden":
        _orden_editable(d["ref_id"])
    else:
        propio("parcelas", d["ref_id"], "La parcela")
    archivo = crudo.get("archivo") or {}
    if archivo.get("b64"):
        if len(archivo["b64"]) > MAX_ARCHIVO_B64:
            raise Fallo("El archivo supera los 2 MB")
        d["archivo_nombre"] = str(archivo.get("nombre") or "archivo")[:120]
        d["archivo_b64"] = archivo["b64"]
    return jsonify(id=bd().insertar("documentos", dict(d, coop_id=g.u["coop_id"], creado=ahora())))


@app.delete("/api/documentos/<int:id_>")
@sesion
def documento_borrar(id_):
    doc = propio("documentos", id_, "El documento")
    if doc["ambito"] == "orden" and propio("ordenes", doc["ref_id"])["dex_codigo"]:
        raise Fallo("La orden ya tiene un DEX emitido. Anúlalo para cambiar sus documentos.", 409)
    bd().ej("DELETE FROM documentos WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


@app.get("/api/documentos/<int:id_>/archivo")
@sesion
def documento_archivo(id_):
    import base64
    doc = propio("documentos", id_, "El documento")
    if not doc["archivo_b64"]:
        raise Fallo("Este documento no tiene archivo adjunto", 404)
    nombre = (doc["archivo_nombre"] or "archivo").replace('"', "")
    return Response(base64.b64decode(doc["archivo_b64"]), mimetype="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="{}"'.format(nombre.encode("ascii", "ignore").decode() or "archivo")})


# ---------- Lotes, entregas y etapas (DPP) ----------

def _lote_abierto(id_):
    l = propio("lotes", id_, "El lote")
    if l["estado"] != "abierto":
        raise Fallo("El lote {} ya está cerrado. Reábrelo para modificarlo.".format(l["codigo"]), 409)
    return l


@app.post("/api/lotes")
@sesion
def lote_crear():
    d = leer({"nombre": (str, 0, "Nombre"), "fecha_inicio": (str, 1, "Fecha de inicio")})
    fecha_valida(d["fecha_inicio"], "Fecha de inicio")
    d.update(coop_id=g.u["coop_id"], codigo=siguiente("lotes", "codigo", "LOT", 3), creado=ahora())
    return jsonify(id=bd().insertar("lotes", d))


@app.delete("/api/lotes/<int:id_>")
@sesion
def lote_borrar(id_):
    propio("lotes", id_, "El lote")
    if bd().uno("SELECT id FROM asignaciones WHERE lote_id = ? AND coop_id = ?", (id_, g.u["coop_id"])):
        raise Fallo("Este lote está asignado a una orden y no se puede eliminar", 409)
    for tabla in ("entregas", "etapas"):
        bd().ej("DELETE FROM {} WHERE lote_id = ? AND coop_id = ?".format(tabla), (id_, g.u["coop_id"]))
    bd().ej("DELETE FROM lotes WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


@app.post("/api/entregas")
@sesion
def entrega_crear():
    d = leer({"lote_id": (int, 1, "Lote"), "parcela_id": (int, 1, "Parcela"), "fecha": (str, 1, "Fecha"),
              "tipo": (str, 1, "Tipo de grano"), "kg": (float, 1, "Kilos"), "gre": (str, 0, "Guía de remisión")})
    _lote_abierto(d["lote_id"])
    propio("parcelas", d["parcela_id"], "La parcela")
    fecha_valida(d["fecha"], "Fecha")
    if d["tipo"] not in ("baba", "seco"):
        raise Fallo("El tipo de grano no es válido")
    if d["kg"] <= 0:
        raise Fallo("Los kilos deben ser mayores que cero")
    return jsonify(id=bd().insertar("entregas", dict(d, gre=d["gre"] or "", coop_id=g.u["coop_id"], creado=ahora())))


@app.put("/api/entregas/<int:id_>/gre")
@sesion
def entrega_gre(id_):
    """Vincular la guía de remisión se permite aun con el lote cerrado: no cambia kilos ni origen."""
    e = propio("entregas", id_, "La entrega")
    d = leer({"gre": (str, 1, "Guía de remisión")})
    for a in bd().todos("SELECT o.dex_codigo FROM asignaciones a JOIN ordenes o ON o.id = a.orden_id "
                        "WHERE a.lote_id = ? AND a.coop_id = ?", (e["lote_id"], g.u["coop_id"])):
        if a["dex_codigo"]:
            raise Fallo("Este lote ya forma parte de un DEX emitido", 409)
    bd().actualizar("entregas", id_, g.u["coop_id"], dict(gre=d["gre"]))
    return jsonify(ok=True)


@app.delete("/api/entregas/<int:id_>")
@sesion
def entrega_borrar(id_):
    e = propio("entregas", id_, "La entrega")
    _lote_abierto(e["lote_id"])
    bd().ej("DELETE FROM entregas WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


@app.post("/api/lotes/<int:id_>/etapas")
@sesion
def etapa_guardar(id_):
    _lote_abierto(id_)
    d = leer({"tipo": (str, 1, "Etapa"), "fecha_inicio": (str, 1, "Inicio"), "fecha_fin": (str, 0, "Fin"),
              "kg_entrada": (float, 1, "Kilos que entran"), "kg_salida": (float, 0, "Kilos que salen"),
              "responsable": (str, 0, "Responsable"), "nota": (str, 0, "Nota")})
    if d["tipo"] not in dict(motor.ETAPAS):
        raise Fallo("La etapa no es válida")
    fecha_valida(d["fecha_inicio"], "Inicio")
    fecha_valida(d["fecha_fin"], "Fin")
    if d["fecha_fin"] and d["fecha_fin"] < d["fecha_inicio"]:
        raise Fallo("La etapa no puede terminar antes de empezar")
    if d["kg_entrada"] <= 0 or (d["kg_salida"] is not None and d["kg_salida"] <= 0):
        raise Fallo("Los kilos deben ser mayores que cero")
    if d["kg_salida"] is not None and d["kg_salida"] > d["kg_entrada"]:
        raise Fallo("De una etapa no pueden salir más kilos de los que entraron")
    bd().ej("DELETE FROM etapas WHERE lote_id = ? AND tipo = ? AND coop_id = ?", (id_, d["tipo"], g.u["coop_id"]))
    bd().insertar("etapas", dict(d, lote_id=id_, coop_id=g.u["coop_id"]))
    return jsonify(ok=True)


@app.delete("/api/etapas/<int:id_>")
@sesion
def etapa_borrar(id_):
    e = propio("etapas", id_, "La etapa")
    _lote_abierto(e["lote_id"])
    bd().ej("DELETE FROM etapas WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


@app.post("/api/lotes/<int:id_>/cerrar")
@sesion
def lote_cerrar(id_):
    l = _lote_abierto(id_)
    d = leer({"kg_seco": (float, 1, "Kilos de grano seco"), "humedad": (float, 0, "Humedad")})
    if d["kg_seco"] <= 0:
        raise Fallo("Los kilos de grano seco deben ser mayores que cero")
    if d["humedad"] is not None and not 0 < d["humedad"] < 30:
        raise Fallo("La humedad debe ser un porcentaje entre 0 y 30")
    if not bd().uno("SELECT id FROM entregas WHERE lote_id = ? AND coop_id = ?", (id_, g.u["coop_id"])):
        raise Fallo("El lote no tiene entregas: no hay origen que documentar")
    hechas = {e["tipo"] for e in bd().todos("SELECT tipo, kg_salida FROM etapas WHERE lote_id = ? AND coop_id = ?",
                                            (id_, g.u["coop_id"])) if e["kg_salida"]}
    faltan = [dict(motor.ETAPAS)[t] for t in motor.ETAPAS_OBLIGATORIAS if t not in hechas]
    if faltan:
        raise Fallo("Para cerrar el lote falta registrar completa la etapa de: {}".format(", ".join(faltan).lower()))
    dpp = l["dpp_codigo"] or siguiente("lotes", "dpp_codigo", "DPP", 3)
    bd().actualizar("lotes", id_, g.u["coop_id"], dict(estado="cerrado", kg_seco=d["kg_seco"], humedad=d["humedad"],
                                                       dpp_codigo=dpp, dpp_fecha=hoy()))
    return jsonify(dpp=dpp)


@app.post("/api/lotes/<int:id_>/reabrir")
@sesion
def lote_reabrir(id_):
    propio("lotes", id_, "El lote")
    if bd().uno("SELECT id FROM asignaciones WHERE lote_id = ? AND coop_id = ?", (id_, g.u["coop_id"])):
        raise Fallo("El lote está asignado a una orden. Quita la asignación antes de reabrirlo.", 409)
    bd().actualizar("lotes", id_, g.u["coop_id"], dict(estado="abierto", kg_seco=None, humedad=None, dpp_fecha=None))
    return jsonify(ok=True)


# ---------- Órdenes, genealogía y DEX ----------

def _orden_editable(id_):
    o = propio("ordenes", id_, "La orden")
    if o["dex_codigo"]:
        raise Fallo("La orden {} ya tiene el {} emitido. Anúlalo para modificarla.".format(o["codigo"], o["dex_codigo"]), 409)
    return o


CAMPOS_ORDEN = {"comprador": (str, 1, "Importador"), "comprador_id": (str, 0, "Identificador del importador"),
                "pais": (str, 1, "País de destino"), "kg": (float, 1, "Kilos"), "fecha": (str, 1, "Fecha"),
                "contrato": (str, 0, "Contrato")}


def _orden():
    d = leer(CAMPOS_ORDEN)
    fecha_valida(d["fecha"], "Fecha")
    if d["kg"] <= 0:
        raise Fallo("Los kilos deben ser mayores que cero")
    return d


@app.post("/api/ordenes")
@sesion
def orden_crear():
    d = _orden()
    d.update(coop_id=g.u["coop_id"], codigo=siguiente("ordenes", "codigo", "OC", 3), creado=ahora())
    return jsonify(id=bd().insertar("ordenes", d))


@app.put("/api/ordenes/<int:id_>")
@sesion
def orden_editar(id_):
    _orden_editable(id_)
    d = _orden()
    asignado = sum(a["kg"] for a in bd().todos("SELECT kg FROM asignaciones WHERE orden_id = ? AND coop_id = ?",
                                               (id_, g.u["coop_id"])))
    if d["kg"] + 0.05 < asignado:
        raise Fallo("La orden ya tiene {:,.0f} kg asignados. Quita asignaciones antes de reducirla.".format(asignado))
    bd().actualizar("ordenes", id_, g.u["coop_id"], d)
    return jsonify(ok=True)


@app.delete("/api/ordenes/<int:id_>")
@sesion
def orden_borrar(id_):
    _orden_editable(id_)
    bd().ej("DELETE FROM asignaciones WHERE orden_id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    bd().ej("DELETE FROM documentos WHERE ambito = 'orden' AND ref_id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    bd().ej("DELETE FROM ordenes WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


def _asignar(orden, lote, kg):
    previa = bd().uno("SELECT id, kg FROM asignaciones WHERE orden_id = ? AND lote_id = ? AND coop_id = ?",
                      (orden["id"], lote["id"], g.u["coop_id"]))
    if previa:
        bd().actualizar("asignaciones", previa["id"], g.u["coop_id"], dict(kg=previa["kg"] + kg))
    else:
        bd().insertar("asignaciones", dict(coop_id=g.u["coop_id"], orden_id=orden["id"], lote_id=lote["id"], kg=kg))


@app.post("/api/ordenes/<int:id_>/asignar")
@sesion
def orden_asignar(id_):
    _orden_editable(id_)
    d = leer({"lote_id": (int, 1, "Lote"), "kg": (float, 1, "Kilos")})
    S = cargar_estado(g.u["coop_id"])
    o = next(x for x in S["ordenes"] if x["id"] == id_)
    l = next((x for x in S["lotes"] if x["id"] == d["lote_id"]), None)
    if not l:
        raise Fallo("El lote no existe", 404)
    if l["estado"] != "cerrado":
        raise Fallo("Solo se asignan lotes cerrados, con DPP emitido")
    if d["kg"] <= 0:
        raise Fallo("Los kilos deben ser mayores que cero")
    if d["kg"] > l["disponible"] + 0.05:
        raise Fallo("El lote {} solo tiene {:,.0f} kg disponibles".format(l["codigo"], l["disponible"]))
    falta = o["kg"] - o["genealogia"]["asignado"]
    if d["kg"] > falta + 0.05:
        raise Fallo("A la orden solo le faltan {:,.0f} kg por cubrir".format(max(falta, 0)))
    _asignar(o, l, d["kg"])
    return jsonify(ok=True)


@app.post("/api/ordenes/<int:id_>/fifo")
@sesion
def orden_fifo(id_):
    """Cubre lo que falta de la orden con los lotes cerrados más antiguos primero."""
    _orden_editable(id_)
    S = cargar_estado(g.u["coop_id"])
    o = next(x for x in S["ordenes"] if x["id"] == id_)
    falta = o["kg"] - o["genealogia"]["asignado"]
    if falta <= 0.05:
        raise Fallo("La orden ya está cubierta")
    usados = []
    for l in sorted((x for x in S["lotes"] if x["estado"] == "cerrado" and x["disponible"] > 0.05),
                    key=lambda x: (x.get("dpp_fecha") or "", x["codigo"])):
        if falta <= 0.05:
            break
        kg = round(min(falta, l["disponible"]), 1)
        _asignar(o, l, kg)
        usados.append({"lote": l["codigo"], "kg": kg})
        falta -= kg
    if not usados:
        raise Fallo("No hay lotes cerrados con kilos disponibles")
    return jsonify(usados=usados, falta=round(max(falta, 0), 1))


@app.delete("/api/asignaciones/<int:id_>")
@sesion
def asignacion_borrar(id_):
    a = propio("asignaciones", id_, "La asignación")
    _orden_editable(a["orden_id"])
    bd().ej("DELETE FROM asignaciones WHERE id = ? AND coop_id = ?", (id_, g.u["coop_id"]))
    return jsonify(ok=True)


@app.post("/api/ordenes/<int:id_>/dex")
@sesion
def dex_emitir(id_):
    _orden_editable(id_)
    S = cargar_estado(g.u["coop_id"])
    o = next(x for x in S["ordenes"] if x["id"] == id_)
    cerradas = [c for c in o["compuertas"] if c["estado"] != "abierta"]
    if cerradas:
        raise Fallo("No se puede generar el DEX: {} compuerta(s) cerrada(s) ({})".format(
            len(cerradas), ", ".join(c["nombre"].lower() for c in cerradas)), 409)
    codigo = siguiente("ordenes", "dex_codigo", "DEX", 3)
    paquete = motor.paquete_dex(codigo, ahora(), g.u["nombre"], o, S)
    h = motor.huella(paquete)
    bd().actualizar("ordenes", id_, g.u["coop_id"], dict(
        dex_codigo=codigo, dex_fecha=paquete["emitido"], dex_hash=h, dex_usuario=g.u["nombre"],
        dex_paquete=json.dumps(paquete, ensure_ascii=False)))
    return jsonify(dex=codigo, huella=h)


@app.post("/api/ordenes/<int:id_>/dex/anular")
@sesion
def dex_anular(id_):
    solo_admin()
    o = propio("ordenes", id_, "La orden")
    if not o["dex_codigo"]:
        raise Fallo("La orden no tiene un DEX emitido")
    bd().actualizar("ordenes", id_, g.u["coop_id"], dict(dex_codigo=None, dex_fecha=None, dex_hash=None,
                                                         dex_usuario=None, dex_paquete=None))
    return jsonify(ok=True)


def _paquete(id_):
    o = propio("ordenes", id_, "La orden")
    if not o["dex_paquete"]:
        raise Fallo("La orden no tiene un DEX emitido", 404)
    return o, json.loads(o["dex_paquete"])


def _descarga(contenido, nombre):
    return Response(json.dumps(contenido, ensure_ascii=False, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": 'attachment; filename="{}"'.format(nombre)})


@app.get("/api/ordenes/<int:id_>/dex")
@sesion
def dex_ver(id_):
    o, p = _paquete(id_)
    return jsonify(paquete=p, huella=o["dex_hash"])


@app.get("/api/ordenes/<int:id_>/dex.json")
@sesion
def dex_json(id_):
    o, p = _paquete(id_)
    return _descarga({"huella_sha256": o["dex_hash"], "paquete": p}, o["dex_codigo"] + ".json")


@app.get("/api/ordenes/<int:id_>/parcelas.geojson")
@sesion
def dex_geojson(id_):
    o, p = _paquete(id_)
    return _descarga(motor.geojson_parcelas(p), o["dex_codigo"] + "-parcelas.geojson")


def _dex_publico(codigo, token):
    """Busca un DEX emitido por su código y el inicio de su huella (el enlace que comparte la cooperativa)."""
    filas = bd().todos("SELECT dex_codigo, dex_hash, dex_paquete FROM ordenes WHERE dex_codigo = ?", (codigo,))
    o = next((f for f in filas if f["dex_hash"] and
              hmac.compare_digest(f["dex_hash"][:20].encode(), token.encode())), None)
    if not o:
        raise Fallo("Este DEX no existe o fue anulado", 404)
    return o


@app.get("/api/publico/dex/<codigo>/<token>")
def dex_publico(codigo, token):
    """Verificación para el importador: sin sesión, con el enlace que le comparte la cooperativa."""
    o = _dex_publico(codigo, token)
    p = json.loads(o["dex_paquete"])
    integro = motor.huella(p) == o["dex_hash"]
    for x in p["parcelas"]:  # al público no se le entregan documentos de identidad
        x.pop("documento_productor", None)
    return jsonify(paquete=p, huella=o["dex_hash"], integro=integro)


@app.get("/api/publico/dex/<codigo>/<token>/parcelas.geojson")
def dex_publico_geojson(codigo, token):
    o = _dex_publico(codigo, token)
    return _descarga(motor.geojson_parcelas(json.loads(o["dex_paquete"])), o["dex_codigo"] + "-parcelas.geojson")


@app.get("/api/publico/config")
def config_publica():
    return jsonify(registro_con_codigo=bool(CODIGO_REGISTRO))


# ---------- Páginas ----------

@app.get("/salud")
def salud():
    bd().uno("SELECT COUNT(*) AS n FROM cooperativas")
    return jsonify(ok=True, base="postgres" if datos.PG else "sqlite", satelite=satelite.MODO)


@app.get("/")
@app.get("/verificar/<codigo>/<token>")
def pagina(codigo=None, token=None):
    r = send_from_directory(app.static_folder, "index.html")
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.after_request
def _cabeceras(r):
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "same-origin")
    if request.path.startswith("/api/"):
        r.headers["Cache-Control"] = "no-store"
    return r


# ---------- Arranque ----------

def iniciar():
    datos.crear_esquema()
    d = datos.DB()
    try:
        if not d.uno("SELECT id FROM usuarios WHERE email = ?", (DEMO_EMAIL,)):
            t = ahora()
            coop = d.insertar("cooperativas", dict(nombre="Cooperativa Agraria de Ejemplo", ruc="20000000001",
                                                   region="San Martín", campania="2026", creado=t))
            d.insertar("usuarios", dict(coop_id=coop, nombre="Operador de ejemplo", email=DEMO_EMAIL,
                                        clave=cifrar(DEMO_CLAVE), rol="admin", creado=t))
            semilla.cargar(d, coop, "Operador de ejemplo", t)
        d.cerrar(ok=True)
    except Exception:
        d.cerrar(ok=False)
        raise


iniciar()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
