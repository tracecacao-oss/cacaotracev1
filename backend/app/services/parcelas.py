"""Parcelas: geometría validada, código PA-#####, alertas y superposiciones.

La parcela pertenece al productor, no a la cooperativa: se alcanza solo a través de una
afiliación activa. El personal ve las parcelas de los productores afiliados a su cooperativa
y el productor ve las suyas.
"""

import json
import uuid
from decimal import Decimal

from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError

from app import ubigeo
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import ahora
from app.models import Afiliacion, Auditoria, Documento, Parcela, Perfil, Productor
from app.schemas.parcelas import (
    GeometriaAnalizada,
    HistorialSalida,
    ParcelaCambios,
    ParcelaDatos,
    ParcelaDetalle,
    ParcelaSalida,
    ProductorDeParcela,
    SuperposicionDeParcela,
    SuperposicionPrevista,
)
from app.services import analisis, documentos, geometria, habilitacion, superposiciones
from app.services.auditoria import aplicar_cambios, registrar_auditoria
from app.services.documentos import Archivo
from app.services.expediente import no_excluida
from app.services.fuentes import registro
from app.services.productores import _afiliacion_activa, documento_salida
from app.storage import ClienteStorage

UMBRAL_DISCREPANCIA = Decimal("0.20")
UMBRAL_DIEZ_HA = Decimal("10")
OBLIGATORIOS = {"nombre", "departamento", "provincia", "distrito", "area_cultivada_ha", "midagri_estado"}


# ---------- Acceso ----------


def _productor_visible(contexto: Contexto, productor_id: uuid.UUID) -> Productor:
    if contexto.rol == "productor" and productor_id != contexto.productor_id:
        raise no_encontrado("El productor no existe.")
    afiliacion, _ = _afiliacion_activa(contexto, productor_id)
    return afiliacion.productor


def _visibles(contexto: Contexto) -> Select:
    consulta = select(Parcela).join(
        Afiliacion,
        and_(
            Afiliacion.productor_id == Parcela.productor_id,
            Afiliacion.estado == "activa",
            Afiliacion.cooperativa_id == cooperativa_del_contexto(contexto),
        ),
    )
    if contexto.rol == "productor":
        consulta = consulta.where(Parcela.productor_id == contexto.productor_id)
    return consulta


def parcela_visible(contexto: Contexto, parcela_id: uuid.UUID) -> Parcela:
    parcela = contexto.sesion.scalar(_visibles(contexto).where(Parcela.id == parcela_id))
    if parcela is None:
        raise no_encontrado("La parcela no existe.")
    return parcela


# ---------- Reglas ----------


def _error_geometria(resultado: geometria.Resultado):
    return error_api(400, resultado.error["codigo"], resultado.error["mensaje"])


def _area_total(tipo: str, calculada: Decimal | None, declarada: Decimal | None) -> Decimal | None:
    return calculada if tipo == "poligono" else declarada


def _ha(valor: Decimal | None) -> Decimal | None:
    """Hectáreas con los 4 decimales de la columna numeric(10,4)."""
    return Decimal(valor).quantize(Decimal("0.0001")) if valor is not None else None


def _comprobar_areas(tipo: str, calculada, declarada, cultivada) -> None:
    if tipo == "punto" and declarada is None:
        raise error_api(
            422, "area_declarada_requerida", "Para una parcela marcada como punto indica su área total."
        )
    total = _area_total(tipo, calculada, declarada)
    if total is not None and cultivada > total:
        raise error_api(
            400,
            "area_cultivada_excede",
            f"El área con cacao ({cultivada} ha) no puede ser mayor "
            f"que el área total de la parcela ({total} ha).",
        )


