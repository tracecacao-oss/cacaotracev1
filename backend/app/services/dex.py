"""El DEX (Parte 9): copia sellada de un lote al emitirse, con su informe de hallazgos, y los archivos que la
cooperativa descarga y envía al importador por su cuenta.

Se sella como el DOP y el DPP (app/services/sello.py): la huella es el SHA-256 de la forma canónica del
contenido y un trigger rechaza todo cambio en el contenido, la huella, el código y el lote. No concluye ni
se firma: la evaluación de riesgo y la DDS son del operador.
"""

import io
import json
import uuid
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from geoalchemy2.shape import to_shape
from sqlalchemy import select

from app import textos
from app.catalogos import documentos_embarque, documentos_legales
from app.config import get_settings
from app.contexto import Contexto, cooperativa_del_contexto
from app.errores import error_api, no_encontrado
from app.fechas import LIMA, ahora
from app.models import (
    Cooperativa,
    Dex,
    Documento,
    Importador,
    Lote,
    LoteGenealogia,
    OrdenCompra,
    Parcela,
    Perfil,
    Recomprobacion,
)
from app.schemas.dex import ArchivoDex, DescargaDex, DexDetalle, DexPublico, DexSalida
from app.services import cooperativa as servicio_cooperativa
from app.services import (
    correlativos,
    declaracion_productor,
    documentos,
    dops,
    geometria,
    hallazgos,
    legalidad,
    recomprobacion,
    sello,
)
from app.services.auditoria import registrar_auditoria
from app.services.documentos import Archivo
from app.services.lotes import lote_visible
from app.services.parcelas import _area_total
from app.storage import ClienteStorage, ErrorStorage

# 2: adenda 4, el respaldo de cada parcela trae su legalidad por requisito en lugar de las siete casillas.
# 3: adenda 5, el bloque "productores": lo que cada productor declaró, con el estado del día de la emisión.
VERSION_CONTENIDO = 3
REFERENCIA_ANEXO = (
    "Reglamento (UE) 2023/1115, anexo II; texto consolidado del 18/09/2026 (CELEX 02023R1115-20260918)"
)
NOMBRE_CIENTIFICO = "Theobroma cacao L."
PAIS_PRODUCCION = "PE"
CENTIMO = Decimal("0.01")
# Clave en `archivos`, tipo de documento y nombre del archivo en el paquete.
ARCHIVOS = (
    ("pdf_es", "dex_pdf_es", "{codigo}-es.pdf"),
    ("pdf_en", "dex_pdf_en", "{codigo}-en.pdf"),
    ("geojson", "dex_geojson", "parcelas.geojson"),
    ("anexo_ii", "dex_anexo_ii", "anexo_ii.json"),
    ("hallazgos", "dex_hallazgos", "hallazgos.json"),
    ("leeme", "dex_leeme", "LEEME.txt"),
    ("paquete", "dex_paquete", "{codigo}.zip"),
)


def url_verificacion(codigo: str) -> str:
    return f"{get_settings().url_interfaz.rstrip('/')}/#/verificar/dex/{codigo}"


