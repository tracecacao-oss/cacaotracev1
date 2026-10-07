"""Genera el paquete de simulación para cargar a mano: guion en HTML, PDF de cada documento, geometría de cada
parcela en GeoJSON y KML, y un LEEME, comprimidos en un ZIP (pedido del equipo del 2026-10-06).

Los datos salen de app/demo/simulacion.py, los mismos que carga la prueba tests/test_simulacion.py. No se
conecta a ninguna base ni a Supabase: solo escribe archivos en una carpeta ignorada por git.

    python scripts/generar_simulacion.py                 # deja simulacion/cacaotrace-simulacion.zip
    python scripts/generar_simulacion.py --hoy 2026-10-06
"""

import argparse
import html
import shutil
import sys
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.demo import simulacion as sim  # noqa: E402
from app.demo.simulacion_pdf import MARCA, documento  # noqa: E402
from app.fechas import LIMA, hoy_lima  # noqa: E402

REPOSITORIO = Path(__file__).resolve().parents[2]
SALIDA = REPOSITORIO / "simulacion"
NOMBRE = "cacaotrace-simulacion"


# ---------- Archivos ----------


def pdf(d: sim.Documento) -> bytes:
    subtitulo = f"{d.nombre} · N.° {d.numero} · Emitido por: {d.entidad} · {d.emision:%d/%m/%Y}"
    if d.vencimiento:
        subtitulo += f" · Vence: {d.vencimiento:%d/%m/%Y}"
    secciones = [(nombre, list(campos)) for nombre, campos in d.secciones]
    return documento(d.titulo, secciones, subtitulo=subtitulo, texto=d.texto)


def documentos_de(c: sim.Cooperativa) -> list[sim.Documento]:
    return [
        *c.documentos,
        *(p.copia_dni for p in c.productores),
        *(d for p in c.parcelas for d in p.documentos),
        *(t.liquidacion for t in c.tandas),
        *c.orden.embarque,
    ]


def escribir(simulacion: sim.Simulacion, carpeta: Path) -> list[Path]:
    escritos = []
    for c in simulacion.cooperativas:
        for d in documentos_de(c):
            ruta = carpeta / d.archivo
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(pdf(d))
            escritos.append(ruta)
        for p in c.parcelas:
            base = carpeta / p.carpeta / f"geometria-{sim._carpeta(p.nombre)}"
            base.parent.mkdir(parents=True, exist_ok=True)
            for extension, contenido in (("geojson", sim.geojson(p)), ("kml", sim.kml(p))):
                ruta = base.with_suffix(f".{extension}")
                ruta.write_text(contenido, encoding="utf-8")
                escritos.append(ruta)
    (carpeta / "guion-de-carga.html").write_text(guion(simulacion), encoding="utf-8")
    (carpeta / "LEEME.txt").write_text(leeme(simulacion), encoding="utf-8")
    return [*escritos, carpeta / "guion-de-carga.html", carpeta / "LEEME.txt"]


def geometria_de(p: sim.Parcela) -> str:
    return f"{p.carpeta}/geometria-{sim._carpeta(p.nombre)}.geojson"


# ---------- Guion ----------

COPIAR, TECLEAR, ELEGIR, MARCAR, ARCHIVO, CONFIRMAR = (
    "copiar", "teclear", "elegir", "marcar", "archivo", "confirmar"
)
AYUDA_MODO = {
    COPIAR: "Copia y pega",
    TECLEAR: "Escríbelo",
    ELEGIR: "Elígelo en la lista",
    MARCAR: "Márcalo",
    ARCHIVO: "Sube este archivo",
    CONFIRMAR: "Ya viene lleno: compruébalo",
}


