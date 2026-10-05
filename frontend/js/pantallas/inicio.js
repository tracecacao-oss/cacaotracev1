// Inicio: saludo, nombre de la cooperativa y número de productores afiliados.

import { llamarApi } from "../api.js";
import { enConsulta, estado, nombreCooperativa } from "../estado.js";
import { h } from "../ui.js";

export default async function inicio() {
  const { total } = await llamarApi("/productores", { parametros: { por_pagina: 1 } });
  const saludo = enConsulta() ? "Consulta de la cooperativa" : `Hola, ${estado.usuario.nombres}`;

  return {
    titulo: saludo,
    contenido: [
      h("p", { class: "panel-sub" }, nombreCooperativa()),
      h(
        "div",
        { class: "kpis" },
        h(
          "a",
          { class: "kpi", href: "#/productores" },
          h("span", { class: "kpi-l" }, "Productores afiliados"),
          h("span", { class: "kpi-v mono" }, String(total)),
        ),
      ),
    ],
  };
}
