// Secciones de cada módulo. Desde la decisión del equipo del 2026-10-07 van en la barra lateral, debajo del
// módulo abierto, y ya no como control segmentado bajo el título: así la página solo muestra sus filtros y
// no se confunden los dos niveles. Con la barra contraída a íconos, vuelven bajo el título (layout.js).

import { rolEfectivo } from "./estado.js";

/** Usuarios y Auditoría son del administrador (el superadmin los consulta); lo demás lo ve todo el personal. */
function cooperativa() {
  const comunes = [
    ["Datos y expediente legal", "#/cooperativa/legal"],
    // Adenda 6: el cuadro de señales y las actuaciones de diligencia.
    ["Diligencia", "#/cooperativa/diligencia"],
    ["Certificaciones", "#/cooperativa/certificaciones"],
    ["Configuración", "#/cooperativa/configuracion"],
    ["Lugares", "#/cooperativa/lugares"],
    ["Plantilla de proceso", "#/cooperativa/plantilla-proceso"],
  ];
  if (["admin_cooperativa", "consulta"].includes(rolEfectivo())) {
    return [["Usuarios", "#/cooperativa/usuarios"], ["Auditoría", "#/cooperativa/auditoria"], ...comunes];
  }
  return comunes;
}

const POR_MODULO = {
  "#/productores": () => [
    ["Padrón", "#/productores"],
    ["Mapa de parcelas", "#/productores/mapa"],
    ["Superposiciones", "#/productores/superposiciones"],
    ["Habilitación", "#/productores/habilitacion"],
  ],
  "#/lotes": () => [
    ["Recepción", "#/lotes/recepcion"],
    ["DOP", "#/lotes/dop"],
    ["Corridas", "#/lotes/corridas"],
    ["Stock", "#/lotes/stock"],
  ],
  "#/trazabilidad": () => [
    ["Genealogía por lote", "#/trazabilidad/lotes"],
    ["Rastreo por origen", "#/trazabilidad/origen"],
  ],
  "#/exportacion": () => [
    ["Órdenes", "#/exportacion/ordenes"],
    ["Lotes", "#/exportacion/lotes"],
    ["DEX", "#/exportacion/dex"],
    ["Importadores", "#/exportacion/importadores"],
  ],
  "#/cooperativa": cooperativa,
  "#/plataforma/cooperativas": () => [
    ["Cooperativas", "#/plataforma/cooperativas"],
    ["Superposiciones", "#/plataforma/superposiciones"],
    ["Configuración", "#/plataforma/configuracion"],
  ],
};

/** Las secciones del módulo con esa ruta en la barra lateral; [] si no tiene. */
export const seccionesDe = (rutaModulo) => POR_MODULO[rutaModulo]?.() ?? [];

// La ruta de un módulo abre su primera sección.
const RAICES = {
  "#/lotes": "#/lotes/recepcion",
  "#/trazabilidad": "#/trazabilidad/lotes",
  "#/exportacion": "#/exportacion/ordenes",
  "#/plataforma": "#/plataforma/cooperativas",
};
// Un detalle no es una sección: se marca la sección de la que sale.
const DETALLES = [
  ["#/parcelas/", "#/productores"],
  ["#/tandas/", "#/lotes/recepcion"],
  ["#/dops/", "#/lotes/dop"],
  ["#/corridas/", "#/lotes/corridas"],
  ["#/dpps/", "#/lotes/corridas"],
  ["#/tandas-finales/", "#/lotes/stock"],
  ["#/ordenes/", "#/exportacion/ordenes"],
  ["#/lotes-exportacion/", "#/exportacion/lotes"],
];

/** La ruta de la sección en la que está `hash`, entre `secciones`; null si ninguna. */
export function seccionActiva(secciones, hash) {
  const destino = RAICES[hash] ?? DETALLES.find(([prefijo]) => hash.startsWith(prefijo))?.[1] ?? hash;
  // La más larga que coincide: "#/productores/mapa" gana a "#/productores".
  const coinciden = secciones.filter(([, ruta]) => destino === ruta || destino.startsWith(`${ruta}/`));
  return coinciden.sort((a, b) => b[1].length - a[1].length)[0]?.[1] ?? null;
}
