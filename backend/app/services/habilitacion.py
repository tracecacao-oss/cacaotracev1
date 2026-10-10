"""Compuerta de habilitación de la parcela (Parte 4; desde la adenda 4, su parte legal la calcula
app/services/legalidad.py).

Una parcela puede respaldar cacao solo después de habilitarse. Habilitarla o excluirla lo decide un
administrador de la cooperativa, nunca el sistema: el sistema solo calcula los requisitos y, si una
parcela habilitada deja de cumplir alguno, la pasa a observada. Habilitar no declara que la parcela
cumple el Reglamento; es la decisión de la cooperativa de aceptar cacao de ella con las evidencias
a la vista. La exclusión es definitiva y ningún endpoint la revierte.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.catalogos import documentos_legales as catalogo
from app.contexto import Contexto
from app.errores import error_api
from app.fechas import ahora, dia_lima
from app.models import (
    Afiliacion,
    AnalisisCobertura,
    DecisionHabilitacion,
    Documento,
    Parcela,
    Perfil,
    Productor,
    RevisionImagenes,
    Superposicion,
    VisitaCampo,
)
from app.schemas.habilitacion import (
    DecisionSalida,
    DetalleAlerta,
    ExcluirEntrada,
    HabilitacionSalida,
    PorVencerSalida,
    Requisito,
    ResumenHabilitacion,
)
from app.services import analisis as servicio_analisis
from app.services import declaracion_productor as servicio_declaracion
from app.services import expediente as servicio_expediente
from app.services import legalidad as servicio_legalidad
from app.services import revisiones_imagenes as servicio_revisiones
from app.services import visitas as servicio_visitas
from app.services.auditoria import registrar_auditoria
from app.services.fuentes import registro

NOMBRE_FUENTE = {"whisp": "Whisp", "gfw": "GFW", "mapbiomas": "MapBiomas"}


@dataclass
class Evaluacion:
    requisitos: list[Requisito]
    alertas: list[str]  # las de la Parte 4 y de las adendas 4 y 5
    legalidad: servicio_legalidad.Legalidad
    analisis: list[AnalisisCobertura]
    visitas: list[VisitaCampo]  # solo para la procedencia: una visita ya no atiende un análisis
    procedencia: object
    # Adenda 2: la revisión de imágenes vigente, si la hay.
    revision: RevisionImagenes | None = None
    observada_ahora: bool = False
    faltan: list[str] = field(default_factory=list)
    # Para explicar las alertas: el estado del análisis y la declaración del productor (adenda 5).
    estado_analisis: dict = field(default_factory=dict)
    declaracion: object | None = None


def _lista(nombres: list[str]) -> str:
    return ", ".join(nombres)


def _requisitos(
    parcela: Parcela,
    *,
    abiertas: int,
    estado_analisis: dict,
    revision_imagenes: RevisionImagenes | None,
    leg: servicio_legalidad.Legalidad,
    dni_documentado: bool,
    consentimiento: bool,
    falta_declaracion: str | None,
) -> list[Requisito]:
    r = []
    r.append(
        Requisito(
            codigo="parcela_activa",
            cumple=parcela.estado == "activa",
            detalle="La parcela está activa." if parcela.estado == "activa" else "La parcela está inactiva.",
        )
    )
    r.append(
        Requisito(
            codigo="sin_superposiciones_abiertas",
            cumple=abiertas == 0,
            detalle="No tiene superposiciones abiertas."
            if abiertas == 0
            else f"Tiene {abiertas} superposición abierta."
            if abiertas == 1
            else f"Tiene {abiertas} superposiciones abiertas.",
        )
    )
    configuradas, sin_vigente = estado_analisis["configuradas"], estado_analisis["sin_vigente"]
    if not configuradas:
        r.append(
            Requisito(
                codigo="analisis_vigente",
                cumple=False,
                detalle="No hay ninguna fuente de análisis configurada.",
            )
        )
    else:
        r.append(
            Requisito(
                codigo="analisis_vigente",
                cumple=not sin_vigente,
                detalle="Cada fuente configurada tiene un análisis vigente."
                if not sin_vigente
                else f"Falta un análisis vigente de: {_lista([NOMBRE_FUENTE[c] for c in sin_vigente])}.",
            )
        )
    revision = [NOMBRE_FUENTE.get(c, c) for c in estado_analisis["requiere_revision"]]
    bosque_2020 = estado_analisis.get("bosque_2020", [])
    if bosque_2020:
        n = len(bosque_2020)
        revision.append(
            f"{n} {'conjunto de datos que registra' if n == 1 else 'conjuntos de datos que registran'} "
            "bosque en 2020"
        )
    # Adenda 2 (8.1): la atiende una revisión de imágenes vigente (no anulada y de la geometría actual) en
    # la que ninguna de las dos observaciones es "no se distingue". Un análisis nuevo no la vence (decisión
    # del equipo del 2026-10-05). Una visita de campo ya no la atiende.
    if not revision:
        r.append(Requisito(codigo="revision_atendida", cumple=True, detalle="Ninguna fuente pide revisión."))
    else:
        motivos = _lista(revision)
        if revision_imagenes is None:
            cumple = False
            detalle = (
                f"Piden revisión: {motivos}. Falta que el administrador revise las imágenes de la parcela "
                "(pestaña Imágenes)."
            )
        elif "no_se_distingue" in (revision_imagenes.observacion_2020, revision_imagenes.observacion_cambio):
            cumple = False
            detalle = (
                f"Piden revisión: {motivos}. La revisión de imágenes del "
                f"{revision_imagenes.revisada_en:%d/%m/%Y} no permite distinguir: busca más imágenes o carga "
                "una imagen externa y registra otra revisión."
            )
        else:
            cumple = True
            detalle = (
                f"Piden revisión: {motivos}. La atiende la revisión de imágenes del "
                f"{revision_imagenes.revisada_en:%d/%m/%Y}."
            )
        r.append(Requisito(codigo="revision_atendida", cumple=cumple, detalle=detalle))
    # Adenda 4, sección 8: expediente_completo se reemplaza por estos cuatro.
    r.extend(leg.compuerta())
    # Adenda 5, sección 8: también la declaración anual vigente.
    falta_productor = [
        n
        for n, ok in (("copia del DNI", dni_documentado), ("consentimiento de datos", consentimiento))
        if not ok
    ]
    if falta_declaracion:
        falta_productor.append(falta_declaracion)
    r.append(
        Requisito(
            codigo="productor_listo",
            cumple=not falta_productor,
            detalle="El DNI del productor está documentado, su consentimiento registrado y su declaración "
            "anual vigente."
            if not falta_productor
            else f"Falta del productor: {_lista(falta_productor)}.",
        )
    )
    return r


def _con_excluida(sesion: Session, parcela_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Parcelas que se superponen con una parcela excluida."""
    otra = aliased(Parcela)
    filas = sesion.execute(
        select(Superposicion.parcela_a_id, Superposicion.parcela_b_id, otra.id)
        .join(otra, or_(otra.id == Superposicion.parcela_a_id, otra.id == Superposicion.parcela_b_id))
        .where(
            or_(Superposicion.parcela_a_id.in_(parcela_ids), Superposicion.parcela_b_id.in_(parcela_ids)),
            otra.habilitacion_estado == "excluida",
        )
    ).all()
    resultado = set()
    for a, b, excluida in filas:
        for pid in (a, b):
            if pid != excluida and pid in parcela_ids:
                resultado.add(pid)
    return resultado


