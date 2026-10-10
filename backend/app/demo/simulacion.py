"""Paquete de simulación para cargar a mano (pedido del equipo del 2026-10-06).

Dos cooperativas de demostración con su flujo completo por el camino feliz: 3 productores con 3 parcelas cada
uno, una tanda por parcela, dos corridas (una segregada y una mezclada), una orden, su lote, los cuatro
documentos de embarque y el DEX. Ningún caso está pensado para fallar: sin documentos vencidos, sin
superposiciones, sin rendimientos fuera de banda y sin volúmenes sobre el tope.

`armar(hoy)` arma los datos, con fechas entre agosto y hoy contadas hacia atrás desde `hoy`. El script
`scripts/generar_simulacion.py` los vuelca en un ZIP con el guion de carga y los archivos; la prueba
`tests/test_simulacion.py` los carga con `cargar(...)` por la capa de servicios, con las mismas reglas que una
persona en la interfaz, y comprueba que ningún paso falla y que las cifras esperadas cuadran.

Decisiones (en el LEEME del paquete):
- Las dos cooperativas son de demostración (Parte 10): sus DOP, DPP y DEX llevan la marca de agua.
- Cada cooperativa tiene un administrador y un operador: el operador registra las tandas y el administrador
  las valida, para que el DEX no muestre "registro y validación por la misma persona".
- Las parcelas son de propiedad titulada (adenda 4): se carga su título y el operador declara su perfil
  legal; lo que responde el cruce con las capas oficiales no se declara, salvo que el cruce no haya
  respondido. Ya no hay exenciones ni documentos laborales, tributarios o de zonificación.
- La plantilla de proceso se llena con "Llenar con la plantilla sugerida": las etapas que se confirman sin
  cambiar lugar, método y distancia salen en el DPP como "no verificado".
- Los pesos de las tandas dan proporciones exactas en cada corrida, así que la genealogía no depende del
  redondeo ni del orden en que se agregan las tandas.
"""

import csv
import gzip
import json
import math
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from app import ubigeo
from app.catalogos import declaracion_productor as cuestionario
from app.catalogos import etapas_proceso
from app.fechas import LIMA

DATOS = Path(__file__).parent / "simulacion_parcelas.json"
LIMITES = Path(__file__).resolve().parents[1] / "datos" / "limites_distritales_inei.json.gz"
VERSION_CONSENTIMIENTO = "1"
TOPE = Decimal("1500")
CALIDAD = "Grado 1"
HUMEDAD = Decimal("7.0")
FIN_VIGENCIA_MINIMO = date(2027, 6, 30)

# Adenda 4: lo que el operador declara del perfil legal de cada parcela (propietario con título, sin riego).
PERFIL_DECLARADO = (
    ("tenencia_tipo", "propietario"),
    ("usa_riego", "no"),
    ("anio_instalacion_cultivo", "2014"),
)
NOTA_HABILITACION_ALERTA = (
    "Se habilita después de revisar las imágenes satelitales de la parcela: antes del 31/12/2020 ya era "
    "cultivo agrícola y no se ve cambio de cobertura después. Datos de la simulación."
)
NOTA_VALIDACION_ALERTA = (
    "La parcela quedó habilitada con su revisión de imágenes registrada; la cooperativa revisó las alertas "
    "antes de validar esta tanda de la simulación."
)
REVISION_IMAGENES = (
    "En la imagen anterior al corte la parcela ya se ve como cultivo agrícola, sin bosque. En las imágenes "
    "posteriores no se ve cambio de cobertura dentro del lindero."
)
OBSERVACION_CALIDAD = "Grano de buen aspecto, sin olores extraños ni materias extrañas a la vista."


# ---------- Utilidades ----------


def ruc_valido(base: str) -> str:
    """RUC de 11 dígitos con su dígito verificador (módulo 11 de SUNAT) a partir de los 10 primeros."""
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = 11 - sum(int(d) * p for d, p in zip(base, pesos, strict=True)) % 11
    return base + str({10: 0, 11: 1}.get(resto, resto))


def _lima(dia: date, hora: int, minuto: int = 0) -> datetime:
    return datetime.combine(dia, time(hora, minuto), tzinfo=LIMA)


def _metros_por_grado(lat: float) -> tuple[float, float]:
    f = math.radians(lat)
    m_lat = 111132.954 - 559.822 * math.cos(2 * f) + 1.175 * math.cos(4 * f)
    m_lon = (math.pi / 180) * 6378137.0 * math.cos(f) / math.sqrt(1 - 0.00669437999014 * math.sin(f) ** 2)
    return m_lat, m_lon


