"""Crea la aplicación FastAPI, configura CORS y errores, y registra los routers."""

import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth import VerificadorJWT
from app.auth_admin import ClienteAuthAdmin, crear_auth_admin
from app.config import Settings, get_settings
from app.contexto import CABECERA_COOPERATIVA
from app.limite import LimitePorIp
from app.routers import (
    auditoria,
    documentos,
    habilitacion,
    health,
    imagenes,
    mi,
    parcelas,
    plataforma,
    proceso,
    productores,
    publico,
    recepcion,
    sesion,
    superposiciones,
    ubigeos,
    usuarios,
)
from app.services import imagenes as servicio_imagenes
from app.services.fuentes import Fuente, registro
from app.storage import ClienteStorage, crear_storage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cacaotrace")

ERRORES_POR_ESTADO = {
    400: ("regla_incumplida", "La solicitud no cumple una regla del sistema."),
    401: ("no_autenticado", "Inicia sesión para continuar."),
    403: ("sin_permiso", "No tienes permiso para esta acción."),
    404: ("no_encontrado", "No encontrado."),
    405: ("metodo_no_permitido", "Método no permitido."),
    409: ("duplicado", "El registro ya existe."),
    422: ("datos_invalidos", "Los datos enviados no son válidos."),
}


def _cuerpo_error(codigo: str, mensaje: str) -> dict:
    return {"error": {"codigo": codigo, "mensaje": mensaje}}


def crear_app(
    settings: Settings | None = None,
    verificador: VerificadorJWT | None = None,
    auth_admin: ClienteAuthAdmin | None = None,
    storage: ClienteStorage | None = None,
    fuentes: dict[str, Fuente] | None = None,
    imagenes_proveedores: servicio_imagenes.Proveedores | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    con_docs = not settings.es_produccion

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        # Parte 4: el bucle de análisis corre dentro de la API (Render gratis no tiene trabajadores aparte).
        trabajador = None
        if settings.analisis_en_segundo_plano and app.state.storage is not None:
            from app.trabajador import Trabajador

            trabajador = Trabajador(app.state.fuentes, app.state.storage)
            trabajador.start()
        elif settings.analisis_en_segundo_plano:
            log.warning("Sin Storage configurado: el análisis de cobertura no se procesa")
        yield
        if trabajador:
            trabajador.detener()

    app = FastAPI(
        title="CacaoTrace API",
        version=settings.git_sha,
        docs_url="/docs" if con_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if con_docs else None,
        lifespan=ciclo_de_vida,
    )
    app.state.settings = settings
    if verificador is None:
        secreto = settings.supabase_jwt_secret.get_secret_value() if settings.supabase_jwt_secret else None
        verificador = VerificadorJWT(settings.supabase_url, jwt_secret=secreto)
    app.state.verificador = verificador
    app.state.auth_admin = auth_admin or crear_auth_admin(settings)
    app.state.storage = storage or crear_storage(settings)
    app.state.fuentes = fuentes if fuentes is not None else registro.construir(settings)
    registro.fijar(app.state.fuentes)
    # Adenda 2 de la Parte 4: Sentinel-2 (Copernicus) y Esri Wayback. Las pruebas fijan los suyos, simulados.
    servicio_imagenes.fijar(imagenes_proveedores or servicio_imagenes.construir(settings))
    app.state.limite_publico = LimitePorIp()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.lista_cors,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", CABECERA_COOPERATIVA],
        max_age=600,
    )

    @app.exception_handler(StarletteHTTPException)
    async def _error_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "codigo" in exc.detail:
            cuerpo = {"error": exc.detail}
        else:
            codigo, mensaje = ERRORES_POR_ESTADO.get(exc.status_code, ("error", "Ocurrió un error."))
            # Los textos por defecto de Starlette vienen en inglés; se reemplazan.
            if isinstance(exc.detail, str) and exc.detail != HTTPStatus(exc.status_code).phrase:
                mensaje = exc.detail
            cuerpo = _cuerpo_error(codigo, mensaje)
        return JSONResponse(cuerpo, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _datos_invalidos(request: Request, exc: RequestValidationError) -> JSONResponse:
        campos = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc") and e["loc"][0] == "body"})
        mensaje = "Los datos enviados no son válidos."
        if campos:
            mensaje = f"Revisa estos campos: {', '.join(campos)}."
        cuerpo = _cuerpo_error("datos_invalidos", mensaje)
        cuerpo["error"]["campos"] = campos
        return JSONResponse(cuerpo, status_code=422)

    @app.exception_handler(Exception)
    async def _error_inesperado(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Error no controlado en %s %s", request.method, request.url.path)
        cuerpo = _cuerpo_error("error_interno", "Ocurrió un error inesperado. Intenta de nuevo.")
        if not settings.es_produccion:
            cuerpo["error"]["detalle"] = repr(exc)
        return JSONResponse(cuerpo, status_code=500)

    for modulo in (
        health,
        sesion,
        plataforma,
        usuarios,
        productores,
        parcelas,
        documentos,
        superposiciones,
        mi,
        auditoria,
        ubigeos,
        habilitacion,
        imagenes,
        recepcion,
        proceso,
        publico,
    ):
        app.include_router(modulo.router)
    return app


app = crear_app()