def _dia(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def _momento(m: datetime) -> str:
    return f"{m.astimezone(LIMA):%d/%m/%Y %H:%M}"


def _kg(valor: Decimal) -> str:
    return f"{valor:.2f}"


def _e(texto) -> str:
    return html.escape(str(texto))


class Guion:
    def __init__(self):
        self.partes: list[str] = []
        self.indice: list[tuple[str, str]] = []
        self.numero = 0

    def seccion(self, ident: str, titulo: str, intro: str | None = None) -> None:
        self.indice.append((ident, titulo))
        self.partes.append(f'<h2 id="{ident}">{_e(titulo)}</h2>')
        if intro:
            self.partes.append(f"<p class='intro'>{_e(intro)}</p>")

    def paso(
        self,
        titulo: str,
        cuenta: str,
        ruta: str,
        campos=(),
        al_final: str | None = None,
        nota: str | None = None,
    ):
        self.numero += 1
        filas = "".join(self._fila(*campo) for campo in campos)
        tabla = (
            "<table><thead><tr><th>Campo en la pantalla</th><th>Valor</th><th>Cómo</th></tr></thead>"
            f"<tbody>{filas}</tbody></table>"
            if campos
            else ""
        )
        partes = [
            f"<section class='paso'><header><span class='n'>Paso {self.numero}</span><h3>{_e(titulo)}</h3>"
            f"<span class='cuenta cuenta-{_e(cuenta.split()[0].lower())}'>{_e(cuenta)}</span></header>",
            f"<p class='ruta'>{_e(ruta)}</p>",
            tabla,
        ]
        if al_final:
            partes.append(f"<p class='final'>Al terminar: <b>{_e(al_final)}</b></p>")
        if nota:
            partes.append(f"<p class='nota'>{_e(nota)}</p>")
        partes.append("</section>")
        self.partes.append("".join(partes))

    def tabla(self, titulo: str, columnas: list[str], filas: list[list[tuple[str, str]]]) -> None:
        cabecera = "".join(f"<th>{_e(c)}</th>" for c in columnas)
        cuerpo = "".join("<tr>" + "".join(self._celda(v, m) for v, m in fila) + "</tr>" for fila in filas)
        self.partes.append(
            f"<div class='tabla-ancha'><p class='titulo-tabla'>{_e(titulo)}</p>"
            f"<table><thead><tr>{cabecera}</tr></thead><tbody>{cuerpo}</tbody></table></div>"
        )

    def texto(self, contenido: str) -> None:
        self.partes.append(contenido)

    def _celda(self, valor: str, modo: str) -> str:
        if modo == COPIAR and valor not in ("", "—"):
            return f"<td>{self._copiable(valor)}</td>"
        return f"<td class='m-{modo or 'texto'}'>{_e(valor)}</td>"

    def _copiable(self, valor: str) -> str:
        return (
            f"<span class='valor'>{_e(valor)}</span>"
            f"<button type='button' class='copiar' data-valor='{_e(valor)}'>Copiar</button>"
        )

    def _fila(self, etiqueta: str, valor: str, modo: str) -> str:
        celda = self._copiable(valor) if modo == COPIAR else f"<span class='valor {modo}'>{_e(valor)}</span>"
        return (
            f"<tr><td class='etiqueta'>{_e(etiqueta)}</td><td>{celda}</td>"
            f"<td class='modo'>{AYUDA_MODO[modo]}</td></tr>"
        )


def _doc_legal(g: Guion, d: sim.Documento, cuenta: str, ruta: str, numero_etiqueta: str) -> None:
    campos = [
        (numero_etiqueta, d.numero, COPIAR),
        ("Entidad emisora", d.entidad, COPIAR),
        ("Fecha de emisión", _dia(d.emision), TECLEAR),
        (
            "Fecha de vencimiento (si tiene)",
            _dia(d.vencimiento) if d.vencimiento else "Déjalo vacío",
            TECLEAR,
        ),
        ("Archivo (foto o PDF, hasta 10 MB)", d.archivo, ARCHIVO),
    ]
    g.paso(f"Cargar: {d.nombre}", cuenta, ruta, campos, "Cargar documento")


def guion(simulacion: sim.Simulacion) -> str:
    g = Guion()
    g.seccion("antes", "Antes de empezar")
    g.texto(_antes_de_empezar(simulacion))
    for k, c in enumerate(simulacion.cooperativas, start=1):
        _cooperativa(g, k, c)
    return _pagina(g)


def _antes_de_empezar(simulacion: sim.Simulacion) -> str:
    puntos = [
        "Este guion carga dos cooperativas de demostración con datos ficticios, de la cooperativa al DEX. "
        "Sigue los pasos en orden: cada uno usa lo que dejó el anterior.",
        "Cada paso dice con qué cuenta se hace. Conviene tener dos ventanas: una normal con el "
        "administrador y una privada (incógnito) con el operador.",
        "Botón «Copiar»: copia el valor exacto. Las fechas y las horas se escriben a mano: los campos de "
        "fecha del navegador no aceptan pegar. Las horas van en formato de 24 horas; si tu navegador pide "
        "a. m. o p. m., usa la equivalente.",
        "Los archivos están en las carpetas del ZIP; la ruta de cada uno va en la columna Valor.",
        f"Fechas del paquete: entre agosto y el {_dia(simulacion.hoy)}, ninguna futura. Solo los "
        "vencimientos de los documentos son posteriores al 31/03/2027.",
        "Si al crear una cuenta Supabase rechaza el correo de ejemplo (dominio .test), usa un correo "
        "del equipo.",
        "La clasificación de riesgo del Perú (Plataforma › Configuración) no está en el guion: es un "
        "dato regulatorio que registra el equipo con su referencia oficial. Si falta, el DEX dice "
        "«clasificación del país no registrada».",
        "Los análisis de cobertura (Whisp, GFW y MapBiomas) son reales. Las parcelas están en zonas "
        "agrícolas de San Martín que MapBiomas Perú clasifica sin bosque entre 2015 y 2024, pero el "
        "resultado de Whisp y GFW no se puede garantizar. Si una parcela sale con la alerta «Análisis "
        "requiere revisión», sigue el recuadro «Si un análisis sale con alerta» de su cooperativa.",
    ]
    return "<ul class='antes'>" + "".join(f"<li>{_e(p)}</li>" for p in puntos) + "</ul>"


def _cooperativa(g: Guion, k: int, c: sim.Cooperativa) -> None:
    dep, prov, dist = c.ubicacion
    admin = f"Administrador · {c.admin.correo}"
    operador = f"Operador · {c.operador.correo}"
    g.seccion(
        f"coop{k}",
        f"Cooperativa {k}: {c.razon_social}",
        "Todas las pantallas de esta sección son de esta cooperativa.",
    )

    # --- Superadministrador ---
    g.paso(
        "Crear la cooperativa (paso 1 del asistente)",
        "Superadministrador",
        "Plataforma › Cooperativas › Nueva cooperativa",
        [
            ("Razón social", c.razon_social, COPIAR),
            ("Nombre comercial (opcional)", c.nombre_comercial, COPIAR),
            ("RUC", c.ruc, COPIAR),
            ("Código de la cooperativa", c.codigo, COPIAR),
            ("Tipo de organización", "Cooperativa agraria", ELEGIR),
            ("Departamento", dep, ELEGIR), ("Provincia", prov, ELEGIR), ("Distrito", dist, ELEGIR),
            (
                "Cooperativa de demostración (datos ficticios). No se puede cambiar después.",
                "Marcado",
                MARCAR,
            ),
        ],
        "Siguiente",
    )
    g.paso(
        "Crear la cooperativa (paso 2: primer administrador)",
        "Superadministrador",
        "Mismo asistente, paso 2. Administrador",
        [
            ("Nombres", c.admin.nombres, COPIAR), ("Apellidos", c.admin.apellidos, COPIAR),
            ("Correo", c.admin.correo, COPIAR),
        ],
        "Crear cooperativa",
        "Copia la contraseña temporal que aparece. El administrador la cambia en su primer ingreso.",
    )

    # --- Administrador: base ---
    g.paso(
        "Datos de la cooperativa",
        admin,
        "Cooperativa › Datos y expediente legal › Editar",
        [
            ("Dirección postal", c.direccion, COPIAR), ("Correo de contacto", c.correo, COPIAR),
            ("Representante legal", c.representante, COPIAR),
            ("DNI del representante", c.representante_dni, COPIAR),
        ],
        "Guardar",
    )
    for d in c.documentos:
        _doc_legal(
            g,
            d,
            admin,
            f"Cooperativa › Datos y expediente legal › fila «{d.nombre}» › Cargar documento",
            "Número (partida, registro o constancia)",
        )
    g.paso(
        "Cuenta del operador",
        admin,
        "Cooperativa › Usuarios › Agregar usuario",
        [
            ("Nombres", c.operador.nombres, COPIAR), ("Apellidos", c.operador.apellidos, COPIAR),
            ("Correo", c.operador.correo, COPIAR), ("Rol", "Operador · registra y edita datos", ELEGIR),
        ],
        "Crear cuenta",
        "Copia la contraseña temporal del operador.",
    )
    g.paso(
        "Configuración",
        admin,
        "Cooperativa › Configuración",
        [
            ("Tope de kilos secos por hectárea al año (kg/ha/año)", str(sim.TOPE), COPIAR),
            ("Los demás campos", "Deja los valores que trae", CONFIRMAR),
        ],
        "Guardar configuración",
    )
    for _, nombre, tipo in c.lugares:
        g.paso(
            f"Lugar: {nombre}",
            admin,
            "Cooperativa › Lugares › Nuevo lugar",
            [
                ("Nombre", nombre, COPIAR),
                (
                    "Tipo",
                    {"cancha_acopio": "Cancha de acopio", "planta": "Planta", "almacen": "Almacén"}[tipo],
                    ELEGIR,
                ),
                ("Departamento", dep, ELEGIR), ("Provincia", prov, ELEGIR), ("Distrito", dist, ELEGIR),
            ],
            "Crear lugar",
        )
    g.paso(
        "Plantilla de proceso y calidad",
        admin,
        "Cooperativa › Plantilla de proceso",
        [
            ("Botón de la sección Etapas", "Llenar con la plantilla sugerida", CONFIRMAR),
            ("Botón al pie de la tabla", "Guardar plantilla", CONFIRMAR),
            ("Calidades › Nueva calidad › Nombre", sim.CALIDAD, COPIAR),
        ],
        "Crear calidad",
        "La plantilla sugerida pone en cada etapa el lugar (cancha, planta o almacén), el método y la "
        "duración. Las etapas que se confirman sin cambiar lugar, método ni distancia salen en el DPP como "
        "«no verificado».",
    )

    # --- Operador: productores y parcelas ---
    for p in c.productores:
        g.paso(
            f"Productor {p.nombres} {p.apellidos} (paso 1 del asistente)",
            operador,
            "Productores › Padrón › Nuevo productor",
            [
                ("DNI", p.dni, COPIAR),
                ("Nombres, como figuran en el DNI", p.nombres, COPIAR),
                ("Apellidos, como figuran en el DNI", p.apellidos, COPIAR),
                ("Dirección postal", p.direccion, COPIAR),
                ("Teléfono, correo y RUC (opcionales)", "Déjalos vacíos", CONFIRMAR),
            ],
            "Siguiente",
        )
        g.paso(
            f"Productor {p.nombres} {p.apellidos} (paso 2: registros)",
            operador,
            "Mismo asistente, paso 2",
            [
                ("La cooperativa cuenta con el consentimiento firmado del productor", "Marcado", MARCAR),
                ("Los demás campos", "Déjalos vacíos", CONFIRMAR),
            ],
            "Registrar productor",
        )
        g.paso(
            f"Copia del DNI de {p.nombres} {p.apellidos}",
            operador,
            f"Productores › {p.nombres} {p.apellidos} › pestaña Documentos",
            [
                ("Tipo de documento", "Copia del DNI", ELEGIR),
                ("Archivo (foto o PDF, hasta 10 MB)", p.copia_dni.archivo, ARCHIVO),
            ],
            "Cargar documento",
        )
    for p in c.parcelas:
        pr = c.productor(p.productor)
        g.paso(
            f"Parcela {p.nombre} ({p.codigo})",
            operador,
            f"Productores › {pr.nombres} {pr.apellidos} › pestaña Parcelas › Nueva parcela",
            [
                ("1. Nombre de la parcela", p.nombre, COPIAR),
                ("1. Caserío o centro poblado (opcional)", p.centro_poblado, COPIAR),
                ("2. Ubicación en el mapa", "Botón «Subir archivo»", CONFIRMAR),
                ("2. Archivo de la parcela (hasta 2 MB, en WGS 84)", geometria_de(p), ARCHIVO),
                ("3. Departamento / Provincia / Distrito", " / ".join(p.ubicacion), CONFIRMAR),
                ("3. Área total", f"{p.area_ha} ha aproximadamente", CONFIRMAR),
                ("3. Área con cacao (ha)", "Deja el valor que trae (toda la parcela)", CONFIRMAR),
                ("3. Registro en MIDAGRI (opcional)", "No lo abras", CONFIRMAR),
            ],
            "Guardar parcela",
            "También puedes subir el KML de la misma carpeta. "
            f"CacaoTrace debe ponerle el código {p.codigo}.",
        )
        for d in p.documentos:
            _doc_legal(
                g,
                d,
                operador,
                f"Parcela {p.codigo} › pestaña Expediente › fila «{d.nombre}» › Cargar documento",
                "Número (partida, constancia o contrato)",
            )

    # --- Administrador: no aplica y habilitación ---
    for p in c.parcelas:
        for _tipo, nombre, motivo in p.exenciones:
            g.paso(
                f"{p.codigo}: {nombre} no aplica",
                admin,
                f"Parcela {p.codigo} › pestaña Expediente › fila «{nombre}» › Declarar que no aplica",
                [
                    ("Por qué no aplica (mínimo 30 caracteres)", motivo, COPIAR),
                ],
                "Declarar que no aplica",
            )
    g.paso(
        "Habilitar las 9 parcelas",
        admin,
        "Cada parcela › pestaña Habilitación › Habilitar",
        [
            (
                "Antes",
                "Espera a que la pestaña Cobertura forestal muestre los análisis terminados",
                CONFIRMAR,
            ),
            ("Nota (opcional)", "Déjala vacía", CONFIRMAR),
        ],
        "Habilitar parcela",
        "Hazlo con " + ", ".join(p.codigo for p in c.parcelas) + ".",
    )
    g.texto(_si_hay_alerta(c))

    # --- Operador: tandas ---
    for t in c.tandas:
        p = c.parcela(t.parcela)
        pr = c.productor(t.productor)
        g.paso(
            f"Tanda de {p.nombre} ({p.codigo})",
            operador,
            "Lotes y proceso › Recepción › Nueva tanda",
            [
                ("1. Buscar productor (DNI o nombre)", pr.dni, COPIAR),
                ("1. ¿De qué parcela es este cacao?", f"{p.codigo} · {p.nombre}", ELEGIR),
                ("2. Fecha y hora del pesaje", _momento(t.recibida_en), TECLEAR),
                ("2. Estado del producto", "En baba", ELEGIR),
                ("2. Peso neto en balanza (kg)", _kg(t.peso), COPIAR),
                ("2. Sacos (opcional)", str(t.sacos), COPIAR),
                ("2. Variedad", t.variedad_nombre, ELEGIR),
                ("2. Cosecha desde", _dia(t.cosecha_desde), TECLEAR),
                ("2. Cosecha hasta", _dia(t.cosecha_hasta), TECLEAR),
                ("3. Tipo de documento", "Liquidación de compra", ELEGIR),
                ("3. Serie y número", t.liquidacion.numero, COPIAR),
                ("3. Fecha de emisión", _dia(t.liquidacion.emision), TECLEAR),
                ("3. RUC del emisor", f"{c.ruc} (se llena solo)", CONFIRMAR),
                ("3. Peso declarado en el documento (kg, opcional)", _kg(t.peso), COPIAR),
                ("3. Foto o PDF del documento de entrega (hasta 10 MB)", t.liquidacion.archivo, ARCHIVO),
                ("4. Revisión", "Botón «Guardar sin validar»", CONFIRMAR),
            ],
            "Guardar sin validar",
            "La valida el administrador en el paso siguiente: así el DEX no muestra «registro "
            "y validación por la misma persona».",
        )
    g.paso(
        "Validar las 9 tandas",
        admin,
        "Lotes y proceso › Recepción › cada tanda › Validar y emitir DOP",
        [
            ("Nota de validación (opcional)", "Déjala vacía", CONFIRMAR),
        ],
        "Validar y emitir DOP",
        "Si una tanda muestra alertas, revisa el recuadro «Si un análisis sale con alerta».",
    )

    # --- Operador: corridas ---
    for corrida in c.corridas:
        pesos = ", ".join(
            f"{c.parcela(c.tanda(t).parcela).nombre} ({_kg(c.tanda(t).peso)} kg)" for t in corrida.tandas
        )
        g.paso(
            f"{corrida.nombre}: crear e iniciar",
            operador,
            "Lotes y proceso › Corridas › Nueva corrida",
            [
                ("Ruta", "Completa", ELEGIR),
                ("Tipo de manejo", "Segregada" if corrida.manejo == "segregado" else "Mezclada", ELEGIR),
                ("Tandas disponibles (marca estas)", pesos, MARCAR),
            ],
            "Iniciar corrida",
        )
        lugares = {clave: nombre for clave, nombre, _ in c.lugares}
        filas = []
        for e in corrida.etapas:
            if e.no_ocurrio:
                filas.append([
                    (str(e.numero), ""), (e.nombre, ""), ("Botón «No ocurrió»", MARCAR), ("—", ""),
                    ("—", ""), ("—", ""), ("—", ""), ("—", ""),
                ])
                continue
            dato = "; ".join(f"{et}: {v}" for et, v in e.etiquetas_datos) or "—"
            filas.append([
                (str(e.numero), ""), (e.nombre, ""), (lugares[e.lugar], CONFIRMAR),
                (_momento(e.inicio), TECLEAR), (_momento(e.fin), TECLEAR), (e.metodo, CONFIRMAR),
                (str(e.distancia), COPIAR) if e.distancia is not None else ("—", ""),
                (dato, COPIAR) if e.etiquetas_datos else ("—", ""),
            ])
        g.paso(
            f"{corrida.nombre}: registrar las etapas",
            operador,
            "Corrida › pestaña Etapas › Registrar (en cada etapa, en este orden)",
            [
                ("Lugar y Método", "Vienen de la plantilla: compruébalos", CONFIRMAR),
                ("Responsable", f"{c.operador.nombres} {c.operador.apellidos} (viene lleno)", CONFIRMAR),
            ],
            "Confirmar etapa (en cada una)",
            "Las etapas 1, 3 y 4 las llena el sistema. En la etapa 17 elige la calidad «Grado 1». "
            "Las fechas de volteo de la etapa 9 se pegan, una por línea.",
        )
        g.tabla(
            f"{corrida.nombre}: valores de cada etapa",
            ["N.º", "Etapa", "Lugar", "Inicio", "Fin", "Método", "Distancia (m, opcional)", "Dato propio"],
            filas,
        )
        g.paso(
            f"{corrida.nombre}: consolidar",
            operador,
            "Corrida › pestaña Consolidación",
            [
                ("Peso final (kg)", _kg(corrida.peso_final), CONFIRMAR),
                ("Humedad final (%)", str(sim.HUMEDAD), CONFIRMAR),
                ("Almacén", lugares["almacen"], CONFIRMAR),
            ],
            "Consolidar y emitir DPP",
            "Consolida la corrida A antes que la B: la sugerencia FIFO del lote toma primero la tanda final "
            "más antigua.",
        )

    # --- Operador: orden, lote y embarque ---
    o = c.orden
    g.paso(
        "Orden de compra (paso 1: importador nuevo)",
        operador,
        "Exportación › Órdenes › Nueva orden",
        [
            ("Opción", "Registrar un importador nuevo", ELEGIR),
            ("Razón social", o.importador.razon_social, COPIAR),
            ("Dirección postal", o.importador.direccion, COPIAR),
            ("País", o.importador.pais, COPIAR), ("Correo de contacto", o.importador.correo, COPIAR),
            ("Número EORI (opcional)", o.importador.eori, COPIAR),
        ],
        "Siguiente",
    )
    g.paso(
        "Orden de compra (paso 2)",
        operador,
        "Mismo asistente, paso 2",
        [
            ("Cantidad (kg de masa neta)", _kg(o.cantidad), COPIAR), ("Tolerancia (%)", "0", CONFIRMAR),
            ("Calidad", sim.CALIDAD, ELEGIR), ("País de destino", o.pais_destino, CONFIRMAR),
            ("Puerto o ciudad de destino", o.lugar_destino, COPIAR),
            ("Fecha de entrega", _dia(o.fecha_entrega), TECLEAR),
            ("Referencia del importador (opcional)", o.referencia, COPIAR),
        ],
        "Crear orden",
    )
    g.paso(
        "Armar y confirmar el lote",
        operador,
        "Orden › Armar lote",
        [
            ("Kilos a tomar", "Deja la sugerencia FIFO", CONFIRMAR),
        ],
        "Confirmar lote",
    )
    for d in o.embarque:
        g.paso(
            f"Embarque: {d.nombre}",
            operador,
            f"Lote › pestaña Embarque › fila «{d.nombre}» › Cargar documento",
            [
                ("Número", d.numero, COPIAR), ("Entidad emisora", d.entidad, COPIAR),
                ("Fecha de emisión", _dia(d.emision), TECLEAR),
                ("Archivo (foto o PDF, hasta 10 MB)", d.archivo, ARCHIVO),
            ],
            "Cargar documento",
        )
    g.paso(
        "Recomprobar el lote",
        operador,
        "Lote › pestaña Recomprobación",
        [],
        "Recomprobar",
        "El lote debe quedar «listo», con las nueve comprobaciones sin observaciones.",
    )
    g.paso(
        "Emitir el DEX",
        admin,
        "Lote › pestaña DEX › Emitir DEX",
        [
            ("Entiendo que el DEX no declara el nivel de riesgo ni reemplaza la DDS", "Marcado", MARCAR),
        ],
        "Emitir DEX",
    )
    g.texto(_resultado(c))


def _si_hay_alerta(c: sim.Cooperativa) -> str:
    pasos = [
        "En la parcela, pestaña Imágenes: espera a que se generen las imágenes de Sentinel-2 y pulsa "
        "«Registrar revisión».",
        "«Qué se ve en la parcela en la imagen anterior al corte»: Cultivo o uso agrícola "
        "(si eso es lo que ves).",
        "«Si dentro del lindero se ve un cambio de cobertura después del corte»: Sin cambio visible "
        "(si eso es lo que ves).",
        f"«Qué observaste (mínimo 50 caracteres)»: {sim.REVISION_IMAGENES}",
        f"Pestaña Habilitación › Habilitar › «Nota (obligatoria…)»: {sim.NOTA_HABILITACION_ALERTA}",
        f"Si después la tanda de esa parcela pide nota al validar: {sim.NOTA_VALIDACION_ALERTA}",
        "Si las imágenes sí muestran bosque o un cambio, no la habilites: avísale al equipo, porque la "
        "parcela tendría que reemplazarse por otra.",
    ]
    return (
        "<aside class='alerta'><h3>Si un análisis sale con alerta</h3><ol>"
        + "".join(f"<li>{_e(p)}</li>" for p in pasos)
        + "</ol></aside>"
    )


def _resultado(c: sim.Cooperativa) -> str:
    esp = sim.esperado(c)
    filas_corrida = "".join(
        f"<tr><td>{_e(co.nombre)}</td><td>{_kg(esp.entrada[co.clave])}</td><td>{_kg(co.peso_final)}</td>"
        f"<td>{esp.rendimiento[co.clave]}</td><td>{_kg(esp.tomado[co.clave])}</td>"
        f"<td>{_kg(esp.saldo[co.clave])}</td></tr>"
        for co in c.corridas
    )
    nombres = {co.clave: co.nombre for co in c.corridas}
    filas_gen = "".join(
        f"<tr><td>{_e(c.parcela(parcela).codigo)} · {_e(c.parcela(parcela).nombre)}</td>"
        f"<td>{_e(c.productor(productor).nombres)} {_e(c.productor(productor).apellidos)}</td>"
        f"<td>{_e(nombres[corrida])}</td><td>{kg:.4f}</td></tr>"
        for parcela, productor, corrida, kg in esp.genealogia
    )
    total = sum((f[3] for f in esp.genealogia), Decimal(0))
    return (
        f"<section class='resultado'><h3>Resultado esperado: {_e(c.razon_social)}</h3>"
        "<ul><li>9 parcelas habilitadas ("
        + ", ".join(p.codigo for p in c.parcelas)
        + "), 9 tandas validadas con su DOP.</li>"
        "<li>Lote cerrado con su DEX vigente.</li>"
        "<li>En el informe de hallazgos se verán, sin bloquear nada: las exenciones declaradas (CUSAF y "
        "autorización forestal de cada parcela), documentos sin cotejar, coordenadas no recorridas en "
        "campo, etapas confirmadas con la plantilla y el vínculo físico no comprobado.</li></ul>"
        "<p class='titulo-tabla'>Stock (Lotes y proceso › Stock) después de confirmar el lote</p>"
        "<table><thead><tr><th>Corrida</th><th>Entrada en baba (kg)</th><th>Tanda final (kg)</th>"
        "<th>Rendimiento</th><th>Tomado por el lote (kg)</th><th>Saldo (kg)</th></tr></thead>"
        f"<tbody>{filas_corrida}</tbody></table>"
        f"<p class='titulo-tabla'>Genealogía del lote ({_kg(c.orden.cantidad)} kg)</p>"
        "<table><thead><tr><th>Parcela</th><th>Productor</th><th>Desde</th>"
        "<th>Kilos en el lote</th></tr></thead>"
        f"<tbody>{filas_gen}<tr class='total'><td colspan='3'>Total</td>"
        f"<td>{total:.4f}</td></tr></tbody></table>"
        "</section>"
    )


ESTILO = """
:root{--fondo:#f6f7f9;--panel:#fff;--tinta:#1f2937;--suave:#6b7280;--linea:#e5e7eb;--verde:#047857;
--verde-claro:#ecfdf5;--ambar:#92400e;--ambar-claro:#fffbeb;--azul:#1d4ed8;--azul-claro:#eff6ff;
--rojo:#b42318}
@media (prefers-color-scheme:dark){:root{--fondo:#0f1115;--panel:#171a21;--tinta:#e5e7eb;--suave:#9ca3af;
--linea:#2a2f3a;--verde:#34d399;--verde-claro:#0b2a20;--ambar:#fbbf24;--ambar-claro:#2a2110;--azul:#93c5fd;
--azul-claro:#0f1d33;--rojo:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--tinta);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:1.6rem;margin:.5rem 0}
h2{margin:2rem 0 .5rem;padding-top:.5rem;border-top:2px solid var(--linea)}h3{margin:0;font-size:1rem}
.marca{color:var(--rojo);font-weight:600}.intro{color:var(--suave)}
nav ol{columns:2;padding-left:1.2rem}nav a{color:var(--azul)}
.paso,.resultado,.alerta{background:var(--panel);border:1px solid var(--linea);border-radius:10px;
padding:12px 14px;margin:12px 0}
.paso header{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.n{font-weight:700;color:var(--verde)}
.cuenta{margin-left:auto;font-size:.8rem;padding:2px 8px;border-radius:99px;background:var(--azul-claro);
color:var(--azul)}
.cuenta-superadministrador{background:var(--ambar-claro);color:var(--ambar)}
.ruta{margin:6px 0;color:var(--suave)}.final{margin:8px 0 0}
.nota{margin:6px 0 0;color:var(--suave);font-size:.9rem}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;border-bottom:1px solid var(--linea);padding:6px;vertical-align:top}
th{color:var(--suave);font-weight:600}
.etiqueta{width:34%}.modo{width:16%;color:var(--suave);font-size:.82rem}
.valor{white-space:pre-wrap;word-break:break-word}
.archivo{font-family:ui-monospace,Consolas,monospace;font-size:.85rem}
.teclear,.m-teclear{font-family:ui-monospace,Consolas,monospace}
.copiar{margin-left:8px;font:inherit;font-size:.78rem;padding:1px 8px;border-radius:6px;
border:1px solid var(--linea);background:var(--verde-claro);color:var(--verde);cursor:pointer}
.copiar.hecho{background:var(--verde);color:#fff}
.tabla-ancha{overflow-x:auto;background:var(--panel);border:1px solid var(--linea);border-radius:10px;
padding:8px;margin:12px 0}
.titulo-tabla{font-weight:600;margin:6px 0}.alerta{background:var(--ambar-claro);border-color:var(--ambar)}
.total td{font-weight:700}ul.antes li{margin:4px 0}
@media (max-width:640px){nav ol{columns:1}.etiqueta{width:auto}}
"""

SCRIPT = """
document.addEventListener('click', async (e) => {
  const b = e.target.closest('button.copiar'); if (!b) return;
  try { await navigator.clipboard.writeText(b.dataset.valor); }
  catch { const t = document.createElement('textarea'); t.value = b.dataset.valor; document.body.append(t);
          t.select(); document.execCommand('copy'); t.remove(); }
  b.classList.add('hecho'); b.textContent = 'Copiado';
  setTimeout(() => { b.classList.remove('hecho'); b.textContent = 'Copiar'; }, 1200);
});
"""


def _pagina(g: Guion) -> str:
    indice = "".join(f"<li><a href='#{i}'>{_e(t)}</a></li>" for i, t in g.indice)
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Guion de carga de la simulación</title><style>{ESTILO}</style></head><body><main>"
        "<h1>Guion de carga de la simulación de CacaoTrace</h1>"
        f"<p class='marca'>Todos los datos y documentos son ficticios ({MARCA}).</p>"
        f"<nav><ol>{indice}</ol></nav>{''.join(g.partes)}</main><script>{SCRIPT}</script></body></html>"
    )


