// Plataforma · superposiciones entre cooperativas: el superadmin revisa ambos lados y acepta con nota.

import { llamarApi } from "../api.js";
import { cargando, h, reemplazar, vacio } from "../ui.js";
import { tarjetaSuperposicion } from "./superposiciones.js";

export default async function superposicionesPlataforma() {
  const lista = h("div", { class: "lista-tarjetas" }, cargando());

  async function cargar() {
    const datos = await llamarApi("/admin/superposiciones", { sinConsulta: true });
    if (!datos.length) {
      lista.replaceChildren(vacio({ titulo: "Sin superposiciones abiertas", texto: "Ninguna parcela se superpone con otra de una cooperativa distinta." }));
      return;
    }
    const tarjetas = [];
    for (const s of datos) {
      tarjetas.push(await tarjetaSuperposicion(s, { puedeAceptar: true, rutaAceptar: (x) => `/admin/superposiciones/${x.id}/aceptar`, alCambiar: cargar }));
    }
    reemplazar(lista, tarjetas);
  }
  cargar();

  return {
    titulo: "Superposiciones entre cooperativas",
    migas: [["Plataforma"], ["Superposiciones"]],
    contenido: lista,
  };
}