def area_aproximada_ha(geometria: dict) -> Decimal:
    """Área del polígono en una proyección local; difiere en milésimas de la que calcula PostGIS."""
    anillo = geometria["coordinates"][0]
    lat0 = sum(p[1] for p in anillo) / len(anillo)
    m_lat, m_lon = _metros_por_grado(lat0)
    pts = [(lon * m_lon, lat * m_lat) for lon, lat in anillo]
    doble = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False))
    return (Decimal(abs(doble) / 2) / 10000).quantize(Decimal("0.01"))


@cache
def _limites() -> list[tuple[str, Any]]:
    distritos = json.loads(gzip.decompress(LIMITES.read_bytes()))["distritos"]
    return [(codigo, shape(g)) for codigo, g in distritos.items()]


@cache
def _nombres() -> dict[str, tuple[str, str, str]]:
    with ubigeo.ARCHIVO.open(encoding="utf-8", newline="") as archivo:
        return {
            f["ubigeo"]: (f["departamento"], f["provincia"], f["distrito"]) for f in csv.DictReader(archivo)
        }


def ubicacion(geometria: dict) -> tuple[str, str, str]:
    """El distrito donde cae el polígono, igual que services/limites.py: el de mayor área en común."""
    forma = shape(geometria)
    candidatos = [(c, d) for c, d in _limites() if d.intersects(forma)]
    codigo, _ = max(candidatos, key=lambda par: par[1].intersection(forma).area)
    return _nombres()[codigo]


# ---------- Datos del escenario ----------


@dataclass(frozen=True)
class Documento:
    tipo: str  # código del catálogo de la aplicación
    nombre: str  # como lo muestra la interfaz
    numero: str
    entidad: str
    emision: date
    vencimiento: date | None
    archivo: str  # ruta dentro del paquete
    titulo: str  # título impreso en el PDF
    secciones: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    texto: str | None = None


@dataclass(frozen=True)
class Cuenta:
    nombres: str
    apellidos: str
    correo: str


@dataclass(frozen=True)
class Productor:
    clave: str
    dni: str
    nombres: str
    apellidos: str
    direccion: str
    copia_dni: Documento
    hoja_declaracion: Documento  # adenda 5: muestra de la hoja firmada de la declaración anual


# Adenda 5: los seis productores trabajan con su familia, sin menores ni agroquímicos, y venden menos de
# 75 UIT: responden cuatro preguntas y nada queda por atender.
DECLARACION_FAMILIA = {
    "quien_trabaja": "solo_familia",
    "menores_trabajan": "no",
    "usa_agroquimicos": "no",
    "ventas_superan_75_uit": "no",
}


@dataclass(frozen=True)
class Parcela:
    clave: str
    codigo: str  # el que le pondrá CacaoTrace si se registran en este orden
    productor: str
    nombre: str
    centro_poblado: str
    geometria: dict
    area_ha: Decimal
    ubicacion: tuple[str, str, str]
    carpeta: str
    documentos: tuple[Documento, ...]
    perfil: tuple[tuple[str, str], ...]  # (variable, valor) que declara el operador (adenda 4)


@dataclass(frozen=True)
class Tanda:
    clave: str
    parcela: str
    productor: str
    recibida_en: datetime
    peso: Decimal
    sacos: int
    variedad: str  # código del catálogo
    variedad_nombre: str
    cosecha_desde: date
    cosecha_hasta: date
    liquidacion: Documento


@dataclass(frozen=True)
class Etapa:
    numero: int
    nombre: str
    lugar: str  # clave del lugar
    inicio: datetime | None
    fin: datetime | None
    metodo: str | None
    distancia: Decimal | None
    datos: dict[str, Any]
    etiquetas_datos: tuple[tuple[str, str], ...]  # (etiqueta en la interfaz, valor)
    no_ocurrio: bool = False


@dataclass(frozen=True)
class Corrida:
    clave: str
    nombre: str
    ruta: str
    manejo: str
    tandas: tuple[str, ...]
    etapas: tuple[Etapa, ...]
    peso_final: Decimal
    kg_descartados: Decimal
    sacos: int


@dataclass(frozen=True)
class Importador:
    razon_social: str
    direccion: str
    pais: str
    correo: str
    eori: str


@dataclass(frozen=True)
class Orden:
    importador: Importador
    referencia: str
    cantidad: Decimal
    pais_destino: str
    lugar_destino: str
    fecha_entrega: date
    embarque: tuple[Documento, ...]


