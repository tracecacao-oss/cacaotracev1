"""Declaración anual del productor: cuestionario, versión 1 (adenda 5, sección 4).

Son 18 preguntas. Cuatro se hacen a todos; las demás aparecen solo si una respuesta o el área las abren.
"Contrata" significa `quien_trabaja` distinto de `solo_familia`. Con menos de 5 ha se presume agricultura
familiar, como hace el orientador: esa presunción solo decide qué preguntas se muestran.

Un cambio de preguntas o de valores crea una versión nueva. Las declaraciones guardan la versión con que se
respondieron. No se guardan nombres ni datos de ningún menor ni de ningún trabajador.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

VERSION = 1
AREA_AGRICULTURA_FAMILIAR_HA = Decimal("5")
TIPOS_PRODUCTO = ("fertilizante", "herbicida", "insecticida", "fungicida", "otro")
ETIQUETAS_TIPO_PRODUCTO = {
    "fertilizante": "Fertilizante",
    "herbicida": "Herbicida",
    "insecticida": "Insecticida",
    "fungicida": "Fungicida",
    "otro": "Otro",
}
MAXIMO_PRODUCTOS = 20


def contrata(r: dict) -> bool:
    return r.get("quien_trabaja") not in (None, "solo_familia")


def cinco_ha_o_mas(contexto: dict) -> bool:
    return Decimal(str(contexto.get("area_total_ha") or 0)) >= AREA_AGRICULTURA_FAMILIAR_HA


# Lo que abre una pregunta. La interfaz aplica las mismas cinco reglas (frontend/js/declaracion.js).
CONDICIONES = {
    "contrata": lambda r, c: contrata(r),
    "permanentes": lambda r, c: r.get("quien_trabaja") == "permanentes",
    "cinco_ha": lambda r, c: cinco_ha_o_mas(c),
    "menores": lambda r, c: r.get("menores_trabajan") not in (None, "no"),
    "usa_agroquimicos": lambda r, c: r.get("usa_agroquimicos") == "si",
}


@dataclass(frozen=True)
class Pregunta:
    codigo: str
    texto: str  # de tú, para el productor
    texto_personal: str  # en tercera persona, para el personal
    ayuda: str
    tipo: str  # opcion, entero, numero o productos
    valores: tuple[tuple[str, str], ...] = ()  # (código, etiqueta)
    minimo: Decimal | None = None
    maximo: Decimal | None = None
    referencias: tuple[str, ...] = ()
    cuando: tuple[str, ...] = ()  # condiciones de CONDICIONES que deben cumplirse todas; vacía, siempre
    ayuda_personal: str = ""  # la ayuda en tercera persona, si la de tú no sirve para el personal

    def condicion(self, respuestas: dict, contexto: dict) -> bool:
        return all(CONDICIONES[c](respuestas, contexto) for c in self.cuando)

    def etiqueta(self, valor: Any) -> str:
        if self.tipo == "opcion":
            return dict(self.valores).get(valor, str(valor))
        if self.tipo == "productos":
            return "; ".join(
                f"{p['nombre']} ({ETIQUETAS_TIPO_PRODUCTO[p['tipo']].lower()})" for p in valor or []
            )
        if self.codigo == "jornal_soles":
            return f"S/ {Decimal(str(valor)):,.2f}"
        if self.tipo == "entero":
            return str(int(valor))
        return f"{float(valor):g}"


SI_NO = (("si", "Sí"), ("no", "No"))

PREGUNTAS: tuple[Pregunta, ...] = (
    Pregunta(
        "quien_trabaja",
        "¿Quién trabaja en tus parcelas?",
        "¿Quién trabaja en sus parcelas?",
        "Solo tú y tu familia; contratas personas por días, en cosecha o poda; o tienes trabajadores todo "
        "el año.",
        "opcion",
        (
            ("solo_familia", "Solo yo y mi familia"),
            ("eventuales", "Contrato personas por días, en cosecha o poda"),
            ("permanentes", "Tengo trabajadores todo el año"),
        ),
        ayuda_personal="Solo el productor y su familia; contrata personas por días, en cosecha o poda; o "
        "tiene trabajadores todo el año.",
        referencias=("4.1",),
    ),
    Pregunta(
        "trabajadores_numero",
        "¿Cuántas personas contratas en la temporada de más trabajo?",
        "¿Cuántas personas contrata en la temporada de más trabajo?",
        "Sin contar a tu familia.",
        "entero",
        minimo=Decimal(1),
        maximo=Decimal(500),
        ayuda_personal="Sin contar a su familia.",
        referencias=("4.1",),
        cuando=("contrata",),
    ),
    Pregunta(
        "acuerdo_por_escrito",
        "¿El acuerdo con ellas está por escrito?",
        "¿El acuerdo con ellas está por escrito?",
        "Un acuerdo de palabra también vale; aquí solo se anota cómo es.",
        "opcion",
        SI_NO,
        referencias=("4.1",),
        cuando=("contrata",),
    ),
    Pregunta(
        "jornal_soles",
        "¿Cuánto pagas por un día de trabajo?",
        "¿Cuánto paga por un día de trabajo?",
        "En soles, lo que recibe cada persona por un día.",
        "numero",
        minimo=Decimal("0.01"),
        maximo=Decimal(10000),
        referencias=("4.3",),
        cuando=("contrata",),
    ),
    Pregunta(
        "horas_por_dia",
        "¿Cuántas horas se trabaja en un día normal?",
        "¿Cuántas horas se trabaja en un día normal?",
        "Sin contar el tiempo para almorzar.",
        "numero",
        minimo=Decimal(1),
        maximo=Decimal(16),
        referencias=("4.2",),
        cuando=("contrata",),
    ),
    Pregunta(
        "seguro_salud",
        "¿Tienen seguro de salud, como EsSalud o el SIS?",
        "¿Tienen seguro de salud, como EsSalud o el SIS?",
        "Las personas que contratas.",
        "opcion",
        (("todos", "Todos"), ("algunos", "Algunos"), ("ninguno", "Ninguno")),
        ayuda_personal="Las personas que contrata.",
        referencias=("4.4",),
        cuando=("contrata",),
    ),
    Pregunta(
        "equipo_proteccion",
        "¿Les das equipo de protección, como botas, guantes y mascarilla?",
        "¿Les da equipo de protección, como botas, guantes y mascarilla?",
        "Sobre todo a quienes aplican productos o usan herramientas.",
        "opcion",
        SI_NO,
        referencias=("4.5",),
        cuando=("contrata",),
    ),
    Pregunta(
        "pueden_dejar_el_trabajo",
        "¿Cualquiera de ellos puede dejar el trabajo cuando quiera, sin deudas ni documentos retenidos?",
        "¿Cualquiera de ellos puede dejar el trabajo cuando quiera, sin deudas ni documentos retenidos?",
        "Nadie debe quedarse a trabajar por una deuda, un adelanto o porque se le guardó su DNI.",
        "opcion",
        SI_NO,
        referencias=("5.3", "5.4"),
        cuando=("contrata",),
    ),
    Pregunta(
        "mismo_pago",
        "¿Pagas lo mismo a hombres y mujeres por el mismo trabajo?",
        "¿Paga lo mismo a hombres y mujeres por el mismo trabajo?",
        "Por la misma labor y las mismas horas.",
        "opcion",
        SI_NO,
        referencias=("4.6",),
        cuando=("contrata", "cinco_ha"),
    ),
    Pregunta(
        "descanso_maternidad_paternidad",
        "¿Respetas el descanso por maternidad y por paternidad?",
        "¿Respeta el descanso por maternidad y por paternidad?",
        "El descanso de la madre antes y después del parto, y el del padre por el nacimiento.",
        "opcion",
        (("si", "Sí"), ("no", "No"), ("no_se_presento", "No se ha presentado el caso")),
        referencias=("4.7",),
        cuando=("permanentes", "cinco_ha"),
    ),
    Pregunta(
        "menores_trabajan",
        "¿Trabaja en tus parcelas alguna persona menor de 18 años?",
        "¿Trabaja en sus parcelas alguna persona menor de 18 años?",
        "Cuenta también a tus hijos y familiares que hacen labores del cultivo.",
        "opcion",
        (
            ("no", "No"),
            ("si_de_la_familia", "Sí, de la familia"),
            ("si_contratados", "Sí, contratados"),
        ),
        ayuda_personal="Cuenta también a sus hijos y familiares que hacen labores del cultivo.",
        referencias=("5.2",),
    ),
    Pregunta(
        "menor_edad_minima",
        "¿Qué edad tiene el más joven?",
        "¿Qué edad tiene el más joven?",
        "En años cumplidos.",
        "entero",
        minimo=Decimal(0),
        maximo=Decimal(17),
        referencias=("5.2",),
        cuando=("menores",),
    ),
    Pregunta(
        "menores_van_a_la_escuela",
        "¿Van a la escuela?",
        "¿Van a la escuela?",
        "Los menores que trabajan en las parcelas.",
        "opcion",
        (("si", "Sí"), ("algunos", "Algunos"), ("no", "No")),
        referencias=("5.2",),
        cuando=("menores",),
    ),
    Pregunta(
        "usa_agroquimicos",
        "¿Usas fertilizantes, herbicidas, insecticidas o fungicidas?",
        "¿Usa fertilizantes, herbicidas, insecticidas o fungicidas?",
        "Productos comprados para abonar o para controlar plagas, malezas u hongos.",
        "opcion",
        (("no", "No"), ("si", "Sí")),
        referencias=("2.3",),
    ),
    Pregunta(
        "productos",
        "¿Cuáles? Escribe el nombre de cada producto",
        "¿Cuáles? Escriba el nombre de cada producto",
        "El nombre comercial que figura en la etiqueta, y qué tipo de producto es.",
        "productos",
        referencias=("2.3",),
        cuando=("usa_agroquimicos",),
    ),
    Pregunta(
        "quien_aplica",
        "¿Quién los aplica?",
        "¿Quién los aplica?",
        "Quién prepara y echa los productos en la parcela.",
        "opcion",
        (
            ("yo_o_mi_familia", "Yo o mi familia"),
            ("trabajadores", "Los trabajadores"),
            ("servicio_contratado", "Un servicio contratado"),
        ),
        referencias=("2.7",),
        cuando=("usa_agroquimicos",),
    ),
    Pregunta(
        "destino_envases",
        "¿Qué haces con los envases vacíos?",
        "¿Qué hace con los envases vacíos?",
        "Los frascos, bolsas o galoneras de los productos, cuando se acaban.",
        "opcion",
        (
            ("devuelve_o_centro_de_acopio", "Los devuelvo o los llevo a un centro de acopio"),
            ("triple_lavado_y_guarda", "Les hago triple lavado y los guardo"),
            ("quema", "Los quemo"),
            ("entierra", "Los entierro"),
            ("bota_o_reutiliza", "Los boto o los vuelvo a usar"),
        ),
        referencias=("2.7",),
        cuando=("usa_agroquimicos",),
    ),
    Pregunta(
        "ventas_superan_75_uit",
        "¿Tus ventas de todo el año pasan de 75 UIT?",
        "¿Sus ventas de todo el año pasan de 75 UIT?",
        "Todo lo que vendes en el año, no solo el cacao.",
        "opcion",
        (("no", "No"), ("si", "Sí"), ("no_sabe", "No sé")),
        ayuda_personal="Todo lo que vende en el año, no solo el cacao.",
        referencias=("7.1",),
    ),
)
POR_CODIGO = {p.codigo: p for p in PREGUNTAS}
CODIGOS = tuple(POR_CODIGO)


def mostradas(respuestas: dict, contexto: dict) -> list[str]:
    """Las preguntas que corresponden al productor según sus respuestas y su área, en orden."""
    return [p.codigo for p in PREGUNTAS if p.condicion(respuestas, contexto)]


def normalizar_nombre(nombre: str) -> str:
    """Para comparar nombres de productos: sin tildes, sin mayúsculas y sin espacios de más."""
    import unicodedata

    sin_marcas = unicodedata.normalize("NFD", nombre.strip().lower())
    return " ".join("".join(c for c in sin_marcas if not unicodedata.combining(c)).split())


class ErrorDeclaracion(ValueError):
    pass


def _numero(valor: Any) -> Decimal:
    if isinstance(valor, bool):
        raise ErrorDeclaracion("no es un número")
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError) as exc:
        raise ErrorDeclaracion("no es un número") from exc


def _valor(pregunta: Pregunta, valor: Any) -> Any:
    if pregunta.tipo == "opcion":
        if valor not in dict(pregunta.valores):
            raise ErrorDeclaracion("no es una respuesta válida")
        return valor
    if pregunta.tipo in ("entero", "numero"):
        numero = _numero(valor)
        if pregunta.tipo == "entero" and numero != numero.to_integral_value():
            raise ErrorDeclaracion("debe ser un número entero")
        if (pregunta.minimo is not None and numero < pregunta.minimo) or (
            pregunta.maximo is not None and numero > pregunta.maximo
        ):
            raise ErrorDeclaracion(f"debe estar entre {pregunta.minimo} y {pregunta.maximo}")
        return int(numero) if pregunta.tipo == "entero" else float(numero.quantize(Decimal("0.01")))
    # productos
    if not isinstance(valor, list) or not 1 <= len(valor) <= MAXIMO_PRODUCTOS:
        raise ErrorDeclaracion(f"debe traer de 1 a {MAXIMO_PRODUCTOS} productos")
    productos = []
    for p in valor:
        if not isinstance(p, dict):
            raise ErrorDeclaracion("cada producto lleva nombre y tipo")
        nombre = " ".join(str(p.get("nombre") or "").split())
        if not 2 <= len(nombre) <= 80:
            raise ErrorDeclaracion("el nombre de cada producto lleva de 2 a 80 caracteres")
        if p.get("tipo") not in TIPOS_PRODUCTO:
            raise ErrorDeclaracion(
                "el tipo de cada producto es fertilizante, herbicida, insecticida, fungicida u otro"
            )
        productos.append({"nombre": nombre, "tipo": p["tipo"]})
    return productos


def validar(respuestas: dict, contexto: dict) -> dict:
    """Exactamente las preguntas que corresponden al productor, con valores válidos (sección 4, regla 2).
    Lanza ErrorDeclaracion con un mensaje para mostrar."""
    if not isinstance(respuestas, dict):
        raise ErrorDeclaracion("Las respuestas no tienen la forma esperada.")
    desconocidas = [c for c in respuestas if c not in POR_CODIGO]
    if desconocidas:
        raise ErrorDeclaracion(f"Estas preguntas no existen en el cuestionario: {', '.join(desconocidas)}.")
    limpias: dict = {}
    # Las condiciones dependen de respuestas anteriores: se validan en orden.
    for pregunta in PREGUNTAS:
        if not pregunta.condicion(limpias, contexto):
            continue
        if pregunta.codigo not in respuestas or respuestas[pregunta.codigo] in (None, ""):
            raise ErrorDeclaracion(f"Falta responder: {pregunta.texto_personal}")
        try:
            limpias[pregunta.codigo] = _valor(pregunta, respuestas[pregunta.codigo])
        except ErrorDeclaracion as exc:
            raise ErrorDeclaracion(f"{pregunta.texto_personal} La respuesta {exc}.") from exc
    sobran = [c for c in respuestas if c not in limpias and respuestas[c] not in (None, "")]
    if sobran:
        nombres = "; ".join(POR_CODIGO[c].texto_personal for c in sobran)
        raise ErrorDeclaracion(f"Estas preguntas no corresponden a este productor: {nombres}")
    return limpias
