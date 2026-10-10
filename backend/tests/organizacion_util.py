"""Ayudas para las pruebas de la adenda 6: política de la organización, actuaciones de diligencia y
declaración aduanera, registradas directo en la base."""

import itertools
import uuid
from datetime import date
from decimal import Decimal

from app.catalogos import actuaciones, requisitos_organizacion
from app.fechas import hoy_lima
from app.models import (
    ActuacionDiligencia,
    ActuacionProductor,
    Cooperativa,
    DeclaracionAduanera,
    Documento,
    Lote,
    Perfil,
    PoliticaOrganizacion,
)

_contador = itertools.count(1)
# Una subpartida de prueba que empieza con la partida 1801 de la orden.
SUBPARTIDA = "1801000000"
DESCRIPCION = "Se revisó la fuente pública con el equipo técnico y se anotaron los casos que aparecieron."
RESULTADO = "No se encontraron casos en la zona de los productores."


def documento(
    sesion, cooperativa_id, entidad: str, entidad_id, tipo: str, perfil: Perfil, **datos
) -> Documento:
    n = next(_contador)
    doc = Documento(
        cooperativa_id=cooperativa_id,
        entidad=entidad,
        entidad_id=entidad_id,
        tipo=tipo,
        ruta=f"prueba/{entidad}/{n}.pdf",
        nombre_original=f"{tipo}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=100,
        sha256=f"{n + 9 * 10**6:064x}",
        subido_por=perfil.id,
        **datos,
    )
    sesion.add(doc)
    sesion.flush()
    return doc


def politica(
    sesion,
    coop: Cooperativa,
    perfil: Perfil,
    temas: tuple[str, ...] = requisitos_organizacion.CODIGOS_TEMAS,
    *,
    adoptada_en: date | None = None,
) -> PoliticaOrganizacion:
    doc = documento(
        sesion, coop.id, "cooperativa", coop.id, "politica_organizacion", perfil, fecha_emision=adoptada_en
    )
    fila = PoliticaOrganizacion(
        cooperativa_id=coop.id,
        documento_id=doc.id,
        temas=list(temas),
        adoptada_en=adoptada_en or hoy_lima(),
        organo="Consejo de Administración",
        version_plantilla=1,
        registrada_por=perfil.id,
    )
    sesion.add(fila)
    sesion.flush()
    return fila


def politica_completa(sesion, coop: Cooperativa, perfil: Perfil) -> PoliticaOrganizacion:
    """Los cinco temas y el contacto del canal: el requisito de integridad queda sustentado."""
    coop.canal_denuncias_contacto = "Buzón de prueba en la oficina"
    return politica(sesion, coop, perfil)


def actuacion(
    sesion,
    coop: Cooperativa,
    perfil: Perfil,
    *,
    tipo: str = "capacitacion",
    temas: tuple[str, ...] = actuaciones.CODIGOS_TEMAS,
    fecha: date | None = None,
    productores: tuple[uuid.UUID, ...] = (),
) -> ActuacionDiligencia:
    fila = ActuacionDiligencia(
        cooperativa_id=coop.id,
        tipo=tipo,
        temas=list(temas),
        fecha=fecha or hoy_lima(),
        descripcion=DESCRIPCION,
        contraparte="Fuente de prueba" if actuaciones.TIPOS_POR_CODIGO[tipo].pide_contraparte else None,
        resultado=RESULTADO,
        registrada_por=perfil.id,
    )
    sesion.add(fila)
    sesion.flush()
    for productor_id in productores:
        sesion.add(ActuacionProductor(actuacion_id=fila.id, productor_id=productor_id))
    sesion.flush()
    return fila


def diligencia_completa(sesion, coop: Cooperativa, perfil: Perfil) -> None:
    """Política con los cinco temas y su contacto, y una actuación vigente en los ocho temas."""
    politica_completa(sesion, coop, perfil)
    actuacion(sesion, coop, perfil)


def dam(
    sesion,
    lote_id,
    perfil: Perfil,
    *,
    numero: str = "DAM-PRUEBA-0001",
    peso: Decimal | None = None,
    subpartida: str = SUBPARTIDA,
) -> Documento:
    """Adenda 7: el archivo y su declaración aduanera, con el peso del lote si no se da otro."""
    doc = documento(
        sesion,
        perfil.cooperativa_id,
        "lote",
        lote_id,
        "dam",
        perfil,
        numero=numero,
        entidad_emisora="SUNAT",
        fecha_emision=hoy_lima(),
    )
    lote = sesion.get(Lote, lote_id)
    sesion.add(
        DeclaracionAduanera(
            lote_id=lote_id,
            documento_id=doc.id,
            numero=numero,
            fecha_numeracion=hoy_lima(),
            peso_neto_kg=peso if peso is not None else lote.masa_neta_kg,
            subpartida=subpartida,
            registrada_por=perfil.id,
            posterior_al_dex=lote.estado == "cerrado",
        )
    )
    sesion.flush()
    return doc
