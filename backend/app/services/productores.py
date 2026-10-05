"""Productores: padrón, ficha con niveles de verificación, afiliación y acceso con DNI.

El productor es único en toda la plataforma y se alcanza a través de su afiliación activa.
Los niveles de verificación y los pendientes no se guardan: se calculan al responder,
según existan documentos vigentes, para que nunca queden desactualizados.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth_admin import ClienteAuthAdmin, ErrorAuthAdmin
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.models import Afiliacion, Cooperativa, Parcela, Perfil, Productor
from app.schemas.parcelas import DocumentoSalida
from app.schemas.productores import (
    AccesoProductor,
    ProductorCambios,
    ProductorDetalle,
    ProductorNuevo,
    ProductorSalida,
    ResumenParcelas,
)
from app.services import cuentas, documentos
from app.services.auditoria import aplicar_cambios, registrar_auditoria
from app.services.paginacion import Paginacion, paginar

LIMA = ZoneInfo("America/Lima")
# Campos que se pueden vaciar con null; los demás son obligatorios.
OPCIONALES = {"ruc", "correo_contacto", "telefono", "ppa_codigo", "codigo_agrodigital", "codigo_socio"}
_AUSENTE = object()


def _consulta(cooperativa_id: uuid.UUID) -> Select:
    activas = (Parcela.productor_id == Productor.id, Parcela.estado == "activa")
    parcelas_activas = select(func.count(Parcela.id)).where(*activas).scalar_subquery()
    area_total = (
        select(
            func.coalesce(
                func.sum(
                    case(
                        (Parcela.tipo_geometria == "poligono", Parcela.area_calculada_ha),
                        else_=Parcela.area_declarada_ha,
                    )
                ),
                0,
            )
        )
        .where(*activas)
        .scalar_subquery()
    )
    return (
        select(
            Afiliacion,
            Perfil,
            parcelas_activas.label("parcelas_activas"),
            area_total.label("area_total"),
            documentos.vigente("productor", Productor.id, "dni").label("tiene_dni"),
            documentos.vigente("productor", Productor.id, "constancia_ppa").label("tiene_ppa"),
        )
        .join(Productor, Productor.id == Afiliacion.productor_id)
        .outerjoin(Perfil, Perfil.productor_id == Productor.id)
        .where(Afiliacion.cooperativa_id == cooperativa_id, Afiliacion.estado == "activa")
    )


def pendientes_de(productor: Productor, tiene_dni: bool, parcelas_activas: int) -> list[str]:
    pendientes = []
    if not tiene_dni:
        pendientes.append("sin_documento_dni")
    if productor.consentimiento_datos_en is None:
        pendientes.append("sin_consentimiento")
    if parcelas_activas == 0:
        pendientes.append("sin_parcelas")
    return pendientes


def _salida(fila, modelo=ProductorSalida, **extra) -> ProductorSalida:
    afiliacion, perfil, parcelas_activas, area_total, tiene_dni, tiene_ppa = fila
    p = afiliacion.productor
    if not p.ppa_registrado:
        nivel_ppa = "no_registrado"
    else:
        nivel_ppa = "documentado" if tiene_ppa else "declarado"
    return modelo(
        id=p.id,
        dni=p.dni,
        nombres=p.nombres,
        apellidos=p.apellidos,
        ruc=p.ruc,
        direccion_postal=p.direccion_postal,
        correo_contacto=p.correo_contacto,
        telefono=p.telefono,
        ppa_registrado=p.ppa_registrado,
        ppa_codigo=p.ppa_codigo,
        codigo_agrodigital=p.codigo_agrodigital,
        codigo_socio=afiliacion.codigo_socio,
        afiliado_desde=afiliacion.desde,
        consentimiento_datos_en=p.consentimiento_datos_en,
        consentimiento_origen=p.consentimiento_origen,
        es_demo=p.es_demo,
        acceso=AccesoProductor(
            existe=perfil is not None,
            activo=bool(perfil and perfil.activo),
            debe_cambiar_clave=bool(perfil and perfil.debe_cambiar_clave),
            ultimo_acceso_en=perfil.ultimo_acceso_en if perfil else None,
        ),
        nivel_identidad="documentado" if tiene_dni else "declarado",
        nivel_ppa=nivel_ppa,
        pendientes=pendientes_de(p, tiene_dni, parcelas_activas),
        parcelas=ResumenParcelas(activas=parcelas_activas, area_total_ha=Decimal(area_total or 0)),
        **extra,
    )


def documento_salida(documento, subido_por_nombre) -> DocumentoSalida:
    return DocumentoSalida.model_validate(documento).model_copy(
        update={"subido_por_nombre": subido_por_nombre, "vigente": documento.anulado_en is None}
    )


def listar(contexto: Contexto, busqueda: str | None, paginacion: Paginacion):
    consulta = _consulta(cooperativa_del_contexto(contexto))
    if busqueda:
        texto = busqueda.strip()
        consulta = consulta.where(
            or_(
                Productor.dni.startswith(texto, autoescape=True),
                func.concat(Productor.nombres, " ", Productor.apellidos).ilike(f"%{texto}%"),
                Afiliacion.codigo_socio.ilike(f"%{texto}%"),
            )
        )
    filas, total = paginar(
        contexto.sesion, consulta.order_by(Productor.apellidos, Productor.nombres), paginacion
    )
    return [_salida(fila) for fila in filas], total


def _fila_activa(contexto: Contexto, productor_id: uuid.UUID):
    """Un productor sin afiliación activa en la cooperativa del contexto responde 404."""
    fila = contexto.sesion.execute(
        _consulta(cooperativa_del_contexto(contexto)).where(Afiliacion.productor_id == productor_id)
    ).first()
    if fila is None:
        raise no_encontrado("El productor no existe.")
    return fila


def _afiliacion_activa(contexto: Contexto, productor_id: uuid.UUID) -> tuple[Afiliacion, Perfil | None]:
    fila = _fila_activa(contexto, productor_id)
    return fila[0], fila[1]


def obtener(contexto: Contexto, productor_id: uuid.UUID) -> ProductorDetalle:
    fila = _fila_activa(contexto, productor_id)
    docs = [
        documento_salida(d, n)
        for d, n in documentos.documentos_de(contexto.sesion, "productor", productor_id)
    ]
    return _salida(fila, ProductorDetalle, documentos=docs)


def crear(contexto: Contexto, datos: ProductorNuevo) -> ProductorDetalle:
    sesion = contexto.sesion
    cooperativa = sesion.get(Cooperativa, contexto.cooperativa_id)
    productor = sesion.scalar(select(Productor).where(Productor.dni == datos.dni))

    if productor is not None:
        activa = sesion.scalar(
            select(Afiliacion).where(Afiliacion.productor_id == productor.id, Afiliacion.estado == "activa")
        )
        if activa is not None and activa.cooperativa_id == cooperativa.id:
            raise error_api(
                409, "productor_ya_registrado", "Este productor ya está registrado en tu cooperativa."
            )
        if activa is not None:
            # Sin revelar cuál es la otra cooperativa.
            raise error_api(
                409, "dni_afiliado_otra_cooperativa", "Este DNI ya está afiliado a otra cooperativa"
            )
    else:
        ficha = datos.model_dump(
            exclude={"codigo_socio", "consentimiento_cooperativa", "version_consentimiento"}
        )
        if not ficha["ppa_registrado"]:
            ficha["ppa_codigo"] = None
        productor = Productor(**ficha, es_demo=cooperativa.es_demo)
        sesion.add(productor)
        sesion.flush()

    afiliacion = Afiliacion(
        productor_id=productor.id,
        cooperativa_id=cooperativa.id,
        codigo_socio=datos.codigo_socio or None,
        estado="activa",
        desde=datetime.now(LIMA).date(),
    )
    sesion.add(afiliacion)
    registrar_auditoria(
        contexto,
        "productor.crear",
        "productor",
        productor.id,
        {
            "dni": productor.dni,
            "nombres": productor.nombres,
            "apellidos": productor.apellidos,
            "codigo_socio": afiliacion.codigo_socio,
        },
    )
    if datos.consentimiento_cooperativa and productor.consentimiento_datos_en is None:
        productor.consentimiento_datos_en = datetime.now(UTC)
        productor.consentimiento_origen = "cooperativa"
        registrar_auditoria(
            contexto,
            "productor.consentimiento",
            "productor",
            productor.id,
            {"origen": "cooperativa", "version_texto": datos.version_consentimiento},
        )
    try:
        sesion.commit()
    except IntegrityError as exc:
        # Otra cooperativa lo afilió al mismo tiempo: el índice único lo impide.
        sesion.rollback()
        raise error_api(
            409, "dni_afiliado_otra_cooperativa", "Este DNI ya está afiliado a otra cooperativa"
        ) from exc
    return obtener(contexto, productor.id)


def editar(
    contexto: Contexto, auth: ClienteAuthAdmin, productor_id: uuid.UUID, datos: ProductorCambios
) -> ProductorDetalle:
    afiliacion, perfil = _afiliacion_activa(contexto, productor_id)
    productor = afiliacion.productor
    valores = {
        k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None or k in OPCIONALES
    }
    motivo = valores.pop("motivo", None)
    codigo_socio = valores.pop("codigo_socio", _AUSENTE)

    cambia_dni = "dni" in valores and valores["dni"] != productor.dni
    if cambia_dni:
        if not motivo:
            raise error_api(422, "motivo_requerido", "Para corregir el DNI escribe el motivo del cambio.")
        if contexto.sesion.scalar(select(Productor.id).where(Productor.dni == valores["dni"])):
            raise error_api(409, "dni_en_uso", "Ese DNI ya está registrado en CacaoTrace.")

    registrado = valores.get("ppa_registrado", productor.ppa_registrado)
    if not registrado:
        valores["ppa_codigo"] = None

    cambios = aplicar_cambios(productor, valores)
    if codigo_socio is not _AUSENTE:
        cambios |= aplicar_cambios(afiliacion, {"codigo_socio": codigo_socio})
    if not cambios:
        return obtener(contexto, productor_id)
    if perfil is not None:
        perfil.nombres, perfil.apellidos = productor.nombres, productor.apellidos

    registrar_auditoria(
        contexto,
        "productor.editar",
        "productor",
        productor.id,
        cambios | ({"motivo": motivo} if cambia_dni else {}),
    )
    if cambia_dni and perfil is not None:
        # El correo técnico de acceso sigue al DNI.
        try:
            auth.cambiar_correo(perfil.id, cuentas.correo_tecnico(productor.dni))
        except ErrorAuthAdmin as exc:
            contexto.sesion.rollback()
            raise error_api(
                503, "autenticacion_no_disponible", "No se pudo actualizar el acceso del productor."
            ) from exc
    try:
        contexto.sesion.commit()
    except IntegrityError as exc:
        contexto.sesion.rollback()
        raise error_api(409, "dni_en_uso", "Ese DNI ya está registrado en CacaoTrace.") from exc
    return obtener(contexto, productor_id)


def editar_telefono(contexto: Contexto, telefono: str | None) -> ProductorDetalle:
    """El productor solo edita su teléfono."""
    afiliacion, _ = _afiliacion_activa(contexto, contexto.productor_id)
    cambios = aplicar_cambios(afiliacion.productor, {"telefono": telefono or None})
    if cambios:
        registrar_auditoria(contexto, "productor.editar", "productor", contexto.productor_id, cambios)
        contexto.sesion.commit()
    return obtener(contexto, contexto.productor_id)


def cerrar_afiliacion(
    contexto: Contexto, auth: ClienteAuthAdmin, productor_id: uuid.UUID, motivo: str | None
) -> None:
    """Un productor no se elimina: se cierra su afiliación y se desactiva su acceso."""
    afiliacion, perfil = _afiliacion_activa(contexto, productor_id)
    afiliacion.estado = "inactiva"
    afiliacion.hasta = datetime.now(LIMA).date()
    registrar_auditoria(
        contexto, "productor.cerrar_afiliacion", "productor", productor_id, {"motivo": motivo}
    )
    if perfil is not None and perfil.activo:
        cuentas.desactivar(
            contexto, auth, perfil, "productor.acceso_desactivar", {"productor_id": productor_id}
        )
    else:
        contexto.sesion.commit()


def crear_acceso(contexto: Contexto, auth: ClienteAuthAdmin, productor_id: uuid.UUID) -> str:
    afiliacion, perfil = _afiliacion_activa(contexto, productor_id)
    productor = afiliacion.productor
    if perfil is not None and perfil.activo:
        raise error_api(409, "acceso_existente", "Este productor ya tiene acceso.")

    if perfil is not None:
        # La cuenta existía desactivada: se reactiva con una nueva contraseña temporal.
        clave = cuentas.generar_clave_temporal()
        perfil.activo = True
        perfil.debe_cambiar_clave = True
        perfil.cooperativa_id = afiliacion.cooperativa_id
        registrar_auditoria(
            contexto,
            "productor.acceso_crear",
            "usuario",
            perfil.id,
            {"productor_id": productor.id, "reactivado": True},
        )
        try:
            auth.cambiar_clave(perfil.id, clave)
            auth.desbloquear(perfil.id)
        except ErrorAuthAdmin as exc:
            contexto.sesion.rollback()
            raise error_api(
                503, "autenticacion_no_disponible", "No se pudo crear el acceso. Intenta de nuevo."
            ) from exc
        contexto.sesion.commit()
        return clave

    _, clave = cuentas.crear_cuenta(
        contexto,
        auth,
        correo_auth=cuentas.correo_tecnico(productor.dni),
        datos_perfil={
            "rol": "productor",
            "nombres": productor.nombres,
            "apellidos": productor.apellidos,
            "correo": None,
            "productor_id": productor.id,
        },
        accion="productor.acceso_crear",
        cooperativa_id=afiliacion.cooperativa_id,
        detalle={"productor_id": productor.id},
    )
    return clave


def _perfil_de_acceso(contexto: Contexto, productor_id: uuid.UUID) -> Perfil:
    _, perfil = _afiliacion_activa(contexto, productor_id)
    if perfil is None:
        raise no_encontrado("El productor no tiene acceso.")
    return perfil


def restablecer_acceso(contexto: Contexto, auth: ClienteAuthAdmin, productor_id: uuid.UUID) -> str:
    perfil = _perfil_de_acceso(contexto, productor_id)
    if not perfil.activo:
        raise error_api(400, "acceso_desactivado", "El acceso está desactivado. Créalo de nuevo.")
    return cuentas.restablecer_clave(contexto, auth, perfil)


def desactivar_acceso(contexto: Contexto, auth: ClienteAuthAdmin, productor_id: uuid.UUID) -> None:
    perfil = _perfil_de_acceso(contexto, productor_id)
    if perfil.activo:
        cuentas.desactivar(
            contexto, auth, perfil, "productor.acceso_desactivar", {"productor_id": perfil.productor_id}
        )
