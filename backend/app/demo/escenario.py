"""Escenario de datos de la cooperativa Prueba (Parte 10, "Escenario de datos de Prueba").

Deja la cadena completa armada, de la cooperativa a un DEX emitido, y un registro detenido en cada punto del
flujo, listo para avanzar durante la demo. Lo usa la prueba de extremo a extremo
(tests/e2e/test_flujo_completo.py); la siembra en producción lo llamará desde su propio comando.

Cómo está escrito (especificación, "Cómo está escrito el escenario"):
1. Cada paso llama a la misma función de app/services que usa su endpoint, con el mismo esquema de entrada.
   No inserta filas ni fuerza estados: pasa por las mismas compuertas, requisitos y auditoría que una
   persona. Lo único que hace fuera de un endpoint es procesar la cola de análisis, como el hilo de
   app/trabajador.py.
2. Cada paso actúa con su rol: el superadministrador crea la cooperativa y su administrador; el
   administrador configura, carga el expediente de la cooperativa, habilita, excluye, anula el documento
   final y emite el DEX; el operador registra productores, parcelas, tandas, corridas, órdenes y lotes.
3. Si un paso no puede cumplirse, se detiene con EscenarioDetenido, que dice qué paso y qué requisito faltó.

Recibe sus dependencias (sesión, Supabase Auth, Storage y fuentes de cobertura) y no importa nada de tests/.

Adaptaciones a la especificación:
- Visitas de campo: desde la adenda 2 de la Parte 4 ya no se registran, y la alerta analisis_requiere_revision
  solo la atiende una revisión de imágenes, que hace una persona. Por eso PA-00001 no muestra "perímetro
  recorrido" y PA-00004 queda habilitada sin visita ni fotos. Si una parcela que debe habilitarse recibe esa
  alerta, el escenario se detiene y lo explica, en vez de registrar una visita.
- Geometrías: la especificación las toma de backend/tests/datos/, pero app/ no lee tests/. Se arman aquí, en
  el mismo lugar de San Martín que usan las pruebas, con las áreas de la tabla de parcelas.
- Adenda 4: cada parcela carga solo su documento de tenencia y el operador declara su perfil legal. Las
  variables que responde el cruce con las capas oficiales se declaran "no" solo si el cruce todavía no
  respondió; el cruce corre después en el trabajador y, si dice algo más exigente, manda lo que diga.
  PA-00008 queda con el perfil incompleto (antes: con el expediente incompleto) y el documento que se anula
  al final es el título de PA-00007 (antes: su sustento laboral, que ya no se carga).
- Adenda 5: cada productor necesita su declaración anual vigente. El operador registra las respuestas de un
  productor que trabaja con su familia, sin menores ni agroquímicos y con ventas de hasta 75 UIT, y carga la
  hoja firmada con la fecha del día.
- Las cuentas nuevas actúan con su contraseña temporal: el cambio obligatorio lo exige la API a las personas
  (app/contexto.py), y cada usuario de demostración la cambia al entrar por primera vez.
- No registra la clasificación del país: es un dato regulatorio de toda la plataforma y lo fija el equipo.
  Mientras falte, el DEX dice "clasificación del país no registrada".
"""

import math
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from fpdf import FPDF
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth_admin import ClienteAuthAdmin
from app.catalogos import documentos_embarque, documentos_legales, etapas_proceso, perfil_legal
from app.contexto import Contexto
from app.fechas import ahora, dia_lima, hoy_lima
from app.models import Perfil
from app.pdf.base import FUENTES
from app.schemas.cooperativa import CooperativaCambios
from app.schemas.dex import EmisionDex
from app.schemas.exportacion import Asignacion, Confirmacion, ImportadorNuevo, OrdenNueva, Seleccion
from app.schemas.habilitacion import CotejoNuevo, ExcluirEntrada, HabilitarEntrada
from app.schemas.legalidad import DeclaracionNueva
from app.schemas.parcelas import Anulacion, ParcelaDatos
from app.schemas.plataforma import CooperativaNueva
from app.schemas.proceso import (
    CalidadNueva,
    Consolidacion,
    CorridaNueva,
    EtapaRegistro,
    PlantillaCambio,
    PlantillaFila,
    TandaACorrida,
)
from app.schemas.productores import ProductorNuevo
from app.schemas.recepcion import (
    ConfiguracionCambio,
    LugarNuevo,
    Motivo,
    TandaDetalle,
    TandaNueva,
    Validacion,
)
from app.schemas.superposiciones import Aceptacion
from app.schemas.usuarios import AdministradorNuevo, UsuarioNuevo
from app.services import (
    analisis,
    configuracion,
    cooperativa,
    corridas,
    declaracion_productor,
    dex,
    documentos,
    embarque,
    expediente,
    habilitacion,
    legalidad,
    lotes,
    lugares,
    ordenes,
    parcelas,
    plataforma,
    proceso,
    productores,
    recomprobacion,
    superposiciones,
    tandas,
    usuarios,
)
from app.services.documentos import Archivo
from app.services.fuentes import Fuente, registro
from app.storage import ClienteStorage

# ---------- Datos fijos (especificación, "La cooperativa Prueba" y "Datos ficticios") ----------

COOPERATIVA = {
    "razon_social": "Cooperativa Prueba (demostración)",
    "ruc": "20000000001",
    "codigo": "PRB",
    "tipo_organizacion": "cooperativa_agraria",
}
UBICACION = {"departamento": "San Martín", "provincia": "Picota", "distrito": "Picota"}
DOMINIO = "cooperativa-prueba.test"
PRODUCTORES = ("Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete")
VERSION_CONSENTIMIENTO = "1"
TOPE_KG_SECO_HA_ANIO = Decimal("1500.00")
CALIDADES = ("Grado 1", "Grado 2")
CALIDAD_DE_LAS_ORDENES = "Grado 1"
LUGARES = (
    ("cancha", "Cancha de acopio Demo", "cancha_acopio"),
    ("planta", "Planta de proceso Demo", "planta"),
    ("almacen", "Almacén Demo", "almacen"),
)
TEXTO_DOCUMENTO = "DOCUMENTO DE DEMOSTRACIÓN — SIN VALOR"
PIE_DOCUMENTO = (
    "Archivo generado por CacaoTrace para la cooperativa de demostración. No es un documento real ni tiene "
    "valor legal o comercial."
)
ENTIDAD_EMISORA = "Entidad emisora de demostración"
RESPONSABLE = "Demo Operador"
HUMEDAD_FINAL = Decimal("7.0")
ESPERA_MAXIMA = timedelta(minutes=15)
PERIODO_COLA = 5  # segundos entre vueltas mientras la cola de análisis espera un reintento