def _nombre_libre(contexto: Contexto, productor_id: uuid.UUID, nombre: str, excepto: uuid.UUID | None = None):
    consulta = select(Parcela.id).where(
        Parcela.productor_id == productor_id, func.lower(Parcela.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(Parcela.id != excepto)
    if contexto.sesion.scalar(consulta):
        raise error_api(409, "nombre_en_uso", f"El productor ya tiene una parcela llamada «{nombre}».")


def _sin_superposicion_propia(productor_id: uuid.UUID, solapes: list[superposiciones.Solape]) -> None:
    propias = [s for s in solapes if s.otra_productor_id == productor_id]
    if propias:
        s = propias[0]
        raise error_api(
            400,
            "superposicion_propia",
            f"La parcela se superpone con otra del mismo productor: {s.otra_codigo} «{s.otra_nombre}». "
            "Corrige el dibujo para que no se crucen.",
        )


def _codigo_nuevo(contexto: Contexto, cooperativa_id: uuid.UUID) -> str:
    """PA- seguido de 5 dígitos, correlativo por cooperativa."""
    contexto.sesion.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:clave))"), {"clave": f"parcelas:{cooperativa_id}"}
    )
    ultimo = contexto.sesion.scalar(
        select(func.max(Parcela.codigo)).where(Parcela.cooperativa_registro_id == cooperativa_id)
    )
    return f"PA-{(int(ultimo[3:]) + 1 if ultimo else 1):05d}"


# ---------- Salidas ----------


def _alertas(parcela: Parcela, abiertas: set, con_sustento: set) -> list[str]:
    alertas = []
    calculada, declarada = parcela.area_calculada_ha, parcela.area_declarada_ha
    if parcela.tipo_geometria == "poligono" and declarada is not None and calculada:
        if abs(declarada - calculada) / calculada > UMBRAL_DISCREPANCIA:
            alertas.append("area_discrepante")
    total = _area_total(parcela.tipo_geometria, calculada, declarada)
    if total is not None and total >= UMBRAL_DIEZ_HA:
        alertas.append("diez_hectareas_o_mas")
    if parcela.id in abiertas:
        alertas.append("superposicion")
    if parcela.midagri_estado != "no_registrada" and parcela.id not in con_sustento:
        alertas.append("sin_sustento_midagri")
    return alertas


def _nivel_midagri(parcela: Parcela, con_sustento: set) -> str:
    if parcela.midagri_estado == "no_registrada":
        return "no_registrada"
    return "documentado" if parcela.id in con_sustento else "declarado"


def salidas(contexto: Contexto, parcelas: list[Parcela]) -> list[ParcelaSalida]:
    ids = [p.id for p in parcelas]
    if not ids:
        return []
    sesion = contexto.sesion
    abiertas = superposiciones.con_superposicion_abierta(sesion, ids)
    con_sustento = set(
        sesion.scalars(
            select(Documento.entidad_id).where(
                Documento.entidad == "parcela",
                Documento.entidad_id.in_(ids),
                Documento.tipo == "sustento_midagri",
                Documento.anulado_en.is_(None),
            )
        )
    )
    productores = {
        p.id: p
        for p in sesion.scalars(select(Productor).where(Productor.id.in_({x.productor_id for x in parcelas})))
    }
    # Parte 4: requisitos y alertas de habilitación. Una parcela habilitada que dejó de cumplir pasa
    # aquí a observada.
    evaluaciones = habilitacion.evaluar(sesion, parcelas)
    resultado = []
    for p in parcelas:
        prod = productores[p.productor_id]
        evaluacion = evaluaciones[p.id]
        resultado.append(
            ParcelaSalida(
                id=p.id,
                codigo=p.codigo,
                productor=ProductorDeParcela(
                    id=prod.id, dni=prod.dni, nombres=prod.nombres, apellidos=prod.apellidos
                ),
                nombre=p.nombre,
                departamento=p.departamento,
                provincia=p.provincia,
                distrito=p.distrito,
                centro_poblado=p.centro_poblado,
                tipo_geometria=p.tipo_geometria,
                geometria=geometria.a_geojson(to_shape(p.geometria)),
                area_calculada_ha=_ha(p.area_calculada_ha),
                area_declarada_ha=_ha(p.area_declarada_ha),
                area_cultivada_ha=_ha(p.area_cultivada_ha),
                area_total_ha=_ha(_area_total(p.tipo_geometria, p.area_calculada_ha, p.area_declarada_ha)),
                origen_geometria=p.origen_geometria,
                midagri_estado=p.midagri_estado,
                midagri_codigo=p.midagri_codigo,
                nivel_midagri=_nivel_midagri(p, con_sustento),
                estado=p.estado,
                alertas=_alertas(p, abiertas, con_sustento) + evaluacion.alertas,
                creado_en=p.creado_en,
                habilitacion_estado=p.habilitacion_estado,
                requisitos_pendientes=evaluacion.faltan,
            )
        )
    return resultado