@dataclass(frozen=True)
class Cooperativa:
    clave: str
    carpeta: str
    razon_social: str
    nombre_comercial: str
    ruc: str
    codigo: str
    ubicacion: tuple[str, str, str]
    admin: Cuenta
    operador: Cuenta
    direccion: str
    correo: str
    representante: str
    representante_dni: str
    documentos: tuple[Documento, ...]
    lugares: tuple[tuple[str, str, str], ...]  # (clave, nombre, tipo)
    productores: tuple[Productor, ...]
    parcelas: tuple[Parcela, ...]
    tandas: tuple[Tanda, ...]
    corridas: tuple[Corrida, ...]
    orden: Orden

    def tanda(self, clave: str) -> Tanda:
        return next(t for t in self.tandas if t.clave == clave)

    def parcela(self, clave: str) -> Parcela:
        return next(p for p in self.parcelas if p.clave == clave)

    def productor(self, clave: str) -> Productor:
        return next(p for p in self.productores if p.clave == clave)


@dataclass(frozen=True)
class Simulacion:
    hoy: date
    cooperativas: tuple[Cooperativa, ...] = field(default_factory=tuple)


# Por cooperativa: (clave, carpeta, nombre corto, código, base del RUC, sufijo de DNI, importador, pesos).
# Pesos en baba: la corrida A lleva las 3 tandas del primer productor y la B las 6 de los otros dos.
# Sus totales (1,000 y 2,500; 1,250 y 2,000) dan proporciones exactas con 6 decimales.
CONFIG = (
    {
        "clave": "norte",
        "carpeta": "01-cooperativa-muestra-norte",
        "nombre": "Muestra Norte",
        "codigo": "MNO",
        "ruc": "2000000011",
        "dni": "11",
        "productores": ("Demo Uno", "Demo Dos", "Demo Tres"),
        "apellidos": "Muestra Norte",
        "pesos": ("300", "300", "400", "450", "400", "350", "500", "375", "425"),
        "rendimientos": ("0.400", "0.400"),
        "cantidad": "1200",
        "dias_atras": 52,
        "importador": Importador(
            "Muestra Cacao Import GmbH (ficticio)",
            "Musterstraße 1, 20457 Hamburgo, Alemania (dirección ficticia)",
            "Alemania",
            "compras@muestra-cacao-import.test",
            "DE000000000000101",
        ),
        "destino": ("Alemania", "Hamburgo"),
    },
    {
        "clave": "sur",
        "carpeta": "02-cooperativa-muestra-sur",
        "nombre": "Muestra Sur",
        "codigo": "MSU",
        "ruc": "2000000012",
        "dni": "12",
        "productores": ("Demo Cuatro", "Demo Cinco", "Demo Seis"),
        "apellidos": "Muestra Sur",
        "pesos": ("500", "350", "400", "300", "350", "400", "250", "375", "325"),
        "rendimientos": ("0.380", "0.420"),
        "cantidad": "1000",
        "dias_atras": 42,
        "importador": Importador(
            "Muestra Chocolate Trading B.V. (ficticio)",
            "Voorbeeldstraat 1, 3011 Róterdam, Países Bajos (dirección ficticia)",
            "Países Bajos",
            "compras@muestra-chocolate-trading.test",
            "NL000000000000102",
        ),
        "destino": ("Países Bajos", "Róterdam"),
    },
)
NOMBRES_PARCELA = (
    ("La Palma", "El Mango", "Los Pinos"),
    ("Santa Rosa", "El Naranjal", "La Lomita"),
    ("Las Brisas", "El Paraíso", "San Juan"),
)
VARIEDADES = (("ccn_51", "CCN-51"), ("trinitario", "Trinitario"), ("ics_95", "ICS-95"))
PRECIO_BABA_SOLES = Decimal("4.20")
PRECIO_FOB_USD = Decimal("7.80")


def _sin_tildes(texto: str) -> str:
    plano = unicodedata.normalize("NFD", texto)
    return "".join(c for c in plano if not unicodedata.combining(c)).replace("ñ", "n").replace("Ñ", "N")


def _carpeta(texto: str) -> str:
    return "-".join(_sin_tildes(texto).lower().replace(",", "").split())


def _vence(hoy: date, dias: int) -> date:
    return max(FIN_VIGENCIA_MINIMO + timedelta(days=dias - 270), hoy + timedelta(days=dias))


def armar(hoy: date) -> Simulacion:
    geometrias = json.loads(DATOS.read_text(encoding="utf-8"))
    return Simulacion(
        hoy=hoy,
        cooperativas=tuple(_cooperativa(hoy, c, geometrias[c["clave"]]) for c in CONFIG),
    )