def evaluar(
    sesion: Session, parcelas: list[Parcela], *, abiertas: dict[uuid.UUID, int] | None = None
) -> dict[uuid.UUID, Evaluacion]:
    """Requisitos, alertas y procedencia de varias parcelas. Una parcela habilitada que dejó de cumplir
    un requisito pasa aquí a observada (se evalúa en cada lectura o escritura)."""
    ids = [p.id for p in parcelas]
    if not ids:
        return {}
    fuentes = registro.actuales()
    if abiertas is None:
        abiertas = dict(
            sesion.execute(
                select(Parcela.id, func.count(Superposicion.id))
                .join(
                    Superposicion,
                    or_(Superposicion.parcela_a_id == Parcela.id, Superposicion.parcela_b_id == Parcela.id),
                )
                .where(Parcela.id.in_(ids), Superposicion.estado == "abierta")
                .group_by(Parcela.id)
            ).all()
        )
    legalidades = servicio_legalidad.legalidades(sesion, parcelas)
    todos_analisis = servicio_analisis.de_parcelas(sesion, ids)
    todas_visitas = servicio_visitas.vigentes(sesion, ids)
    todas_revisiones = servicio_revisiones.de_parcelas(sesion, ids)
    con_excluida = _con_excluida(sesion, ids)
    productores = {
        p.id: p
        for p in sesion.scalars(select(Productor).where(Productor.id.in_({x.productor_id for x in parcelas})))
    }
    con_dni = set(
        sesion.scalars(
            select(Documento.entidad_id).where(
                Documento.entidad == "productor",
                Documento.entidad_id.in_(productores),
                Documento.tipo == "dni",
                Documento.anulado_en.is_(None),
            )
        )
    )

    # La declaración es ante la organización de la afiliación activa, como _cooperativa_de del análisis.
    afiliadas = dict(
        sesion.execute(
            select(Afiliacion.productor_id, Afiliacion.cooperativa_id).where(
                Afiliacion.productor_id.in_(productores), Afiliacion.estado == "activa"
            )
        ).all()
    )
    organizacion = {p.id: afiliadas.get(p.productor_id, p.cooperativa_registro_id) for p in parcelas}
    declaraciones = servicio_declaracion.estados(
        sesion, {(p.productor_id, organizacion[p.id]) for p in parcelas}
    )

    resultado = {}
    cambio = False
    for parcela in parcelas:
        estado_analisis = servicio_analisis.resumen(fuentes, parcela, todos_analisis[parcela.id])
        revision_vigente = servicio_revisiones.vigente(
            todas_revisiones[parcela.id], servicio_analisis.huella_parcela(parcela)
        )
        leg = legalidades[parcela.id]
        productor = productores[parcela.productor_id]
        declaracion = declaraciones[(parcela.productor_id, organizacion[parcela.id])]
        requisitos = _requisitos(
            parcela,
            abiertas=abiertas.get(parcela.id, 0),
            estado_analisis=estado_analisis,
            revision_imagenes=revision_vigente,
            leg=leg,
            dni_documentado=productor.id in con_dni,
            consentimiento=productor.consentimiento_datos_en is not None,
            falta_declaracion=declaracion.falta,
        )
        alertas = servicio_analisis.alertas(estado_analisis) + leg.alertas() + declaracion.alertas
        if parcela.id in con_excluida:
            alertas.append("superposicion_con_excluida")
        evaluacion = Evaluacion(
            requisitos=requisitos,
            alertas=alertas,
            legalidad=leg,
            analisis=todos_analisis[parcela.id],
            visitas=todas_visitas[parcela.id],
            procedencia=servicio_visitas.procedencia(parcela, todas_visitas[parcela.id]),
            revision=revision_vigente,
            faltan=[r.codigo for r in requisitos if not r.cumple],
            estado_analisis=estado_analisis,
            declaracion=declaracion,
        )
        if parcela.habilitacion_estado == "habilitada" and evaluacion.faltan:
            _observar(sesion, parcela, evaluacion)
            evaluacion.observada_ahora = True
            cambio = True
        resultado[parcela.id] = evaluacion
    if cambio:
        sesion.commit()
    return resultado


