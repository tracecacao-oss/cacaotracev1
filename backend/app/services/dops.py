"""El DOP (Parte 5): copia sellada de todo lo que respalda una tanda en el momento de validarla.

Lo que cambie después en el productor, la parcela o el expediente no lo altera. La huella es el SHA-256
de la forma canónica del contenido (app/services/sello.py); un trigger rechaza todo cambio en el
contenido, la huella, el código y la tanda. El PDF se genera una sola vez, al emitir.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import segno
from sqlalchemy import select

from app.catalogos import guia_remision, variedades
from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora
from app.models import Cooperativa, Documento, Dop, Lugar, Parcela, Perfil, Productor, Tanda
from app.schemas.recepcion import DopDetalle, DopPublico, DopSalida, ProductorDeTanda
from app.services import (
    analisis,
    correlativos,
    documentos,
    expediente,
    habilitacion,
    parcelas,
    productores,
    sello,
)
from app.services.auditoria import registrar_auditoria
from app.services.documentos import Archivo
from app.services.fuentes import registro
from app.storage import ClienteStorage, ErrorStorage

# 2: adenda 2 de la Parte 4, las imágenes y la revisión de las parcelas con alerta de análisis.
VERSION_CONTENIDO = 2
NIVEL = {
    "declarado": "Declarado",
    "documentado": "Documentado",
    "verificado_en_fuente": "Verificado en fuente",
}
LEYENDA = (
    "Este documento reúne la información de origen de una tanda de cacao tal como estaba registrada al "
    "emitirse. No es una constancia ni un certificado, y no declara el cumplimiento del Reglamento (UE) "
    "2023/1115"
)


def url_verificacion(codigo: str) -> str:
    return f"{get_settings().url_interfaz.rstrip('/')}/#/verificar/dop/{codigo}"


def _nombre(sesion, perfil_id: uuid.UUID | None) -> str | None:
    if perfil_id is None:
        return None
    perfil = sesion.get(Perfil, perfil_id)
    return f"{perfil.nombres} {perfil.apellidos}" if perfil else None


def _texto(valor: Any) -> Any:
    """Valores listos para JSON: decimales y fechas como texto."""
    if isinstance(valor, dict):
        return {k: _texto(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_texto(v) for v in valor]
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return valor


# ---------- Contenido sellado ----------


def _bloque_productor(contexto: Contexto, productor_id: uuid.UUID) -> dict[str, Any]:
    p = productores.obtener(contexto, productor_id)
    identidad = p.nivel_identidad
    return {
        "dni": {"valor": p.dni, "nivel": identidad},
        "nombres": {"valor": f"{p.nombres} {p.apellidos}", "nivel": identidad},
        "direccion_postal": {"valor": p.direccion_postal, "nivel": "declarado"},
        "correo": {"valor": p.correo_contacto, "nivel": "declarado"},
        "ruc": {"valor": p.ruc, "nivel": "declarado"},
        "ppa": {"registrado": p.ppa_registrado, "codigo": p.ppa_codigo, "nivel": p.nivel_ppa},
        "codigo_agrodigital": p.codigo_agrodigital,
        "codigo_socio": p.codigo_socio,
    }


def _bloque_parcela(contexto: Contexto, parcela: Parcela) -> dict[str, Any]:
    d = parcelas.obtener(contexto, parcela.id)
    procedencia = d.procedencia.model_dump(mode="json") if d.procedencia else None
    return {
        "codigo": d.codigo,
        "nombre": d.nombre,
        "ubicacion": {
            "departamento": d.departamento,
            "provincia": d.provincia,
            "distrito": d.distrito,
            "centro_poblado": d.centro_poblado,
        },
        "tipo_geometria": d.tipo_geometria,
        "geometria": d.geometria,
        "area_calculada_ha": d.area_calculada_ha,
        "area_declarada_ha": d.area_declarada_ha,
        "area_cultivada_ha": d.area_cultivada_ha,
        "midagri": {"estado": d.midagri_estado, "codigo": d.midagri_codigo, "nivel": d.nivel_midagri},
        "procedencia": procedencia,
    }


def _bloque_habilitacion(contexto: Contexto, parcela: Parcela) -> dict[str, Any]:
    estado = habilitacion.obtener(contexto, parcela)
    # Las decisiones vienen de la más reciente a la más antigua: la vigente es la primera de habilitar.
    vigente = next((d for d in estado.decisiones if d.decision == "habilitar"), None)
    return {
        "estado": estado.estado,
        "decision": vigente.model_dump(
            mode="json",
            exclude={"id", "evidencia_visita_id", "evidencia_analisis_id", "evidencia_revision_id"},
        )
        if vigente
        else None,
    }


def _bloque_cobertura(contexto: Contexto, parcela: Parcela) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fuentes = registro.actuales()
    todos = analisis.de_parcelas(contexto.sesion, [parcela.id])[parcela.id]
    elegidos = analisis.ultimos_completados(fuentes, parcela, todos)
    huellas = dict(
        contexto.sesion.execute(
            select(Documento.id, Documento.sha256).where(
                Documento.id.in_([a.respuesta_documento_id for a in elegidos if a.respuesta_documento_id])
            )
        ).all()
    )
    salidas = {s.id: s for s in analisis.salidas(contexto.sesion, fuentes, parcela, elegidos)}
    cobertura = []
    for a in elegidos:
        s = salidas[a.id]
        cobertura.append(
            {
                "fuente": a.fuente,
                "nombre": fuentes[a.fuente].nombre if a.fuente in fuentes else a.fuente,
                "resultado_fuente": a.resultado_fuente,
                "resultado_texto": s.resultado_texto,
                "indicadores": a.indicadores,
                "completado_en": a.completado_en,
                "version": a.version_fuente,
                "es_aproximacion": a.es_aproximacion,
                "vigente": s.vigente,
                "respuesta_sha256": huellas.get(a.respuesta_documento_id),
            }
        )
    convergencia = analisis.convergencia_salida(contexto.sesion, fuentes, parcela).model_dump(mode="json")
    return cobertura, convergencia


def _bloque_expediente(contexto: Contexto, parcela: Parcela) -> dict[str, Any]:
    salida = expediente.salida(contexto.sesion, parcela)
    contadas = expediente.expediente(contexto.sesion, parcela.id).casillas
    casillas = []
    for c in salida.casillas:
        doc = contadas[c.codigo].documento
        casillas.append(
            {
                "codigo": c.codigo,
                "nombre": c.nombre,
                "estado": c.estado,
                "nivel": c.nivel,
                "registro_consultable": c.registro_consultable,
                "documento": {
                    "numero": doc.numero,
                    "entidad_emisora": doc.entidad_emisora,
                    "fecha_emision": doc.fecha_emision,
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "cotejado_en": doc.cotejado_en,
                    "sha256": doc.sha256,
                }
                if doc
                else None,
                "exencion": {"motivo": c.exencion.motivo, "declarada_en": c.exencion.declarada_en}
                if c.exencion and not c.exencion.retirada_en
                else None,
            }
        )
    return {"estado": salida.estado, "faltan": salida.faltan, "casillas": casillas}


def _bloque_tanda(sesion, tanda: Tanda, evaluacion: dict[str, Any]) -> dict[str, Any]:
    lugar = sesion.get(Lugar, tanda.lugar_id)
    guia = evaluacion["guia"]
    return {
        "codigo": tanda.codigo,
        "lugar": {
            "nombre": lugar.nombre,
            "distrito": lugar.distrito,
            "provincia": lugar.provincia,
            "departamento": lugar.departamento,
        },
        "recibida_en": tanda.recibida_en,
        "estado_producto": tanda.estado_producto,
        "peso_kg": tanda.peso_kg,
        "peso_seco_equivalente_kg": evaluacion["peso_seco_equivalente_kg"],
        "numero_sacos": tanda.numero_sacos,
        "humedad_pct": tanda.humedad_pct,
        "variedad": variedades.nombre(tanda.variedad, tanda.variedad_otra),
        "tipo_semilla": tanda.tipo_semilla,
        "cosecha_desde": tanda.cosecha_desde,
        "cosecha_hasta": tanda.cosecha_hasta,
        "guia_remision": {
            "numero": tanda.gre_numero,
            "fecha_emision": tanda.gre_fecha_emision,
            "ruc_emisor": tanda.gre_ruc_emisor,
            "peso_kg": tanda.gre_peso_kg,
            "documento_sha256": guia.sha256 if guia else None,
            "nivel": "documentado",
            "registro_consultable": guia_remision.REGISTRO_CONSULTABLE,
        },
    }


def _no_verificado(contenido: dict[str, Any]) -> list[str]:
    """Lo que el sistema no comprobó, dicho tal cual."""
    lista = []
    procedencia = contenido["parcela"]["procedencia"] or {}
    if not procedencia.get("recorrida_en_campo"):
        lista.append("Las coordenadas de la parcela no fueron recorridas en campo por un técnico.")
    if contenido["productor"]["dni"]["nivel"] == "declarado":
        lista.append("La identidad del productor está declarada, sin copia del DNI.")
    for casilla in contenido["expediente"]["casillas"]:
        if not casilla["documento"]:
            continue
        if not casilla["registro_consultable"]:
            lista.append(f"{casilla['nombre']}: no tiene registro público contra el cual cotejarse.")
        elif casilla["nivel"] != "verificado_en_fuente":
            lista.append(f"{casilla['nombre']}: no se cotejó en su registro.")
    for fuente in contenido["cobertura"]:
        if fuente["es_aproximacion"]:
            lista.append(
                f"{fuente['nombre']}: analizó un círculo con el área declarada (la parcela es un punto)."
            )
        indicadores = fuente.get("indicadores") or {}
        if fuente["fuente"] == "mapbiomas" and indicadores.get("ultimo_anio"):
            lista.append(f"MapBiomas Perú no cubre lo ocurrido después de {indicadores['ultimo_anio']}.")
        if fuente["fuente"] == "mapbiomas" and indicadores.get("pocos_pixeles"):
            lista.append("MapBiomas Perú: la parcela tiene menos de 10 píxeles de 30 m.")
    lista.append(
        "Guía de remisión: no tiene registro público consultable; SUNAT solo la muestra, con Clave SOL, a "
        "quienes figuran en ella."
    )
    lista.append("El sistema no comprueba el vínculo físico entre el grano entregado y la parcela.")
    return lista


def construir_contenido(
    contexto: Contexto,
    tanda: Tanda,
    evaluacion: dict[str, Any],
    nota: str | None,
    codigo: str,
    emitido_en: datetime,
    imagenes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sesion = contexto.sesion
    cooperativa = sesion.get(Cooperativa, tanda.cooperativa_id)
    parcela = sesion.get(Parcela, tanda.parcela_id)
    productor = sesion.get(Productor, tanda.productor_id)
    cobertura, convergencia = _bloque_cobertura(contexto, parcela)
    contenido = {
        "version": VERSION_CONTENIDO,
        "leyenda": LEYENDA,
        "es_demo": bool(cooperativa.es_demo or productor.es_demo),
        "identificacion": {
            "codigo": codigo,
            "cooperativa": {
                "razon_social": cooperativa.razon_social,
                "ruc": cooperativa.ruc,
                "codigo": cooperativa.codigo,
            },
            "emitido_en": emitido_en,
            "registrada_por": _nombre(sesion, tanda.registrada_por),
            "validada_por": _nombre(sesion, contexto.usuario_id),
            "misma_persona": tanda.registrada_por == contexto.usuario_id,
        },
        "productor": _bloque_productor(contexto, productor.id),
        "parcela": _bloque_parcela(contexto, parcela),
        "habilitacion": _bloque_habilitacion(contexto, parcela),
        "cobertura": cobertura,
        "convergencia": convergencia,
        **({"imagenes": imagenes} if imagenes else {}),
        "expediente": _bloque_expediente(contexto, parcela),
        "tanda": _bloque_tanda(sesion, tanda, evaluacion),
        "alertas": {
            "tanda": evaluacion["alertas"],
            "parcela": evaluacion["alertas_parcela"],
            "nota": nota,
        },
    }
    contenido = _texto(contenido)
    contenido["no_verificado"] = _no_verificado(contenido)
    return contenido


def _bloque_imagenes(contexto: Contexto, tanda: Tanda) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Adenda 2 (12): solo para una parcela con la alerta de análisis, sus imágenes de Sentinel-2 anterior al
    corte y reciente, las versiones de Wayback como datos y la revisión de imágenes vigente."""
    from app.services import analisis, imagenes, revisiones_imagenes  # evita importación circular

    sesion = contexto.sesion
    parcela = sesion.get(Parcela, tanda.parcela_id)
    revision = revisiones_imagenes.vigente(
        revisiones_imagenes.de_parcelas(sesion, [parcela.id])[parcela.id], analisis.huella_parcela(parcela)
    )
    resumen = revisiones_imagenes.resumen(revision, revisiones_imagenes.nombre_de(sesion, revision))
    return imagenes.para_dop(sesion, parcela, resumen)


