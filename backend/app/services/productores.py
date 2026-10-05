"""Productores, versión mínima: padrón, alta con afiliación y acceso con DNI.

El productor es único en toda la plataforma y se alcanza a través de su afiliación activa.
La Parte 3 agrega la ficha completa y las parcelas.
"""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth_admin import ClienteAuthAdmin, ErrorAuthAdmin
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.models import Afiliacion, Cooperativa, Perfil, Productor
from app.schemas.productores import AccesoProductor, ProductorNuevo, ProductorSalida
from app.services import cuentas
from app.services.auditoria import registrar_auditoria
from app.services.paginacion import Paginacion, paginar

LIMA = ZoneInfo("America/Lima")


def _consulta(cooperativa_id: uuid.UUID) -> Select:
    return (
        select(Afiliacion, Perfil)
        .join(Productor, Productor.id == Afiliacion.productor_id)
        .outerjoin(Perfil, Perfil.productor_id == Productor.id)
        .where(Afiliacion.cooperativa_id == cooperativa_id, Afiliacion.estado == "activa")
    )


def _salida(afiliacion: Afiliacion, perfil: Perfil | None) -> ProductorSalida:
    productor = afiliacion.productor
    return ProductorSalida(
        id=productor.id,
        dni=productor.dni,
        nombres=productor.nombres,
        apellidos=productor.apellidos,
        telefono=productor.telefono,
        codigo_socio=afiliacion.codigo_socio,
        afiliado_desde=afiliacion.desde,
        consentimiento_datos_en=productor.consentimiento_datos_en,
        consentimiento_origen=productor.consentimiento_origen,
        es_demo=productor.es_demo,
        acceso=AccesoProductor(
            existe=perfil is not None,
            activo=bool(perfil and perfil.activo),
            debe_cambiar_clave=bool(perfil and perfil.debe_cambiar_clave),
            ultimo_acceso_en=perfil.ultimo_acceso_en if perfil else None,
        ),
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
    return [_salida(*fila) for fila in filas], total


def _afiliacion_activa(contexto: Contexto, productor_id: uuid.UUID) -> tuple[Afiliacion, Perfil | None]:
    """Un productor sin afiliación activa en la cooperativa del contexto responde 404."""
    fila = contexto.sesion.execute(
        _consulta(cooperativa_del_contexto(contexto)).where(Afiliacion.productor_id == productor_id)
    ).first()
    if fila is None:
        raise no_encontrado("El productor no existe.")
    return fila[0], fila[1]


def obtener(contexto: Contexto, productor_id: uuid.UUID) -> ProductorSalida:
    return _salida(*_afiliacion_activa(contexto, productor_id))


def crear(contexto: Contexto, datos: ProductorNuevo) -> ProductorSalida:
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
        productor = Productor(
            dni=datos.dni,
            nombres=datos.nombres,
            apellidos=datos.apellidos,
            telefono=datos.telefono or None,
            es_demo=cooperativa.es_demo,
        )
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