def _foto(evaluacion: Evaluacion, alertas: list[str], sesion: Session | None = None) -> dict:
    """Copia de los requisitos, las alertas y la revisión de imágenes vigente tal como estaban al decidir."""
    foto = {"requisitos": [r.model_dump() for r in evaluacion.requisitos], "alertas": alertas}
    if evaluacion.revision is not None and sesion is not None:
        foto["revision_imagenes"] = servicio_revisiones.resumen(
            evaluacion.revision, servicio_revisiones.nombre_de(sesion, evaluacion.revision)
        )
    return foto


def nota_obligatoria(evaluacion: Evaluacion, alertas: list[str]) -> bool:
    """Con alertas, o si la revisión de imágenes vigente registró un cambio visible (adenda 2, 8.4)."""
    return bool(alertas) or (
        evaluacion.revision is not None and evaluacion.revision.observacion_cambio == "cambio_visible"
    )


def _observar(sesion: Session, parcela: Parcela, evaluacion: Evaluacion) -> None:
    """Decisión del sistema: no es un juicio de riesgo, es el control de que los requisitos siguen en pie."""
    parcela.habilitacion_estado = "observada"
    incumplidos = [r for r in evaluacion.requisitos if not r.cumple]
    nota = "Dejó de cumplir: " + "; ".join(r.detalle for r in incumplidos)
    sesion.add(
        DecisionHabilitacion(
            parcela_id=parcela.id,
            decision="observar",
            decidida_por=None,
            decidida_en=ahora(),
            nota=nota,
            requisitos=_foto(evaluacion, evaluacion.alertas),
            geometria_sha256=servicio_analisis.huella_parcela(parcela),
        )
    )
    registrar_auditoria(
        None,
        "parcela.observar",
        "parcela",
        parcela.id,
        {"requisitos_incumplidos": [r.codigo for r in incumplidos]},
        cooperativa_id=parcela.cooperativa_registro_id,
        sesion=sesion,
    )