# ---------- LEEME ----------


def leeme(simulacion: sim.Simulacion) -> str:
    lineas = [
        "PAQUETE DE SIMULACIÓN DE CACAOTRACE",
        "",
        f"Generado para el {_dia(simulacion.hoy)}. Todo es ficticio: nombres, DNI, RUC, partidas y números.",
        f'Cada PDF lleva la marca "{MARCA}" en cada página, sin logos, sellos ni elementos de seguridad.',
        "",
        "CÓMO USARLO",
        (
            "Abre guion-de-carga.html en el navegador y sigue los pasos en orden. Cada valor tiene su "
            "botón Copiar; las"
        ),
        "fechas y horas se escriben a mano. Cada paso dice con qué cuenta se hace.",
        "",
        "CONTENIDO",
        (
            "guion-de-carga.html   El guion, separado por cooperativa, con el resultado esperado al final "
            "de cada una."
        ),
        "LEEME.txt             Este archivo.",
    ]
    for c in simulacion.cooperativas:
        lineas += [
            "",
            f"{c.carpeta}/   {c.razon_social}",
            "  01-expediente-cooperativa/   Los 6 documentos legales de la cooperativa (PDF).",
            "  02-productores/              La copia del DNI de cada uno de los 3 productores (PDF).",
            (
                "  03-parcelas/                 Una carpeta por parcela (9): su geometría en GeoJSON y en "
                "KML, y los 4"
            ),
            (
                "                               documentos de su expediente (título SUNARP, SUNAFIL, SUNAT "
                "y zonificación)."
            ),
            "  04-tandas/                   La liquidación de compra de cada una de las 9 tandas (PDF).",
            "  05-embarque/                 Factura comercial, Lista de empaque, Certificado de origen y",
            "                               Certificado fitosanitario del lote (PDF).",
        ]
    lineas += [
        "",
        "DECISIONES DEL ESCENARIO",
        "- Las dos cooperativas se crean como de demostración: sus DOP, DPP y DEX llevan la marca de agua.",
        "- Cada cooperativa tiene un administrador y un operador: el operador registra las tandas y el",
        "  administrador las valida.",
        (
            "- Las parcelas son de propiedad titulada: el CUSAF y la autorización forestal se declaran "
            "\"no aplica\""
        ),
        "  con su motivo, que aparece en el informe de hallazgos.",
        (
            "- Solo camino feliz: sin documentos vencidos, sin superposiciones, con rendimientos dentro de "
            "la banda"
        ),
        "  (0.330 a 0.450) y volúmenes muy por debajo del tope de 1,500 kg/ha/año.",
        "- Las parcelas son polígonos de menos de 4 ha en zonas agrícolas de San Martín que MapBiomas Perú",
        (
            "  (Colección 3) clasifica sin bosque entre 2015 y 2024. Whisp y GFW se consultan de verdad al "
            "cargarlas."
        ),
        (
            "- La prueba automática tests/test_simulacion.py carga este mismo escenario por la capa de "
            "servicios."
        ),
    ]
    return "\n".join(lineas) + "\n"


# ---------- Comando ----------


def generar(hoy: date, salida: Path) -> Path:
    carpeta = salida / NOMBRE
    if carpeta.exists():
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True)
    archivos = escribir(sim.armar(hoy), carpeta)
    destino = salida / f"{NOMBRE}.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zip_:
        for ruta in sorted(archivos):
            zip_.write(ruta, f"{NOMBRE}/{ruta.relative_to(carpeta).as_posix()}")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--hoy", type=date.fromisoformat, default=None, help="fecha de referencia (AAAA-MM-DD)"
    )
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args()
    destino = generar(args.hoy or hoy_lima(), args.salida)
    with zipfile.ZipFile(destino) as zip_:
        total = len(zip_.namelist())
    print(f"{total} archivos en {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
