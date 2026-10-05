"""Superposición entre parcelas: una misma tierra no debe respaldar el cacao de dos productores.

Cada vez que se guarda una geometría se compara con todas las parcelas activas de la
plataforma, de todas las cooperativas. Las de una cooperativa de demostración solo se
comparan entre sí (Parte 10).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session, aliased

from app.errores import error_api, no_encontrado
from app.models import Afiliacion, Cooperativa, Parcela, Productor, Superposicion
from app.services.auditoria import registrar_auditoria

# Por debajo de estos umbrales se considera imprecisión de linderos.
UMBRAL_AREA_HA = Decimal("0.05")
UMBRAL_PORCENTAJE = Decimal("5")
SIN_PARCELA = uuid.UUID(int=0)


@dataclass(frozen=True)
class Solape:
    otra_id: uuid.UUID
    otra_productor_id: uuid.UUID
    otra_codigo: str
    otra_nombre: str
    tipo: str
    area_ha: Decimal | None
    porcentaje: Decimal | None


def _q(valor, decimales: str) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal(decimales), rounding=ROUND_HALF_UP)


def detectar(
    sesion: Session,
    *,
    wkt: str,
    tipo: str,
    area_ha: Decimal | None,
    es_demo: bool,
    excluir: uuid.UUID | None = None,
) -> list[Solape]:
    filas = sesion.execute(
        text(
            """
            WITH g AS (SELECT ST_GeomFromText(:wkt, 4326) AS geom)
            SELECT o.id, o.productor_id, o.codigo, o.nombre, o.tipo_geometria, o.area_calculada_ha,
                   CASE WHEN o.tipo_geometria = 'poligono' AND :tipo = 'poligono'
                        THEN ST_Area(ST_Intersection(o.geometria, g.geom)::geography) / 10000 END AS comun
            FROM parcelas o
            JOIN productores p ON p.id = o.productor_id
            CROSS JOIN g
            WHERE o.estado = 'activa' AND o.id <> :excluir AND p.es_demo = :es_demo
              AND ST_Intersects(o.geometria, g.geom)
            """
        ),
        {"wkt": wkt, "tipo": tipo, "es_demo": es_demo, "excluir": excluir or SIN_PARCELA},
    ).all()

    solapes = []
    for fila in filas:
        if tipo == "punto" and fila.tipo_geometria == "punto":
            continue  # dos puntos no se comparan
        if tipo == "poligono" and fila.tipo_geometria == "poligono":
            comun = _q(fila.comun or 0, "0.0001")
            menor = min(area_ha, fila.area_calculada_ha)
            porcentaje = _q(comun / menor * 100, "0.01") if menor else Decimal("0")
            if comun < UMBRAL_AREA_HA and porcentaje < UMBRAL_PORCENTAJE:
                continue
            solapes.append(
                Solape(
                    fila.id,
                    fila.productor_id,
                    fila.codigo,
                    fila.nombre,
                    "poligono_poligono",
                    comun,
                    porcentaje,
                )
            )
        else:
            solapes.append(
                Solape(fila.id, fila.productor_id, fila.codigo, fila.nombre, "punto_en_poligono", None, None)
            )
    return solapes


def _par(uno: uuid.UUID, otro: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (uno, otro) if uno < otro else (otro, uno)


def recalcular(sesion: Session, parcela: Parcela, solapes: list[Solape], motivo: str) -> None:
    """Deja la tabla al día para esta parcela: abre las nuevas, actualiza las vigentes y
    marca como resueltas las que desaparecieron."""
    ahora = datetime.now(UTC)
    vigentes = {s.otra_id: s for s in solapes}
    existentes = sesion.scalars(
        select(Superposicion).where(
            or_(Superposicion.parcela_a_id == parcela.id, Superposicion.parcela_b_id == parcela.id)
        )
    ).all()
    for fila in existentes:
        otra = fila.parcela_b_id if fila.parcela_a_id == parcela.id else fila.parcela_a_id
        solape = vigentes.pop(otra, None)
        if solape is None:
            if fila.estado != "resuelta":
                fila.estado, fila.cerrada_en, fila.cerrada_por, fila.nota = "resuelta", ahora, None, motivo
            continue
        fila.tipo, fila.area_ha, fila.porcentaje = solape.tipo, solape.area_ha, solape.porcentaje
        if fila.estado != "abierta":
            # La tierra volvió a superponerse o cambió: se revisa de nuevo.
            fila.estado, fila.cerrada_en, fila.cerrada_por, fila.nota = "abierta", None, None, None
    for solape in vigentes.values():
        a, b = _par(parcela.id, solape.otra_id)
        sesion.add(
            Superposicion(
                parcela_a_id=a,
                parcela_b_id=b,
                tipo=solape.tipo,
                area_ha=solape.area_ha,
                porcentaje=solape.porcentaje,
                estado="abierta",
            )
        )


def cerrar_por_desactivacion(sesion: Session, parcela_id: uuid.UUID) -> None:
    ahora = datetime.now(UTC)
    for fila in sesion.scalars(
        select(Superposicion).where(
            or_(Superposicion.parcela_a_id == parcela_id, Superposicion.parcela_b_id == parcela_id),
            Superposicion.estado == "abierta",
        )
    ):
        fila.estado, fila.cerrada_en, fila.nota = "resuelta", ahora, "Una de las parcelas se desactivó."


def con_superposicion_abierta(sesion: Session, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    filas = sesion.execute(
        select(Superposicion.parcela_a_id, Superposicion.parcela_b_id).where(
            Superposicion.estado == "abierta",
            or_(Superposicion.parcela_a_id.in_(ids), Superposicion.parcela_b_id.in_(ids)),
        )
    ).all()
    buscadas = set(ids)
    return {i for fila in filas for i in fila if i in buscadas}


def consulta_con_cooperativas():
    """Superposición con sus dos parcelas y la cooperativa actual de cada una."""
    pa, pb = aliased(Parcela), aliased(Parcela)
    afa, afb = aliased(Afiliacion), aliased(Afiliacion)
    consulta = (
        select(Superposicion, pa, pb, afa.cooperativa_id.label("coop_a"), afb.cooperativa_id.label("coop_b"))
        .join(pa, pa.id == Superposicion.parcela_a_id)
        .join(pb, pb.id == Superposicion.parcela_b_id)
        .outerjoin(afa, and_(afa.productor_id == pa.productor_id, afa.estado == "activa"))
        .outerjoin(afb, and_(afb.productor_id == pb.productor_id, afb.estado == "activa"))
    )
    return consulta, afa, afb


# ---------- Listados y aceptación ----------


def _vista(sesion: Session, fila, cooperativa_id: uuid.UUID | None, completa: bool) -> dict:
    """Superposición vista desde una cooperativa. De otra cooperativa solo se ve la parcela propia,
    el área común y el aviso. Con completa=True (superadmin) se ven ambas."""
    s, pa, pb, coop_a, coop_b = fila
    entre = coop_a != coop_b
    visibles = [(p, c) for p, c in ((pa, coop_a), (pb, coop_b)) if completa or c == cooperativa_id]
    nombres_prod = {
        p.id: f"{p.nombres} {p.apellidos}"
        for p in sesion.scalars(
            select(Productor).where(Productor.id.in_([p.productor_id for p, _ in visibles]))
        )
    }
    nombres_coop = {}
    if completa:
        nombres_coop = {
            c.id: c.nombre_comercial or c.razon_social
            for c in sesion.scalars(select(Cooperativa).where(Cooperativa.id.in_([coop_a, coop_b])))
        }
    geometrias = dict(
        sesion.execute(
            select(Parcela.id, func.ST_AsGeoJSON(Parcela.geometria, 8)).where(
                Parcela.id.in_([p.id for p, _ in visibles])
            )
        ).all()
    )
    interseccion = sesion.scalar(
        select(func.ST_AsGeoJSON(func.ST_Intersection(pa.geometria, pb.geometria), 8))
    )
    return {
        "id": s.id,
        "tipo": s.tipo,
        "estado": s.estado,
        "area_ha": s.area_ha,
        "porcentaje": s.porcentaje,
        "entre_cooperativas": entre,
        "aviso": "Superposición con una parcela de otra cooperativa" if entre and not completa else None,
        "parcelas": [
            {
                "id": p.id,
                "codigo": p.codigo,
                "nombre": p.nombre,
                "productor_nombre": nombres_prod.get(p.productor_id, ""),
                "cooperativa_id": c,
                "cooperativa_nombre": nombres_coop.get(c),
                "geometria": json.loads(geometrias[p.id]),
            }
            for p, c in visibles
        ],
        "interseccion": json.loads(interseccion) if interseccion else None,
        "nota": s.nota,
        "cerrada_en": s.cerrada_en,
        "creado_en": s.creado_en,
    }


def listar(sesion: Session, cooperativa_id: uuid.UUID, estado: str | None) -> list[dict]:
    consulta, afa, afb = consulta_con_cooperativas()
    consulta = consulta.where(or_(afa.cooperativa_id == cooperativa_id, afb.cooperativa_id == cooperativa_id))
    if estado:
        consulta = consulta.where(Superposicion.estado == estado)
    filas = sesion.execute(consulta.order_by(Superposicion.creado_en.desc())).all()
    return [_vista(sesion, f, cooperativa_id, completa=False) for f in filas]


def listar_entre_cooperativas(sesion: Session, estado: str | None = "abierta") -> list[dict]:
    consulta, afa, afb = consulta_con_cooperativas()
    consulta = consulta.where(afa.cooperativa_id.is_distinct_from(afb.cooperativa_id))
    if estado:
        consulta = consulta.where(Superposicion.estado == estado)
    filas = sesion.execute(consulta.order_by(Superposicion.creado_en.desc())).all()
    return [_vista(sesion, f, None, completa=True) for f in filas]


def buscar(sesion: Session, superposicion_id: uuid.UUID):
    consulta, _, _ = consulta_con_cooperativas()
    return sesion.execute(consulta.where(Superposicion.id == superposicion_id)).first()


def aceptar(contexto, superposicion_id: uuid.UUID, nota: str, *, como_superadmin: bool) -> dict:
    """Dentro de una cooperativa la acepta su administrador; entre cooperativas, solo un superadmin."""
    sesion = contexto.sesion
    fila = buscar(sesion, superposicion_id)
    if fila is None:
        raise no_encontrado("La superposición no existe.")
    s, pa, pb, coop_a, coop_b = fila
    entre = coop_a != coop_b
    if como_superadmin:
        if not entre:
            raise error_api(
                400,
                "superposicion_interna",
                "Esta superposición es de una sola cooperativa: la acepta su administrador.",
            )
    else:
        if contexto.cooperativa_id not in (coop_a, coop_b):
            raise no_encontrado("La superposición no existe.")
        if entre:
            raise error_api(
                403,
                "solo_superadmin",
                "Una superposición con otra cooperativa solo la acepta el equipo CacaoTrace.",
            )
    if s.estado != "abierta":
        raise error_api(400, "superposicion_no_abierta", "La superposición ya no está abierta.")

    s.estado, s.nota, s.cerrada_por, s.cerrada_en = "aceptada", nota, contexto.usuario_id, datetime.now(UTC)
    for cooperativa in {coop_a, coop_b} - {None}:
        registrar_auditoria(
            contexto,
            "superposicion.aceptar",
            "superposicion",
            s.id,
            {"nota": nota, "parcelas": [pa.codigo, pb.codigo]},
            cooperativa_id=cooperativa,
        )
    sesion.commit()
    return _vista(sesion, buscar(sesion, s.id), contexto.cooperativa_id, completa=como_superadmin)
