"""Cruce de la parcela con las capas oficiales (adenda 4, sección 10).

Corre en la cola del trabajador que ya existe (app/trabajador.py), una parcela a la vez: al crear la
parcela, al cambiar su geometría, con el botón "Volver a cruzar" y en la tarea diaria. Cada variable cruzada
guarda una fila en `parcela_variables` con `origen = cruce`, la capa y la fecha en `fuente` y lo que encontró
en `detalle`. Si una capa no responde, su variable queda sin cruce: una persona puede declararla y la tarea
diaria vuelve a intentarlo. Un cruce antiguo no bloquea: conserva su valor y su fecha.

El sistema nunca dice que una parcela "no está" en una zona: dice que no figura en la capa consultada.
"""

import json
import logging
import math
from datetime import timedelta

from geoalchemy2.shape import to_shape
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.catalogos import capas_legales as catalogo
from app.catalogos import perfil_legal
from app.config import get_settings
from app.fechas import LIMA, ahora
from app.models import Parcela, ParcelaVariable
from app.services import geometria
from app.services.auditoria import registrar_auditoria
from app.services.capas_legales import Consulta, ErrorCapa
from app.services.capas_legales.registro import Capas
from app.ubigeo import codigo_departamento

log = logging.getLogger(__name__)

# Si una capa falla, el cruce se repite pronto dos veces; después lo retoma la tarea diaria.
ESPERAS = (timedelta(minutes=5), timedelta(hours=1))
MAX_INTENTOS = 3
# Mientras se cruza, la parcela sale de la cola; si el proceso se cae, vuelve a ella después de esto.
EN_CURSO = timedelta(minutes=15)


# ---------- Cola ----------


def solicitar(sesion: Session, parcela: Parcela, *, geometria_nueva: bool = False) -> None:
    """Pone la parcela en la cola del cruce. Con una geometría nueva, los cruces anteriores dejan de valer:
    describían otra geometría. No confirma."""
    parcela.cruce_solicitado_en = ahora()
    if geometria_nueva:
        sesion.execute(
            update(ParcelaVariable)
            .where(
                ParcelaVariable.parcela_id == parcela.id,
                ParcelaVariable.origen == "cruce",
                ParcelaVariable.vigente,
            )
            .values(vigente=False)
        )
        parcela.cruce_estado = None


def en_cola(parcela: Parcela) -> bool:
    return parcela.cruce_solicitado_en is not None


def geometria_para(sesion: Session, parcela: Parcela) -> tuple[dict, bool, float]:
    """(GeoJSON que se cruza, si es aproximación, área en ha). Un punto se cruza como círculo con su área
    declarada, y su resultado queda marcado como aproximación."""
    geo = geometria.a_geojson(to_shape(parcela.geometria))
    if parcela.tipo_geometria != "punto":
        return geo, False, float(parcela.area_calculada_ha)
    area = float(parcela.area_declarada_ha)
    radio_m = math.sqrt(area * 10_000 / math.pi)
    circulo = sesion.execute(
        text(
            "SELECT ST_AsGeoJSON(ST_Buffer(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)::geography, :r, 16)"
            "::geometry, 8)"
        ),
        {"g": json.dumps(geo), "r": radio_m},
    ).scalar_one()
    return json.loads(circulo), True, area


def _fuente(codigos: list[str], momento) -> str:
    capas = "; ".join(f"{catalogo.POR_CODIGO[c].nombre} ({catalogo.POR_CODIGO[c].entidad})" for c in codigos)
    return f"{capas}. Consultada el {momento.astimezone(LIMA):%d/%m/%Y}."


# ---------- Variables desde lo que encontró cada capa ----------


def _elementos(resultados: dict, codigo: str, clave: str = "elementos") -> list:
    return (resultados.get(codigo) or {}).get(clave) or []


