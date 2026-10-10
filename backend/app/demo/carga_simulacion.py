"""Carga del paquete de simulación (app/demo/simulacion.py) por la capa de servicios.

Sigue el guion paso a paso, con el rol que corresponde en cada pantalla: el superadministrador crea la
cooperativa; el administrador carga sus datos y su expediente, crea al operador, configura, habilita,
valida las tandas y emite el DEX; el operador registra productores, parcelas con su título y su perfil
legal (adenda 4), tandas, corridas, la orden, el lote y el embarque. Llama a las mismas funciones que los
endpoints, con los mismos esquemas de entrada; no inserta filas ni fuerza estados.

Como el escenario es el camino feliz, cualquier alerta que pida una nota detiene la carga con
EscenarioDetenido: la prueba la corre con Whisp y GFW simulados sin alertas.
"""

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.catalogos import perfil_legal
from app.demo.escenario import EscenarioDetenido, _contexto, _paso
from app.demo.simulacion import CALIDAD, HUMEDAD, Cooperativa, Documento, Simulacion, geojson
from app.fechas import ahora
from app.models import Perfil
from app.schemas.cooperativa import CooperativaCambios
from app.schemas.exportacion import Confirmacion, ImportadorNuevo, OrdenNueva
from app.schemas.legalidad import DeclaracionNueva
from app.schemas.plataforma import CooperativaNueva
from app.schemas.proceso import (
    CalidadNueva,
    Consolidacion,
    CorridaNueva,
    EtapaRegistro,
    PlantillaCambio,
    TandaACorrida,
)
from app.schemas.productores import ProductorNuevo
from app.schemas.recepcion import ConfiguracionCambio, LugarNuevo, TandaNueva
from app.schemas.usuarios import AdministradorNuevo, UsuarioNuevo
from app.services import (
    analisis,
    configuracion,
    cooperativa,
    corridas,
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
    tandas,
    usuarios,
)
from app.services.documentos import Archivo
from app.services.fuentes import registro

ESPERA_ANALISIS = timedelta(minutes=15)


def cargar(
    sesion,
    superadmin: Perfil,
    *,
    auth,
    storage,
    fuentes: dict,
    ritmo,
    simulacion: Simulacion,
    pdf: Callable[[Documento], bytes],
) -> dict[str, dict[str, Any]]:
    if fuentes is not registro.actuales():
        registro.fijar(fuentes)
    resultado = {}
    for c in simulacion.cooperativas:
        carga = _Carga(sesion, _contexto(sesion, superadmin), auth, storage, fuentes, ritmo, pdf, c)
        resultado[c.clave] = carga.todo()
    return resultado