def _superposiciones_de(contexto: Contexto, parcela: Parcela) -> list[SuperposicionDeParcela]:
    consulta, _, _ = superposiciones.consulta_con_cooperativas()
    filas = contexto.sesion.execute(
        consulta.where(
            or_(
                superposiciones.Superposicion.parcela_a_id == parcela.id,
                superposiciones.Superposicion.parcela_b_id == parcela.id,
            )
        )
    ).all()
    resultado = []
    for s, pa, pb, coop_a, coop_b in filas:
        otra, coop_otra = (pb, coop_b) if pa.id == parcela.id else (pa, coop_a)
        otra_coop = coop_otra != cooperativa_del_contexto(contexto)
        # El productor ve la alerta sin datos de la otra parcela; de otra cooperativa nadie los ve.
        visible = not otra_coop and contexto.rol != "productor"
        resultado.append(
            SuperposicionDeParcela(
                id=s.id,
                tipo=s.tipo,
                estado=s.estado,
                area_ha=s.area_ha,
                porcentaje=s.porcentaje,
                otra_cooperativa=otra_coop,
                otra_parcela={"id": str(otra.id), "codigo": otra.codigo, "nombre": otra.nombre}
                if visible
                else None,
            )
        )
    return resultado


def _historial(contexto: Contexto, parcela: Parcela) -> list[HistorialSalida]:
    nombre = func.concat(Perfil.nombres, " ", Perfil.apellidos)
    filas = contexto.sesion.execute(
        select(Auditoria, nombre)
        .outerjoin(Perfil, Perfil.id == Auditoria.usuario_id)
        .where(
            or_(
                and_(Auditoria.entidad == "parcela", Auditoria.entidad_id == str(parcela.id)),
                and_(
                    Auditoria.entidad == "documento",
                    Auditoria.detalle["entidad_id"].astext == str(parcela.id),
                ),
            )
        )
        .order_by(Auditoria.ocurrido_en.desc(), Auditoria.id.desc())
    ).all()
    return [
        HistorialSalida(ocurrido_en=a.ocurrido_en, accion=a.accion, usuario_nombre=n, detalle=a.detalle)
        for a, n in filas
    ]


def obtener(contexto: Contexto, parcela_id: uuid.UUID) -> ParcelaDetalle:
    parcela = parcela_visible(contexto, parcela_id)
    base = salidas(contexto, [parcela])[0]
    docs = [
        documento_salida(d, n) for d, n in documentos.documentos_de(contexto.sesion, "parcela", parcela.id)
    ]
    evaluacion = habilitacion.evaluar(contexto.sesion, [parcela])[parcela.id]
    return ParcelaDetalle(
        **base.model_dump(),
        documentos=docs,
        superposiciones=_superposiciones_de(contexto, parcela),
        historial=_historial(contexto, parcela) if contexto.rol != "productor" else [],
        procedencia=evaluacion.procedencia.model_dump(),
    )


def listar(
    contexto: Contexto,
    *,
    productor_id: uuid.UUID | None = None,
    estado: str | None = None,
    alerta: str | None = None,
) -> list[ParcelaSalida]:
    consulta = _visibles(contexto)
    if productor_id:
        consulta = consulta.where(Parcela.productor_id == productor_id)
    if estado:
        consulta = consulta.where(Parcela.estado == estado)
    parcelas = list(contexto.sesion.scalars(consulta.order_by(Parcela.codigo)))
    resultado = salidas(contexto, parcelas)
    if alerta:
        resultado = [p for p in resultado if alerta in p.alertas]
    return resultado