def combinar(variable: str, resultados: dict, apoyo: dict) -> tuple[str, dict]:
    """El valor de una variable y su detalle, desde las capas que la deciden y las de apoyo."""
    if variable == "en_anp":
        areas = _elementos(resultados, "sernanp_anp")
        zonas = _elementos(resultados, "sernanp_amortiguamiento")
        valor = "dentro" if areas else "zona_de_amortiguamiento" if zonas else "no"
        detalle = {
            "areas": areas,
            "zonas_de_amortiguamiento": zonas,
            "roces": _elementos(resultados, "sernanp_anp", "roces")
            + _elementos(resultados, "sernanp_amortiguamiento", "roces"),
        }
        if "sernanp_conservacion" in apoyo:
            detalle["areas_de_conservacion"] = _elementos(apoyo, "sernanp_conservacion")
        return valor, detalle
    if variable == "en_tierra_forestal":
        z = resultados["serfor_zonificacion"]
        forestales = z["elementos"]
        valor = "si" if forestales else "no" if z["otras"] or z["zonificados"] else "sin_zonificacion"
        detalle = {
            "zonas": forestales,
            "otras": z["otras"],
            "roces": z["roces"],
            "departamentos": z["departamentos"],
            "zonificados": z["zonificados"],
        }
        if "serfor_modalidad_acceso" in apoyo:
            detalle["cesiones"] = apoyo["serfor_modalidad_acceso"]["cesiones"]
            detalle["cambios_de_uso"] = apoyo["serfor_modalidad_acceso"]["cambios_de_uso"]
        return valor, detalle
    if variable == "en_tierra_comunal":
        comunidades = _elementos(resultados, "idep_comunidades")
        detalle = {"comunidades": comunidades, "roces": _elementos(resultados, "idep_comunidades", "roces")}
        if comunidades:
            detalle |= {
                "comunidad_nombre": comunidades[0].get("nombre"),
                "comunidad_tipo": comunidades[0]["tipo"],
            }
        return ("si" if comunidades else "no"), detalle
    if variable == "junto_a_cuerpo_de_agua":
        cuerpos = _elementos(resultados, "ign_hidrografia")
        detalle = {
            "cuerpos": cuerpos,
            "distancia_maxima_m": resultados["ign_hidrografia"]["distancia_maxima_m"],
        }
        if cuerpos:
            detalle |= {"distancia_m": cuerpos[0]["distancia_m"], "nombre": cuerpos[0].get("nombre")}
        if "ana_faja_marginal" in apoyo:
            detalle["fajas_marginales"] = apoyo["ana_faja_marginal"]["fajas"]
        return ("si" if cuerpos else "no"), detalle
    if variable == "en_patrimonio_cultural":
        monumentos = _elementos(resultados, "sigda_monumentos")
        detalle = {"monumentos": monumentos, "roces": _elementos(resultados, "sigda_monumentos", "roces")}
        return ("si" if monumentos else "no"), detalle
    raise ValueError(f"La variable {variable} no se cruza.")


# ---------- Proceso ----------


