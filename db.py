"""Capa de datos de CacaoTrace.

En local usa un archivo SQLite; en producción usa PostgreSQL si existe la
variable DATABASE_URL. El SQL de la app es el mismo para ambos motores.
"""
import os
import sqlite3

URL = os.environ.get("DATABASE_URL", "").strip()
PG = URL.startswith("postgres")
RUTA_SQLITE = os.environ.get(
    "SQLITE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cacaotrace.db")
)

if PG:
    import psycopg2
    import psycopg2.extras

PK = "SERIAL PRIMARY KEY" if PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
NUM = "DOUBLE PRECISION"

ESQUEMA = [
    f"""CREATE TABLE IF NOT EXISTS cooperativas (
        id {PK}, nombre TEXT NOT NULL, ruc TEXT, region TEXT, campania TEXT,
        factor_baba {NUM} NOT NULL DEFAULT 0.42, tolerancia {NUM} NOT NULL DEFAULT 0.10,
        creado TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS usuarios (
        id {PK}, coop_id INTEGER NOT NULL, nombre TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
        clave TEXT NOT NULL, rol TEXT NOT NULL DEFAULT 'operador', creado TEXT)""",
    """CREATE TABLE IF NOT EXISTS sesiones (
        token TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL, expira TEXT NOT NULL)""",
    f"""CREATE TABLE IF NOT EXISTS productores (
        id {PK}, coop_id INTEGER NOT NULL, nombre TEXT NOT NULL, dni TEXT, comunidad TEXT,
        distrito TEXT, provincia TEXT, telefono TEXT, creado TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS parcelas (
        id {PK}, coop_id INTEGER NOT NULL, productor_id INTEGER NOT NULL, codigo TEXT NOT NULL,
        nombre TEXT NOT NULL, area_ha {NUM}, geometria TEXT, fuente_geo TEXT, vigente_hasta TEXT,
        sat_estado TEXT NOT NULL DEFAULT 'pendiente', sat_detalle TEXT, sat_fuente TEXT, sat_fecha TEXT,
        rev_resultado TEXT, rev_nota TEXT, rev_usuario TEXT, rev_fecha TEXT, creado TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS lotes (
        id {PK}, coop_id INTEGER NOT NULL, codigo TEXT NOT NULL, nombre TEXT, fecha_inicio TEXT,
        estado TEXT NOT NULL DEFAULT 'abierto', kg_seco {NUM}, humedad {NUM},
        dpp_codigo TEXT, dpp_fecha TEXT, creado TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS entregas (
        id {PK}, coop_id INTEGER NOT NULL, parcela_id INTEGER NOT NULL, lote_id INTEGER NOT NULL,
        fecha TEXT, tipo TEXT NOT NULL DEFAULT 'baba', kg {NUM} NOT NULL, gre TEXT, creado TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS etapas (
        id {PK}, coop_id INTEGER NOT NULL, lote_id INTEGER NOT NULL, tipo TEXT NOT NULL,
        fecha_inicio TEXT, fecha_fin TEXT, kg_entrada {NUM}, kg_salida {NUM},
        responsable TEXT, nota TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS ordenes (
        id {PK}, coop_id INTEGER NOT NULL, codigo TEXT NOT NULL, comprador TEXT NOT NULL,
        comprador_id TEXT, pais TEXT, kg {NUM} NOT NULL, fecha TEXT, contrato TEXT,
        dex_codigo TEXT, dex_fecha TEXT, dex_hash TEXT, dex_usuario TEXT, dex_paquete TEXT, creado TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS asignaciones (
        id {PK}, coop_id INTEGER NOT NULL, orden_id INTEGER NOT NULL, lote_id INTEGER NOT NULL,
        kg {NUM} NOT NULL)""",
    f"""CREATE TABLE IF NOT EXISTS documentos (
        id {PK}, coop_id INTEGER NOT NULL, ambito TEXT NOT NULL, ref_id INTEGER NOT NULL,
        tipo TEXT NOT NULL, numero TEXT, nivel TEXT NOT NULL DEFAULT 'declarado', fecha TEXT,
        nota TEXT, archivo_nombre TEXT, archivo_b64 TEXT, creado TEXT)""",
]


class DB:
    """Una conexión por petición. Se confirma o revierte al cerrar."""

    def __init__(self):
        if PG:
            self.c = psycopg2.connect(URL.replace("postgres://", "postgresql://", 1))
        else:
            self.c = sqlite3.connect(RUTA_SQLITE, timeout=20)
            self.c.row_factory = sqlite3.Row
            self.c.execute("PRAGMA foreign_keys=ON")

    def ej(self, sql, p=()):
        if PG:
            cur = self.c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql.replace("?", "%s"), tuple(p))
        else:
            cur = self.c.cursor()
            cur.execute(sql, tuple(p))
        return cur

    def todos(self, sql, p=()):
        return [dict(f) for f in self.ej(sql, p).fetchall()]

    def uno(self, sql, p=()):
        f = self.ej(sql, p).fetchone()
        return dict(f) if f else None

    def insertar(self, tabla, datos):
        cols = list(datos)
        sql = "INSERT INTO {} ({}) VALUES ({}) RETURNING id".format(
            tabla, ", ".join(cols), ", ".join("?" for _ in cols)
        )
        return dict(self.ej(sql, [datos[c] for c in cols]).fetchone())["id"]

    def actualizar(self, tabla, id_, coop_id, datos):
        cols = list(datos)
        sql = "UPDATE {} SET {} WHERE id = ? AND coop_id = ?".format(
            tabla, ", ".join(c + " = ?" for c in cols)
        )
        self.ej(sql, [datos[c] for c in cols] + [id_, coop_id])

    def confirmar(self):
        self.c.commit()

    def revertir(self):
        self.c.rollback()

    def cerrar(self, ok=True):
        try:
            self.c.commit() if ok else self.c.rollback()
        finally:
            self.c.close()


def crear_esquema():
    d = DB()
    for sql in ESQUEMA:
        d.ej(sql)
    d.cerrar()
