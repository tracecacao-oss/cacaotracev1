// Departamento, provincia y distrito elegidos del catálogo oficial del INEI (GET /ubigeos).
// Las tres listas van encadenadas: cada una se llena al elegir la anterior. Se guardan los
// nombres tal como los escribe el INEI, en mayúsculas.

import { llamarApi } from "./api.js";
import { campo, h } from "./ui.js";

let pedido = null;

/** El catálogo se pide una vez por sesión de la página; si falla, se reintenta la próxima vez. */
export function cargarUbigeos() {
  pedido ??= llamarApi("/ubigeos", { sinConsulta: true }).catch((error) => {
    pedido = null;
    throw error;
  });
  return pedido;
}

/** Igual que en la API: sin tildes, sin eñe, en mayúsculas y sin espacios repetidos. */
const clave = (texto) =>
  (texto ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase().trim().replace(/\s+/g, " ");

const buscar = (lista, nombre) => lista.find((x) => clave(x.nombre ?? x) === clave(nombre));

function llenar(select, aviso, nombres) {
  select.replaceChildren(h("option", { value: "" }, aviso), ...nombres.map((n) => h("option", { value: n }, n)));
}

/**
 * Devuelve los tres campos [departamento, provincia, distrito] para ubicarlos en el formulario.
 * `actual` trae los valores guardados; si alguno no está en el catálogo (registros anteriores),
 * las listas quedan sin elegir y se muestra la ubicación anterior como referencia.
 */
export function camposUbigeo(actual = {}) {
  const campos = [
    campo({ etiqueta: "Departamento", name: "departamento", required: true, opciones: [["", "Cargando…"]] }),
    campo({ etiqueta: "Provincia", name: "provincia", required: true, opciones: [["", "—"]] }),
    campo({ etiqueta: "Distrito", name: "distrito", required: true, opciones: [["", "—"]] }),
  ];
  const [dep, prov, dist] = campos.map((c) => c.querySelector("select"));
  let departamentos = [];

  const provinciasDe = () => buscar(departamentos, dep.value)?.provincias ?? [];
  function alElegirDepartamento() {
    if (dep.value) llenar(prov, "Elige…", provinciasDe().map((p) => p.nombre));
    else llenar(prov, "—", []);
    alElegirProvincia();
  }
  function alElegirProvincia() {
    const provincia = buscar(provinciasDe(), prov.value);
    if (provincia) llenar(dist, "Elige…", provincia.distritos);
    else llenar(dist, "—", []);
  }
  dep.addEventListener("change", alElegirDepartamento);
  prov.addEventListener("change", alElegirProvincia);

  cargarUbigeos()
    .then((catalogo) => {
      departamentos = catalogo.departamentos;
      llenar(dep, "Elige…", departamentos.map((d) => d.nombre));
      const d = buscar(departamentos, actual.departamento);
      const p = d && buscar(d.provincias, actual.provincia);
      const t = p && buscar(p.distritos, actual.distrito);
      if (d) dep.value = d.nombre;
      alElegirDepartamento();
      if (p) prov.value = p.nombre;
      alElegirProvincia();
      if (t) dist.value = t;
      if (actual.distrito && !t) {
        const anterior = [actual.distrito, actual.provincia, actual.departamento].join(", ");
        campos[2].append(h("small", {}, `Ubicación anterior: ${anterior}. Elígela de la lista oficial.`));
      }
    })
    .catch((error) => {
      llenar(dep, "No se pudo cargar la lista", []);
      campos[0].append(h("small", { class: "error" }, `${error.message} Cierra y vuelve a intentarlo.`));
    });
  return campos;
}