def coleccion_geojson(contexto: Contexto, parcelas: list[ParcelaSalida]) -> dict:
    """FeatureCollection para el mapa de parcelas de la cooperativa."""

    def estado_mapa(p: ParcelaSalida) -> str:
        if "superposicion" in p.alertas:
            return "superposicion"
        return "con_alertas" if p.alertas else "sin_alertas"

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": p.geometria,
                "properties": {
                    "parcela_id": str(p.id),
                    "codigo": p.codigo,
                    "nombre": p.nombre,
                    "productor": f"{p.productor.nombres} {p.productor.apellidos}",
                    "tipo_geometria": p.tipo_geometria,
                    "area_ha": float(p.area_total_ha) if p.area_total_ha is not None else None,
                    "alertas": p.alertas,
                    "estado_mapa": estado_mapa(p),
                },
            }
            for p in parcelas
        ],
    }


def exportar_geojson(contexto: Contexto, parcela_id: uuid.UUID) -> dict:
    """Feature sin datos personales; 8 decimales y anillo en sentido antihorario."""
    parcela = parcela_visible(contexto, parcela_id)
    geojson = contexto.sesion.scalar(
        select(func.ST_AsGeoJSON(func.ST_ForcePolygonCCW(Parcela.geometria), 8)).where(
            Parcela.id == parcela.id
        )
    )
    total = _area_total(parcela.tipo_geometria, parcela.area_calculada_ha, parcela.area_declarada_ha)
    return {
        "type": "Feature",
        "geometry": json.loads(geojson),
        "properties": {
            "parcela_id": str(parcela.id),
            "nombre": parcela.nombre,
            "tipo_geometria": parcela.tipo_geometria,
            "area_ha": float(total) if total is not None else None,
        },
    }


# ---------- Archivo ----------


def _previstas(
    contexto: Contexto, productor: Productor, r: geometria.Resultado, excluir: uuid.UUID | None
) -> list[SuperposicionPrevista]:
    solapes = superposiciones.detectar(
        contexto.sesion,
        wkt=r.geometria.wkt,
        tipo=r.tipo,
        area_ha=r.area_ha,
        es_demo=productor.es_demo,
        excluir=excluir,
    )
    if not solapes:
        return []
    de_la_cooperativa = set(
        contexto.sesion.scalars(
            select(Afiliacion.productor_id).where(
                Afiliacion.productor_id.in_({s.otra_productor_id for s in solapes}),
                Afiliacion.cooperativa_id == cooperativa_del_contexto(contexto),
                Afiliacion.estado == "activa",
            )
        )
    )
    previstas = []
    for s in solapes:
        propia = s.otra_productor_id == productor.id
        visible = s.otra_productor_id in de_la_cooperativa and (propia or contexto.rol != "productor")
        previstas.append(
            SuperposicionPrevista(
                propia=propia,
                otra_cooperativa=s.otra_productor_id not in de_la_cooperativa,
                codigo=s.otra_codigo if visible else None,
                nombre=s.otra_nombre if visible else None,
                tipo=s.tipo,
                area_ha=s.area_ha,
                porcentaje=s.porcentaje,
            )
        )
    return previstas


def analizar(
    contexto: Contexto,
    archivo: Archivo,
    productor_id: uuid.UUID | None = None,
    excluir: uuid.UUID | None = None,
) -> list[GeometriaAnalizada]:
    """Devuelve las geometrías del archivo con sus validaciones. No guarda nada.

    Con productor_id también anticipa las superposiciones que se abrirían al guardar
    (excluir: la parcela que se está editando)."""
    try:
        entidades = geometria.leer_archivo(archivo.nombre, archivo.contenido)
    except geometria.ErrorArchivo as exc:
        raise documentos.error_de_archivo(exc) from exc
    productor = _productor_visible(contexto, productor_id) if productor_id else None
    resultado = []
    for i, (nombre, geo) in enumerate(entidades):
        r = geometria.validar(contexto.sesion, geo, indice=i, nombre=nombre)
        resultado.append(
            GeometriaAnalizada(
                indice=i,
                nombre=nombre,
                tipo=r.tipo,
                area_ha=r.area_ha,
                geometria=geometria.a_geojson(r.geometria) if r.geometria is not None else None,
                valida=r.valida,
                errores=r.errores,
                superposiciones=_previstas(contexto, productor, r, excluir) if productor and r.valida else [],
            )
        )
    return resultado