def revisar_habilitadas(sesion: Session) -> int:
    """Tarea diaria: evalúa todas las parcelas habilitadas (vencimientos que llegan solos con la fecha)."""
    parcelas = list(sesion.scalars(select(Parcela).where(Parcela.habilitacion_estado == "habilitada")))
    return sum(e.observada_ahora for e in evaluar(sesion, parcelas).values())


# ---------- Decisiones ----------


def _alertas_completas(contexto: Contexto, parcela: Parcela) -> list[str]:
    from app.services.parcelas import salidas  # evita importación circular

    return salidas(contexto, [parcela])[0].alertas


def habilitar(contexto: Contexto, parcela: Parcela, nota: str | None) -> HabilitacionSalida:
    servicio_expediente.no_excluida(parcela)
    if parcela.habilitacion_estado == "habilitada":
        raise error_api(400, "ya_habilitada", "La parcela ya está habilitada.")
    evaluacion = evaluar(contexto.sesion, [parcela])[parcela.id]
    if evaluacion.faltan:
        incumplidos = [r for r in evaluacion.requisitos if not r.cumple]
        raise_requisitos(incumplidos)
    alertas = _alertas_completas(contexto, parcela)
    if nota_obligatoria(evaluacion, alertas) and len(nota or "") < 50:
        raise error_api(
            422,
            "nota_requerida",
            "La parcela tiene alertas o su revisión de imágenes registró un cambio visible: explica en una "
            "nota de al menos 50 caracteres por qué se habilita.",
        )
    parcela.habilitacion_estado = "habilitada"
    decision = DecisionHabilitacion(
        parcela_id=parcela.id,
        decision="habilitar",
        decidida_por=contexto.usuario_id,
        decidida_en=ahora(),
        nota=nota or None,
        requisitos=_foto(evaluacion, alertas, contexto.sesion),
        geometria_sha256=servicio_analisis.huella_parcela(parcela),
    )
    contexto.sesion.add(decision)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "parcela.habilitar",
        "parcela",
        parcela.id,
        {"decision_id": decision.id, "nota": nota, "alertas": alertas},
    )
    contexto.sesion.commit()
    return obtener(contexto, parcela)


def raise_requisitos(incumplidos: list[Requisito]):
    from fastapi import HTTPException

    raise HTTPException(
        status_code=400,
        detail={
            "codigo": "requisitos_incompletos",
            "mensaje": "Faltan requisitos para habilitar: " + " ".join(r.detalle for r in incumplidos),
            "faltan": [r.codigo for r in incumplidos],
        },
    )