# ---------- Emisión ----------


def emitir(
    contexto: Contexto,
    storage: ClienteStorage,
    tanda: Tanda,
    evaluacion: dict[str, Any],
    nota: str | None,
    momento: datetime,
) -> tuple[Dop, str]:
    """Emite el DOP dentro de la transacción de la validación. Devuelve (dop, ruta del PDF en Storage) para
    que quien llama borre el archivo si la transacción falla."""
    from app.pdf import dop as pdf_dop  # evita cargar fpdf2 al importar

    cooperativa = contexto.sesion.get(Cooperativa, tanda.cooperativa_id)
    anio = momento.astimezone(LIMA).year
    numero = correlativos.siguiente(contexto.sesion, tanda.cooperativa_id, "dop", anio)
    codigo = f"DOP-{cooperativa.codigo}-{anio}-{numero:06d}"
    bloque_imagenes, rutas = _bloque_imagenes(contexto, tanda)
    contenido = construir_contenido(contexto, tanda, evaluacion, nota, codigo, momento, bloque_imagenes)
    huella = sello.huella(contenido)
    dop = Dop(
        cooperativa_id=tanda.cooperativa_id,
        codigo=codigo,
        tanda_id=tanda.id,
        productor_id=tanda.productor_id,
        parcela_id=tanda.parcela_id,
        emitido_en=momento,
        emitido_por=contexto.usuario_id,
        contenido=contenido,
        contenido_sha256=huella,
        estado="vigente",
    )
    contexto.sesion.add(dop)
    contexto.sesion.flush()
    # Las dos imágenes en color natural van dibujadas en el PDF; su huella va en el contenido sellado.
    png = {papel: storage.descargar(ruta) for papel, ruta in rutas.items()}
    pdf = pdf_dop.generar(contenido, huella, url_verificacion(codigo), png)
    documento, ruta = documentos.guardar(
        contexto,
        storage,
        entidad="dop",
        entidad_id=dop.id,
        tipo="dop_pdf",
        archivo=Archivo(nombre=f"{codigo}.pdf", contenido=pdf),
    )
    dop.pdf_documento_id = documento.id
    registrar_auditoria(
        contexto, "dop.emitir", "dop", dop.id, {"codigo": codigo, "tanda": tanda.codigo, "sha256": huella}
    )
    contexto.sesion.flush()
    return dop, ruta