# ---------- Crear, editar y desactivar ----------


def crear(
    contexto: Contexto,
    storage: ClienteStorage,
    productor_id: uuid.UUID,
    datos: ParcelaDatos,
    *,
    geometria_dibujada: dict | None = None,
    archivo: Archivo | None = None,
    indice: int | None = None,
) -> ParcelaDetalle:
    sesion = contexto.sesion
    productor = _productor_visible(contexto, productor_id)
    valores = datos.model_dump()
    ubigeo.normalizar(valores)

    if archivo is not None:
        try:
            entidades = geometria.leer_archivo(archivo.nombre, archivo.contenido)
        except geometria.ErrorArchivo as exc:
            raise documentos.error_de_archivo(exc) from exc
        if indice is None or not 0 <= indice < len(entidades):
            raise error_api(400, "indice_invalido", "Elige una de las geometrías del archivo.")
        geo, origen = entidades[indice][1], "archivo"
    elif geometria_dibujada:
        geo, origen = geometria_dibujada, "dibujada"
    else:
        raise error_api(422, "geometria_requerida", "Dibuja la parcela en el mapa o sube un archivo.")

    r = geometria.validar(sesion, geo, indice=indice or 0, area_declarada_ha=datos.area_declarada_ha)
    if not r.valida:
        raise _error_geometria(r)
    _comprobar_areas(r.tipo, r.area_ha, datos.area_declarada_ha, datos.area_cultivada_ha)
    _nombre_libre(contexto, productor.id, datos.nombre)
    solapes = superposiciones.detectar(
        sesion, wkt=r.geometria.wkt, tipo=r.tipo, area_ha=r.area_ha, es_demo=productor.es_demo
    )
    _sin_superposicion_propia(productor.id, solapes)

    parcela_id = uuid.uuid4()
    ruta = None
    try:
        documento = None
        if archivo is not None:
            documento, ruta = documentos.guardar(
                contexto,
                storage,
                entidad="parcela",
                entidad_id=parcela_id,
                tipo="archivo_geometria",
                archivo=archivo,
                tipo_mime=geometria.tipo_mime_de(archivo.nombre),
            )
        cooperativa_id = cooperativa_del_contexto(contexto)
        parcela = Parcela(
            id=parcela_id,
            codigo=_codigo_nuevo(contexto, cooperativa_id),
            productor_id=productor.id,
            **valores,
            tipo_geometria=r.tipo,
            geometria=from_shape(r.geometria, srid=4326),
            area_calculada_ha=r.area_ha,
            origen_geometria=origen,
            archivo_documento_id=documento.id if documento else None,
            registrada_por=contexto.usuario_id,
            registrada_por_rol=contexto.rol,
            cooperativa_registro_id=cooperativa_id,
            geometria_actualizada_en=ahora(),
        )
        sesion.add(parcela)
        sesion.flush()
        superposiciones.recalcular(sesion, parcela, solapes, motivo=None)
        # Parte 4: el análisis de cobertura se lanza solo al crear la parcela.
        analisis.solicitar(sesion, registro.actuales(), parcela)
        registrar_auditoria(
            contexto,
            "parcela.crear",
            "parcela",
            parcela.id,
            {
                "codigo": parcela.codigo,
                "nombre": parcela.nombre,
                "productor_id": productor.id,
                "tipo_geometria": r.tipo,
                "origen": origen,
                "area_total_ha": _area_total(r.tipo, r.area_ha, datos.area_declarada_ha),
                "superposiciones": len(solapes),
            },
        )
        sesion.commit()
    except IntegrityError as exc:
        sesion.rollback()
        if ruta:
            documentos.descartar(storage, ruta)
        raise error_api(409, "nombre_en_uso", "El productor ya tiene una parcela con ese nombre.") from exc
    except Exception:
        sesion.rollback()
        if ruta:
            documentos.descartar(storage, ruta)
        raise
    return obtener(contexto, parcela_id)