def excluir(contexto: Contexto, parcela: Parcela, datos: ExcluirEntrada) -> HabilitacionSalida:
    servicio_expediente.no_excluida(parcela)
    if datos.confirmacion != "EXCLUIR":
        raise error_api(
            422, "confirmacion_requerida", "Escribe EXCLUIR para confirmar que la exclusión es definitiva."
        )
    if not (datos.evidencia_revision_id or datos.evidencia_analisis_id):
        raise error_api(
            422,
            "evidencia_requerida",
            "La exclusión debe citar una revisión de imágenes o un análisis de esta parcela.",
        )
    if datos.evidencia_revision_id:
        citada = contexto.sesion.get(RevisionImagenes, datos.evidencia_revision_id)
        if citada is None or citada.parcela_id != parcela.id or citada.anulada_en is not None:
            raise error_api(
                422, "evidencia_invalida", "La revisión citada no es de esta parcela o está anulada."
            )
    if datos.evidencia_analisis_id:
        citado = contexto.sesion.get(AnalisisCobertura, datos.evidencia_analisis_id)
        if citado is None or citado.parcela_id != parcela.id:
            raise error_api(422, "evidencia_invalida", "El análisis citado no es de esta parcela.")
    evaluacion = evaluar(contexto.sesion, [parcela])[parcela.id]
    alertas = _alertas_completas(contexto, parcela)
    parcela.habilitacion_estado = "excluida"
    decision = DecisionHabilitacion(
        parcela_id=parcela.id,
        decision="excluir",
        decidida_por=contexto.usuario_id,
        decidida_en=ahora(),
        nota=datos.descripcion,
        requisitos=_foto(evaluacion, alertas, contexto.sesion),
        geometria_sha256=servicio_analisis.huella_parcela(parcela),
        evidencia_revision_id=datos.evidencia_revision_id,
        evidencia_analisis_id=datos.evidencia_analisis_id,
    )
    contexto.sesion.add(decision)
    contexto.sesion.flush()
    registrar_auditoria(
        contexto,
        "parcela.excluir",
        "parcela",
        parcela.id,
        {
            "decision_id": decision.id,
            "descripcion": datos.descripcion,
            "evidencia_revision_id": datos.evidencia_revision_id,
            "evidencia_analisis_id": datos.evidencia_analisis_id,
        },
    )
    # Parte 8: los lotes ya cerrados con cacao de esta parcela reciben su alerta (el DEX no cambia).
    from app.services import recomprobacion  # evita importación circular

    recomprobacion.exclusion_posterior_al_cierre(contexto, parcela)
    contexto.sesion.commit()
    return obtener(contexto, parcela)


def decisiones(sesion: Session, parcela_id: uuid.UUID) -> list[DecisionSalida]:
    filas = sesion.execute(
        select(DecisionHabilitacion, func.concat(Perfil.nombres, " ", Perfil.apellidos))
        .outerjoin(Perfil, Perfil.id == DecisionHabilitacion.decidida_por)
        .where(DecisionHabilitacion.parcela_id == parcela_id)
        .order_by(DecisionHabilitacion.decidida_en.desc())
    ).all()
    return [
        DecisionSalida.model_validate(d).model_copy(
            update={"decidida_por_nombre": nombre if d.decidida_por else None}
        )
        for d, nombre in filas
    ]


INCIDENCIA = {"tenencia": "de tenencia", "ambiental": "ambiental", "otra": "de otro tipo"}
ESTADO_MIDAGRI = {"sin_observacion": "Sin observación", "en_revision": "En revisión", "validado": "Validado"}


def _fecha(valor) -> str:
    if valor is None:
        return "—"
    dia = dia_lima(valor) if isinstance(valor, datetime) else valor
    return dia.strftime("%d/%m/%Y")


def _ha(valor) -> str:
    return f"{Decimal(valor):.2f}".replace(".", ",") + " ha" if valor is not None else "—"


def _superpuestas(sesion: Session, parcela: Parcela, *, solo_excluidas: bool) -> list[str]:
    """Las otras parcelas con las que se superpone: las abiertas o, si no, las que están excluidas."""
    otra = aliased(Parcela)
    consulta = (
        select(otra.codigo, otra.nombre, Superposicion.area_ha)
        .join(otra, or_(otra.id == Superposicion.parcela_a_id, otra.id == Superposicion.parcela_b_id))
        .where(
            or_(Superposicion.parcela_a_id == parcela.id, Superposicion.parcela_b_id == parcela.id),
            otra.id != parcela.id,
        )
        .order_by(otra.codigo)
    )
    if solo_excluidas:
        consulta = consulta.where(otra.habilitacion_estado == "excluida")
    else:
        consulta = consulta.where(Superposicion.estado == "abierta")
    sufijo = ", excluida" if solo_excluidas else ""
    return [f"Con {c} ({n}{sufijo}): {_ha(area)} en común." for c, n, area in sesion.execute(consulta)]


