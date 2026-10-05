"""Verificación satelital con veredicto de tres estados: verde, ámbar o rojo.

- Con GFW_API_KEY: consulta la pérdida de cobertura arbórea posterior a 2020 en la
  API de datos de Global Forest Watch. (Conector experimental: validar con la llave real.)
- Sin llave: modo simulado, marcado como tal en la fuente del resultado.

"Ámbar" significa no concluyente y va a revisión humana. Evita bloquear por error a
productores con cacao bajo sombra, donde la poda o el raleo se confunden con pérdida de bosque.
"""
import hashlib
import json
import math
import os
import urllib.request

LLAVE = os.environ.get("GFW_API_KEY", "").strip()
URL_GFW = "https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss/latest/query/json"
MODO = "gfw" if LLAVE else "simulado"


def _como_poligono(geom, area_ha):
    """Un punto se convierte en un cuadrado del área declarada para poder consultarlo."""
    if geom["type"] == "Polygon":
        return geom
    lng, lat = geom["coordinates"]
    lado = math.sqrt(max(area_ha or 1, 0.1) * 10000) / 2
    dx = lado / (111320 * math.cos(math.radians(lat)))
    dy = lado / 110540
    return {"type": "Polygon", "coordinates": [[
        [lng - dx, lat - dy], [lng + dx, lat - dy], [lng + dx, lat + dy], [lng - dx, lat + dy], [lng - dx, lat - dy]]]}


def _gfw(geom, area_ha):
    cuerpo = json.dumps({
        "sql": "SELECT SUM(area__ha) AS ha FROM results WHERE umd_tree_cover_loss__year >= 2021",
        "geometry": _como_poligono(geom, area_ha),
    }).encode("utf-8")
    pet = urllib.request.Request(URL_GFW, data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/json", "x-api-key": LLAVE})
    with urllib.request.urlopen(pet, timeout=25) as r:
        filas = json.loads(r.read().decode("utf-8")).get("data") or []
    perdida = float((filas[0].get("ha") if filas else 0) or 0)
    fuente = "Global Forest Watch, pérdida de cobertura arbórea (Hansen/UMD)"
    if perdida <= 0.01:
        return "verde", "Sin pérdida de cobertura arbórea detectada desde 2021.", fuente
    proporcion = perdida / area_ha if area_ha else 1
    if perdida < 0.3 or proporcion < 0.10:
        return ("ambar", "Se detectó {:.2f} ha de pérdida de cobertura desde 2021 ({:.0f}% de la parcela). "
                "Puede ser manejo de sombra: requiere revisión humana.".format(perdida, proporcion * 100), fuente)
    return ("rojo", "Se detectó {:.2f} ha de pérdida de cobertura desde 2021 ({:.0f}% de la parcela)."
            .format(perdida, proporcion * 100), fuente)


def _simulado(geom):
    n = int(hashlib.sha256(json.dumps(geom, sort_keys=True).encode()).hexdigest(), 16) % 100
    fuente = "Simulación de CacaoTrace (sin consulta satelital real)"
    if n < 70:
        return "verde", "Sin pérdida de cobertura arbórea desde 2021 (resultado simulado).", fuente
    if n < 90:
        return ("ambar", "Cambio de cobertura no concluyente, compatible con manejo de sombra "
                "(resultado simulado). Requiere revisión humana.", fuente)
    return "rojo", "Pérdida de cobertura arbórea posterior a 2020 dentro de la parcela (resultado simulado).", fuente


def verificar(geom, area_ha):
    """Devuelve (estado, detalle, fuente)."""
    if MODO == "gfw":
        try:
            return _gfw(geom, area_ha)
        except Exception as e:  # si la consulta falla nunca se aprueba por defecto
            return ("ambar", "No se pudo completar la consulta a Global Forest Watch ({}). "
                    "Queda en revisión humana.".format(type(e).__name__), "Global Forest Watch (consulta fallida)")
    return _simulado(geom)