def editar(contexto: Contexto, parcela_id: uuid.UUID, datos: ParcelaCambios) -> ParcelaDetalle:
    sesion = contexto.sesion
    parcela = parcela_visible(contexto, parcela_id)
    no_excluida(parcela)
    if parcela.estado != "activa":
        raise error_api(400, "parcela_inactiva", "La parcela está inactiva y no se puede editar.")
    valores = {
        k: v
        for k, v in datos.model_dump(exclude_unset=True).items()
        if v is not None or k not in OBLIGATORIOS
    }
    nueva_geometria = valores.pop("geometria", None)
    motivo = valores.pop("motivo", None)
    ubigeo.normalizar(valores, parcela)
    productor = sesion.get(Productor, parcela.productor_id)

    declarada = valores.get("area_declarada_ha", parcela.area_declarada_ha)
    tipo, calculada, resultado, solapes = parcela.tipo_geometria, parcela.area_calculada_ha, None, []
    if nueva_geometria is not None:
        if not motivo:
            raise error_api(
                422, "motivo_requerido", "Para cambiar la geometría escribe el motivo del cambio."
            )
        resultado = geometria.validar(sesion, nueva_geometria, area_declarada_ha=declarada)
        if not resultado.valida:
            raise _error_geometria(resultado)
        tipo, calculada = resultado.tipo, resultado.area_ha
        solapes = superposiciones.detectar(
            sesion,
            wkt=resultado.geometria.wkt,
            tipo=tipo,
            area_ha=calculada,
            es_demo=productor.es_demo,
            excluir=parcela.id,
        )
        _sin_superposicion_propia(parcela.productor_id, solapes)
    elif tipo == "punto" and declarada is not None and declarada >= geometria.AREA_POLIGONO_OBLIGATORIO_HA:
        raise error_api(400, "poligono_requerido", geometria.MENSAJES["poligono_requerido"])

    _comprobar_areas(tipo, calculada, declarada, valores.get("area_cultivada_ha", parcela.area_cultivada_ha))
    if "nombre" in valores and valores["nombre"].lower() != parcela.nombre.lower():
        _nombre_libre(contexto, parcela.productor_id, valores["nombre"], excepto=parcela.id)

    cambios = aplicar_cambios(parcela, valores)
    if resultado is not None:
        anterior = to_shape(parcela.geometria)
        registrar_auditoria(
            contexto,
            "parcela.editar_geometria",
            "parcela",
            parcela.id,
            {
                "motivo": motivo,
                "geometria_anterior": anterior.wkt,
                "tipo_anterior": parcela.tipo_geometria,
                "area_calculada_anterior": parcela.area_calculada_ha,
                "area_calculada_nueva": calculada,
            },
        )
        parcela.geometria = from_shape(resultado.geometria, srid=4326)
        parcela.tipo_geometria, parcela.area_calculada_ha = tipo, calculada
        parcela.origen_geometria, parcela.archivo_documento_id = "dibujada", None
        parcela.geometria_actualizada_en = ahora()
        sesion.flush()
        superposiciones.recalcular(sesion, parcela, solapes, motivo="Se corrigió la geometría.")
        # Parte 4: los análisis previos quedan obsoletos y se solicita uno nuevo.
        analisis.solicitar(sesion, registro.actuales(), parcela)
    if cambios:
        registrar_auditoria(contexto, "parcela.editar", "parcela", parcela.id, cambios)
    sesion.commit()
    return obtener(contexto, parcela.id)


def desactivar(contexto: Contexto, parcela_id: uuid.UUID) -> ParcelaDetalle:
    """Una parcela no se elimina; pasa a inactiva y sus superposiciones abiertas se cierran."""
    parcela = parcela_visible(contexto, parcela_id)
    no_excluida(parcela)
    if parcela.estado == "inactiva":
        return obtener(contexto, parcela.id)
    parcela.estado = "inactiva"
    superposiciones.cerrar_por_desactivacion(contexto.sesion, parcela.id)
    registrar_auditoria(contexto, "parcela.desactivar", "parcela", parcela.id, {"codigo": parcela.codigo})
    contexto.sesion.commit()
    return obtener(contexto, parcela.id)
