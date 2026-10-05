"""Análisis de cobertura forestal (Parte 4): solicitud, cola, evidencia, vigencia y alertas.

Principio: exponer, no concluir. Se registra lo que dice cada fuente, con su nombre, su versión y
su fecha; el sistema no combina fuentes ni emite un veredicto propio. Si una fuente falla, el
análisis queda en error: nunca se simula un resultado.

El análisis corre en segundo plano dentro de la API (app/trabajador.py), una consulta externa a la
vez. Cada consulta es una fila de analisis_cobertura que no se borra ni se sobrescribe.
"""

import hashlib
import json
import logging
import math
import time
import uuid
from datetime import timedelta

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora
from app.models import Afiliacion, AnalisisCobertura, Documento, Parcela, Perfil
from app.schemas.habilitacion import (
    AnalisisDetalle,
    AnalisisSalida,
    ConvergenciaSalida,
    FilaConvergencia,
    FuenteSalida,
    MedidaSalida,
)
from app.services import convergencia as servicio_convergencia
from app.services import geometria
from app.services.auditoria import registrar_auditoria
from app.services.fuentes import ErrorFuente, Fuente
from app.storage import ClienteStorage, ErrorStorage, construir_ruta, sha256

log = logging.getLogger(__name__)

# Un fallo se reintenta con estas esperas; al tercer intento fallido la fila queda en error.
ESPERAS = (10, 60, 300)
MAX_INTENTOS = 3
TIEMPO_MAXIMO = 60  # segundos por petición
TOPE_POR_MINUTO = 20  # por fuente; Whisp admite 30
ATASCADO = timedelta(minutes=10)
RENOVAR_ANTES = timedelta(days=15)


# ---------- Huella y geometría enviada ----------


