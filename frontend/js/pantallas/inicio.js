// Inicio: saludo, nombre de la cooperativa y número de productores afiliados, con el aspecto del
// resumen del diseño (saludo según la hora y tarjeta de indicador con ícono).

import { llamarApi } from "../api.js";
import { enConsulta, estado, nombreCooperativa } from "../estado.js";
import { h, icono } from "../ui.js";

const HORA_LIMA = new Intl.DateTimeFormat("es-PE", { timeZone: "America/Lima", hour: "numeric", hourCycle: "h23" });

function saludo() {
  const hora = Number(HORA_LIMA.format(new Date()));
  return hora < 12 ? "Buenos días" : hora < 19 ? "Buenas tardes" : "Buenas noches";
}

export default async function inicio() {
  const { total } = await llamarApi("/productores", { parametros: { por_pagina: 1 } });
  const titulo = enConsulta() ? "Consulta de la cooperativa" : `${saludo()}, ${estado.usuario.nombres}`;

  return {
    titulo,
    migas: [["Inicio"]],
    antetitulo: nombreCooperativa(),
    contenido: h(
      "section",
      { class: "kpis", "aria-label": "Indicadores" },
      h(
        "a",
        { class: "kpi is-ok", href: "#/productores" },
        h("span", { class: "kpi-ic" }, icono("users")),
        h("span", { class: "kpi-l" }, "Productores afiliados"),
        h("span", { class: "kpi-v" }, String(total), h("small", {}, total === 1 ? "productor" : "productores")),
        h("span", { class: "kpi-s" }, "Ver el padrón"),
      ),
    ),
  };
}