def detalle_alertas(
    sesion: Session, parcela: Parcela, evaluacion: Evaluacion, alertas: list[str]
) -> list[DetalleAlerta]:
    """Pedido del equipo del 2026-10-10: cada alerta dice qué hay detrás, en concreto, y dónde se atiende.
    Solo lee lo que ya calcularon las Partes 3 y 4, la legalidad (adenda 4) y la declaración del productor
    (adenda 5): no cambia cuándo salta una alerta."""
    salida = []
    declaracion = evaluacion.declaracion
    requisitos_productor = list(declaracion.requisitos.values()) if declaracion is not None else []
    ficha_productor = f"#/productores/{parcela.productor_id}/declaracion"
    leg = evaluacion.legalidad
    analisis = evaluacion.estado_analisis
    requisito = {r.codigo: r for r in evaluacion.requisitos}
    for codigo in alertas:
        lineas: list[str] = []
        pestana = enlace = None
        if codigo == "area_discrepante":
            pestana = "general"
            calculada, declarada = parcela.area_calculada_ha, parcela.area_declarada_ha
            diferencia = abs(declarada - calculada) / calculada * 100
            lineas = [
                f"Área declarada {_ha(declarada)} y calculada del polígono {_ha(calculada)}: difieren "
                f"{diferencia:.0f} %. Corrige el área declarada o la geometría."
            ]
        elif codigo == "diez_hectareas_o_mas":
            pestana = "general"
            total = (
                parcela.area_calculada_ha
                if parcela.tipo_geometria == "poligono"
                else parcela.area_declarada_ha
            )
            lineas = [f"La parcela tiene {_ha(total)}."]
        elif codigo == "superposicion":
            pestana = "general"
            lineas = _superpuestas(sesion, parcela, solo_excluidas=False)
        elif codigo == "superposicion_con_excluida":
            pestana = "general"
            lineas = _superpuestas(sesion, parcela, solo_excluidas=True)
        elif codigo == "sin_sustento_midagri":
            pestana = "general"
            estado = ESTADO_MIDAGRI.get(parcela.midagri_estado, parcela.midagri_estado)
            codigo_midagri = f", código {parcela.midagri_codigo}" if parcela.midagri_codigo else ""
            lineas = [
                f"En MIDAGRI figura como «{estado}»{codigo_midagri}, y falta cargar el documento "
                "«Sustento de MIDAGRI» en Documentos."
            ]
        elif codigo == "sin_analisis_vigente":
            pestana = "cobertura"
            fuentes = [NOMBRE_FUENTE.get(c, c) for c in analisis["sin_vigente"]]
            lineas = [f"Falta un análisis vigente de: {_lista(fuentes)}."]
        elif codigo == "analisis_con_error":
            pestana = "cobertura"
            fuentes = [NOMBRE_FUENTE.get(c, c) for c in analisis["con_error"]]
            lineas = [f"Falló el último análisis de: {_lista(fuentes)}. Vuelve a pedirlo."]
        elif codigo == "analisis_requiere_revision":
            pestana = "imagenes"
            lineas = [requisito["revision_atendida"].detalle]
        elif codigo == "tenencia_sin_documento_formal":
            pestana = "legalidad"
            lineas = ["El único sustento de la tenencia es la declaración jurada de tenencia."]
        elif codigo == "tenencia_solo_posesion":
            pestana = "legalidad"
            lineas = ["El único sustento de la tenencia es una constancia de posesión."]
        elif codigo in ("tierra_forestal_por_excepcion", "zonificacion_forestal_desconocida"):
            pestana = "legalidad"
            lineas = [leg.requisitos["tierra_forestal"].motivo]
        elif codigo == "en_zona_de_amortiguamiento":
            pestana = "legalidad"
            fila = leg.perfil["en_anp"].manda
            zonas = ((fila.detalle or {}) if fila is not None else {}).get("zonas_de_amortiguamiento") or []
            lineas = [
                f"Zona de amortiguamiento de {z.get('nombre') or 'un área protegida'}: "
                f"{_ha(z.get('area_comun_ha'))} en común. No pide documento."
                for z in zonas
            ] or [leg.requisitos["area_protegida"].motivo]
        elif codigo == "productor_por_atender":
            enlace = ficha_productor
            for r in requisitos_productor:
                if r.estado != "por_atender":
                    continue
                hechos = [f"{h.texto} {h.etiqueta}" for h in r.hechos]
                hechos += [f"{p.nombre}: no figura en el registro de SENASA" for p in r.no_figuran]
                lineas.append(f"{r.requisito.nombre}: " + ("; ".join(hechos) if hechos else r.motivo))
        elif codigo == "productor_sin_sustento":
            enlace = ficha_productor
            lineas = [
                f"{r.requisito.nombre}: {r.siguiente or r.motivo}"
                for r in requisitos_productor
                if r.estado == "sin_sustento"
            ]
        elif codigo == "requisito_sin_sustento":
            pestana = "legalidad"
            lineas = [
                f"{r.requisito.nombre}: {'vencido' if r.estado == 'vencido' else 'sin sustento'}. {r.motivo}"
                for r in leg.requisitos.values()
                if r.estado in ("sin_sustento", "vencido") and not r.requisito.bloquea
            ]
        elif codigo in ("documento_por_vencer", "documento_vencido"):
            pestana = "legalidad"
            estado = "por_vencer" if codigo == "documento_por_vencer" else "vencido"
            for r in leg.requisitos.values():
                if r.estado != estado:
                    continue
                doc = r.sustento if estado == "por_vencer" else r.vencido
                vence = _fecha(doc.fecha_vencimiento) if doc is not None else "—"
                lineas.append(
                    f"{r.requisito.nombre}: {'vence' if estado == 'por_vencer' else 'venció'} el {vence}"
                )
        elif codigo == "incidencia_abierta":
            pestana = "legalidad"
            lineas = [
                f"Incidencia {INCIDENCIA.get(i.tipo, i.tipo)} registrada el {_fecha(i.registrada_en)}: "
                f"{i.descripcion}"
                for i in leg.incidencias
                if i.estado == "abierta"
            ]
        if lineas:
            salida.append(DetalleAlerta(codigo=codigo, lineas=lineas, pestana=pestana, enlace=enlace))
    return salida