# ---------- Consultas ----------


def dop_visible(contexto: Contexto, dop_id: uuid.UUID) -> Dop:
    dop = contexto.sesion.get(Dop, dop_id)
    if dop is None or dop.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("El DOP no existe.")
    if contexto.rol == "productor" and dop.productor_id != contexto.productor_id:
        raise no_encontrado("El DOP no existe.")
    return dop


def _salidas(sesion, dops: list[Dop]) -> list[DopSalida]:
    if not dops:
        return []
    tandas = {t.id: t for t in sesion.scalars(select(Tanda).where(Tanda.id.in_([d.tanda_id for d in dops])))}
    productores_ = {
        p.id: p
        for p in sesion.scalars(select(Productor).where(Productor.id.in_({d.productor_id for d in dops})))
    }
    parcelas_ = {
        p.id: p for p in sesion.scalars(select(Parcela).where(Parcela.id.in_({d.parcela_id for d in dops})))
    }
    salida = []
    for d in dops:
        t, p, pa = tandas[d.tanda_id], productores_[d.productor_id], parcelas_[d.parcela_id]
        salida.append(
            DopSalida(
                id=d.id,
                codigo=d.codigo,
                estado=d.estado,
                tanda_id=t.id,
                tanda_codigo=t.codigo,
                productor=ProductorDeTanda(id=p.id, dni=p.dni, nombres=p.nombres, apellidos=p.apellidos),
                parcela_codigo=pa.codigo,
                parcela_nombre=pa.nombre,
                peso_kg=t.peso_kg,
                estado_producto=t.estado_producto,
                emitido_en=d.emitido_en,
                contenido_sha256=d.contenido_sha256,
            )
        )
    return salida