class _Carga:
    def __init__(self, sesion, superadmin, auth, storage, fuentes, ritmo, pdf, c: Cooperativa):
        self.sesion, self.superadmin, self.auth, self.storage = sesion, superadmin, auth, storage
        self.fuentes, self.ritmo, self.pdf, self.c = fuentes, ritmo, pdf, c
        self.ids: dict[str, Any] = {
            "parcelas": {},
            "productores": {},
            "tandas": {},
            "corridas": {},
            "finales": {},
        }

    def _archivo(self, d: Documento) -> Archivo:
        return Archivo(nombre=d.archivo.rsplit("/", 1)[-1], contenido=self.pdf(d))

    def _paso(self, texto: str):
        return _paso(f"{self.c.razon_social}: {texto}")

    def todo(self) -> dict[str, Any]:
        self._cooperativa()
        self._datos_y_expediente()
        self._operador()
        self._configuracion()
        self._productores()
        self._parcelas()
        self._habilitacion()
        self._tandas()
        for corrida in self.c.corridas:
            self._corrida(corrida)
        self._exportacion()
        return self.ids

    # ---------- Plataforma y cooperativa ----------

    def _cooperativa(self) -> None:
        c = self.c
        dep, prov, dist = c.ubicacion
        with self._paso("crear la cooperativa"):
            datos = CooperativaNueva(
                razon_social=c.razon_social,
                nombre_comercial=c.nombre_comercial,
                ruc=c.ruc,
                departamento=dep,
                provincia=prov,
                distrito=dist,
                es_demo=True,
                codigo=c.codigo,
                tipo_organizacion="cooperativa_agraria",
                administrador=AdministradorNuevo(
                    nombres=c.admin.nombres, apellidos=c.admin.apellidos, correo=c.admin.correo
                ),
            )
            creada, administrador, _ = plataforma.crear(self.superadmin, self.auth, datos)
        self.ids["cooperativa"] = creada.id
        self.admin = _contexto(self.sesion, administrador)

    def _datos_y_expediente(self) -> None:
        c = self.c
        with self._paso("datos de la cooperativa"):
            cooperativa.editar(
                self.admin,
                CooperativaCambios(
                    direccion_postal=c.direccion,
                    correo=c.correo,
                    representante_nombre=c.representante,
                    representante_dni=c.representante_dni,
                ),
            )
        for d in c.documentos:
            with self._paso(f"cargar «{d.nombre}»"):
                legales = expediente.validar_datos_legales(
                    d.tipo, d.numero, d.entidad, d.emision, d.vencimiento
                )
                documentos.cargar(
                    self.admin,
                    self.storage,
                    entidad="cooperativa",
                    entidad_id=self.ids["cooperativa"],
                    tipo=d.tipo,
                    archivo=self._archivo(d),
                    datos_legales=legales,
                )

    def _operador(self) -> None:
        o = self.c.operador
        with self._paso("crear la cuenta del operador"):
            perfil, _ = usuarios.crear(
                self.admin,
                self.auth,
                UsuarioNuevo(nombres=o.nombres, apellidos=o.apellidos, correo=o.correo, rol="operador"),
            )
        self.operador = _contexto(self.sesion, perfil)
        self.responsable = f"{o.nombres} {o.apellidos}"

    def _configuracion(self) -> None:
        from app.demo.simulacion import TOPE

        c = self.c
        with self._paso("configuración"):
            actual = configuracion.obtener(self.admin)
            valores = {campo: getattr(actual, campo) for campo in configuracion.CAMPOS} | {
                "tope_kg_seco_ha_anio": TOPE
            }
            configuracion.cambiar(self.admin, ConfiguracionCambio(**valores))
        dep, prov, dist = c.ubicacion
        self.lugares = {}
        for clave, nombre, tipo in c.lugares:
            with self._paso(f"crear el lugar «{nombre}»"):
                lugar = lugares.crear(
                    self.admin,
                    LugarNuevo(nombre=nombre, tipo=tipo, departamento=dep, provincia=prov, distrito=dist),
                )
            self.lugares[clave] = lugar.id
        with self._paso("crear la calidad"):
            self.calidad_id = proceso.crear_calidad(self.admin, CalidadNueva(nombre=CALIDAD)).id
        with self._paso("plantilla de proceso sugerida"):
            proceso.cambiar_plantilla(
                self.admin, PlantillaCambio(filas=proceso.plantilla_sugerida(self.admin))
            )

    # ---------- Productores y parcelas ----------

    def _productores(self) -> None:
        for p in self.c.productores:
            with self._paso(f"registrar a {p.nombres} {p.apellidos}"):
                creado = productores.crear(
                    self.operador,
                    ProductorNuevo(
                        dni=p.dni,
                        nombres=p.nombres,
                        apellidos=p.apellidos,
                        direccion_postal=p.direccion,
                        consentimiento_cooperativa=True,
                        version_consentimiento="1",
                    ),
                )
                documentos.cargar(
                    self.operador,
                    self.storage,
                    entidad="productor",
                    entidad_id=creado.id,
                    tipo="dni",
                    archivo=self._archivo(p.copia_dni),
                )
            self.ids["productores"][p.clave] = creado.id

    def _parcelas(self) -> None:
        for p in self.c.parcelas:
            archivo = Archivo(nombre=f"parcela-{p.nombre}.geojson", contenido=geojson(p).encode("utf-8"))
            productor_id = self.ids["productores"][p.productor]
            with self._paso(f"ubicar la parcela {p.nombre}"):
                analizada = parcelas.analizar(self.operador, archivo, productor_id)[0]
            if not analizada.valida or analizada.superposiciones:
                raise EscenarioDetenido(f"parcela {p.nombre}", "la geometría no es válida o se superpone.")
            u = analizada.ubicacion
            if u is None or (u.departamento, u.provincia, u.distrito) != p.ubicacion:
                raise EscenarioDetenido(f"parcela {p.nombre}", f"la ubicación sugerida no es {p.ubicacion}.")
            with self._paso(f"guardar la parcela {p.nombre}"):
                detalle = parcelas.crear(
                    self.operador,
                    self.storage,
                    productor_id,
                    parcelas_datos(p, analizada.area_ha),
                    archivo=archivo,
                    indice=0,
                )
            if detalle.codigo != p.codigo:
                raise EscenarioDetenido(f"parcela {p.nombre}", f"quedó con el código {detalle.codigo}.")
            self.ids["parcelas"][p.clave] = detalle.id
            for d in p.documentos:
                with self._paso(f"{p.codigo}: cargar «{d.nombre}»"):
                    parcela = parcelas.parcela_visible(self.operador, detalle.id)
                    legales = expediente.validar_datos_legales(
                        d.tipo, d.numero, d.entidad, d.emision, d.vencimiento
                    )
                    documentos.cargar(
                        self.operador,
                        self.storage,
                        entidad="parcela",
                        entidad_id=parcela.id,
                        tipo=d.tipo,
                        archivo=self._archivo(d),
                        datos_legales=legales,
                    )
            with self._paso(f"{p.codigo}: declarar el perfil legal"):
                parcela = parcelas.parcela_visible(self.operador, detalle.id)
                actual = legalidad.legalidad(self.sesion, parcela)
                # Lo que no respondió el cruce con las capas oficiales (en la prueba no corre) va como "no".
                respuestas = dict(p.perfil) | {
                    c: "no" for c in perfil_legal.CRUZABLES if actual.valor(c) is None
                }
                for variable, valor in respuestas.items():
                    datos = DeclaracionNueva(variable=variable, valor=valor)
                    legalidad.declarar(self.operador, parcela, datos.variable, datos.valor)

    def _habilitacion(self) -> None:
        limite = ahora() + ESPERA_ANALISIS
        ids = list(self.ids["parcelas"].values())
        while True:
            while analisis.procesar_siguiente(self.sesion, self.fuentes, self.storage, self.ritmo):
                pass
            filas = [a for lista in analisis.de_parcelas(self.sesion, ids).values() for a in lista]
            if not any(a.estado in ("pendiente", "en_proceso") for a in filas) or ahora() >= limite:
                break
            self.ritmo.dormir(5)
        for p in self.c.parcelas:
            parcela = parcelas.parcela_visible(self.admin, self.ids["parcelas"][p.clave])
            with self._paso(f"habilitar {p.codigo}"):
                estado = habilitacion.obtener(self.admin, parcela)
                if estado.alertas or estado.nota_obligatoria:
                    raise EscenarioDetenido(
                        f"habilitar {p.codigo}", f"tiene alertas: {', '.join(estado.alertas)}."
                    )
                habilitacion.habilitar(self.admin, parcela, None)

    # ---------- Recepción ----------

    def _tandas(self) -> None:
        for t in self.c.tandas:
            p = self.c.parcela(t.parcela)
            with self._paso(f"registrar la tanda de {p.codigo}"):
                detalle = tandas.registrar(
                    self.operador,
                    TandaNueva(
                        productor_id=self.ids["productores"][t.productor],
                        parcela_id=self.ids["parcelas"][t.parcela],
                        lugar_id=self.lugares["cancha"],
                        recibida_en=t.recibida_en,
                        estado_producto="baba",
                        peso_kg=t.peso,
                        numero_sacos=t.sacos,
                        variedad=t.variedad,
                        cosecha_desde=t.cosecha_desde,
                        cosecha_hasta=t.cosecha_hasta,
                        doc_entrega_tipo="liquidacion_compra",
                        doc_entrega_numero=t.liquidacion.numero,
                        doc_entrega_fecha_emision=t.liquidacion.emision,
                        doc_entrega_peso_kg=t.peso,
                    ),
                )
                detalle = tandas.cargar_documento(
                    self.operador, self.storage, detalle.id, self._archivo(t.liquidacion)
                )
            # El administrador valida: así el DEX no muestra "registro y validación por la misma persona".
            with self._paso(f"validar la tanda {detalle.codigo}"):
                if detalle.alertas or detalle.nota_obligatoria:
                    raise EscenarioDetenido(
                        f"validar {detalle.codigo}", f"tiene alertas: {', '.join(detalle.alertas)}."
                    )
                tandas.validar(self.admin, self.storage, detalle.id, None)
            self.ids["tandas"][t.clave] = detalle.id

    # ---------- Proceso ----------

    def _corrida(self, corrida) -> None:
        with self._paso(f"{corrida.nombre}: crear e iniciar"):
            creada = corridas.crear(
                self.operador, CorridaNueva(ruta=corrida.ruta, tipo_manejo=corrida.manejo)
            )
            for t in corrida.tandas:
                corridas.agregar_tanda(
                    self.operador, creada.id, TandaACorrida(tanda_id=self.ids["tandas"][t])
                )
            corridas.iniciar(self.operador, creada.id)
        for e in corrida.etapas:
            with self._paso(f"{corrida.nombre}: etapa {e.numero}"):
                if e.no_ocurrio:
                    entrada = EtapaRegistro(situacion="no_ocurrio")
                else:
                    datos = dict(e.datos)
                    if "calidad_id" in datos:
                        datos["calidad_id"] = str(self.calidad_id)
                    entrada = EtapaRegistro(
                        lugar_id=self.lugares[e.lugar],
                        inicio=e.inicio,
                        fin=e.fin,
                        metodo=e.metodo,
                        responsable=self.responsable,
                        distancia_m=e.distancia,
                        datos=datos,
                    )
                corridas.registrar_etapa(self.operador, creada.id, e.numero, entrada)
        with self._paso(f"{corrida.nombre}: consolidar"):
            if corridas.obtener(self.operador, creada.id).rendimiento.alerta:
                raise EscenarioDetenido(
                    f"{corrida.nombre}: consolidar", "el rendimiento salió fuera de la banda."
                )
            consolidada = corridas.consolidar(
                self.operador,
                self.storage,
                creada.id,
                Consolidacion(
                    peso_final_kg=corrida.peso_final, humedad_pct=HUMEDAD, lugar_id=self.lugares["almacen"]
                ),
            )
        self.ids["corridas"][corrida.clave] = creada.id
        self.ids["finales"][corrida.clave] = consolidada.tanda_final.id

    # ---------- Exportación ----------

    def _exportacion(self) -> None:
        o = self.c.orden
        with self._paso("registrar al importador y la orden"):
            imp = ordenes.crear_importador(
                self.operador,
                ImportadorNuevo(
                    razon_social=o.importador.razon_social,
                    direccion=o.importador.direccion,
                    pais=o.importador.pais,
                    correo=o.importador.correo,
                    eori=o.importador.eori,
                ),
            )
            orden = ordenes.crear(
                self.operador,
                OrdenNueva(
                    importador_id=imp.id,
                    referencia_importador=o.referencia,
                    cantidad_kg=o.cantidad,
                    calidad_id=self.calidad_id,
                    pais_destino=o.pais_destino,
                    lugar_destino=o.lugar_destino,
                    fecha_entrega=o.fecha_entrega,
                ),
            )
        with self._paso("armar y confirmar el lote con la sugerencia FIFO"):
            lote = lotes.crear(self.operador, orden.id)
            lotes.confirmar(self.operador, lote.id, Confirmacion(motivo_desviacion=None))
        for d in o.embarque:
            with self._paso(f"cargar «{d.nombre}»"):
                embarque.cargar(
                    self.operador,
                    self.storage,
                    lote.id,
                    d.tipo,
                    self._archivo(d),
                    d.numero,
                    d.entidad,
                    d.emision,
                )
        with self._paso("recomprobar el lote"):
            salida = recomprobacion.recomprobar(self.operador, lote.id)
        if salida.estado_lote != "listo":
            casos = "; ".join(caso.texto for c in salida.comprobaciones for caso in c.casos)
            raise EscenarioDetenido("recomprobar el lote", f"quedó {salida.estado_lote}: {casos}")
        with self._paso("emitir el DEX"):
            emitido = dex.emitir(self.admin, self.storage, lote.id, True)
        self.ids.update(orden=orden.id, lote=lote.id, dex=emitido.id)


def parcelas_datos(p, area_ha: Decimal):
    """Lo que envía el paso Confirmar del asistente: la ubicación sugerida y el área con cacao igual al
    total."""
    from app.schemas.parcelas import ParcelaDatos

    dep, prov, dist = p.ubicacion
    return ParcelaDatos(
        nombre=p.nombre,
        departamento=dep,
        provincia=prov,
        distrito=dist,
        centro_poblado=p.centro_poblado,
        area_cultivada_ha=Decimal(area_ha).quantize(Decimal("0.0001")),
    )