def obtener(contexto: Contexto, parcela: Parcela) -> HabilitacionSalida:
    evaluacion = evaluar(contexto.sesion, [parcela])[parcela.id]
    alertas = _alertas_completas(contexto, parcela)
    return HabilitacionSalida(
        parcela_id=parcela.id,
        estado=parcela.habilitacion_estado,
        requisitos=evaluacion.requisitos,
        puede_habilitar=parcela.habilitacion_estado in ("pendiente", "observada") and not evaluacion.faltan,
        alertas=alertas,
        nota_obligatoria=nota_obligatoria(evaluacion, alertas),
        decisiones=decisiones(contexto.sesion, parcela.id),
        detalle_alertas=detalle_alertas(contexto.sesion, parcela, evaluacion, alertas),
    )


def resumen(contexto: Contexto) -> ResumenHabilitacion:
    from app.services.parcelas import _visibles  # evita importación circular

    parcelas = list(contexto.sesion.scalars(_visibles(contexto)))
    evaluar(contexto.sesion, [p for p in parcelas if p.habilitacion_estado == "habilitada"])
    por_estado = {e: 0 for e in ("pendiente", "habilitada", "observada", "excluida")}
    for p in parcelas:
        por_estado[p.habilitacion_estado] += 1
    activas = {p.id: p for p in parcelas if p.estado == "activa" and p.habilitacion_estado != "excluida"}
    productores = {
        p.id: p
        for p in contexto.sesion.scalars(
            select(Productor).where(Productor.id.in_({x.productor_id for x in activas.values()}))
        )
    }
    por_vencer = []
    for parcela, requisito, documento in servicio_legalidad.sustentos_por_vencer(
        contexto.sesion, list(activas.values())
    ):
        productor = productores[parcela.productor_id]
        por_vencer.append(
            PorVencerSalida(
                parcela_id=parcela.id,
                parcela_codigo=parcela.codigo,
                parcela_nombre=parcela.nombre,
                productor_nombre=f"{productor.nombres} {productor.apellidos}",
                tipo=documento.tipo,
                tipo_nombre=catalogo.POR_CODIGO[documento.tipo].nombre,
                estado=requisito.estado,
                vence_en=documento.fecha_vencimiento,
            )
        )
    return ResumenHabilitacion(por_estado=por_estado, por_vencer=por_vencer)
