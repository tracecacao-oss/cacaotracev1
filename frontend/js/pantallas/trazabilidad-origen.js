// Rastreo por origen (Trazabilidad): se busca un productor (nombre o DNI), una parcela (PA-…) o un DOP
// (DOP-…) y se ve a qué lotes llegó su cacao, con las tandas, las corridas y las tandas finales del camino.

import { llamarApi } from "../api.js";
import { estadoLote, nombreProductor, porcentaje, seccionesTrazabilidad } from "../exportacion.js";
import { PRODUCTO, kilos } from "../textos.js";
import { buscador, cargando, conRetraso, errorDeCarga, fecha, h, icono, reemplazar, seccion, vacio } from "../ui.js";

let origen = null;

function tablaLotes(lotes) {
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Lote"), h("th", {}, "Orden"), h("th", { class: "num" }, "Kilos desde el origen"))),
      h(
        "tbody",
        {},
        lotes.map((l) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/lotes-exportacion/${l.lote.id}`, class: "mono" }, l.lote.codigo), " ", estadoLote(l.lote.estado)),
            h("td", {}, h("a", { href: `#/ordenes/${l.orden.id}`, class: "mono" }, l.orden.codigo)),
            h("td", { class: "num mono" }, kilos(l.kg)),
          ),
        ),
      ),
    ),
  );
}

function vistaRecorrido(r) {
  return [
    h("div", { class: "recorrido-h" }, h("b", {}, r.titulo), h("span", { class: "sec" }, r.subtitulo)),
    seccion({
      titulo: "Lotes donde terminó su cacao",
      sub: r.lotes.length ? `${kilos(r.kg_en_lotes)} en ${r.lotes.length} ${r.lotes.length === 1 ? "lote" : "lotes"}, según la genealogía de cada lote.` : "Su cacao todavía no entró a un lote de exportación confirmado.",
      contenido: [r.lotes.length > 0 && tablaLotes(r.lotes), r.lotes_anulados.length > 0 && [h("div", { class: "subtitulo-seccion" }, "Lotes anulados (historial)"), tablaLotes(r.lotes_anulados)]],
    }),
    seccion({
      titulo: "Recorrido de cada tanda",
      sub: "Tanda, DOP, corrida con la proporción de la tanda, tanda final y lotes, con kilos.",
      contenido: r.tandas.length
        ? h(
            "div",
            { class: "tbl-box" },
            h(
              "table",
              { class: "tabla" },
              h("thead", {}, h("tr", {}, h("th", {}, "Tanda y DOP"), h("th", { class: "ocultar-sm" }, "Parcela"), h("th", {}, "Corrida"), h("th", {}, "Tanda final"), h("th", {}, "Lotes"))),
              h(
                "tbody",
                {},
                r.tandas.map((t) =>
                  h(
                    "tr",
                    {},
                    h(
                      "td",
                      {},
                      h("a", { href: `#/tandas/${t.tanda.id}`, class: "mono" }, t.tanda.codigo),
                      h("span", { class: "sec" }, `${fecha(t.recibida_en)} · ${kilos(t.peso_kg)} · ${PRODUCTO[t.estado_producto]}`),
                      t.dop && h("a", { href: `#/dops/${t.dop.id}`, class: "sec mono" }, t.dop.codigo),
                    ),
                    h("td", { class: "ocultar-sm" }, h("span", { class: "mono" }, t.parcela_codigo), h("span", { class: "sec" }, nombreProductor(t.productor))),
                    h("td", {}, t.corrida ? [h("a", { href: `#/corridas/${t.corrida.id}`, class: "mono" }, t.corrida.codigo), t.proporcion && h("span", { class: "sec" }, porcentaje(t.proporcion))] : h("span", { class: "sec" }, "Sin corrida")),
                    h("td", {}, t.tanda_final ? [h("a", { href: `#/tandas-finales/${t.tanda_final.id}`, class: "mono" }, t.tanda_final.codigo), h("span", { class: "sec" }, kilos(t.kg_en_tanda_final))] : "—"),
                    h("td", {}, t.lotes.length ? t.lotes.map((l) => h("span", { class: "linea" }, h("a", { href: `#/lotes-exportacion/${l.lote.id}`, class: "mono" }, l.lote.codigo), ` ${kilos(l.kg)}`)) : "—"),
                  ),
                ),
              ),
            ),
          )
        : h("p", { class: "panel-sub" }, "Sin tandas recibidas en la cooperativa."),
    }),
  ];
}

