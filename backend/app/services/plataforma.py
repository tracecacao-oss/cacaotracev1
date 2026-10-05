"""Gestión de cooperativas por el equipo CacaoTrace (rol superadmin)."""

import uuid

from sqlalchemy import Select, func, or_, select

from app.auth_admin import ClienteAuthAdmin
from app.contexto import Contexto
from app.errores import error_api, no_encontrado
from app.models import ROLES_PERSONAL, Afiliacion, Cooperativa, Perfil
from app.schemas.plataforma import CooperativaCambios, CooperativaNueva, CooperativaSalida
from app.schemas.usuarios import AdministradorNuevo
from app.services import cuentas
from app.services.auditoria import aplicar_cambios, registrar_auditoria
from app.services.paginacion import Paginacion, paginar


def _conteos() -> tuple:
    usuarios = (
        select(func.count(Perfil.id))
        .where(Perfil.cooperativa_id == Cooperativa.id, Perfil.rol.in_(ROLES_PERSONAL))
        .scalar_subquery()
        .label("usuarios")
    )
    productores = (
        select(func.count(Afiliacion.id))
        .where(Afiliacion.cooperativa_id == Cooperativa.id, Afiliacion.estado == "activa")
        .scalar_subquery()
        .label("productores")
    )
    return usuarios, productores


def _salida(cooperativa: Cooperativa, usuarios: int, productores: int) -> CooperativaSalida:
    return CooperativaSalida.model_validate(cooperativa).model_copy(
        update={"usuarios": usuarios, "productores": productores}
    )


def _consulta(busqueda: str | None) -> Select:
    consulta = select(Cooperativa, *_conteos())
    if busqueda:
        patron = f"%{busqueda.strip()}%"
        consulta = consulta.where(
            or_(
                Cooperativa.razon_social.ilike(patron),
                Cooperativa.nombre_comercial.ilike(patron),
                Cooperativa.ruc.startswith(busqueda.strip()),
            )
        )
    return consulta.order_by(Cooperativa.razon_social)


def listar(contexto: Contexto, busqueda: str | None, paginacion: Paginacion):
    filas, total = paginar(contexto.sesion, _consulta(busqueda), paginacion)
    return [_salida(*fila) for fila in filas], total


def _cooperativa(contexto: Contexto, cooperativa_id: uuid.UUID) -> Cooperativa:
    cooperativa = contexto.sesion.get(Cooperativa, cooperativa_id)
    if cooperativa is None:
        raise no_encontrado("La cooperativa no existe.")
    return cooperativa


def obtener(contexto: Contexto, cooperativa_id: uuid.UUID) -> CooperativaSalida:
    fila = contexto.sesion.execute(_consulta(None).where(Cooperativa.id == cooperativa_id)).first()
    if fila is None:
        raise no_encontrado("La cooperativa no existe.")
    return _salida(*fila)


def _comprobar_ruc_libre(contexto: Contexto, ruc: str, excepto: uuid.UUID | None = None) -> None:
    consulta = select(Cooperativa.id).where(Cooperativa.ruc == ruc)
    if excepto:
        consulta = consulta.where(Cooperativa.id != excepto)
    if contexto.sesion.scalar(consulta) is not None:
        raise error_api(409, "ruc_en_uso", "Ya existe una cooperativa con ese RUC.")


def _datos_administrador(datos: AdministradorNuevo) -> dict:
    return {
        "rol": "admin_cooperativa",
        "nombres": datos.nombres,
        "apellidos": datos.apellidos,
        "correo": datos.correo,
    }


def crear(contexto: Contexto, auth: ClienteAuthAdmin, datos: CooperativaNueva):
    _comprobar_ruc_libre(contexto, datos.ruc)
    cuentas.comprobar_correo_libre(contexto.sesion, datos.administrador.correo)

    cooperativa = Cooperativa(**datos.model_dump(exclude={"administrador"}), estado="activa")
    contexto.sesion.add(cooperativa)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "cooperativa.crear",
        "cooperativa",
        cooperativa.id,
        datos.model_dump(exclude={"administrador"}),
        cooperativa_id=cooperativa.id,
    )
    # crear_cuenta confirma la cooperativa y el administrador juntos, o deshace ambos.
    administrador, clave = cuentas.crear_cuenta(
        contexto,
        auth,
        correo_auth=datos.administrador.correo,
        datos_perfil=_datos_administrador(datos.administrador),
        accion="usuario.crear",
        cooperativa_id=cooperativa.id,
    )
    return obtener(contexto, cooperativa.id), administrador, clave


def editar(contexto: Contexto, cooperativa_id: uuid.UUID, datos: CooperativaCambios) -> CooperativaSalida:
    cooperativa = _cooperativa(contexto, cooperativa_id)
    valores = datos.model_dump(exclude_unset=True)
    nuevo_estado = valores.pop("estado", None)
    if "ruc" in valores:
        _comprobar_ruc_libre(contexto, valores["ruc"], excepto=cooperativa.id)
    # Los campos obligatorios no se vacían con null.
    valores = {k: v for k, v in valores.items() if v is not None or k == "nombre_comercial"}

    cambios = aplicar_cambios(cooperativa, valores)
    if cambios:
        registrar_auditoria(
            contexto,
            "cooperativa.editar",
            "cooperativa",
            cooperativa.id,
            cambios,
            cooperativa_id=cooperativa.id,
        )
    if nuevo_estado and nuevo_estado != cooperativa.estado:
        accion = "cooperativa.suspender" if nuevo_estado == "suspendida" else "cooperativa.reactivar"
        registrar_auditoria(
            contexto,
            accion,
            "cooperativa",
            cooperativa.id,
            {"estado": {"antes": cooperativa.estado, "despues": nuevo_estado}},
            cooperativa_id=cooperativa.id,
        )
        cooperativa.estado = nuevo_estado
    contexto.sesion.commit()
    return obtener(contexto, cooperativa.id)


def crear_administrador(
    contexto: Contexto, auth: ClienteAuthAdmin, cooperativa_id: uuid.UUID, datos: AdministradorNuevo
):
    cooperativa = _cooperativa(contexto, cooperativa_id)
    cuentas.comprobar_correo_libre(contexto.sesion, datos.correo)
    return cuentas.crear_cuenta(
        contexto,
        auth,
        correo_auth=datos.correo,
        datos_perfil=_datos_administrador(datos),
        accion="usuario.crear",
        cooperativa_id=cooperativa.id,
    )


def restablecer_clave_administrador(contexto: Contexto, auth: ClienteAuthAdmin, usuario_id: uuid.UUID) -> str:
    perfil = contexto.sesion.get(Perfil, usuario_id)
    if perfil is None:
        raise no_encontrado("El usuario no existe.")
    if perfil.rol != "admin_cooperativa":
        raise error_api(
            400,
            "solo_administradores",
            "Desde la plataforma solo se restablece a administradores de cooperativa.",
        )
    return cuentas.restablecer_clave(contexto, auth, perfil)
