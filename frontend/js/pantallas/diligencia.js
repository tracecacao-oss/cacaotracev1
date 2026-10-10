// Diligencia de la organización (adenda 6, secciones 6 y 10): arriba el cuadro de señales, que dice con cifras
// dónde se espera una actuación, con "Registrar actuación" en cada tema; debajo, las actuaciones con sus
// filtros; y la lista de productos buscados en el registro del SENASA, para repartir. Nada de esto frena un
// lote: lo que falte llega al informe de hallazgos. Registran el administrador y el operador; anula solo el
// administrador; el lector solo ve.

import { descargarArchivo, llamarApi } from "../api.js";
import { TEMAS, abrirActuacion, tablaActuaciones } from "../diligencia.js";
import { rolEfectivo } from "../estado.js";
import { ESTADOS_REQUISITO } from "../textos.js";
import { cabeceraFicha, cargando, claseTono, errorDeCarga, fecha, h, icono, leyendaTonos, ordenarPorTono, reemplazar, seccion, toast, vacio } from "../ui.js";

const ESTADOS_SENAL = {
  sustentado: ["ok", "Con actuación vigente"],
  sin_sustento: ["warn", "Falta una actuación"],
  no_se_espera: ["", "No se espera"],
};
const TONO_SENAL = { sustentado: "listo", sin_sustento: "falta", no_se_espera: "opcional" };
const REVISIONES = {
  figura: ["ok", "Figura en el registro"],
  no_figura: ["warn", "No figura en el registro"],
  sin_revisar: ["", "Sin buscar"],
};
const TIPOS_PRODUCTO = { fertilizante: "Fertilizante", herbicida: "Herbicida", insecticida: "Insecticida", fungicida: "Fungicida", otro: "Otro" };

function insignia([clase, texto]) {
  return h("span", { class: `badge ${clase}`.trim() }, h("span", { class: "dot" }), texto);
}

function cuadroSenales(d, registra, recargar) {
  return h(
    "ul",
    { class: "casillas" },
    ordenarPorTono(d.senales, (s) => TONO_SENAL[s.estado]).map((s) =>
      h(
        "li",
        { class: claseTono(TONO_SENAL[s.estado]) },
        h(
          "div",
          { class: "casilla-h" },
          h(
            "div",
            {},
            h("b", {}, s.nombre),
            h("span", { class: "sec" }, `Orientador, ${s.referencias.join(", ")} · diligencia ${s.diligencia === "estandar" ? "estándar" : "aligerada"} · se espera: ${s.regla.toLowerCase()}`),
            h("span", { class: "senal-cuenta" }, s.texto),
          ),
          h(
            "span",
            { class: "fila-acciones" },
            insignia(ESTADOS_SENAL[s.estado]),
            s.actuaciones_vigentes > 0 && h("span", { class: "badge" }, `${s.actuaciones_vigentes} vigente${s.actuaciones_vigentes === 1 ? "" : "s"} · última ${fecha(s.ultima)}`),
          ),
        ),
        registra && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirActuacion(d, { tema: s.codigo, alGuardar: recargar }) }, icono("mas"), "Registrar actuación")),
      ),
    ),
  );
}

function listaActuaciones(recargar) {
  const caja = h("div", {}, cargando());
  const filtros = { tema: "", tipo: "" };
  const chips = h("div", { class: "fchips", role: "group", "aria-label": "Tema", "data-etiqueta": "Tema" });
  for (const [valor, texto] of [["", "Todos"], ...TEMAS]) {
    chips.append(h("button", { class: "fchip", type: "button", "data-valor": valor, onclick: () => ((filtros.tema = valor), cargar()) }, texto));
  }
  async function cargar() {
    for (const b of chips.children) b.setAttribute("aria-pressed", String(b.dataset.valor === filtros.tema));
    try {
      const lista = await llamarApi("/actuaciones", { parametros: filtros });
      reemplazar(caja, lista.length ? tablaActuaciones(lista, recargar) : vacio({ titulo: "Sin actuaciones", texto: filtros.tema ? "Ninguna actuación en ese tema." : "Registra lo que la organización hace en su zona: consultas, capacitaciones, visitas y apoyo a los productores." }));
    } catch (error) {
      reemplazar(caja, errorDeCarga(error));
    }
  }
  cargar();
  return [h("div", { class: "barra-lista" }, chips), caja];
}