export default async function trazabilidadOrigen() {
  const resultados = h("div", { class: "opciones resultados-origen" });
  const vista = h("div", {});
  let parcelas = null;
  let dops = null;

  async function abrir(tipo, id, etiqueta) {
    origen = { tipo, id, etiqueta };
    reemplazar(vista, cargando());
    try {
      const ruta = { productor: "productores", parcela: "parcelas", dop: "dops" }[tipo];
      reemplazar(vista, vistaRecorrido(await llamarApi(`/trazabilidad/${ruta}/${id}`)));
    } catch (error) {
      reemplazar(vista, errorDeCarga(error));
    }
  }

  function opcion(tipo, id, titulo, detalle) {
    return h(
      "button",
      {
        class: "opcion",
        type: "button",
        onclick: () => {
          reemplazar(resultados);
          abrir(tipo, id, titulo);
        },
      },
      icono({ productor: "productores", parcela: "parcelas", dop: "file" }[tipo]),
      h("span", {}, h("b", {}, titulo), h("span", { class: "sec" }, detalle)),
      icono("chev", "chev-derecha"),
    );
  }

  async function buscar(texto) {
    const q = texto.trim();
    if (q.length < 2) {
      reemplazar(resultados);
      return;
    }
    try {
      if (/^pa-/i.test(q)) {
        parcelas ??= await llamarApi("/parcelas");
        const encontradas = parcelas.filter((p) => p.codigo.toLowerCase().includes(q.toLowerCase())).slice(0, 10);
        reemplazar(resultados, encontradas.length ? encontradas.map((p) => opcion("parcela", p.id, `${p.codigo} · ${p.nombre}`, `Parcela de ${p.productor.nombres} ${p.productor.apellidos}`)) : h("p", { class: "panel-sub" }, "Ninguna parcela con ese código."));
      } else if (/^dop-/i.test(q)) {
        dops ??= await llamarApi("/dops");
        const encontrados = dops.filter((d) => d.codigo.toLowerCase().includes(q.toLowerCase())).slice(0, 10);
        reemplazar(resultados, encontrados.length ? encontrados.map((d) => opcion("dop", d.id, d.codigo, `DOP de ${nombreProductor(d.productor)} · ${d.parcela_codigo}`)) : h("p", { class: "panel-sub" }, "Ningún DOP con ese código."));
      } else {
        const pagina = await llamarApi("/productores", { parametros: { q, por_pagina: 10 } });
        reemplazar(resultados, pagina.items.length ? pagina.items.map((p) => opcion("productor", p.id, nombreProductor(p), `DNI ${p.dni}`)) : h("p", { class: "panel-sub" }, "Ningún productor coincide."));
      }
    } catch (error) {
      reemplazar(resultados, errorDeCarga(error));
    }
  }

  const caja = buscador({ placeholder: "Productor (nombre o DNI), parcela (PA-…) o DOP (DOP-…)", etiqueta: "Buscar el origen", alEscribir: conRetraso(buscar) });
  if (origen) await abrir(origen.tipo, origen.id, origen.etiqueta);
  else reemplazar(vista, vacio({ titulo: "Busca un origen", texto: "Escribe el nombre o el DNI de un productor, el código de una parcela o el de un DOP." }));

  return {
    titulo: "Rastreo por origen",
    antetitulo: "Trazabilidad",
    descripcion: "Desde un productor, una parcela o un DOP, a qué lotes de exportación llegó su cacao.",
    migas: [["Trazabilidad", "#/trazabilidad"], ["Rastreo por origen"]],
    secciones: seccionesTrazabilidad(),
    contenido: h("section", { class: "panel inspector" }, h("div", { class: "barra-lista" }, caja), resultados, vista),
  };
}