NOTA_COTEJO = "Cotejo de demostración: datos ficticios, sin consulta real al registro de SUNARP."
# Adenda 4: lo que el operador declara del perfil legal de cada parcela de demostración.
TENENCIA_TIPO = {"titulo_sunarp": "propietario", "constancia_posesion": "poseedor"}
PERFIL_DECLARADO = {"usa_riego": "no", "anio_instalacion_cultivo": "2015"}
NOTA_SUPERPOSICION = (
    "Lindero compartido entre dos productores de demostración: la cooperativa acepta la superposición."
)
DESCRIPCION_EXCLUSION = (
    "Exclusión de demostración: la cooperativa decide no recibir cacao de esta parcela ficticia y cita su "
    "análisis de cobertura como evidencia."
)
EXPLICACION_RENDIMIENTO = (
    "Rendimiento de demostración sobre la banda: el grano de estas tandas llegó con menos agua que lo "
    "habitual."
)
MOTIVO_DESVIACION = "El importador pidió el grano segregado de un solo productor (dato de demostración)."
MOTIVO_OBSERVACION = "Falta el archivo de la liquidación de compra: cárgalo y valida la tanda de nuevo."
MOTIVO_ANULACION = "Anulado al final de la siembra de demostración, para mostrar un lote bloqueado."
REVISION_PENDIENTE = (
    "Whisp o GFW piden revisión (alerta analisis_requiere_revision). Desde la adenda 2 de la Parte 4 solo la "
    "atiende una revisión de las imágenes de la parcela, que hace una persona, y el escenario no la simula: "
    "revisa las imágenes y habilita la parcela a mano."
)
NOMBRE_FUENTE = {"whisp": "Whisp", "gfw": "GFW"}

# ---------- Parcelas (especificación, "Parcelas") ----------

# Geometrías ficticias en San Martín, a partir de este origen; solo PA-00006 y PA-00007 se superponen.
LAT, LON = -6.95, -76.55


@dataclass(frozen=True)
class ParcelaDemo:
    codigo: str
    productor: str
    este_m: float
    norte_m: float
    # Sin ancho ni alto, la parcela es un punto con su área declarada.
    ancho_m: float | None
    alto_m: float | None
    cultivada_ha: str
    declarada_ha: str | None = None
    tenencia: str = "titulo_sunarp"
    # Documentos legales que se cargan; None: solo el de tenencia.
    casillas: tuple[str, ...] | None = None
    # Adenda 4: sin el riego ni el año de instalación, el perfil queda incompleto.
    perfil_completo: bool = True


PARCELAS = (
    ParcelaDemo("PA-00001", "Uno", 0, 0, 150, 140, "2.0"),  # 2.1 ha
    ParcelaDemo("PA-00002", "Uno", 300, 0, 140, 100, "1.3"),  # 1.4 ha
    ParcelaDemo("PA-00003", "Dos", 600, 0, 100, 50, "0.2", tenencia="constancia_posesion"),
    ParcelaDemo("PA-00004", "Tres", 0, 300, 100, 100, "0.9"),
    ParcelaDemo("PA-00005", "Cuatro", 350, 350, None, None, "1.5", declarada_ha="1.8"),
    ParcelaDemo("PA-00006", "Cinco", 600, 300, 120, 100, "1.1"),
    ParcelaDemo("PA-00007", "Seis", 700, 300, 100, 100, "0.9"),  # 0.2 ha en común con PA-00006
    ParcelaDemo("PA-00008", "Siete", 0, 600, 100, 100, "0.9", perfil_completo=False),
    ParcelaDemo("PA-00009", "Siete", 300, 600, 100, 100, "0.9", casillas=()),
)
POR_CODIGO = {p.codigo: p for p in PARCELAS}
HABILITADAS = ("PA-00001", "PA-00002", "PA-00003", "PA-00004", "PA-00005", "PA-00006", "PA-00007")
EXCLUIDA = "PA-00009"
SUPERPUESTAS = {"PA-00006", "PA-00007"}
COTEJADA = ("PA-00001", "titulo_sunarp")
# Al final se anula este documento: la parcela pasa a observada y bloquea el lote 2.
ANULADO = ("PA-00007", "titulo_sunarp")


# Adenda 5: la declaración más corta (cuatro preguntas).
RESPUESTAS_FAMILIA = {
    "quien_trabaja": "solo_familia",
    "menores_trabajan": "no",
    "usa_agroquimicos": "no",
    "ventas_superan_75_uit": "no",
}


def _metros_por_grado(lat: float) -> tuple[float, float]:
    f = math.radians(lat)
    m_lat = 111132.954 - 559.822 * math.cos(2 * f) + 1.175 * math.cos(4 * f)
    m_lon = (math.pi / 180) * 6378137.0 * math.cos(f) / math.sqrt(1 - 0.00669437999014 * math.sin(f) ** 2)
    return m_lat, m_lon


def geometria(parcela: ParcelaDemo) -> dict[str, Any]:
    """Rectángulo de ancho × alto metros (o punto), desplazado este/norte desde el origen, en GeoJSON."""
    m_lat, m_lon = _metros_por_grado(LAT)
    x0, y0 = LON + parcela.este_m / m_lon, LAT + parcela.norte_m / m_lat
    if parcela.ancho_m is None or parcela.alto_m is None:
        return {"type": "Point", "coordinates": [round(x0, 8), round(y0, 8)]}
    x1, y1 = x0 + parcela.ancho_m / m_lon, y0 + parcela.alto_m / m_lat
    anillo = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    return {"type": "Polygon", "coordinates": [[[round(x, 8), round(y, 8)] for x, y in anillo]]}