def listar(
    contexto: Contexto,
    *,
    estado: str | None = None,
    productor_id: uuid.UUID | None = None,
    parcela_id: uuid.UUID | None = None,
    desde=None,
    hasta=None,
) -> list[DopSalida]:
    from datetime import timedelta

    consulta = select(Dop).where(Dop.cooperativa_id == cooperativa_del_contexto(contexto))
    if contexto.rol == "productor":
        consulta = consulta.where(Dop.productor_id == contexto.productor_id)
    if estado:
        consulta = consulta.where(Dop.estado == estado)
    if productor_id:
        consulta = consulta.where(Dop.productor_id == productor_id)
    if parcela_id:
        consulta = consulta.where(Dop.parcela_id == parcela_id)
    if desde:
        consulta = consulta.where(Dop.emitido_en >= datetime.combine(desde, datetime.min.time(), LIMA))
    if hasta:
        consulta = consulta.where(
            Dop.emitido_en < datetime.combine(hasta, datetime.min.time(), LIMA) + timedelta(days=1)
        )
    dops = list(contexto.sesion.scalars(consulta.order_by(Dop.emitido_en.desc()).limit(500)))
    return _salidas(contexto.sesion, dops)


def matriz_qr(texto: str) -> list[str]:
    return [
        "".join("1" if m else "0" for m in fila) for fila in segno.make(texto, error="m", micro=False).matrix
    ]


