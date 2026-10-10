// Cuadro de legalidad por requisito del lote (adenda 7, sección 5): cada requisito del orientador con cuántos
// sujetos del lote le aplican y en qué estado están, con el porcentaje de la masa del lote que aportan. Lo
// calcula la API; esta vista solo lo dibuja. No hay totales, puntajes ni colores que califiquen un estado:
// cada cuenta es un enlace a las parcelas o los productores que hay detrás, y cada uno lleva a su ficha.

import { llamarApi } from "./api.js";
import { abrirModal, cargando, fecha, h, reemplazar } from "./ui.js";

const GRUPOS = [
  ["parcela", "Parcelas"],
  ["productor", "Productores"],
  ["organizacion", "Organización"],
  ["lote", "Lote"],
];
const COLUMNAS = [
  ["aplica", "Le aplica a"],
  ["con_sustento", "Con sustento"],
  ["por_atender", "Por atender"],
  ["sin_sustento", "Sin sustento"],
];
// Los estados de cada columna (sección 5.3).
const ESTADOS_COLUMNA = {
  aplica: null,
  con_sustento: ["sustentado", "por_vencer", "declarado"],
  por_atender: ["por_atender"],
  sin_sustento: ["sin_sustento", "vencido", "sin_dato"],
};
const ESTADOS = {
  sustentado: "Sustentado",
  por_vencer: "Por vencer",
  declarado: "Declarado",
  por_atender: "Por atender",
  sin_sustento: "Sin sustento",
  vencido: "Vencido",
  sin_dato: "Falta el dato",
  no_aplica: "No aplica",
};
const NIVELES = { declarado: "declarado", documentado: "documentado", verificado_en_fuente: "verificado en fuente" };
const NIVEL_ORIENTADOR = { alto: "alto", bajo: "bajo" };
const DILIGENCIA = { aligerada: "aligerada", estandar: "estándar" };

/** Un decimal en pantalla; el contenido sellado lleva dos. */
function pct(valor) {
  return `${Number(valor).toLocaleString("es-PE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

function etiquetaFila(f) {
  const orientador = f.nivel_texto ? ` · ${f.nivel_texto}` : f.nivel_orientador ? ` · nivel ${NIVEL_ORIENTADOR[f.nivel_orientador]}, diligencia ${DILIGENCIA[f.diligencia]}` : "";
  return h("div", {}, h("b", {}, f.nombre), h("span", { class: "sec" }, `Orientador, ${f.referencias.length ? f.referencias.join(", ") : "varios"}${orientador}`));
}

/** Los sujetos de una columna de una fila, cada uno con su estado, su peso y su sustento, y su ficha. */
function abrirSujetos(loteId, fila, columna, titulo) {
  const cuerpo = h("div", {}, cargando());
  const { cerrar } = abrirModal({ titulo: `${fila.nombre}: ${titulo.toLowerCase()}`, subtitulo: "Las parcelas o los productores que hay detrás de la cuenta.", contenido: cuerpo, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cerrar")] });
  llamarApi(`/lotes/${loteId}/legalidad/${fila.codigo}`)
    .then(({ fila: detalle }) => {
      const estados = ESTADOS_COLUMNA[columna];
      const sujetos = detalle.sujetos.filter((s) => (estados ? estados.includes(s.estado) : s.estado !== "no_aplica"));
      const ruta = (s) => (s.tipo === "parcela" ? `#/parcelas/${s.id}` : `#/productores/${s.id}/declaracion`);
      reemplazar(
        cuerpo,
        h(
          "ul",
          { class: "casillas" },
          sujetos.map((s) =>
            h(
              "li",
              { class: "casilla" },
              h(
                "div",
                { class: "casilla-h" },
                h("div", {}, h("a", { href: ruta(s), onclick: () => cerrar() }, s.codigo ? `${s.codigo} · ${s.nombre}` : s.nombre), h("span", { class: "sec" }, s.sustento ?? "—")),
                h("span", { class: "fila-acciones" }, h("span", { class: "badge" }, ESTADOS[s.estado] ?? s.estado), s.nivel && h("span", { class: "badge" }, NIVELES[s.nivel]), h("span", { class: "badge mono" }, pct(s.peso))),
              ),
            ),
          ),
        ),
      );
    })
    .catch((error) => reemplazar(cuerpo, h("p", { class: "alerta bad" }, error.message)));
}