def huella(geojson: dict) -> str:
    return hashlib.sha256(json.dumps(geojson, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def huella_parcela(parcela: Parcela) -> str:
    return huella(geometria.a_geojson(to_shape(parcela.geometria)))


def geometria_para(sesion: Session, parcela: Parcela, fuente: Fuente) -> tuple[dict, bool]:
    """La geometría que recibe la fuente. Un punto va como círculo con el área declarada si la fuente
    solo analiza polígonos; ese análisis queda marcado como aproximación."""
    geo = geometria.a_geojson(to_shape(parcela.geometria))
    if parcela.tipo_geometria != "punto" or not fuente.requiere_poligono:
        return geo, False
    radio_m = math.sqrt(float(parcela.area_declarada_ha) * 10_000 / math.pi)
    circulo = sesion.execute(
        text(
            "SELECT ST_AsGeoJSON(ST_Buffer(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)::geography, :r, 16)"
            "::geometry, 8)"
        ),
        {"g": json.dumps(geo), "r": radio_m},
    ).scalar_one()
    return json.loads(circulo), True


# ---------- Solicitud ----------


def _cooperativa_de(sesion: Session, parcela: Parcela) -> uuid.UUID:
    activa = sesion.scalar(
        select(Afiliacion.cooperativa_id).where(
            Afiliacion.productor_id == parcela.productor_id, Afiliacion.estado == "activa"
        )
    )
    return activa or parcela.cooperativa_registro_id


def configuradas(fuentes: dict[str, Fuente]) -> list[Fuente]:
    return [f for f in fuentes.values() if f.configurada]


def solicitar(
    sesion: Session,
    fuentes: dict[str, Fuente],
    parcela: Parcela,
    *,
    contexto: Contexto | None = None,
    solo=None,
) -> list[AnalisisCobertura]:
    """Crea una fila pendiente por cada fuente configurada (o solo las de `solo`). No confirma.

    contexto None: lo lanzó el sistema (al crear la parcela, al cambiar su geometría o en la tarea
    diaria); queda en auditoría con usuario nulo.
    """
    elegidas = [f for f in configuradas(fuentes) if solo is None or f.codigo in solo]
    if not elegidas:
        return []
    momento = ahora()
    cooperativa_id = cooperativa_del_contexto(contexto) if contexto else _cooperativa_de(sesion, parcela)
    filas = []
    for fuente in elegidas:
        geo, aproximacion = geometria_para(sesion, parcela, fuente)
        fila = AnalisisCobertura(
            parcela_id=parcela.id,
            cooperativa_id=cooperativa_id,
            fuente=fuente.codigo,
            estado="pendiente",
            geometria=from_shape(shape(geo), srid=4326),
            geometria_sha256=huella_parcela(parcela),
            es_aproximacion=aproximacion,
            solicitado_por=contexto.usuario_id if contexto else None,
            solicitado_en=momento,
            reintentar_en=momento,
        )
        sesion.add(fila)
        filas.append(fila)
    sesion.flush()
    registrar_auditoria(
        contexto,
        "analisis.solicitar",
        "parcela",
        parcela.id,
        {"fuentes": [f.fuente for f in filas], "analisis": [f.id for f in filas]},
        cooperativa_id=cooperativa_id,
        sesion=sesion,
    )
    return filas


def solicitar_a_pedido(
    contexto: Contexto, fuentes: dict[str, Fuente], parcela: Parcela
) -> list[AnalisisCobertura]:
    from app.services.expediente import no_excluida  # evita importación circular

    no_excluida(parcela)
    if parcela.estado != "activa":
        raise error_api(400, "parcela_inactiva", "La parcela está inactiva.")
    filas = solicitar(contexto.sesion, fuentes, parcela, contexto=contexto)
    if not filas:
        raise error_api(400, "sin_fuentes_configuradas", "No hay ninguna fuente de análisis configurada.")
    contexto.sesion.commit()
    return filas


# ---------- Vigencia, salida y alertas ----------


def obsoleto(analisis: AnalisisCobertura, huella_actual: str) -> bool:
    return analisis.geometria_sha256 != huella_actual


def vigente(analisis: AnalisisCobertura, huella_actual: str) -> bool:
    vigencia = timedelta(days=get_settings().analisis_vigencia_dias)
    return (
        analisis.estado == "completado"
        and not obsoleto(analisis, huella_actual)
        and analisis.completado_en is not None
        and ahora() - analisis.completado_en < vigencia
    )


def de_parcelas(sesion: Session, parcela_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[AnalisisCobertura]]:
    """Análisis de cada parcela, del más reciente al más antiguo."""
    resultado: dict[uuid.UUID, list[AnalisisCobertura]] = {pid: [] for pid in parcela_ids}
    if not parcela_ids:
        return resultado
    for a in sesion.scalars(
        select(AnalisisCobertura)
        .where(AnalisisCobertura.parcela_id.in_(parcela_ids))
        .order_by(AnalisisCobertura.solicitado_en.desc(), AnalisisCobertura.creado_en.desc())
    ):
        resultado[a.parcela_id].append(a)
    return resultado


def ultimos_completados(
    fuentes: dict[str, Fuente], parcela: Parcela, analisis: list[AnalisisCobertura]
) -> list[AnalisisCobertura]:
    """El último análisis completado de cada fuente en uso, sobre la geometría actual."""
    actual = huella_parcela(parcela)
    elegidos = []
    for codigo in fuentes:
        completado = next(
            (
                a
                for a in analisis
                if a.fuente == codigo and a.estado == "completado" and not obsoleto(a, actual)
            ),
            None,
        )
        if completado is not None:
            elegidos.append(completado)
    return elegidos


def area_parcela(parcela: Parcela) -> float | None:
    area = parcela.area_calculada_ha if parcela.tipo_geometria == "poligono" else parcela.area_declarada_ha
    return float(area) if area is not None else None


def convergencia_de(
    fuentes: dict[str, Fuente], parcela: Parcela, analisis: list[AnalisisCobertura]
) -> servicio_convergencia.Convergencia:
    return servicio_convergencia.calcular(
        ultimos_completados(fuentes, parcela, analisis),
        area_parcela(parcela),
        get_settings().umbral_bosque_2020_pct,
        es_punto=parcela.tipo_geometria == "punto",
    )


def convergencia_salida(sesion: Session, fuentes: dict[str, Fuente], parcela: Parcela) -> ConvergenciaSalida:
    c = convergencia_de(fuentes, parcela, de_parcelas(sesion, [parcela.id])[parcela.id])

    def celda(medidas):
        return [MedidaSalida(**vars(m)) for m in medidas] or None

    return ConvergenciaSalida(
        filas=[
            FilaConvergencia(
                conjunto=f.conjunto,
                nombre=f.nombre,
                vias=f.vias,
                fechas=f.fechas,
                al_2020=celda(f.al_2020),
                despues_2020=celda(f.despues_2020),
                registra_bosque_2020=f.registra_bosque_2020,
                registra_cambio=f.registra_cambio,
            )
            for f in c.filas
        ],
        frase=c.frase,
        conteos=c.conteos,
        discrepan=c.discrepan,
        umbral_bosque_2020_pct=c.umbral_pct,
        mapas_minimos_bosque_2020=servicio_convergencia.MAPAS_MINIMOS_BOSQUE_2020,
        hubo_bosque_2020=c.hubo_bosque_2020,
        area_ha=c.area_ha,
    )


def resumen(fuentes: dict[str, Fuente], parcela: Parcela, analisis: list[AnalisisCobertura]) -> dict:
    """Estado del análisis de una parcela para alertas y requisitos."""
    actual = huella_parcela(parcela)
    codigos = [f.codigo for f in configuradas(fuentes)]
    sin_vigente = [c for c in codigos if not any(a.fuente == c and vigente(a, actual) for a in analisis)]
    ultimo = {c: next((a for a in analisis if a.fuente == c), None) for c in fuentes}
    con_error = [c for c, a in ultimo.items() if a is not None and a.estado == "error"]
    # Lo que dice cada fuente en su último análisis completado sobre la geometría actual.
    completados = ultimos_completados(fuentes, parcela, analisis)
    # Adenda de la Parte 4, 7.2 regla 3, con la decisión del equipo del 2026-10-05: pide revisión si al
    # menos 3 conjuntos registran bosque en 2020 en al menos el umbral del área de la parcela.
    convergencia = convergencia_de(fuentes, parcela, analisis)
    hubo_bosque = convergencia.hubo_bosque_2020
    bosque_2020 = convergencia.registran_bosque_2020 if hubo_bosque else []
    revision = [
        a.fuente
        for a in completados
        if fuentes[a.fuente].requiere_revision(
            a.resultado_fuente, a.indicadores or {}, hubo_bosque_2020=hubo_bosque
        )
    ]
    return {
        "configuradas": codigos,
        "sin_vigente": sin_vigente,
        "con_error": con_error,
        "requiere_revision": revision,
        "bosque_2020": bosque_2020,
    }


def alertas(estado: dict) -> list[str]:
    resultado = []
    if estado["sin_vigente"]:
        resultado.append("sin_analisis_vigente")
    if estado["requiere_revision"] or estado.get("bosque_2020"):
        resultado.append("analisis_requiere_revision")
    if estado["con_error"]:
        resultado.append("analisis_con_error")
    return resultado


def salidas(
    sesion: Session,
    fuentes: dict[str, Fuente],
    parcela: Parcela,
    analisis: list[AnalisisCobertura],
    *,
    con_respuesta=True,
) -> list[AnalisisSalida]:
    actual = huella_parcela(parcela)
    nombres = dict(
        sesion.execute(
            select(Perfil.id, func.concat(Perfil.nombres, " ", Perfil.apellidos)).where(
                Perfil.id.in_({a.solicitado_por for a in analisis if a.solicitado_por})
            )
        ).all()
    )
    resultado = []
    hubo_bosque = convergencia_de(fuentes, parcela, analisis).hubo_bosque_2020
    for a in analisis:
        fuente = fuentes.get(a.fuente)
        resultado.append(
            AnalisisSalida(
                id=a.id,
                parcela_id=a.parcela_id,
                fuente=a.fuente,
                estado=a.estado,
                es_aproximacion=a.es_aproximacion,
                resultado_fuente=a.resultado_fuente,
                resultado_texto=fuente.texto(a.resultado_fuente, a.indicadores or {})
                if fuente and a.estado == "completado"
                else None,
                indicadores=a.indicadores,
                version_fuente=a.version_fuente,
                solicitado_en=a.solicitado_en,
                solicitado_por_nombre=nombres.get(a.solicitado_por),
                completado_en=a.completado_en,
                intentos=a.intentos,
                error_detalle=a.error_detalle,
                obsoleto=obsoleto(a, actual),
                vigente=vigente(a, actual),
                requiere_revision=bool(
                    fuente
                    and a.estado == "completado"
                    and fuente.requiere_revision(
                        a.resultado_fuente, a.indicadores or {}, hubo_bosque_2020=hubo_bosque
                    )
                ),
                respuesta_documento_id=a.respuesta_documento_id if con_respuesta else None,
            )
        )
    return resultado


def fuentes_salida(fuentes: dict[str, Fuente]) -> list[FuenteSalida]:
    return [
        FuenteSalida(fuente=f.codigo, nombre=f.nombre, configurada=f.configurada) for f in fuentes.values()
    ]


def analisis_visible(contexto: Contexto, analisis_id: uuid.UUID) -> tuple[AnalisisCobertura, Parcela]:
    from app.services.parcelas import parcela_visible  # evita importación circular

    analisis = contexto.sesion.get(AnalisisCobertura, analisis_id)
    if analisis is None:
        raise no_encontrado("El análisis no existe.")
    return analisis, parcela_visible(contexto, analisis.parcela_id)


def detalle(
    contexto: Contexto, fuentes: dict[str, Fuente], storage: ClienteStorage, analisis_id: uuid.UUID
) -> AnalisisDetalle:
    analisis, parcela = analisis_visible(contexto, analisis_id)
    base = salidas(contexto.sesion, fuentes, parcela, [analisis])[0]
    url = None
    if analisis.respuesta_documento_id:
        documento = contexto.sesion.get(Documento, analisis.respuesta_documento_id)
        momento = (analisis.completado_en or analisis.solicitado_en).astimezone(LIMA).strftime("%Y%m%d-%H%M")
        try:
            url = storage.url_firmada(
                documento.ruta, descarga=f"{analisis.fuente}-{parcela.codigo}-{momento}.json"
            )
        except ErrorStorage:
            url = None
    return AnalisisDetalle(**base.model_dump(), respuesta_url=url)


# ---------- Cola ----------


class Ritmo:
    """Respeta el tope de peticiones por minuto de cada fuente."""

    def __init__(self, por_minuto: int = TOPE_POR_MINUTO, reloj=time.monotonic, dormir=time.sleep):
        self.intervalo = 60 / por_minuto
        self.ultima: dict[str, float] = {}
        self.reloj, self.dormir = reloj, dormir

    def esperar(self, fuente: str) -> None:
        anterior = self.ultima.get(fuente)
        if anterior is not None:
            falta = self.intervalo - (self.reloj() - anterior)
            if falta > 0:
                self.dormir(falta)
        self.ultima[fuente] = self.reloj()


def recuperar_atascados(sesion: Session) -> int:
    """Al arrancar: lo que quedó pendiente o en proceso hace más de 10 minutos vuelve a la cola."""
    limite = ahora() - ATASCADO
    resultado = sesion.execute(
        update(AnalisisCobertura)
        .where(
            AnalisisCobertura.estado.in_(("pendiente", "en_proceso")),
            AnalisisCobertura.actualizado_en < limite,
        )
        .values(estado="pendiente", reintentar_en=ahora())
    )
    sesion.commit()
    return resultado.rowcount


def _guardar_respuesta(
    sesion: Session, storage: ClienteStorage, fila: AnalisisCobertura, contenido: bytes
) -> Documento:
    """La respuesta completa se guarda en Storage, como documento del sistema, antes de interpretarla."""
    ruta = construir_ruta(fila.cooperativa_id, "analisis", fila.id, "json")
    storage.subir(ruta, contenido, "application/json")
    documento = Documento(
        cooperativa_id=fila.cooperativa_id,
        entidad="analisis",
        entidad_id=fila.id,
        tipo="respuesta_analisis",
        ruta=ruta,
        nombre_original=f"{fila.fuente}-{fila.id}.json",
        tipo_mime="application/json",
        tamano_bytes=len(contenido),
        sha256=sha256(contenido),
        subido_por=None,
    )
    sesion.add(documento)
    sesion.flush()
    return documento


def procesar_siguiente(
    sesion: Session, fuentes: dict[str, Fuente], storage: ClienteStorage, ritmo: Ritmo
) -> bool:
    """Toma la fila pendiente más antigua que ya puede intentarse y la procesa. False si no había."""
    fila = sesion.scalar(
        select(AnalisisCobertura)
        .where(AnalisisCobertura.estado == "pendiente", AnalisisCobertura.reintentar_en <= ahora())
        .order_by(AnalisisCobertura.solicitado_en, AnalisisCobertura.creado_en)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if fila is None:
        return False
    fuente = fuentes.get(fila.fuente)
    if fuente is None or not fuente.configurada:
        fila.estado, fila.error_detalle = "error", "La fuente ya no está configurada."
        sesion.commit()
        return True

    fila.estado = "en_proceso"
    fila.intentos += 1
    geo = geometria.a_geojson(to_shape(fila.geometria))
    sesion.commit()

    ritmo.esperar(fuente.codigo)
    try:
        # Solo la geometría y un identificador opaco: el del propio análisis.
        contenido = fuente.consultar(geo, str(fila.id))
        documento = _guardar_respuesta(sesion, storage, fila, contenido)
    except (ErrorFuente, ErrorStorage) as exc:
        sesion.rollback()
        detalle = exc.detalle if isinstance(exc, ErrorFuente) else f"No se pudo guardar la respuesta: {exc}"
        espera = exc.espera if isinstance(exc, ErrorFuente) else None
        if fila.intentos >= MAX_INTENTOS:
            fila.estado = "error"
        else:
            fila.estado = "pendiente"
            fila.reintentar_en = ahora() + timedelta(seconds=espera or ESPERAS[fila.intentos - 1])
        fila.error_detalle = detalle
        log.warning("Análisis %s de %s falló (intento %s): %s", fila.id, fila.fuente, fila.intentos, detalle)
        sesion.commit()
        return True

    try:
        resultado, indicadores, version = fuente.interpretar(contenido)
        fila.error_detalle = None
    except Exception as exc:  # una respuesta con forma inesperada queda guardada y sin resultado
        log.exception("No se pudo interpretar la respuesta de %s", fila.fuente)
        resultado, indicadores, version = None, {}, None
        fila.error_detalle = f"La respuesta no se pudo interpretar: {type(exc).__name__}"
    fila.estado = "completado"
    fila.resultado_fuente = resultado
    fila.indicadores = indicadores
    fila.version_fuente = version
    fila.respuesta_documento_id = documento.id
    fila.completado_en = ahora()
    sesion.commit()
    return True


def renovar_por_caducar(sesion: Session, fuentes: dict[str, Fuente]) -> int:
    """Tarea diaria: 15 días antes de que el análisis vigente caduque se solicita uno nuevo, para que la
    parcela no quede observada solo por antigüedad."""
    vigencia = timedelta(days=get_settings().analisis_vigencia_dias)
    parcelas = list(
        sesion.scalars(
            select(Parcela).where(Parcela.estado == "activa", Parcela.habilitacion_estado != "excluida")
        )
    )
    todos = de_parcelas(sesion, [p.id for p in parcelas])
    solicitados = 0
    for parcela in parcelas:
        actual = huella_parcela(parcela)
        renovar = []
        for fuente in configuradas(fuentes):
            propios = [a for a in todos[parcela.id] if a.fuente == fuente.codigo]
            if any(a.estado in ("pendiente", "en_proceso") for a in propios):
                continue
            vigentes = [a for a in propios if vigente(a, actual)]
            if vigentes and max(a.completado_en for a in vigentes) + vigencia - ahora() <= RENOVAR_ANTES:
                renovar.append(fuente.codigo)
        if renovar:
            solicitados += len(solicitar(sesion, fuentes, parcela, solo=renovar))
    sesion.commit()
    return solicitados