def _cooperativa(hoy: date, c: dict, geometrias: list[dict]) -> Cooperativa:
    base = hoy - timedelta(days=c["dias_atras"])
    ruc = ruc_valido(c["ruc"])
    razon = f"Cooperativa Agraria {c['nombre']} (simulación)"
    dominio = f"{_carpeta(c['nombre'])}.test"
    ubic = ubicacion(geometrias[0])
    dep, prov, dist = ubic
    lugar_txt = f"{dist.title()}, {prov.title()}, {dep.title()}"
    carpeta = c["carpeta"]
    representante = f"Demo Representante {c['nombre'].split()[-1]}"
    rep_dni = f"000001{c['dni'][1]}9"
    emision_coop = base - timedelta(days=8)

    def doc_coop(i, tipo, nombre, numero, entidad, titulo, campos, vence=None):
        return Documento(
            tipo, nombre, numero, entidad, emision_coop + timedelta(days=i), vence,
            f"{carpeta}/01-expediente-cooperativa/{i + 1:02d}-{tipo.replace('_', '-')}.pdf", titulo,
            (("Datos del documento", tuple(campos)),),
        )

    partida_coop = f"11{c['dni']}9001"  # 8 dígitos, distinta de las de las parcelas
    documentos = (
        doc_coop(
            0, "rnca",
            "Constancia de inscripción en el Registro Nacional de Cooperativas Agrarias (MIDAGRI)",
            f"RNCA-{c['codigo']}-2026-001",
            "MIDAGRI, Dirección General de Asociatividad (muestra)",
            "Constancia de inscripción en el Registro Nacional de Cooperativas Agrarias",
            [
                ("Número de registro", f"RNCA-{c['codigo']}-2026-001"),
                ("Razón social", razon),
                ("RUC", ruc),
                ("Tipo de cooperativa", "Cooperativa agraria de servicios"),
                ("Domicilio", lugar_txt),
                ("Fecha de inscripción", f"{emision_coop:%d/%m/%Y}"),
            ],
            _vence(hoy, 700),
        ),
        doc_coop(
            1, "partida_sunarp", "Partida registral de la organización en SUNARP", partida_coop,
            "SUNARP, Zona Registral N.° III, Sede Moyobamba",
            "Copia literal de la partida registral de la persona jurídica",
            [
                ("Partida N.°", partida_coop),
                ("Oficina registral", "Moyobamba"),
                ("Persona jurídica", razon),
                ("Asiento de inscripción", "A00001"),
                ("Objeto social", "Acopio, beneficio y comercialización de cacao de sus socios"),
                ("Domicilio", lugar_txt),
            ],
        ),
        doc_coop(
            2, "ficha_ruc", "Ficha RUC de SUNAT", ruc, "SUNAT", "Ficha RUC",
            [
                ("Número de RUC", ruc),
                ("Razón social", razon),
                ("Tipo de contribuyente", "Cooperativa agraria"),
                ("Estado del contribuyente", "Activo"),
                ("Condición del domicilio fiscal", "Habido"),
                ("Domicilio fiscal", f"Jr. Muestra 101, {lugar_txt}"),
                ("Actividad económica principal", "Venta al por mayor de materias primas agropecuarias"),
                ("Comercio exterior", "Exportador"),
            ],
        ),
        doc_coop(
            3, "vigencia_poderes", "Vigencia de poderes del representante legal (SUNARP)",
            f"VP-{partida_coop}", "SUNARP, Zona Registral N.° III, Sede Moyobamba",
            "Vigencia de poder del representante legal",
            [
                ("Partida N.°", partida_coop),
                ("Persona jurídica", razon),
                ("Representante", representante),
                ("DNI del representante", rep_dni),
                ("Cargo", "Gerente general"),
                (
                    "Facultades",
                    "Representar a la cooperativa ante entidades públicas y privadas, y suscribir "
                    "contratos de compraventa y exportación",
                ),
                ("Asiento", "C00002"),
            ],
            _vence(hoy, 270),
        ),
        # Adenda 6: la declaración anual de renta reemplaza a los dos registros de exportador, que no existen.
        doc_coop(
            4, "renta_anual",
            "Declaración jurada anual del impuesto a la renta, o constancia de haberla presentado",
            f"OR-{c['codigo']}-2025-0001", "SUNAT",
            "Constancia de presentación de la declaración jurada anual del impuesto a la renta",
            [
                ("Número de orden", f"OR-{c['codigo']}-2025-0001"),
                ("Número de RUC", ruc),
                ("Razón social", razon),
                ("Ejercicio", "2025"),
                ("Fecha de presentación", f"{emision_coop + timedelta(days=4):%d/%m/%Y}"),
            ],
        ),
    )

    productores, parcelas, tandas = [], [], []
    for i, nombre in enumerate(c["productores"]):
        clave = f"P{i + 1}"
        dni = f"000001{c['dni'][1]}{i + 1}"
        direccion = f"Caserío {NOMBRES_PARCELA[i][0]}, {lugar_txt} (dirección ficticia)"
        copia = Documento(
            "dni", "Copia del DNI", dni, "RENIEC", base - timedelta(days=6), None,
            f"{carpeta}/02-productores/{_carpeta(nombre)}-copia-dni.pdf",
            "Copia del Documento Nacional de Identidad (DNI)",
            (("Datos del documento", (
                ("DNI", dni), ("Apellidos", c["apellidos"]), ("Nombres", nombre),
                ("Domicilio", direccion), ("Fecha de emisión", f"{base - timedelta(days=6):%d/%m/%Y}"),
                ("Fecha de caducidad", f"{_vence(hoy, 2900):%d/%m/%Y}"),
            )),),
            "Copia simplificada: solo los datos que usa CacaoTrace.",
        )
        respuestas = tuple(
            (cuestionario.POR_CODIGO[k].texto_personal, cuestionario.POR_CODIGO[k].etiqueta(v))
            for k, v in DECLARACION_FAMILIA.items()
        )
        hoja = Documento(
            "hoja_declaracion_productor", "Hoja firmada de la declaración anual", "Versión 1", razon, hoy,
            None,
            f"{carpeta}/02-productores/{_carpeta(nombre)}-declaracion-anual-firmada.pdf",
            "Declaración jurada anual del productor (hoja firmada)",
            (
                ("Productor", (("Nombres y apellidos", f"{nombre} {c['apellidos']}"), ("DNI", dni))),
                ("Respuestas", respuestas),
                ("Firma", (("Firma y huella del productor", "Firmada (muestra)"),)),
            ),
            "Muestra simplificada: la hoja real la descarga CacaoTrace al registrar la declaración, con el "
            "texto completo del Anexo A, y el productor la firma y pone su huella.",
        )
        productores.append(Productor(clave, dni, nombre, c["apellidos"], direccion, copia, hoja))
        for j, nombre_parcela in enumerate(NOMBRES_PARCELA[i]):
            n = i * 3 + j
            geometria = geometrias[n]
            area = area_aproximada_ha(geometria)
            ubic_p = ubicacion(geometria)
            p_carpeta = f"{carpeta}/03-parcelas/parcela-{n + 1:02d}-{_carpeta(nombre_parcela)}"
            emision = base - timedelta(days=5 - j)
            partida = f"11{c['dni']}0{n + 1:03d}"
            centro = f"Caserío {nombre_parcela}"
            titular = (("Titular", f"{nombre} {c['apellidos']}"), ("DNI del titular", dni))
            predio = (
                ("Predio", f"Parcela {nombre_parcela}"),
                ("Ubicación", f"{centro}, {ubic_p[2].title()}, {ubic_p[1].title()}, {ubic_p[0].title()}"),
                ("Área", f"{area} ha"),
            )
            documentos_p = (
                Documento(
                    "titulo_sunarp", "Título de propiedad inscrito en SUNARP", partida,
                    "SUNARP, Zona Registral N.° III, Sede Moyobamba", emision, None,
                    f"{p_carpeta}/titulo-sunarp.pdf",
                    "Copia literal de la partida registral del predio",
                    (
                        (
                            "Partida",
                            (
                                ("Partida N.°", partida),
                                ("Oficina registral", "Juanjuí"),
                                ("Asiento de dominio", "C00001"),
                            ),
                        ),
                        ("Predio", predio),
                        ("Titularidad", titular),
                    ),
                ),
            )
            parcelas.append(
                Parcela(
                    f"N{n + 1}", f"PA-{n + 1:05d}", clave, nombre_parcela, centro, geometria, area, ubic_p,
                    p_carpeta, documentos_p, PERFIL_DECLARADO,
                )
            )
            # Una tanda por parcela: la corrida A recibe en los días 0 y 1; la B en los días 3 a 5.
            dia = base + timedelta(days=(j // 2) if i == 0 else 3 + ((i - 1) * 3 + j) // 2)
            recibida = _lima(dia, 8 + 2 * (n % 2), 30 if n % 3 else 0)
            peso = Decimal(c["pesos"][n])
            numero = f"L001-{(1 if c['clave'] == 'norte' else 2)}0{n + 1:02d}"
            variedad, variedad_nombre = VARIEDADES[n % 3]
            liquidacion = Documento(
                "liquidacion_compra", "Liquidación de compra", numero, razon, dia, None,
                f"{carpeta}/04-tandas/tanda-{n + 1:02d}-liquidacion-{numero.lower()}.pdf",
                "Liquidación de compra electrónica",
                (
                    ("Comprobante", (("Serie y número", numero), ("Fecha de emisión", f"{dia:%d/%m/%Y}"))),
                    ("Emisor (comprador)", (("Razón social", razon), ("RUC", ruc))),
                    (
                        "Vendedor",
                        (("Nombre", f"{nombre} {c['apellidos']}"), ("DNI", dni), ("Domicilio", direccion)),
                    ),
                    ("Detalle", (
                        ("Descripción", f"Cacao en baba ({variedad_nombre}), de la parcela {nombre_parcela}"),
                        ("Cantidad", f"{peso:.2f} kg"), ("Precio unitario", f"S/ {PRECIO_BABA_SOLES}"),
                        ("Importe total", f"S/ {(peso * PRECIO_BABA_SOLES).quantize(Decimal('0.01'))}"),
                    )),
                ),
            )
            tandas.append(
                Tanda(
                    f"T{n + 1}", f"N{n + 1}", clave, recibida, peso, math.ceil(peso / 60), variedad,
                    variedad_nombre, dia - timedelta(days=4), dia - timedelta(days=1), liquidacion,
                )
            )

    lugares = (
        ("cancha", f"Cancha de acopio {c['nombre']}", "cancha_acopio"),
        ("planta", f"Planta de beneficio {c['nombre']}", "planta"),
        ("almacen", f"Almacén {c['nombre']}", "almacen"),
    )
    corridas = []
    for k, (clave_corrida, manejo, claves) in enumerate(
        (("A", "segregado", ("T1", "T2", "T3")), ("B", "mezclado", ("T4", "T5", "T6", "T7", "T8", "T9")))
    ):
        entrada = sum((Decimal(c["pesos"][int(t[1:]) - 1]) for t in claves), Decimal(0))
        peso_final = (entrada * Decimal(c["rendimientos"][k])).quantize(Decimal("0.01"))
        descartados = (entrada / 100).quantize(Decimal("0.01"))
        sacos = math.ceil(peso_final / 69)
        ultima = max(t.recibida_en for t in tandas if t.clave in claves)
        etapas = _etapas(ultima + timedelta(hours=2), peso_final, descartados, sacos)
        nombre_corrida = f"Corrida {clave_corrida} ({'segregada' if manejo == 'segregado' else 'mezclada'})"
        corridas.append(
            Corrida(
                clave_corrida, nombre_corrida, "completa", manejo, claves, etapas,
                peso_final, descartados, sacos,
            )
        )

    cantidad = Decimal(c["cantidad"])
    pais, puerto = c["destino"]
    fin_corridas = max(e.fin for co in corridas for e in co.etapas if e.fin)
    emision_emb = min(hoy, fin_corridas.date() + timedelta(days=3))
    referencia = f"PO-{c['codigo']}-2026-001"
    imp = c["importador"]
    sacos_lote = math.ceil(cantidad / 69)

    def doc_emb(i, tipo, nombre, numero, entidad, titulo, secciones):
        return Documento(tipo, nombre, numero, entidad, emision_emb, None,
                         f"{carpeta}/05-embarque/{i + 1:02d}-{tipo.replace('_', '-')}.pdf", titulo, secciones)

    producto = (("Producto", "Granos de cacao fermentados y secos, calidad Grado 1 (partida 1801)"),
                ("Cantidad (masa neta)", f"{cantidad:.2f} kg"), ("Sacos de yute", str(sacos_lote)))
    partes = (
        (
            "Exportador",
            (("Razón social", razon), ("RUC", ruc), ("Domicilio", f"Jr. Muestra 101, {lugar_txt}")),
        ),
        (
            "Importador",
            (("Razón social", imp.razon_social), ("Dirección", imp.direccion), ("EORI", imp.eori)),
        ),
    )
    embarque = (
        doc_emb(
            0, "factura_comercial", "Factura comercial", f"F001-{(1 if c['clave'] == 'norte' else 2)}001",
            razon, "Factura electrónica de exportación",
            partes
            + (
                (
                    "Detalle",
                    producto
                    + (
                        ("Incoterm", "FOB Paita"),
                        ("Precio unitario", f"US$ {PRECIO_FOB_USD} por kg"),
                        ("Importe total", f"US$ {(cantidad * PRECIO_FOB_USD).quantize(Decimal('0.01'))}"),
                        ("Orden del importador", referencia),
                    ),
                ),
            ),
        ),
        doc_emb(
            1, "packing_list", "Lista de empaque", f"PL-{c['codigo']}-2026-001", razon,
            "Lista de empaque (packing list)",
            partes
            + (
                (
                    "Contenido",
                    producto
                    + (
                        ("Peso bruto", f"{cantidad + sacos_lote:.2f} kg (sacos de 1 kg)"),
                        ("Marcas", f"{c['codigo']}-LOTE-001"),
                    ),
                ),
            ),
        ),
        doc_emb(
            2, "certificado_origen", "Certificado de origen", f"CO-{c['codigo']}-2026-0001",
            "Entidad autorizada para emitir el documento de origen (muestra)", "Certificado de origen",
            partes
            + (
                (
                    "Mercancía",
                    producto
                    + (
                        ("País de origen", "Perú"),
                        ("País de destino", pais),
                        ("Criterio de origen", "Totalmente obtenido"),
                    ),
                ),
            ),
        ),
        doc_emb(
            3, "certificado_fitosanitario", "Certificado fitosanitario", f"CF-{c['codigo']}-2026-0001",
            "SENASA (muestra)", "Certificado fitosanitario",
            partes
            + (
                (
                    "Envío",
                    producto
                    + (
                        ("Lugar de origen", lugar_txt),
                        ("Punto de salida", "Puerto de Paita"),
                        ("País de destino", pais),
                        (
                            "Declaración",
                            "Producto inspeccionado y libre de plagas cuarentenarias (texto de muestra)",
                        ),
                    ),
                ),
            ),
        ),
    )
    orden = Orden(imp, referencia, cantidad, pais, puerto, hoy, embarque)

    return Cooperativa(
        clave=c["clave"],
        carpeta=carpeta,
        razon_social=razon,
        nombre_comercial=f"Muestra {c['nombre'].split()[-1]}",
        ruc=ruc,
        codigo=c["codigo"],
        ubicacion=ubic,
        admin=Cuenta("Demo", f"Administrador {c['nombre'].split()[-1]}", f"admin@{dominio}"),
        operador=Cuenta("Demo", f"Operador {c['nombre'].split()[-1]}", f"operador@{dominio}"),
        direccion=f"Jr. Muestra 101, {lugar_txt} (dirección ficticia)",
        correo=f"contacto@{dominio}",
        representante=representante,
        representante_dni=rep_dni,
        documentos=documentos,
        lugares=lugares,
        productores=tuple(productores),
        parcelas=tuple(parcelas),
        tandas=tuple(tandas),
        corridas=tuple(corridas),
        orden=orden,
    )


# Duración de cada etapa en horas, igual a la de la plantilla sugerida; la 23 dura un día.
DURACION = {n: Decimal(h) for n, h in etapas_proceso.HORAS_SUGERIDAS.items()} | {23: Decimal(24)}
DISTANCIA = {6: Decimal("120"), 11: Decimal("60"), 15: Decimal("40"), 20: Decimal("25"), 22: Decimal("150")}
LARGAS = {9, 12, 23}


def _siguiente(momento: datetime) -> datetime:
    """La etapa siguiente empieza 15 minutos después; las cortas, entre las 7:00 y las 17:00."""
    inicio = momento + timedelta(minutes=15)
    local = inicio.astimezone(LIMA)
    if local.hour >= 17:
        return _lima(local.date() + timedelta(days=1), 7, 30)
    if local.hour < 7:
        return _lima(local.date(), 7, 30)
    return inicio


def _etapas(desde: datetime, peso_final: Decimal, descartados: Decimal, sacos: int) -> tuple[Etapa, ...]:
    lugar = {
        n: etapas_proceso.LUGAR_SUGERIDO[n].replace("cancha_acopio", "cancha") for n in etapas_proceso.NUMEROS
    }
    momento = _siguiente(desde - timedelta(minutes=15))
    etapas = []
    for e in etapas_proceso.ETAPAS:
        if e.automatica:
            continue
        if e.opcional:
            etapas.append(
                Etapa(e.numero, e.nombre, lugar[e.numero], None, None, None, None, {}, (), no_ocurrio=True)
            )
            continue
        inicio = momento if e.numero in LARGAS else _siguiente(momento - timedelta(minutes=15))
        fin = inicio + timedelta(hours=float(DURACION[e.numero]))
        datos, etiquetas = _datos_propios(e.numero, inicio, peso_final, descartados, sacos)
        etapas.append(Etapa(
            e.numero, e.nombre, lugar[e.numero], inicio, fin, etapas_proceso.METODOS[e.numero][0],
            DISTANCIA.get(e.numero), datos, etiquetas,
        ))
        momento = _siguiente(fin)
    return tuple(etapas)


def _datos_propios(
    numero: int, inicio: datetime, peso_final: Decimal, descartados: Decimal, sacos: int
):
    if numero == 2:
        return (
            {"observacion_calidad": OBSERVACION_CALIDAD},
            (("Observación de calidad", OBSERVACION_CALIDAD),),
        )
    if numero == 9:
        volteos = [inicio + timedelta(hours=48), inicio + timedelta(hours=96)]
        texto = "\n".join(f"{v.astimezone(LIMA):%d/%m/%Y %H:%M}" for v in volteos)
        return (
            {"fechas_volteo": [v.isoformat() for v in volteos]},
            (("Fechas de volteo (una por línea, dd/mm/aaaa hh:mm)", texto),),
        )
    if numero == 10:
        return {"pct_bien_fermentados": "82"}, (("Granos bien fermentados (%)", "82"),)
    if numero == 13:
        return {"humedad_pct": str(HUMEDAD)}, (("Humedad (%)", str(HUMEDAD)),)
    if numero == 17:
        return {"calidad_id": None}, (("Calidad asignada", CALIDAD),)
    if numero == 18:
        return {"kg_descartados": str(descartados)}, (("Kilos descartados (kg)", str(descartados)),)
    if numero == 19:
        return {"peso_final_kg": str(peso_final)}, (("Peso final (kg)", str(peso_final)),)
    if numero == 21:
        return {"numero_sacos": sacos}, (("Número de sacos", str(sacos)),)
    return {}, ()


# ---------- Resultado esperado ----------


@dataclass(frozen=True)
class Esperado:
    entrada: dict[str, Decimal]  # por corrida
    rendimiento: dict[str, Decimal]
    tomado: dict[str, Decimal]  # kilos de cada tanda final en el lote
    saldo: dict[str, Decimal]
    genealogia: tuple[tuple[str, str, str, Decimal], ...]  # (parcela, productor, corrida, kilos)


def proporciones(pesos: list[Decimal]) -> list[Decimal]:
    """Igual que services/corridas.proporciones (la prueba lo comprueba): 6 decimales, la última ajusta."""
    total = sum(pesos, Decimal(0))
    resultado = [(p / total).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) for p in pesos[:-1]]
    return [*resultado, Decimal("1.000000") - sum(resultado, Decimal(0))]


def ajustar(valores: list[Decimal], total: Decimal) -> list[Decimal]:
    """Igual que services/lotes._ajustar (la prueba lo comprueba): la fila más grande absorbe el redondeo."""
    valores = list(valores)
    mayor = max(range(len(valores)), key=lambda i: valores[i])
    valores[mayor] += total - sum(valores, Decimal(0))
    return valores


def esperado(c: Cooperativa) -> Esperado:
    """Las cifras que deben verse, con las mismas reglas de la aplicación (Partes 6 y 7). Este módulo no
    importa los servicios para que el script que genera el paquete no necesite una base de datos."""
    entrada, rendimiento, tomado, saldo, filas = {}, {}, {}, {}, []
    por_tomar = c.orden.cantidad
    for corrida in c.corridas:  # se consolidan en este orden: el FIFO toma primero la A
        pesos = [c.tanda(t).peso for t in corrida.tandas]
        entrada[corrida.clave] = sum(pesos, Decimal(0))
        rendimiento[corrida.clave] = (corrida.peso_final / entrada[corrida.clave]).quantize(Decimal("0.001"))
        kg = min(por_tomar, corrida.peso_final)
        por_tomar -= kg
        tomado[corrida.clave] = kg
        saldo[corrida.clave] = corrida.peso_final - kg
        if kg:
            for t, p in zip(corrida.tandas, proporciones(pesos), strict=True):
                tanda = c.tanda(t)
                kilos_fila = (kg * p).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                filas.append((tanda.parcela, tanda.productor, corrida.clave, kilos_fila))
    kilos = ajustar([f[3] for f in filas], c.orden.cantidad)
    genealogia = tuple((p, pr, co, k) for (p, pr, co, _), k in zip(filas, kilos, strict=True))
    return Esperado(entrada, rendimiento, tomado, saldo, genealogia)


# ---------- Archivos de geometría ----------


def geojson(p: Parcela) -> str:
    return json.dumps(
        {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"nombre": f"Parcela {p.nombre}"}, "geometry": p.geometria}
        ]},
        ensure_ascii=False, indent=1,
    )


def kml(p: Parcela) -> str:
    coordenadas = " ".join(f"{lon},{lat},0" for lon, lat in p.geometria["coordinates"][0])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
        f"<name>Parcela {p.nombre}</name>\n"
        f"<Placemark><name>Parcela {p.nombre}</name><Polygon><outerBoundaryIs><LinearRing>"
        f"<coordinates>{coordenadas}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>\n"
        "</Document></kml>\n"
    )


# ---------- Carga por la capa de servicios (la usa la prueba) ----------


def cargar(
    sesion,
    superadmin,
    *,
    auth,
    storage,
    fuentes: dict,
    ritmo,
    simulacion: Simulacion,
    pdf: Callable[[Documento], bytes],
) -> dict[str, dict[str, Any]]:
    """Carga las dos cooperativas como lo haría una persona con el guion. Devuelve los ids de cada una."""
    from app.demo import carga_simulacion

    return carga_simulacion.cargar(
        sesion,
        superadmin,
        auth=auth,
        storage=storage,
        fuentes=fuentes,
        ritmo=ritmo,
        simulacion=simulacion,
        pdf=pdf,
    )