function celdaCuenta(loteId, fila, columna, titulo) {
  const x = fila[columna];
  const texto = `${x.n} (${pct(x.pct)})`;
  const cuenta = x.n > 0 ? h("button", { class: "btn-link mono", type: "button", onclick: () => abrirSujetos(loteId, fila, columna, titulo) }, texto) : h("span", { class: "mono" }, texto);
  const niveles = columna === "con_sustento" && x.n > 0 && h("span", { class: "sec" }, Object.entries(x.niveles).map(([n, c]) => `${NIVELES[n]} ${c}`).join(" · "));
  return h("td", { "data-columna": titulo }, cuenta, niveles);
}

function tablaConteos(loteId, filas) {
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla cuadro-legalidad" },
      h("thead", {}, h("tr", {}, h("th", {}, "Requisito"), COLUMNAS.map(([, t]) => h("th", {}, t)))),
      h(
        "tbody",
        {},
        filas.map((f) =>
          h(
            "tr",
            {},
            h("td", { class: "cuadro-requisito" }, etiquetaFila(f)),
            f.aplica.n === 0
              ? h("td", { colspan: 4, class: "sec" }, "No aplica a este lote")
              : COLUMNAS.map(([c, t]) => celdaCuenta(loteId, f, c, t)),
          ),
        ),
      ),
    ),
  );
}

function tablaEstado(filas) {
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla cuadro-legalidad" },
      h("thead", {}, h("tr", {}, h("th", {}, "Requisito"), h("th", {}, "Estado"), h("th", {}, "Falta"))),
      h(
        "tbody",
        {},
        filas.map((f) =>
          h(
            "tr",
            {},
            h("td", { class: "cuadro-requisito" }, etiquetaFila(f)),
            h("td", { "data-columna": "Estado" }, h("span", { class: "badge" }, ESTADOS[f.estado] ?? f.estado), f.nivel && h("span", { class: "sec" }, NIVELES[f.nivel]), f.numero && h("span", { class: "sec mono" }, `N.º ${f.numero}${f.difiere ? " · difiere del lote" : ""}`)),
            h("td", { "data-columna": "Falta" }, f.falta?.length ? f.falta.join(", ") : "—"),
          ),
        ),
      ),
    ),
  );
}

/** El cuadro completo, agrupado por de quién es cada fila, con los requisitos que no se piden debajo. */
export function vistaCuadro(cuadro, loteId) {
  if (cuadro.estado === "no_disponible") {
    return h("p", { class: "alerta info" }, `El DEX ${cuadro.dex} se emitió antes del cuadro de legalidad por requisito: no lo trae.`);
  }
  const encabezado =
    cuadro.estado === "sellado"
      ? h("div", { class: "verif" }, h("div", {}, h("b", {}, `Sellado en el DEX ${cuadro.dex}`), h("span", {}, `Calculado al emitirlo, el ${fecha(cuadro.calculado_en, { hora: true })}. No cambia aunque cambien los datos.`)))
      : h("div", { class: "verif" }, h("div", {}, h("b", {}, "Preliminar"), h("span", {}, "Con el estado de hoy: cambia con los datos hasta que se emita el DEX, y entonces queda sellado.")));
  return h(
    "div",
    { class: "cuadro" },
    encabezado,
    h(
      "p",
      { class: "panel-sub" },
      "Los requisitos son los del documento orientador del MIDAGRI, el MINCETUR y ADEX (2026), que no es jurídicamente vinculante. El cuadro cuenta los sujetos del lote en cada estado y el porcentaje de la masa del lote que aportan; no califica al lote.",
    ),
    GRUPOS.map(([grupo, titulo]) => {
      const filas = cuadro.filas.filter((f) => f.de === grupo);
      if (!filas.length) return null;
      return [h("h4", { class: "dex-sub" }, titulo), grupo === "parcela" || grupo === "productor" ? tablaConteos(loteId, filas) : tablaEstado(filas)];
    }),
    h(
      "details",
      { class: "no-aplican" },
      h("summary", {}, `Requisitos que no se piden (${cuadro.no_se_piden.length})`),
      h("ul", { class: "lista-simple" }, cuadro.no_se_piden.map((x) => h("li", {}, h("b", {}, `${x.referencia} · ${x.requisito}. `), x.motivo))),
    ),
  );
}