def _tomar(sesion: Session) -> Parcela | None:
    """La parcela que espera hace más tiempo. Sale de la cola mientras se cruza (EN_CURSO)."""
    parcela = sesion.scalar(
        select(Parcela)
        .where(
            Parcela.cruce_solicitado_en <= ahora(),
            Parcela.estado == "activa",
            Parcela.habilitacion_estado != "excluida",
        )
        .order_by(Parcela.cruce_solicitado_en)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if parcela is None:
        return None
    parcela.cruce_solicitado_en = ahora() + EN_CURSO
    sesion.commit()
    return parcela


def cruzar(sesion: Session, parcela: Parcela, capas: Capas) -> dict:
    """Consulta cada capa y guarda las variables cuyas capas respondieron. No confirma."""
    from app.services.analisis import huella_parcela  # evita importación circular

    huella = huella_parcela(parcela)
    geo, aproximacion, area = geometria_para(sesion, parcela)
    consulta = Consulta(
        cliente=capas.cliente,
        sesion=sesion,
        geometria=geo,
        area_ha=area,
        departamento=codigo_departamento(parcela.departamento),
        distancia_agua_m=capas.distancia_agua_m,
        dormir=capas.dormir,
    )
    resultados, apoyo, estado_capas = {}, {}, {}
    for grupo, destino in ((capas.activas, resultados), (capas.apoyo, apoyo)):
        for codigo, capa in grupo.items():
            momento = ahora()
            try:
                # Un error de PostGIS con una geometría rara de la capa no arrastra a las demás capas.
                with sesion.begin_nested():
                    destino[codigo] = capa.cruzar(consulta)
                estado_capas[codigo] = {"estado": "hecho", "consultada_en": momento.isoformat()}
            except Exception as exc:
                detalle = exc.detalle if isinstance(exc, ErrorCapa) else f"{type(exc).__name__}: {exc}"[:300]
                estado_capas[codigo] = {
                    "estado": "fallo",
                    "consultada_en": momento.isoformat(),
                    "error": detalle,
                }
                log.warning("El cruce de la parcela %s con %s falló: %s", parcela.id, codigo, detalle)
    return {
        "huella": huella,
        "aproximacion": aproximacion,
        "resultados": resultados,
        "apoyo": apoyo,
        "capas": estado_capas,
        "enviado": consulta.enviado,
    }


def registrar(sesion: Session, parcela: Parcela, cruce: dict, capas: Capas) -> dict[str, str]:
    """Guarda una fila por variable cuyas capas respondieron todas. Devuelve {variable: valor}."""
    from app.services.legalidad import registrar_cruce  # evita importación circular

    valores = {}
    momento = ahora()
    for variable in perfil_legal.CRUZABLES:
        codigos = [c for c in capas.activas if catalogo.POR_CODIGO[c].variable == variable]
        if not codigos or any(cruce["capas"][c]["estado"] != "hecho" for c in codigos):
            continue
        valor, detalle = combinar(variable, cruce["resultados"], cruce["apoyo"])
        detalle |= {"capas": codigos, "aproximacion": cruce["aproximacion"]}
        registrar_cruce(sesion, parcela, variable, valor, detalle, _fuente(codigos, momento))
        valores[variable] = valor
    return valores


def procesar_siguiente(sesion: Session, capas: Capas | None) -> bool:
    """Cruza la parcela que espera hace más tiempo. False si no había ninguna."""
    if capas is None or not capas.activas:
        return False
    parcela = _tomar(sesion)
    if parcela is None:
        return False
    try:
        cruce = cruzar(sesion, parcela, capas)
    except Exception:
        sesion.rollback()
        log.exception("No se pudo cruzar la parcela %s", parcela.id)
        cruce = None
    sesion.refresh(parcela)
    from app.services.analisis import huella_parcela  # evita importación circular

    if cruce is None or cruce["huella"] != huella_parcela(parcela):
        # Falló sin respuesta de las capas, o la geometría cambió mientras se cruzaba: se repite.
        if cruce is None:
            parcela.cruce_solicitado_en = ahora() + ESPERAS[0]
        sesion.commit()
        return True
    valores = registrar(sesion, parcela, cruce, capas)
    anterior = parcela.cruce_estado or {}
    fallaron = [c for c in capas.activas if cruce["capas"][c]["estado"] != "hecho"]
    intentos = (anterior.get("intentos", 0) + 1) if fallaron else 0
    parcela.cruce_estado = {
        "capas": cruce["capas"],
        "aproximacion": cruce["aproximacion"],
        "terminado_en": ahora().isoformat(),
        "intentos": intentos,
    }
    if fallaron and intentos < MAX_INTENTOS:
        parcela.cruce_solicitado_en = ahora() + ESPERAS[intentos - 1]
    else:
        parcela.cruce_solicitado_en = None
    registrar_auditoria(
        None,
        "parcela.cruce",
        "parcela",
        parcela.id,
        {"valores": valores, "fallaron": fallaron, "aproximacion": cruce["aproximacion"]},
        cooperativa_id=parcela.cooperativa_registro_id,
        sesion=sesion,
    )
    sesion.commit()
    from app.services import habilitacion  # evita importación circular

    habilitacion.evaluar(sesion, [parcela])
    return True


def tarea_diaria(sesion: Session) -> int:
    """Vuelve a la cola el cruce que falló, el que nunca corrió y el que tiene más de ANALISIS_VIGENCIA_DIAS
    días."""
    settings = get_settings()
    activas = [c for c in settings.lista_capas_legales if c in catalogo.POR_CODIGO]
    limite = ahora() - timedelta(days=settings.analisis_vigencia_dias)
    parcelas = sesion.scalars(
        select(Parcela).where(
            Parcela.estado == "activa",
            Parcela.habilitacion_estado != "excluida",
            Parcela.cruce_solicitado_en.is_(None),
        )
    )
    solicitadas = 0
    for parcela in parcelas:
        estado = parcela.cruce_estado or {}
        capas = estado.get("capas") or {}
        terminado = estado.get("terminado_en")
        antiguo = terminado is None or terminado < limite.isoformat()
        fallo = any((capas.get(c) or {}).get("estado") != "hecho" for c in activas)
        if antiguo or fallo:
            parcela.cruce_solicitado_en = ahora()
            if fallo:
                estado = dict(estado, intentos=0)
                parcela.cruce_estado = estado
            solicitadas += 1
    sesion.commit()
    return solicitadas


# ---------- Salida ----------


def estado_por_capa(parcela: Parcela) -> list[dict]:
    """Las capas activas con su último resultado: hecho, falló o pendiente."""
    settings = get_settings()
    capas = (parcela.cruce_estado or {}).get("capas") or {}
    salida = []
    for codigo in settings.lista_capas_legales:
        capa = catalogo.POR_CODIGO.get(codigo)
        if capa is None or capa.variable is None:
            continue
        dato = capas.get(codigo) or {}
        salida.append(
            {
                "codigo": codigo,
                "nombre": capa.nombre,
                "entidad": capa.entidad,
                "variable": capa.variable,
                "estado": dato.get("estado", "pendiente"),
                "consultada_en": dato.get("consultada_en"),
                "error": dato.get("error"),
                # Para que la interfaz dibuje la capa en el mapa de la parcela.
                "servicio": capa.servicio,
                "numeros": list(capa.capas),
            }
        )
    return salida