def _texto(valor: Any) -> Any:
    """Valores listos para JSON: decimales, identificadores y fechas como texto."""
    if isinstance(valor, dict):
        return {k: _texto(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_texto(v) for v in valor]
    if isinstance(valor, Decimal | uuid.UUID):
        return str(valor)
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return valor


def _nombre(sesion, perfil_id: uuid.UUID | None) -> str | None:
    perfil = sesion.get(Perfil, perfil_id) if perfil_id else None
    return f"{perfil.nombres} {perfil.apellidos}".strip() if perfil else None


# ---------- Contenido sellado ----------


def _documento(doc: Documento | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    return {
        "numero": doc.numero,
        "entidad_emisora": doc.entidad_emisora,
        "fecha_emision": doc.fecha_emision,
        "fecha_vencimiento": doc.fecha_vencimiento,
        "cotejado_en": doc.cotejado_en,
        "sha256": doc.sha256,
    }


def _bloque_exportador(d: hallazgos.DatosLote) -> dict[str, Any]:
    coop = d.cooperativa
    casillas = servicio_cooperativa.casillas(d.sesion, coop.id)
    return {
        "razon_social": coop.razon_social,
        "ruc": coop.ruc,
        "codigo": coop.codigo,
        "direccion_postal": coop.direccion_postal,
        "correo": coop.correo,
        "representante": {"nombre": coop.representante_nombre, "dni": coop.representante_dni},
        "documentos": [
            {
                "codigo": t.codigo,
                "estado": casillas[t.codigo].estado,
                "nivel": casillas[t.codigo].nivel,
                "registro_consultable": t.registro_consultable,
                "documento": _documento(casillas[t.codigo].documento),
            }
            for t in documentos_legales.TIPOS_COOPERATIVA
        ],
    }


def _bloque_importador_orden(d: hallazgos.DatosLote) -> tuple[dict, dict]:
    i, o = d.importador, d.orden
    importador = {
        "razon_social": i.razon_social,
        "direccion": i.direccion,
        "pais": i.pais,
        "correo": i.correo,
        "eori": i.eori,
    }
    orden = {
        "codigo": o.codigo,
        "referencia_importador": o.referencia_importador,
        "cantidad_kg": o.cantidad_kg,
        "tolerancia_pct": o.tolerancia_pct,
        "calidad": d.calidad.nombre,
        "partida_sa": o.partida_sa,
        "pais_destino": o.pais_destino,
        "lugar_destino": o.lugar_destino,
        "fecha_entrega": o.fecha_entrega,
    }
    return importador, orden


def _bloque_genealogia(d: hallazgos.DatosLote) -> dict[str, Any]:
    kg: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    cosecha: dict[uuid.UUID, list] = defaultdict(list)
    for f in d.filas:
        kg[f.parcela_id] += Decimal(f.kg_atribuidos)
        t = d.tandas[f.tanda_id]
        cosecha[f.parcela_id] += [t.cosecha_desde, t.cosecha_hasta]
    parcelas = []
    for p in sorted(d.parcelas.values(), key=lambda p: (-d.peso_parcela[p.id], p.codigo)):
        productor = d.productores[p.productor_id]
        parcelas.append(
            {
                "codigo": p.codigo,
                "nombre": p.nombre,
                # Nombres y apellidos; nunca DNI, teléfono ni dirección (Parte 9, datos personales).
                "productor": f"{productor.nombres} {productor.apellidos}".strip(),
                "ubicacion": {
                    "departamento": p.departamento,
                    "provincia": p.provincia,
                    "distrito": p.distrito,
                },
                "area_ha": _area_total(p.tipo_geometria, p.area_calculada_ha, p.area_declarada_ha),
                "area_declarada_ha": p.area_declarada_ha,
                "tipo_geometria": p.tipo_geometria,
                "geometria": geometria.a_geojson(to_shape(p.geometria)),
                "kg": kg[p.id].quantize(CENTIMO, rounding=ROUND_HALF_UP),
                "proporcion_pct": d.peso_parcela[p.id],
                "cosecha": {"desde": min(cosecha[p.id]), "hasta": max(cosecha[p.id])},
            }
        )
    filas = []
    for f in sorted(d.filas, key=lambda f: (-Decimal(f.kg_atribuidos), str(f.id))):
        tf = d.finales[f.tanda_final_id]
        filas.append(
            {
                "parcela": d.parcelas[f.parcela_id].codigo,
                "tanda": d.tandas[f.tanda_id].codigo,
                "dop": d.dops[f.dop_id].codigo,
                "corrida": d.corridas[tf.corrida_id].codigo,
                "dpp": d.dpps[f.dpp_id].codigo,
                "tanda_final": tf.codigo,
                "kg": Decimal(f.kg_atribuidos).quantize(CENTIMO, rounding=ROUND_HALF_UP),
            }
        )
    fechas = [x for lista in cosecha.values() for x in lista]
    return {
        "masa_neta_kg": d.masa,
        "cosecha": {"desde": min(fechas), "hasta": max(fechas)} if fechas else None,
        "parcelas": parcelas,
        "filas": filas,
    }


def _bloque_respaldo(contexto: Contexto, d: hallazgos.DatosLote) -> list[dict[str, Any]]:
    bloques = []
    for p in sorted(d.parcelas.values(), key=lambda p: (-d.peso_parcela[p.id], p.codigo)):
        habilitar = [x for x in d.decisiones.get(p.id, []) if x.decision == "habilitar"]
        vigente = habilitar[-1] if habilitar else None
        cobertura, convergencia = dops._bloque_cobertura(contexto, p)
        bloque = {
            "parcela": p.codigo,
            "dops": [
                {
                    "codigo": dop.codigo,
                    "sha256": dop.contenido_sha256,
                    "tanda": d.tandas[tanda_id].codigo,
                    "estado": dop.estado,
                }
                for tanda_id, dop in sorted(d.dop_de_tanda.items(), key=lambda par: par[1].codigo)
                if d.tandas[tanda_id].parcela_id == p.id
            ],
            "habilitacion": {
                "estado": p.habilitacion_estado,
                "decidida_por": d.nombres.get(vigente.decidida_por) if vigente else None,
                "decidida_en": vigente.decidida_en if vigente else None,
                "nota": vigente.nota if vigente else None,
            },
            "cobertura": cobertura,
            "convergencia": convergencia,
            # Adenda 4: la legalidad por requisito en lugar de las siete casillas.
            "legalidad": legalidad.bloque(contexto.sesion, p),
        }
        imagenes = (d.imagenes.get(p.id) or (None, {}))[0]
        if imagenes:
            bloque["imagenes"] = imagenes
        bloques.append(bloque)
    return bloques


def _bloque_productores(d: hallazgos.DatosLote) -> list[dict[str, Any]]:
    """Adenda 5, sección 11: por cada productor del lote, lo mismo que sella el DOP, con el estado de hoy, más
    la nota de seguimiento. Nombres y apellidos, nunca DNI, teléfono ni dirección."""
    bloques = []
    for p in sorted(d.productores.values(), key=lambda x: (-d.peso_productor(x.id), x.apellidos, x.nombres)):
        estado = d.declaraciones[p.id]
        bloque = declaracion_productor.bloque(d.sesion, p.id, d.cooperativa.id)
        bloque["documentos"] = [{"tipo": x["tipo"], "sha256": x["sha256"]} for x in bloque["documentos"]]
        bloques.append(
            {
                "productor": f"{p.nombres} {p.apellidos}".strip(),
                "parcelas": sorted(x.codigo for x in d.parcelas.values() if x.productor_id == p.id),
                "peso_en_lote_pct": d.peso_productor(p.id),
                **bloque,
                "seguimiento": estado.vigente.seguimiento_nota if estado.valida else None,
            }
        )
    return bloques


def _bloque_proceso(d: hallazgos.DatosLote) -> list[dict[str, Any]]:
    salida = []
    for dpp in sorted(d.dpps.values(), key=lambda x: x.codigo):
        corrida = d.corridas[dpp.corrida_id]
        tf = d.finales.get(dpp.tanda_final_id)
        salida.append(
            {
                "dpp": dpp.codigo,
                "sha256": dpp.contenido_sha256,
                "estado": dpp.estado,
                "corrida": corrida.codigo,
                "ruta": corrida.ruta,
                "tipo_manejo": corrida.tipo_manejo,
                "tanda_final": tf.codigo if tf else None,
                "rendimiento": (dpp.contenido or {}).get("rendimiento"),
            }
        )
    return salida


def _documentos_embarque(sesion, lote: Lote) -> list[Documento]:
    docs = {
        doc.tipo: doc
        for doc in sesion.scalars(
            select(Documento)
            .where(
                Documento.entidad == "lote", Documento.entidad_id == lote.id, Documento.anulado_en.is_(None)
            )
            .order_by(Documento.creado_en)
        )
    }
    return [docs[t.codigo] for t in documentos_embarque.TIPOS if t.codigo in docs]


def _evidencia(contenido: dict[str, Any], d: hallazgos.DatosLote, certificaciones) -> list[dict[str, Any]]:
    """Los documentos que respaldan el lote, con su número, su fecha y su huella. No van en el paquete."""
    lista = []
    coop = contenido["exportador"]["codigo"] or contenido["exportador"]["ruc"]
    for x in contenido["exportador"]["documentos"]:
        if x["documento"]:
            lista.append({"tipo": x["codigo"], "de": coop, **_resumen_doc(x["documento"])})
    for c in certificaciones:
        if c["sha256"]:
            lista.append(
                {
                    "tipo": "certificacion",
                    "de": coop,
                    "numero": c["numero"],
                    "fecha": c["vigente_desde"],
                    "sha256": c["sha256"],
                }
            )
    for r in contenido["respaldo"]:
        vistos = set()
        for requisito in r["legalidad"]["requisitos"]:
            doc = requisito.get("documento")
            if doc and doc["sha256"] not in vistos:
                vistos.add(doc["sha256"])
                lista.append({"tipo": doc["tipo"], "de": r["parcela"], **_resumen_doc(doc)})
    for t in sorted(d.tandas.values(), key=lambda t: t.codigo):
        bloque = (d.dop_de_tanda[t.id].contenido or {}).get("tanda") or {}
        doc = bloque.get("documento_entrega") or bloque.get("guia_remision")
        if doc:
            lista.append(
                {
                    "tipo": doc.get("tipo") or "guia_remision",
                    "de": t.codigo,
                    "numero": doc.get("numero"),
                    "fecha": doc.get("fecha_emision"),
                    "sha256": doc.get("documento_sha256"),
                }
            )
    for x in contenido["embarque"]:
        lista.append(
            {"tipo": x["tipo"], "de": contenido["identificacion"]["lote"]["codigo"], **_resumen_doc(x)}
        )
    return lista


def _resumen_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {"numero": doc.get("numero"), "fecha": doc.get("fecha_emision"), "sha256": doc.get("sha256")}


def construir_contenido(
    contexto: Contexto,
    d: hallazgos.DatosLote,
    informe: dict[str, Any],
    recomprobada: Recomprobacion,
    codigo: str,
    momento: datetime,
) -> dict[str, Any]:
    sesion = contexto.sesion
    importador, orden = _bloque_importador_orden(d)
    embarque = [
        {
            "tipo": doc.tipo,
            "numero": doc.numero,
            "entidad_emisora": doc.entidad_emisora,
            "fecha_emision": doc.fecha_emision,
            "sha256": doc.sha256,
        }
        for doc in _documentos_embarque(sesion, d.lote)
    ]
    certificaciones = []
    for c in hallazgos.informe.certificaciones_vigentes(d):
        doc = sesion.get(Documento, c.documento_id) if c.documento_id else None
        certificaciones.append(
            {
                "nombre": c.nombre,
                "entidad_certificadora": c.entidad_certificadora,
                "numero": c.numero,
                "vigente_desde": c.vigente_desde,
                "vigente_hasta": c.vigente_hasta,
                "sha256": doc.sha256 if doc else None,
            }
        )
    contenido = {
        "version": VERSION_CONTENIDO,
        "leyenda": {i: textos.obtener(i, "leyenda") for i in textos.IDIOMAS},
        "es_demo": bool(d.cooperativa.es_demo),
        "identificacion": {
            "codigo": codigo,
            "emitido_en": momento,
            "emitido_por": _nombre(sesion, contexto.usuario_id),
            "lote": {"codigo": d.lote.codigo},
            "cooperativa": {
                "razon_social": d.cooperativa.razon_social,
                "ruc": d.cooperativa.ruc,
                "codigo": d.cooperativa.codigo,
            },
        },
        "exportador": _bloque_exportador(d),
        "importador": importador,
        "orden": orden,
        "producto": {
            "partida_sa": d.orden.partida_sa,
            "descripcion": {i: textos.obtener(i, "pdf.descripcion_valor") for i in textos.IDIOMAS},
            "nombre_cientifico": NOMBRE_CIENTIFICO,
            "masa_neta_kg": d.masa,
            "pais_produccion": PAIS_PRODUCCION,
        },
        "genealogia": _bloque_genealogia(d),
        "respaldo": _bloque_respaldo(contexto, d),
        "productores": _bloque_productores(d),
        "proceso": _bloque_proceso(d),
        "embarque": embarque,
        "recomprobacion": {
            "ejecutada_en": recomprobada.ejecutada_en,
            "resultado": recomprobada.resultado,
            "comprobaciones": recomprobada.detalle["comprobaciones"],
        },
        "certificaciones": certificaciones,
        "informe": informe,
    }
    contenido = _texto(contenido)
    contenido["evidencia"] = _texto(_evidencia(contenido, d, contenido["certificaciones"]))
    return contenido


# ---------- Archivos ----------


def _coordenada(valor: float) -> str:
    """Al menos 6 decimales, sin perder los que tenga la geometría guardada (hasta 8)."""
    texto = f"{valor:.8f}".rstrip("0")
    entero, _, decimales = texto.partition(".")
    return f"{entero}.{decimales.ljust(6, '0')}"


def _coordenadas(valor: Any) -> str:
    if isinstance(valor, list | tuple) and valor and isinstance(valor[0], int | float):
        return "[" + ",".join(_coordenada(float(v)) for v in valor[:2]) + "]"
    return "[" + ",".join(_coordenadas(v) for v in valor) + "]"


def geojson(sesion, parcelas: list[dict[str, Any]], es_demo: bool = False) -> dict[str, Any]:
    """FeatureCollection en WGS 84, un Feature por parcela, sin datos personales. Propiedades según la
    descripción del archivo GeoJSON del EUDR de la Comisión Europea: ProductionPlace y ProducerCountry, y
    Area (en hectáreas) solo para un punto. Cada geometría vuelve a pasar las validaciones de la Parte 3."""
    features = []
    for p in parcelas:
        declarada = Decimal(p["area_declarada_ha"]) if p.get("area_declarada_ha") is not None else None
        resultado = geometria.validar(sesion, p["geometria"], nombre=p["codigo"], area_declarada_ha=declarada)
        if not resultado.valida:
            raise error_api(
                400,
                "geometria_no_valida",
                f"La geometría de la parcela {p['codigo']} no pasa las validaciones: "
                f"{resultado.error['mensaje']}",
            )
        propiedades: dict[str, Any] = {"ProductionPlace": p["codigo"], "ProducerCountry": PAIS_PRODUCCION}
        if p["geometria"]["type"] == "Point" and declarada is not None:
            propiedades["Area"] = float(declarada)
        features.append({"type": "Feature", "properties": propiedades, "geometry": p["geometria"]})
    # Parte 10: el archivo dice si viene de una cooperativa de demostración (miembro adicional).
    return {"type": "FeatureCollection", "es_demo": es_demo, "features": features}


def geojson_texto(coleccion: dict[str, Any]) -> str:
    """El GeoJSON como texto, con las coordenadas escritas con al menos 6 decimales."""
    partes = []
    for f in coleccion["features"]:
        geometria_ = f["geometry"]
        partes.append(
            '{"type":"Feature","properties":'
            + json.dumps(f["properties"], ensure_ascii=False)
            + ',"geometry":{"type":'
            + json.dumps(geometria_["type"])
            + ',"coordinates":'
            + _coordenadas(geometria_["coordinates"])
            + "}}"
        )
    demo = "true" if coleccion.get("es_demo") else "false"
    return '{"type":"FeatureCollection","es_demo":' + demo + ',"features":[' + ",".join(partes) + "]}\n"


def anexo_ii(contenido: dict[str, Any], huella: str) -> dict[str, Any]:
    """Ayuda para el importador con los campos del Anexo II (texto consolidado del 18/09/2026). Los datos
    del importador van como la cooperativa los registró, a confirmar; la afirmación y la firma, vacías."""
    a_confirmar = {i: textos.obtener(i, "anexo.a_confirmar") for i in textos.IDIOMAS}
    del_operador = {i: textos.obtener(i, "anexo.corresponde_operador") for i in textos.IDIOMAS}

    def oficial(punto: int) -> dict[str, str]:
        return {i: textos.obtener(i, f"anexo.punto_{punto}") for i in textos.IDIOMAS}

    imp, prod, exp = contenido["importador"], contenido["producto"], contenido["exportador"]
    return {
        "nota": {i: textos.obtener(i, "anexo.nota_general") for i in textos.IDIOMAS},
        "referencia": REFERENCIA_ANEXO,
        "es_demo": bool(contenido.get("es_demo")),
        "dex": {"codigo": contenido["identificacion"]["codigo"], "contenido_sha256": huella},
        "campos": [
            {
                "punto": 1,
                "texto_oficial": oficial(1),
                "valor": {
                    "nombre": imp["razon_social"],
                    "direccion": imp["direccion"],
                    "pais": imp["pais"],
                    "correo": imp["correo"],
                    "eori": imp["eori"],
                },
                "nota": a_confirmar,
            },
            {
                "punto": 2,
                "texto_oficial": oficial(2),
                "valor": {
                    "codigo_sistema_armonizado": prod["partida_sa"],
                    "descripcion": prod["descripcion"],
                    "nombre_cientifico": prod["nombre_cientifico"],
                    "masa_neta_kg": prod["masa_neta_kg"],
                },
            },
            {
                "punto": 3,
                "texto_oficial": oficial(3),
                "valor": {
                    "pais_produccion": prod["pais_produccion"],
                    "geolocalizacion": "parcelas.geojson",
                    "parcelas": len(contenido["genealogia"]["parcelas"]),
                },
                "nota": {i: textos.obtener(i, "anexo.geojson") for i in textos.IDIOMAS},
            },
            {"punto": 4, "texto_oficial": oficial(4), "valor": None},
            {"punto": 5, "texto_oficial": oficial(5), "valor": None, "nota": del_operador},
            {
                "punto": 6,
                "texto_oficial": oficial(6),
                "valor": {
                    "firmado_en_nombre_de": None,
                    "fecha": None,
                    "nombre_y_funcion": None,
                    "firma": None,
                },
                "nota": del_operador,
            },
        ],
        "informacion_complementaria": {
            "nota": {i: textos.obtener(i, "anexo.complementaria") for i in textos.IDIOMAS},
            "campos": [
                {
                    "referencia": "art. 9.1 d)",
                    "texto": {i: textos.obtener(i, "anexo.intervalo_cosecha") for i in textos.IDIOMAS},
                    "valor": contenido["genealogia"]["cosecha"],
                },
                {
                    "referencia": "art. 9.1 e)",
                    "texto": {i: textos.obtener(i, "anexo.proveedor") for i in textos.IDIOMAS},
                    "valor": {
                        "razon_social": exp["razon_social"],
                        "ruc": exp["ruc"],
                        "direccion_postal": exp["direccion_postal"],
                        "correo": exp["correo"],
                    },
                },
            ],
        },
    }


def leeme(contenido: dict[str, Any], huella: str, url: str) -> str:
    ident = contenido["identificacion"]
    bloques = []
    for idioma in textos.IDIOMAS:
        valores = {
            "codigo": ident["codigo"],
            "cooperativa": ident["cooperativa"]["razon_social"],
            "fecha": textos.fecha(idioma, ident["emitido_en"]),
            "huella": huella,
            "url": url,
        }
        bloques.append("\n".join(linea.format(**valores) for linea in textos.obtener(idioma, "leeme")))
    return ("\n\n" + "-" * 72 + "\n\n").join(bloques) + "\n"


def _json(datos: Any) -> bytes:
    return (json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def generar_archivos(contenido: dict[str, Any], huella: str, url: str, sesion, png: dict) -> dict[str, bytes]:
    """Los seis archivos y el paquete ZIP que los reúne, todos desde el mismo contenido sellado."""
    from app.pdf import dex as pdf_dex  # evita cargar fpdf2 al importar

    codigo = contenido["identificacion"]["codigo"]
    archivos = {
        "pdf_es": pdf_dex.generar(contenido, huella, url, "es", png),
        "pdf_en": pdf_dex.generar(contenido, huella, url, "en", png),
        "geojson": geojson_texto(
            geojson(sesion, contenido["genealogia"]["parcelas"], bool(contenido.get("es_demo")))
        ).encode("utf-8"),
        "anexo_ii": _json(anexo_ii(contenido, huella)),
        "hallazgos": _json(
            {
                "dex": codigo,
                "contenido_sha256": huella,
                "es_demo": bool(contenido.get("es_demo")),
                "informe": contenido["informe"],
            }
        ),
        "leeme": leeme(contenido, huella, url).encode("utf-8"),
    }
    paquete = io.BytesIO()
    with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED) as zz:
        for clave, _, nombre in ARCHIVOS[:-1]:
            zz.writestr(nombre.format(codigo=codigo), archivos[clave])
    archivos["paquete"] = paquete.getvalue()
    return archivos


# ---------- Emisión ----------


def emitir(contexto: Contexto, storage: ClienteStorage, lote_id: uuid.UUID, entiendo: bool) -> DexDetalle:
    """Recomprueba en ese instante y, en una sola transacción, calcula el informe, arma y sella el contenido,
    genera los archivos, cierra el lote y la orden. Si falla un archivo, nada cambia."""
    if not entiendo:
        raise error_api(
            422,
            "entendimiento_requerido",
            "Marca la casilla: el DEX no declara el nivel de riesgo ni reemplaza la DDS.",
        )
    sesion = contexto.sesion
    lote = lote_visible(contexto, lote_id, bloquear=True)
    if lote.estado != "listo":
        raise error_api(
            400, "lote_no_listo", "Solo se emite el DEX de un lote listo: recomprueba el lote primero."
        )
    comprobaciones = recomprobacion.comprobar(sesion, lote)
    lote = lote_visible(contexto, lote_id, bloquear=True)  # evaluar pudo confirmar la sesión
    resultado = recomprobacion.resultado_de(comprobaciones)
    fila = Recomprobacion(
        lote_id=lote.id,
        ejecutada_por=contexto.usuario_id,
        ejecutada_en=ahora(),
        resultado=resultado,
        detalle={"comprobaciones": comprobaciones},
    )
    sesion.add(fila)
    sesion.flush()
    registrar_auditoria(
        contexto,
        "lote.recomprobar",
        "lote",
        lote.id,
        {"codigo": lote.codigo, "resultado": resultado, "por": "emision_dex"},
    )
    if resultado != "sin_observaciones":
        recomprobacion.cambiar_estado(sesion, contexto, lote, resultado)
        sesion.commit()
        raise error_api(
            400,
            "lote_bloqueado",
            "La recomprobación al emitir encontró observaciones: el lote quedó bloqueado y no se emitió "
            "el DEX. Revisa la pestaña Recomprobación.",
        )
    d = hallazgos.reunir(sesion, lote, comprobaciones)
    informe = hallazgos.calcular(d, preliminar=False)
    momento = ahora()
    anio = momento.astimezone(LIMA).year
    numero = correlativos.siguiente(sesion, lote.cooperativa_id, "dex", anio)
    codigo = f"DEX-{d.cooperativa.codigo}-{anio}-{numero:06d}"
    contenido = construir_contenido(contexto, d, informe, fila, codigo, momento)
    huella = sello.huella(contenido)
    dex = Dex(
        cooperativa_id=lote.cooperativa_id,
        codigo=codigo,
        lote_id=lote.id,
        emitido_en=momento,
        emitido_por=contexto.usuario_id,
        contenido=contenido,
        contenido_sha256=huella,
        estado="vigente",
    )
    sesion.add(dex)
    sesion.flush()
    rutas: list[str] = []
    try:
        png = {
            str(p.codigo): {
                papel: storage.descargar(ruta)
                for papel, ruta in (d.imagenes.get(p.id) or (None, {}))[1].items()
            }
            for p in d.parcelas.values()
        }
        generados = generar_archivos(contenido, huella, url_verificacion(codigo), sesion, png)
        ids = {}
        for clave, tipo, nombre in ARCHIVOS:
            documento, ruta = documentos.guardar(
                contexto,
                storage,
                entidad="dex",
                entidad_id=dex.id,
                tipo=tipo,
                archivo=Archivo(nombre=nombre.format(codigo=codigo), contenido=generados[clave]),
            )
            rutas.append(ruta)
            ids[clave] = str(documento.id)
        dex.archivos = ids
        lote.estado = "cerrado"
        orden = sesion.get(OrdenCompra, lote.orden_compra_id)
        orden.estado = "cerrada"
        registrar_auditoria(
            contexto,
            "dex.emitir",
            "dex",
            dex.id,
            {"codigo": codigo, "lote": lote.codigo, "orden": orden.codigo, "sha256": huella},
        )
        sesion.commit()
    except Exception as exc:
        sesion.rollback()
        for ruta in rutas:
            documentos.descartar(storage, ruta)
        if isinstance(exc, ErrorStorage):
            raise error_api(
                503,
                "archivos_no_disponibles",
                "No se pudieron guardar los archivos del DEX. Intenta de nuevo.",
            ) from exc
        raise
    return obtener(contexto, dex.id)


# ---------- Consultas ----------


def dex_visible(contexto: Contexto, dex_id: uuid.UUID) -> Dex:
    dex = contexto.sesion.get(Dex, dex_id)
    if dex is None or dex.cooperativa_id != cooperativa_del_contexto(contexto):
        raise no_encontrado("El DEX no existe.")
    return dex


def _salidas(sesion, filas: list[Dex]) -> list[DexSalida]:
    if not filas:
        return []
    lotes = {x.id: x for x in sesion.scalars(select(Lote).where(Lote.id.in_({f.lote_id for f in filas})))}
    ordenes = {
        x.id: x
        for x in sesion.scalars(
            select(OrdenCompra).where(OrdenCompra.id.in_({lo.orden_compra_id for lo in lotes.values()}))
        )
    }
    importadores = {
        x.id: x
        for x in sesion.scalars(
            select(Importador).where(Importador.id.in_({o.importador_id for o in ordenes.values()}))
        )
    }
    salida = []
    for f in filas:
        lote = lotes[f.lote_id]
        orden = ordenes[lote.orden_compra_id]
        salida.append(
            DexSalida(
                id=f.id,
                codigo=f.codigo,
                estado=f.estado,
                lote_id=lote.id,
                lote_codigo=lote.codigo,
                orden_codigo=orden.codigo,
                importador_id=orden.importador_id,
                importador=importadores[orden.importador_id].razon_social,
                masa_neta_kg=Decimal(f.contenido["producto"]["masa_neta_kg"]),
                emitido_en=f.emitido_en,
                contenido_sha256=f.contenido_sha256,
            )
        )
    return salida


def listar(
    contexto: Contexto, *, estado: str | None = None, importador_id: uuid.UUID | None = None
) -> list[DexSalida]:
    consulta = select(Dex).where(Dex.cooperativa_id == cooperativa_del_contexto(contexto))
    if estado:
        consulta = consulta.where(Dex.estado == estado)
    filas = list(contexto.sesion.scalars(consulta.order_by(Dex.emitido_en.desc()).limit(500)))
    salida = _salidas(contexto.sesion, filas)
    if importador_id:
        salida = [s for s in salida if s.importador_id == importador_id]
    return salida


def de_lote(sesion, lote_id: uuid.UUID) -> Dex | None:
    """El DEX vigente del lote o, si no lo hay, el último emitido."""
    return sesion.scalar(
        select(Dex)
        .where(Dex.lote_id == lote_id)
        .order_by((Dex.estado == "vigente").desc(), Dex.emitido_en.desc())
        .limit(1)
    )


def obtener(contexto: Contexto, dex_id: uuid.UUID) -> DexDetalle:
    sesion = contexto.sesion
    dex = dex_visible(contexto, dex_id)
    base = _salidas(sesion, [dex])[0]
    url = url_verificacion(dex.codigo)
    docs = {
        str(doc.id): doc
        for doc in sesion.scalars(
            select(Documento).where(Documento.id.in_([uuid.UUID(v) for v in (dex.archivos or {}).values()]))
        )
    }
    archivos = [
        ArchivoDex(
            clave=clave,
            nombre=docs[dex.archivos[clave]].nombre_original,
            tamano_bytes=docs[dex.archivos[clave]].tamano_bytes,
        )
        for clave, _, _ in ARCHIVOS
        if clave in (dex.archivos or {}) and dex.archivos[clave] in docs
    ]
    return DexDetalle(
        **base.model_dump(),
        contenido=dex.contenido,
        url_verificacion=url,
        qr=dops.matriz_qr(url),
        archivos=archivos,
        emitido_por_nombre=_nombre(sesion, dex.emitido_por),
        anulado_en=dex.anulado_en,
        anulado_por_nombre=_nombre(sesion, dex.anulado_por),
        motivo_anulacion=dex.motivo_anulacion,
    )


def descargas(contexto: Contexto, storage: ClienteStorage, dex_id: uuid.UUID) -> list[DescargaDex]:
    """URLs firmadas de 5 minutos del paquete y de cada archivo. Cada descarga se audita."""
    dex = dex_visible(contexto, dex_id)
    docs = {
        str(doc.id): doc
        for doc in contexto.sesion.scalars(
            select(Documento).where(Documento.id.in_([uuid.UUID(v) for v in (dex.archivos or {}).values()]))
        )
    }
    salida = []
    try:
        for clave, _, _ in (ARCHIVOS[-1], *ARCHIVOS[:-1]):
            doc = docs.get((dex.archivos or {}).get(clave, ""))
            if doc is None:
                continue
            salida.append(
                DescargaDex(
                    clave=clave,
                    nombre=doc.nombre_original,
                    url=storage.url_firmada(doc.ruta, descarga=doc.nombre_original),
                )
            )
    except ErrorStorage as exc:
        raise error_api(
            503, "archivos_no_disponibles", "No se pudo preparar la descarga. Intenta de nuevo."
        ) from exc
    registrar_auditoria(contexto, "dex.descargar", "dex", dex.id, {"codigo": dex.codigo})
    contexto.sesion.commit()
    return salida


def anular(contexto: Contexto, dex_id: uuid.UUID, motivo: str) -> DexDetalle:
    """El DEX conserva su contenido y sus archivos; el lote vuelve a armado y la orden a con_lote. Para emitir
    de nuevo hay que recomprobar, y la nueva emisión recibe un código nuevo."""
    sesion = contexto.sesion
    dex = dex_visible(contexto, dex_id)
    if dex.estado == "anulado":
        raise error_api(400, "dex_anulado", "El DEX ya estaba anulado.")
    lote = lote_visible(contexto, dex.lote_id, bloquear=True)
    orden = sesion.get(OrdenCompra, lote.orden_compra_id)
    dex.estado = "anulado"
    dex.anulado_en = ahora()
    dex.anulado_por = contexto.usuario_id
    dex.motivo_anulacion = motivo
    if lote.estado == "cerrado":
        lote.estado = "armado"
    if orden.estado == "cerrada":
        orden.estado = "con_lote"
    registrar_auditoria(
        contexto, "dex.anular", "dex", dex.id, {"codigo": dex.codigo, "lote": lote.codigo, "motivo": motivo}
    )
    sesion.commit()
    return obtener(contexto, dex.id)


def publico(sesion, codigo: str) -> DexPublico:
    """Sin token: los mismos cinco datos que el DOP (código, estado, fecha, huella y cooperativa)."""
    fila = sesion.execute(
        select(Dex, Cooperativa.razon_social, Cooperativa.es_demo)
        .join(Cooperativa, Cooperativa.id == Dex.cooperativa_id)
        .where(Dex.codigo == codigo.strip().upper())
    ).first()
    if fila is None:
        raise no_encontrado("No existe un DEX con ese código.")
    dex, razon_social, es_demo = fila
    return DexPublico(
        codigo=dex.codigo,
        estado=dex.estado,
        emitido_en=dex.emitido_en,
        contenido_sha256=dex.contenido_sha256,
        cooperativa=razon_social,
        es_demo=bool(es_demo),
    )


def geojson_preliminar(contexto: Contexto, lote_id: uuid.UUID) -> dict[str, Any]:
    """GeoJSON de las parcelas de la genealogía del lote, con el estado de hoy."""
    lote = lote_visible(contexto, lote_id)
    if lote.estado in ("en_armado", "anulado"):
        raise error_api(
            400, "lote_sin_genealogia", "El GeoJSON se arma con la genealogía de un lote confirmado."
        )
    parcelas = contexto.sesion.scalars(
        select(Parcela)
        .where(Parcela.id.in_(select(LoteGenealogia.parcela_id).where(LoteGenealogia.lote_id == lote.id)))
        .order_by(Parcela.codigo)
    )
    return geojson(
        contexto.sesion,
        [
            {
                "codigo": p.codigo,
                "geometria": geometria.a_geojson(to_shape(p.geometria)),
                "area_declarada_ha": p.area_declarada_ha,
            }
            for p in parcelas
        ],
        bool(contexto.sesion.get(Cooperativa, lote.cooperativa_id).es_demo),
    )