# ---------- Tandas, corridas y órdenes (especificación, "Corridas y stock" y "Órdenes y lotes") ----------


@dataclass(frozen=True)
class TandaDemo:
    parcela: str
    kilos: str
    producto: str  # baba o seco
    hace: timedelta  # recepción, contada hacia atrás desde el inicio del escenario


@dataclass(frozen=True)
class CorridaDemo:
    numero: int
    ruta: str
    manejo: str
    tandas: tuple[TandaDemo, ...]
    peso_final: str
    sacos: int
    descartados: str
    consolidar: bool = True


def _hace(dias: int, horas: int = 0) -> timedelta:
    return timedelta(days=dias) - timedelta(hours=horas)


# Las recepciones y las etapas quedan en el pasado y en orden: la corrida 1 es la más antigua, así que su
# tanda final entra primero al stock (FIFO), luego la 2 y luego la 3.
CORRIDAS = (
    CorridaDemo(
        1,
        "completa",
        "mezclado",
        (
            TandaDemo("PA-00001", "500.00", "baba", _hace(40)),
            TandaDemo("PA-00003", "300.00", "baba", _hace(40, 2)),
            TandaDemo("PA-00004", "200.00", "baba", _hace(40, 4)),
        ),
        peso_final="400.00",  # rendimiento 0.400
        sacos=6,
        descartados="6.00",
    ),
    CorridaDemo(
        2,
        "completa",
        "mezclado",
        (
            TandaDemo("PA-00002", "400.00", "baba", _hace(35)),
            TandaDemo("PA-00005", "300.00", "baba", _hace(35, 2)),
            TandaDemo("PA-00006", "200.00", "baba", _hace(35, 4)),
        ),
        peso_final="450.00",  # rendimiento 0.500, sobre la banda
        sacos=7,
        descartados="4.00",
    ),
    CorridaDemo(
        3,
        "seco",
        "segregado",
        (TandaDemo("PA-00007", "310.00", "seco", _hace(20)),),
        peso_final="300.00",
        sacos=5,
        descartados="10.00",
    ),
    CorridaDemo(
        4,
        "completa",
        "mezclado",
        (
            TandaDemo("PA-00001", "300.00", "baba", _hace(16)),
            TandaDemo("PA-00006", "200.00", "baba", _hace(16, 2)),
        ),
        peso_final="200.00",
        sacos=3,
        descartados="3.00",
        consolidar=False,  # detenida: todas sus etapas registradas, sin consolidar
    ),
)
# Registros detenidos: una tanda observada con motivo y una que supera el tope acumulado, sin validar.
TANDA_OBSERVADA = TandaDemo("PA-00004", "250.00", "baba", _hace(2))
TANDA_SIN_VALIDAR = TandaDemo("PA-00003", "600.00", "baba", _hace(1))
# (cantidad, días hasta la fecha de entrega). La orden 4 queda abierta y sin lote.
ORDENES = (("600.00", 60), ("300.00", 75), ("150.00", 90), ("100.00", 105))

# Plantilla de las 23 etapas: (número, lugar, método, distancia en metros, duración en horas). Las etapas de
# cada corrida se registran con estos valores, una tras otra, cada una con su duración.
PLANTILLA = (
    (1, "cancha", "Pesaje en balanza de plataforma", None, "0.5"),
    (2, "cancha", "Revisión visual de una muestra de cada saco", None, "1"),
    (3, "cancha", "Código de corrida asignado por CacaoTrace", None, "0"),
    (4, "cancha", "Revisión de la compuerta de cada tanda en CacaoTrace", None, "0"),
    (5, "cancha", "Separación según el tipo de manejo", None, "1"),
    (6, "planta", "Traslado en carretilla", "150", "0.5"),
    (7, "planta", "Espera en patio techado", None, "2"),
    (8, "planta", "Llenado manual del cajón", None, "1"),
    (9, "planta", "Cajones de madera con volteo cada 48 horas", None, "144"),
    (10, "planta", "Corte de 100 granos", None, "1"),
    (11, "planta", "Traslado en carretilla", "40", "0.5"),
    (12, "planta", "Tendal solar con volteo cada 2 horas", None, "120"),
    (13, "planta", "Medición con higrómetro", None, "1"),
    (14, "planta", "Cobertizo con techo de calamina", None, "6"),
    (15, "planta", "Traslado en carretilla", "30", "0.5"),
    (16, "planta", "Zarandeo manual", None, "4"),
    (17, "planta", "Clasificación por tamaño y aspecto del grano", None, "4"),
    (18, "planta", "Selección manual en mesa", None, "4"),
    (19, "planta", "Pesaje en balanza de plataforma", None, "1"),
    (20, "planta", "Traslado en carretilla", "25", "0.5"),
    (21, "planta", "Sacos de yute de 69 kg", None, "2"),
    (22, "almacen", "Traslado en camión de la cooperativa", "200", "0.5"),
    (23, "almacen", "Tarimas de madera en almacén ventilado", None, "24"),
)


# ---------- Resultado y errores ----------


@dataclass
class Escenario:
    """Lo que dejó el escenario. Las claves temporales son para que la siembra las muestre una sola vez."""

    cooperativa_id: uuid.UUID
    usuarios: dict[str, uuid.UUID] = field(default_factory=dict)  # admin, operador y lector
    claves: dict[str, str] = field(default_factory=dict)  # correo (o DNI del productor) y su clave temporal
    productores: dict[str, uuid.UUID] = field(default_factory=dict)  # "Demo Uno"
    parcelas: dict[str, uuid.UUID] = field(default_factory=dict)  # "PA-00001"
    # "corrida 1 PA-00001" y las detenidas: "observada" y "sin validar".
    tandas: dict[str, uuid.UUID] = field(default_factory=dict)
    corridas: dict[int, uuid.UUID] = field(default_factory=dict)
    tandas_finales: dict[int, uuid.UUID] = field(default_factory=dict)  # por número de corrida
    ordenes: dict[int, uuid.UUID] = field(default_factory=dict)
    lotes: dict[int, uuid.UUID] = field(default_factory=dict)  # por número de orden
    importador_id: uuid.UUID | None = None
    dex_id: uuid.UUID | None = None
    documento_anulado_id: uuid.UUID | None = None