function listaProductos() {
  const caja = h("div", {}, cargando());
  llamarApi("/cooperativa/productos-revisados")
    .then((p) =>
      reemplazar(
        caja,
        p.productos.length === 0
          ? vacio({ titulo: "Sin productos declarados", texto: "Aquí aparecen los productos que declaran los productores en su declaración anual vigente." })
          : h(
              "div",
              { class: "tbl-box" },
              h(
                "table",
                { class: "tabla" },
                h("thead", {}, h("tr", {}, h("th", {}, "Producto"), h("th", {}, "Búsqueda en el SENASA"), h("th", { class: "ocultar-sm" }, "Buscado el"), h("th", {}, "Productores"))),
                h(
                  "tbody",
                  {},
                  p.productos.map((x) =>
                    h(
                      "tr",
                      {},
                      h("td", {}, h("b", {}, x.nombre), h("span", { class: "sec" }, TIPOS_PRODUCTO[x.tipo] ?? x.tipo)),
                      h("td", {}, insignia(REVISIONES[x.revision] ?? ["", x.revision]), x.registro && h("span", { class: "sec mono" }, x.registro)),
                      h("td", { class: "ocultar-sm fecha" }, x.revisado_en ? fecha(x.revisado_en) : "—"),
                      h("td", {}, String(x.productores)),
                    ),
                  ),
                ),
              ),
            ),
        h("p", { class: "panel-sub fila-acciones" }, "Consultas del SENASA: ", p.consultas.map((c) => h("a", { href: c.url, target: "_blank", rel: "noopener" }, c.nombre))),
      ),
    )
    .catch((error) => reemplazar(caja, errorDeCarga(error)));
  return caja;
}

export default async function diligencia({ recargar }) {
  const d = await llamarApi("/cooperativa/diligencia");
  const registra = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  const faltan = d.senales.filter((s) => s.estado === "sin_sustento").length;
  const descargar = () => descargarArchivo("/cooperativa/productos-revisados/hoja", `productos-senasa-${new Date().toISOString().slice(0, 10)}.pdf`).catch((error) => toast(error.message, "bad"));
  return {
    titulo: "Diligencia",
    migas: [["Cooperativa", "#/cooperativa"], ["Diligencia"]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("shield")),
        titulo: "Diligencia de la organización",
        detalle: `Lo que la organización hace en su zona para conocer o reducir un riesgo de legalidad. Una actuación cuenta para sus temas durante ${d.vigencia_meses} meses. No frena un lote.`,
        cifra: String(faltan),
        cifraTexto: faltan === 1 ? "tema sin actuación" : "temas sin actuación",
        accion: registra && h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirActuacion(d, { alGuardar: recargar }) }, icono("mas"), "Registrar actuación"),
      }),
      seccion({
        titulo: "Cuadro de señales",
        sub: "Con el estado de hoy de los productores afiliados y sus parcelas activas. Con diligencia estándar se espera actuar siempre que la organización esté expuesta; con diligencia aligerada, solo cuando salta un caso.",
        contenido: [
          h("p", { class: "requisito-org" }, h("b", {}, d.requisito.nombre), " ", insignia(ESTADOS_REQUISITO[d.requisito.estado] ?? ["", d.requisito.estado]), d.requisito.falta.length > 0 && h("span", { class: "sec" }, ` Falta en: ${d.requisito.falta.join(", ")}.`)),
          leyendaTonos({ bloquea: null, falta: "se espera una actuación y no hay una vigente", listo: "con actuación vigente", opcional: "no se espera" }),
          cuadroSenales(d, registra, recargar),
        ],
      }),
      seccion({ titulo: "Actuaciones", sub: "Las anuladas se conservan. La evidencia no sale del sistema: el DEX dice si existe.", contenido: listaActuaciones(recargar) }),
      seccion({
        titulo: "Productos buscados en el SENASA",
        sub: "Los productos que declaran los productores en su declaración anual vigente, con la búsqueda más reciente del personal. Esta lista no reemplaza la consulta del registro.",
        acciones: h("button", { class: "btn btn-sm", type: "button", onclick: descargar }, icono("download"), "Descargar lista de productos"),
        contenido: listaProductos(),
      }),
    ),
  };
}