def obtener(contexto: Contexto, dop_id: uuid.UUID) -> DopDetalle:
    dop = dop_visible(contexto, dop_id)
    base = _salidas(contexto.sesion, [dop])[0]
    url = url_verificacion(dop.codigo)
    return DopDetalle(
        **base.model_dump(),
        contenido=dop.contenido,
        url_verificacion=url,
        qr=matriz_qr(url),
        anulado_en=dop.anulado_en,
        anulado_por_nombre=_nombre(contexto.sesion, dop.anulado_por),
        motivo_anulacion=dop.motivo_anulacion,
    )


def url_pdf(contexto: Contexto, storage: ClienteStorage, dop_id: uuid.UUID) -> str:
    dop = dop_visible(contexto, dop_id)
    documento = contexto.sesion.get(Documento, dop.pdf_documento_id)
    try:
        return storage.url_firmada(documento.ruta, descarga=f"{dop.codigo}.pdf")
    except ErrorStorage as exc:
        raise error_api(
            503, "archivos_no_disponibles", "No se pudo preparar la descarga. Intenta de nuevo."
        ) from exc


def anular(contexto: Contexto, dop_id: uuid.UUID, motivo: str) -> DopDetalle:
    """Solo antes de que la tanda entre a una corrida de proceso (Parte 6, todavía no existe). El DOP
    conserva su contenido y su PDF; su tanda sigue validada, pero cuenta como anulada."""
    dop = dop_visible(contexto, dop_id)
    if dop.estado == "anulado":
        raise error_api(400, "dop_anulado", "El DOP ya estaba anulado.")
    dop.estado = "anulado"
    dop.anulado_en = ahora()
    dop.anulado_por = contexto.usuario_id
    dop.motivo_anulacion = motivo
    registrar_auditoria(contexto, "dop.anular", "dop", dop.id, {"codigo": dop.codigo, "motivo": motivo})
    contexto.sesion.commit()
    contexto.sesion.refresh(dop)
    return obtener(contexto, dop.id)


def publico(sesion, codigo: str) -> DopPublico:
    """Sin token: solo código, estado, fecha de emisión, huella y razón social. Nada personal."""
    fila = sesion.execute(
        select(Dop, Cooperativa.razon_social)
        .join(Cooperativa, Cooperativa.id == Dop.cooperativa_id)
        .where(Dop.codigo == codigo.strip().upper())
    ).first()
    if fila is None:
        raise no_encontrado("No existe un DOP con ese código.")
    dop, razon_social = fila
    return DopPublico(
        codigo=dop.codigo,
        estado=dop.estado,
        emitido_en=dop.emitido_en,
        contenido_sha256=dop.contenido_sha256,
        cooperativa=razon_social,
    )