class EscenarioDetenido(Exception):
    """Un paso no pudo cumplirse. Nada se forzó: el mensaje dice qué paso y qué requisito faltó."""

    def __init__(self, paso: str, motivo: str):
        super().__init__(f"El escenario se detuvo en «{paso}»: {motivo}")
        self.paso = paso
        self.motivo = motivo


def _motivo(exc: HTTPException) -> str:
    detalle = exc.detail
    if not isinstance(detalle, dict):
        return str(detalle)
    texto = f"{detalle.get('mensaje', '')} [{detalle.get('codigo', exc.status_code)}]".strip()
    if detalle.get("faltan"):
        texto += f" Requisitos que faltan: {', '.join(detalle['faltan'])}."
    return texto


@contextmanager
def _paso(nombre: str) -> Iterator[None]:
    """Convierte el rechazo de un servicio (o de su esquema de entrada) en EscenarioDetenido."""
    try:
        yield
    except HTTPException as exc:
        raise EscenarioDetenido(nombre, _motivo(exc)) from exc
    except ValidationError as exc:
        campos = ", ".join(".".join(str(x) for x in e["loc"]) or "datos" for e in exc.errors())
        raise EscenarioDetenido(nombre, f"los datos no pasan su esquema de entrada ({campos}).") from exc


def _contexto(sesion: Session, perfil: Perfil) -> Contexto:
    """El mismo contexto que arma la API (app/contexto.py) para una persona con ese perfil."""
    return Contexto(
        sesion=sesion,
        perfil=perfil,
        usuario_id=perfil.id,
        rol=perfil.rol,
        cooperativa_id=perfil.cooperativa_id,
        productor_id=perfil.productor_id,
        ip=None,
    )


