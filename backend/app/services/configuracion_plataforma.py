"""Configuración de plataforma (Parte 9): la clasificación de riesgo del país, que el informe muestra como
contexto (criterio 6). La mantiene el superadministrador. Si está vacía, el informe dice "clasificación del
país no registrada": el sistema no asume un valor."""

from sqlalchemy.orm import Session

from app.contexto import Contexto
from app.fechas import ahora
from app.models import ConfiguracionPlataforma, Perfil
from app.schemas.dex import ConfiguracionPlataformaEntrada, ConfiguracionPlataformaSalida
from app.services.auditoria import aplicar_cambios, registrar_auditoria


def _fila(sesion: Session) -> ConfiguracionPlataforma | None:
    return sesion.get(ConfiguracionPlataforma, 1)


def salida(sesion: Session) -> ConfiguracionPlataformaSalida:
    fila = _fila(sesion)
    if fila is None:
        return ConfiguracionPlataformaSalida(
            clasificacion_pais=None,
            clasificacion_fecha=None,
            clasificacion_referencia=None,
            actualizado_en=None,
            actualizado_por_nombre=None,
        )
    perfil = sesion.get(Perfil, fila.actualizado_por) if fila.actualizado_por else None
    return ConfiguracionPlataformaSalida(
        clasificacion_pais=fila.clasificacion_pais,
        clasificacion_fecha=fila.clasificacion_fecha,
        clasificacion_referencia=fila.clasificacion_referencia,
        actualizado_en=fila.actualizado_en,
        actualizado_por_nombre=f"{perfil.nombres} {perfil.apellidos}".strip() if perfil else None,
    )


def cambiar(contexto: Contexto, datos: ConfiguracionPlataformaEntrada) -> ConfiguracionPlataformaSalida:
    sesion = contexto.sesion
    fila = _fila(sesion)
    if fila is None:
        fila = ConfiguracionPlataforma(id=1)
        sesion.add(fila)
    valores = datos.model_dump()
    if not valores["clasificacion_pais"]:
        valores = {"clasificacion_pais": None, "clasificacion_fecha": None, "clasificacion_referencia": None}
    cambios = aplicar_cambios(fila, valores)
    if cambios:
        fila.actualizado_en = ahora()
        fila.actualizado_por = contexto.usuario_id
        registrar_auditoria(
            contexto, "plataforma.configurar", "configuracion_plataforma", 1, cambios, cooperativa_id=None
        )
    sesion.commit()
    return salida(sesion)