def pdf_de_demostracion(titulo: str, referencia: str) -> bytes:
    """Una página que dice a la vista que no tiene valor. La referencia la hace única: el sistema rechaza el
    mismo archivo dos veces para un mismo registro."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_creator("CacaoTrace")
    pdf.set_title(TEXTO_DOCUMENTO)
    # La tipografía del diseño sin fijar su peso: así cada archivo se arma en milisegundos.
    pdf.add_font("Jakarta", "", str(FUENTES / "PlusJakartaSans-Variable.ttf"))
    pdf.add_page()
    pdf.set_font("Jakarta", "", 22)
    pdf.multi_cell(0, 11, TEXTO_DOCUMENTO, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Jakarta", "", 12)
    for linea in (COOPERATIVA["razon_social"], titulo, f"Corresponde a: {referencia}", PIE_DOCUMENTO):
        pdf.multi_cell(0, 7, linea, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


# ---------- El escenario ----------


def construir(
    sesion: Session,
    superadmin: Perfil,
    *,
    auth: ClienteAuthAdmin,
    storage: ClienteStorage,
    fuentes: dict[str, Fuente],
    ritmo: analisis.Ritmo | None = None,
    espera_maxima: timedelta = ESPERA_MAXIMA,
) -> Escenario:
    """Crea la cooperativa Prueba con todo su escenario y devuelve lo creado.

    superadmin: el perfil del superadministrador que crea la cooperativa. fuentes: las de cobertura, que
    quedan en uso como al arrancar la API. ritmo: el de la cola de análisis (las pruebas pasan uno sin
    esperas). espera_maxima: cuánto se espera a que terminen los análisis antes de detenerse."""
    if superadmin.rol != "superadmin":
        raise EscenarioDetenido(
            "Crear la cooperativa Prueba", "solo un superadministrador crea una cooperativa."
        )
    if fuentes is not registro.actuales():
        registro.fijar(fuentes)
    siembra = _Siembra(sesion, superadmin, auth, storage, fuentes, ritmo or analisis.Ritmo(), espera_maxima)
    return siembra.todo()


class _Siembra:
    def __init__(
        self,
        sesion: Session,
        superadmin: Perfil,
        auth: ClienteAuthAdmin,
        storage: ClienteStorage,
        fuentes: dict[str, Fuente],
        ritmo: analisis.Ritmo,
        espera_maxima: timedelta,
    ):
        self.sesion = sesion
        self.superadmin = _contexto(sesion, superadmin)
        self.auth = auth
        self.storage = storage
        self.fuentes = fuentes
        self.ritmo = ritmo
        self.espera_maxima = espera_maxima
        self.inicio = ahora()
        self.hoy = hoy_lima()
        self.archivos = 0
        self.liquidaciones = 0
        self.lugares: dict[str, uuid.UUID] = {}
        self.calidades: dict[str, uuid.UUID] = {}
        self.plantilla: dict[int, tuple[uuid.UUID, str, Decimal | None, Decimal]] = {}
        self.documentos_parcela: dict[str, dict[str, uuid.UUID]] = {}

    def todo(self) -> Escenario:
        self._cooperativa()
        self._personal()
        self._configuracion()
        self._expediente_de_la_cooperativa()
        self._productores()
        self._parcelas()
        self._legalidad_y_habilitacion()
        for corrida in CORRIDAS:
            self._corrida(corrida)
        self._tandas_detenidas()
        self._exportacion()
        self._bloquear_lote_2()
        return self.resultado

    def _archivo(self, titulo: str, referencia: str) -> Archivo:
        self.archivos += 1
        return Archivo(
            nombre=f"documento-demo-{self.archivos:03d}.pdf",
            contenido=pdf_de_demostracion(titulo, referencia),
        )

    # ---------- Base: cooperativa, personal, configuración y expediente de la cooperativa ----------

    def _cooperativa(self) -> None:
        with _paso("Crear la cooperativa Prueba y su administrador"):
            datos = CooperativaNueva(
                **COOPERATIVA,
                **UBICACION,
                es_demo=True,
                administrador=AdministradorNuevo(
                    nombres="Demo", apellidos="Administradora", correo=f"admin@{DOMINIO}"
                ),
            )
            creada, administrador, clave = plataforma.crear(self.superadmin, self.auth, datos)
        self.resultado = Escenario(cooperativa_id=creada.id)
        self.resultado.usuarios["admin"] = administrador.id
        self.resultado.claves[administrador.correo] = clave
        self.admin = _contexto(self.sesion, administrador)

    def _personal(self) -> None:
        for rol, apellidos in (("operador", "Operador"), ("lector", "Lector")):
            with _paso(f"Crear la cuenta del {rol}"):
                datos = UsuarioNuevo(nombres="Demo", apellidos=apellidos, correo=f"{rol}@{DOMINIO}", rol=rol)
                perfil, clave = usuarios.crear(self.admin, self.auth, datos)
            self.resultado.usuarios[rol] = perfil.id
            self.resultado.claves[perfil.correo] = clave
            if rol == "operador":
                self.operador = _contexto(self.sesion, perfil)

    def _configuracion(self) -> None:
        with _paso("Fijar el tope de kilos por hectárea"):
            actual = configuracion.obtener(self.admin)
            valores = {c: getattr(actual, c) for c in configuracion.CAMPOS}
            valores["tope_kg_seco_ha_anio"] = TOPE_KG_SECO_HA_ANIO
            configuracion.cambiar(self.admin, ConfiguracionCambio(**valores))
        for clave, nombre, tipo in LUGARES:
            with _paso(f"Crear el lugar «{nombre}»"):
                lugar = lugares.crear(self.admin, LugarNuevo(nombre=nombre, tipo=tipo, **UBICACION))
            self.lugares[clave] = lugar.id
        for nombre in CALIDADES:
            with _paso(f"Crear la calidad «{nombre}»"):
                self.calidades[nombre] = proceso.crear_calidad(self.admin, CalidadNueva(nombre=nombre)).id
        with _paso("Completar la plantilla de las 23 etapas"):
            filas = []
            for numero, lugar, metodo, distancia, horas in PLANTILLA:
                distancia_m = Decimal(distancia) if distancia else None
                filas.append(
                    PlantillaFila(
                        numero=numero,
                        lugar_id=self.lugares[lugar],
                        metodo=metodo,
                        distancia_m=distancia_m,
                        duracion_horas=Decimal(horas),
                    )
                )
                self.plantilla[numero] = (self.lugares[lugar], metodo, distancia_m, Decimal(horas))
            proceso.cambiar_plantilla(self.admin, PlantillaCambio(filas=filas))

    def _expediente_de_la_cooperativa(self) -> None:
        with _paso("Completar los datos de la cooperativa"):
            cooperativa.editar(
                self.admin,
                CooperativaCambios(
                    direccion_postal="Jr. Demostración 100, Picota, San Martín (dirección ficticia)",
                    correo=f"contacto@{DOMINIO}",
                    representante_nombre="Demo Representante",
                    representante_dni="00000008",
                ),
            )
        for tipo in documentos_legales.TIPOS_COOPERATIVA:
            with _paso(f"Cargar «{tipo.nombre}» de la cooperativa"):
                datos_legales = expediente.validar_datos_legales(
                    tipo.codigo,
                    f"DEMO-{tipo.codigo.upper()}",
                    ENTIDAD_EMISORA,
                    self.hoy - timedelta(days=200),
                    None,
                )
                documentos.cargar(
                    self.admin,
                    self.storage,
                    entidad="cooperativa",
                    entidad_id=self.resultado.cooperativa_id,
                    tipo=tipo.codigo,
                    archivo=self._archivo(tipo.nombre, COOPERATIVA["razon_social"]),
                    datos_legales=datos_legales,
                )

    # ---------- Productores y parcelas ----------

    def _productores(self) -> None:
        for numero, nombre in enumerate(PRODUCTORES, start=1):
            dni = f"{numero:08d}"
            with _paso(f"Registrar al productor Demo {nombre}"):
                productor = productores.crear(
                    self.operador,
                    ProductorNuevo(
                        dni=dni,
                        nombres="Demo",
                        apellidos=nombre,
                        direccion_postal="Caserío de demostración, Picota, San Martín (dirección ficticia)",
                        consentimiento_cooperativa=True,
                        version_consentimiento=VERSION_CONSENTIMIENTO,
                    ),
                )
            with _paso(f"Cargar la copia del DNI de Demo {nombre}"):
                # Como el endpoint: solo un productor de la cooperativa recibe documentos.
                productores.obtener(self.operador, productor.id)
                documentos.cargar(
                    self.operador,
                    self.storage,
                    entidad="productor",
                    entidad_id=productor.id,
                    tipo="dni",
                    archivo=self._archivo("Copia del DNI", f"Demo {nombre}, DNI {dni}"),
                )
            with _paso(f"Registrar la declaración anual de Demo {nombre}"):
                declaracion = declaracion_productor.registrar(self.operador, productor.id, RESPUESTAS_FAMILIA)
                declaracion_productor.cargar_hoja_firmada(
                    self.operador,
                    self.storage,
                    productor.id,
                    declaracion.id,
                    self._archivo("Hoja firmada de la declaración anual", f"Demo {nombre}, DNI {dni}"),
                    hoy_lima(),
                )
            self.resultado.productores[f"Demo {nombre}"] = productor.id
        with _paso("Crear el acceso del productor Demo Uno"):
            clave = productores.crear_acceso(self.operador, self.auth, self.resultado.productores["Demo Uno"])
        self.resultado.claves["00000001"] = clave

    def _productor_de(self, codigo: str) -> uuid.UUID:
        return self.resultado.productores[f"Demo {POR_CODIGO[codigo].productor}"]

    def _parcelas(self) -> None:
        for p in PARCELAS:
            with _paso(f"Registrar la parcela {p.codigo}"):
                datos = ParcelaDatos(
                    nombre=f"Parcela Demo {int(p.codigo[3:])}",
                    **UBICACION,
                    area_cultivada_ha=Decimal(p.cultivada_ha),
                    area_declarada_ha=Decimal(p.declarada_ha) if p.declarada_ha else None,
                )
                detalle = parcelas.crear(
                    self.operador,
                    self.storage,
                    self._productor_de(p.codigo),
                    datos,
                    geometria_dibujada=geometria(p),
                )
            if detalle.codigo != p.codigo:
                raise EscenarioDetenido(
                    f"Registrar la parcela {p.codigo}",
                    f"quedó con el código {detalle.codigo}: la cooperativa ya tenía parcelas.",
                )
            self.resultado.parcelas[p.codigo] = detalle.id
        faltan = [
            nombre
            for codigo, nombre in NOMBRE_FUENTE.items()
            if codigo not in self.fuentes or not self.fuentes[codigo].configurada
        ]
        if faltan:
            raise EscenarioDetenido(
                "Análisis de cobertura",
                f"falta la clave de {' y '.join(faltan)}. Las parcelas quedaron registradas sin análisis: "
                "configura la clave y pide el análisis de cada parcela.",
            )
        self._esperar_analisis(list(self.resultado.parcelas.values()))

    def _esperar_analisis(self, parcela_ids: list[uuid.UUID]) -> None:
        """Procesa la cola como el hilo de app/trabajador.py hasta que terminen los análisis de estas
        parcelas. Un reintento se espera hasta espera_maxima; un análisis en error detiene el escenario."""
        limite = ahora() + self.espera_maxima
        while True:
            while analisis.procesar_siguiente(self.sesion, self.fuentes, self.storage, self.ritmo):
                pass
            filas = [a for lista in analisis.de_parcelas(self.sesion, parcela_ids).values() for a in lista]
            pendientes = [a for a in filas if a.estado in ("pendiente", "en_proceso")]
            if not pendientes:
                break
            if ahora() >= limite:
                raise EscenarioDetenido(
                    "Análisis de cobertura",
                    f"{len(pendientes)} consultas siguen en la cola después de esperar "
                    f"{int(self.espera_maxima.total_seconds() // 60)} minutos. Las parcelas quedaron "
                    "registradas; espera a que terminen sus análisis y habilítalas a mano.",
                )
            self.ritmo.dormir(PERIODO_COLA)
        codigos = {v: k for k, v in self.resultado.parcelas.items()}
        errores = [a for a in filas if a.estado == "error"]
        if errores:
            raise EscenarioDetenido(
                "Análisis de cobertura",
                "; ".join(
                    f"{NOMBRE_FUENTE.get(a.fuente, a.fuente)} falló en {codigos[a.parcela_id]}: "
                    f"{a.error_detalle}"
                    for a in errores
                )
                + ".",
            )

    def _legalidad_y_habilitacion(self) -> None:
        for p in PARCELAS:
            casillas = p.casillas if p.casillas is not None else (p.tenencia,)
            for numero, tipo in enumerate(casillas, start=1):
                nombre = documentos_legales.POR_CODIGO[tipo].nombre
                with _paso(f"Cargar «{nombre}» de {p.codigo}"):
                    # Lo mismo que el endpoint POST /parcelas/{id}/documentos.
                    parcela = parcelas.parcela_visible(self.operador, self.resultado.parcelas[p.codigo])
                    expediente.no_excluida(parcela)
                    datos_legales = expediente.validar_datos_legales(
                        tipo,
                        f"DEMO-{p.codigo}-{numero}",
                        ENTIDAD_EMISORA,
                        self.hoy - timedelta(days=400),
                        None,
                    )
                    documento = documentos.cargar(
                        self.operador,
                        self.storage,
                        entidad="parcela",
                        entidad_id=parcela.id,
                        tipo=tipo,
                        archivo=self._archivo(nombre, f"Parcela {p.codigo}"),
                        datos_legales=datos_legales,
                    )
                self.documentos_parcela.setdefault(p.codigo, {})[tipo] = documento.id
            if p.codigo != EXCLUIDA:
                self._perfil(p)
        codigo, tipo = COTEJADA
        with _paso(f"Cotejar el título de {codigo}"):
            documento = documentos.documento_visible(self.operador, self.documentos_parcela[codigo][tipo])
            expediente.cotejar(self.operador, documento, CotejoNuevo(nota=NOTA_COTEJO).nota)
        self._aceptar_superposicion()
        for codigo in HABILITADAS:
            self._habilitar(codigo)
        self._excluir(EXCLUIDA)

    def _perfil(self, p: ParcelaDemo) -> None:
        """Lo mismo que el endpoint POST /parcelas/{id}/perfil, una variable a la vez."""
        with _paso(f"Declarar el perfil legal de {p.codigo}"):
            parcela = parcelas.parcela_visible(self.operador, self.resultado.parcelas[p.codigo])
            actual = legalidad.legalidad(self.sesion, parcela)
            respuestas = {"tenencia_tipo": TENENCIA_TIPO[p.tenencia]}
            if p.perfil_completo:
                respuestas |= PERFIL_DECLARADO
                respuestas |= {c: "no" for c in perfil_legal.CRUZABLES if actual.valor(c) is None}
            for variable, valor in respuestas.items():
                datos = DeclaracionNueva(variable=variable, valor=valor)
                legalidad.declarar(self.operador, parcela, datos.variable, datos.valor)

    def _aceptar_superposicion(self) -> None:
        paso = f"Aceptar la superposición entre {' y '.join(sorted(SUPERPUESTAS))}"
        with _paso(paso):
            abiertas = superposiciones.listar(self.sesion, self.resultado.cooperativa_id, "abierta")
            elegida = next(
                (s for s in abiertas if {x["codigo"] for x in s["parcelas"]} == SUPERPUESTAS), None
            )
            if elegida is None:
                raise EscenarioDetenido(paso, "no se abrió la superposición esperada entre las dos parcelas.")
            nota = Aceptacion(nota=NOTA_SUPERPOSICION).nota
            superposiciones.aceptar(self.admin, elegida["id"], nota, como_superadmin=False)

    def _habilitar(self, codigo: str) -> None:
        paso = f"Habilitar {codigo}"
        with _paso(paso):
            parcela = parcelas.parcela_visible(self.admin, self.resultado.parcelas[codigo])
            estado = habilitacion.obtener(self.admin, parcela)
            if "analisis_requiere_revision" in estado.alertas:
                raise EscenarioDetenido(paso, REVISION_PENDIENTE)
            nota = None
            if estado.nota_obligatoria:
                nota = (
                    f"Habilitación de demostración con alertas a la vista ({', '.join(estado.alertas)}): la "
                    "cooperativa revisó cada una con los datos ficticios del escenario."
                )
            habilitacion.habilitar(self.admin, parcela, HabilitarEntrada(nota=nota).nota)

    def _excluir(self, codigo: str) -> None:
        paso = f"Excluir {codigo}"
        with _paso(paso):
            parcela = parcelas.parcela_visible(self.admin, self.resultado.parcelas[codigo])
            de_la_parcela = analisis.de_parcelas(self.sesion, [parcela.id])[parcela.id]
            evidencia = next((a for a in de_la_parcela if a.estado == "completado"), None)
            if evidencia is None:
                raise EscenarioDetenido(paso, "la parcela no tiene un análisis completado que citar.")
            datos = ExcluirEntrada(
                descripcion=DESCRIPCION_EXCLUSION, evidencia_analisis_id=evidencia.id, confirmacion="EXCLUIR"
            )
            habilitacion.excluir(self.admin, parcela, datos)

    # ---------- Tandas y corridas ----------

    def _registrar_tanda(self, t: TandaDemo, *, con_archivo: bool = True) -> TandaDetalle:
        recibida = self.inicio - t.hace
        dia = dia_lima(recibida)
        seco = t.producto == "seco"
        kilos = Decimal(t.kilos)
        self.liquidaciones += 1
        nombre = f"tanda de {t.parcela} ({t.kilos} kg en {t.producto})"
        with _paso(f"Registrar la {nombre}"):
            datos = TandaNueva(
                productor_id=self._productor_de(t.parcela),
                parcela_id=self.resultado.parcelas[t.parcela],
                lugar_id=self.lugares["cancha"],
                recibida_en=recibida,
                estado_producto=t.producto,
                peso_kg=kilos,
                numero_sacos=max(1, round(kilos / 60)),
                humedad_pct=Decimal("7.5") if seco else None,
                variedad="ccn_51",
                cosecha_desde=dia - timedelta(days=40 if seco else 6),
                cosecha_hasta=dia - timedelta(days=30 if seco else 2),
                doc_entrega_tipo="liquidacion_compra",
                doc_entrega_numero=f"L001-{self.liquidaciones}",
                doc_entrega_fecha_emision=dia,
                doc_entrega_peso_kg=kilos,
            )
            detalle = tandas.registrar(self.operador, datos)
        if con_archivo:
            with _paso(f"Cargar la liquidación de compra de la {nombre}"):
                referencia = f"{detalle.codigo}, {datos.doc_entrega_numero}"
                archivo = self._archivo("Liquidación de compra", referencia)
                detalle = tandas.cargar_documento(self.operador, self.storage, detalle.id, archivo)
        return detalle

    def _validar(self, detalle: TandaDetalle) -> None:
        with _paso(f"Validar la tanda {detalle.codigo}"):
            nota = None
            if detalle.nota_obligatoria:
                nota = (
                    f"Validación de demostración con alertas a la vista ({', '.join(detalle.alertas)}): la "
                    "cooperativa las revisó antes de validar."
                )
            tandas.validar(self.operador, self.storage, detalle.id, Validacion(nota=nota).nota)

    def _corrida(self, c: CorridaDemo) -> None:
        tanda_ids = []
        for t in c.tandas:
            detalle = self._registrar_tanda(t)
            self._validar(detalle)
            tanda_ids.append(detalle.id)
            self.resultado.tandas[f"corrida {c.numero} {t.parcela}"] = detalle.id
        paso = f"Corrida {c.numero}"
        with _paso(f"{paso}: crear, agregar sus tandas e iniciar"):
            corrida = corridas.crear(self.operador, CorridaNueva(ruta=c.ruta, tipo_manejo=c.manejo))
            for tanda_id in tanda_ids:
                corridas.agregar_tanda(self.operador, corrida.id, TandaACorrida(tanda_id=tanda_id))
            corridas.iniciar(self.operador, corrida.id)
        self.resultado.corridas[c.numero] = corrida.id
        # Las etapas empiezan dos horas después de la última recepción y siguen una tras otra.
        momento = max(self.inicio - t.hace for t in c.tandas) + timedelta(hours=2)
        for etapa in etapas_proceso.ETAPAS:
            if etapa.automatica or not etapas_proceso.aplica(etapa, c.ruta):
                continue
            with _paso(f"{paso}: etapa {etapa.numero}, {etapa.nombre}"):
                entrada, momento = self._etapa(c, etapa, momento)
                corridas.registrar_etapa(self.operador, corrida.id, etapa.numero, entrada)
        if not c.consolidar:
            return
        with _paso(f"{paso}: consolidar"):
            alerta = corridas.obtener(self.operador, corrida.id).rendimiento.alerta
            datos = Consolidacion(
                peso_final_kg=Decimal(c.peso_final),
                humedad_pct=HUMEDAD_FINAL,
                lugar_id=self.lugares["almacen"],
                explicacion=EXPLICACION_RENDIMIENTO if alerta else None,
            )
            consolidada = corridas.consolidar(self.operador, self.storage, corrida.id, datos)
        self.resultado.tandas_finales[c.numero] = consolidada.tanda_final.id

    def _etapa(
        self, c: CorridaDemo, etapa: etapas_proceso.Etapa, inicio: datetime
    ) -> tuple[EtapaRegistro, datetime]:
        """La etapa con los valores de la plantilla, desde `inicio` y con su duración. Las opcionales (7 y 14)
        no ocurren."""
        if etapa.opcional:
            entrada = EtapaRegistro(situacion="no_ocurrio", observacion="No hizo falta en esta corrida.")
            return entrada, inicio
        lugar_id, metodo, distancia, horas = self.plantilla[etapa.numero]
        fin = inicio + timedelta(hours=float(horas))
        datos = {
            2: {"observacion_calidad": "Grano de demostración sin defectos a la vista."},
            9: {"fechas_volteo": [(inicio + timedelta(hours=h)).isoformat() for h in (48, 96)]},
            10: {"pct_bien_fermentados": "85"},
            13: {"humedad_pct": "7.0"},
            17: {"calidad_id": str(self.calidades[CALIDAD_DE_LAS_ORDENES])},
            18: {"kg_descartados": c.descartados},
            19: {"peso_final_kg": c.peso_final},
            21: {"numero_sacos": c.sacos},
        }.get(etapa.numero, {})
        entrada = EtapaRegistro(
            lugar_id=lugar_id,
            inicio=inicio,
            fin=fin,
            metodo=metodo,
            responsable=RESPONSABLE,
            distancia_m=distancia if etapa.transporte else None,
            datos=datos,
        )
        return entrada, fin

    def _tandas_detenidas(self) -> None:
        detalle = self._registrar_tanda(TANDA_OBSERVADA, con_archivo=False)
        with _paso(f"Observar la tanda {detalle.codigo}"):
            tandas.observar(self.operador, detalle.id, Motivo(motivo=MOTIVO_OBSERVACION).motivo)
        self.resultado.tandas["observada"] = detalle.id
        self.resultado.tandas["sin validar"] = self._registrar_tanda(TANDA_SIN_VALIDAR).id

    # ---------- Exportación ----------

    def _exportacion(self) -> None:
        with _paso("Registrar al importador"):
            importador = ordenes.crear_importador(
                self.operador,
                ImportadorNuevo(
                    razon_social="Importador Demo B.V.",
                    direccion="Calle de Demostración 1, Rotterdam (dirección ficticia)",
                    pais="Países Bajos",
                    correo="compras@importador-demo.test",
                ),
            )
        self.resultado.importador_id = importador.id
        for numero, (kilos, dias) in enumerate(ORDENES, start=1):
            with _paso(f"Crear la orden {numero}"):
                orden = ordenes.crear(
                    self.operador,
                    OrdenNueva(
                        importador_id=importador.id,
                        referencia_importador=f"DEMO-{numero}",
                        cantidad_kg=Decimal(kilos),
                        calidad_id=self.calidades[CALIDAD_DE_LAS_ORDENES],
                        pais_destino="Países Bajos",
                        lugar_destino="Rotterdam",
                        fecha_entrega=self.hoy + timedelta(days=dias),
                    ),
                )
            self.resultado.ordenes[numero] = orden.id
        tf = self.resultado.tandas_finales
        # Lote 1: sigue el orden FIFO. Lote 2: se aparta, con motivo. Lote 3: FIFO otra vez.
        self._lote(1, sugerida={tf[1]: Decimal("400"), tf[2]: Decimal("200")})
        self._lote(
            2,
            sugerida={tf[2]: Decimal("250"), tf[3]: Decimal("50")},
            seleccion={tf[3]: Decimal("300.00")},
            motivo=MOTIVO_DESVIACION,
        )
        self._lote(3, sugerida={tf[2]: Decimal("150")})
        for numero in (1, 2, 3):
            self._embarque(numero)
            self._recomprobar(numero, "listo")
        with _paso("Emitir el DEX del lote 1"):
            entiendo = EmisionDex(entiendo=True).entiendo
            emitido = dex.emitir(self.admin, self.storage, self.resultado.lotes[1], entiendo)
        self.resultado.dex_id = emitido.id

    def _lote(
        self,
        numero: int,
        *,
        sugerida: dict[uuid.UUID, Decimal],
        seleccion: dict[uuid.UUID, Decimal] | None = None,
        motivo: str | None = None,
    ) -> None:
        paso = f"Lote de la orden {numero}"
        with _paso(f"{paso}: armar con la sugerencia FIFO"):
            lote = lotes.crear(self.operador, self.resultado.ordenes[numero])
        if {a.tanda_final_id: a.kg_asignados for a in lote.asignaciones} != sugerida:
            tomadas = ", ".join(f"{a.codigo}: {a.kg_asignados} kg" for a in lote.asignaciones) or "nada"
            raise EscenarioDetenido(
                f"{paso}: armar", f"la sugerencia FIFO tomó {tomadas}, distinta de la del escenario."
            )
        if seleccion:
            with _paso(f"{paso}: cambiar la selección"):
                asignaciones = [Asignacion(tanda_final_id=k, kg_asignados=v) for k, v in seleccion.items()]
                lotes.cambiar_seleccion(self.operador, lote.id, Seleccion(asignaciones=asignaciones))
        with _paso(f"{paso}: confirmar"):
            lotes.confirmar(self.operador, lote.id, Confirmacion(motivo_desviacion=motivo))
        self.resultado.lotes[numero] = lote.id

    def _embarque(self, numero: int) -> None:
        lote_id = self.resultado.lotes[numero]
        for n, tipo in enumerate(documentos_embarque.TIPOS, start=1):
            with _paso(f"Lote de la orden {numero}: cargar «{tipo.nombre}»"):
                embarque.cargar(
                    self.operador,
                    self.storage,
                    lote_id,
                    tipo.codigo,
                    self._archivo(tipo.nombre, f"Lote de la orden {numero}"),
                    f"DEMO-LOTE{numero}-{n}",
                    ENTIDAD_EMISORA,
                    self.hoy,
                )

    def _recomprobar(self, numero: int, esperado: str) -> None:
        paso = f"Lote de la orden {numero}: recomprobar"
        with _paso(paso):
            salida = recomprobacion.recomprobar(self.operador, self.resultado.lotes[numero])
        if salida.estado_lote != esperado:
            casos = "; ".join(caso.texto for c in salida.comprobaciones for caso in c.casos)
            raise EscenarioDetenido(
                paso, f"el lote quedó {salida.estado_lote} y el escenario esperaba {esperado}. {casos}."
            )

    def _bloquear_lote_2(self) -> None:
        """Anula un documento de PA-00007: la recomprobación la pasa a observada y bloquea el lote 2."""
        codigo, tipo = ANULADO
        documento_id = self.documentos_parcela[codigo][tipo]
        with _paso(f"Anular un documento de {codigo}"):
            documentos.anular(self.admin, documento_id, Anulacion(motivo=MOTIVO_ANULACION).motivo)
        self.resultado.documento_anulado_id = documento_id
        self._recomprobar(2, "bloqueado")
