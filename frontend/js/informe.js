// Informe de hallazgos (Parte 9) con la composición del diseño de referencia: encabezado, contadores por
// grupo, mensaje final y una tarjeta por hallazgo. A diferencia del diseño, no hay colores de gravedad: los
// tres grupos se distinguen por su título, y ningún bloque muestra puntaje, semáforo ni frase que califique
// el lote. Los textos del informe llegan hechos de la API, en español y en inglés.

import { h, icono, rejilla, toast } from "./ui.js";

const GRUPOS = ["impide_cierre", "requiere_atencion", "no_verificado"];
const ETAPAS = { 1: "Parcela", 2: "Acopio y proceso", 3: "Lote" };
const IDIOMAS = [
  ["es", "Español"],
  ["en", "English"],
];

/** Enlace al registro de donde sale el hallazgo; null si es del lote o del sistema. */
export function enlaceSujeto(sujeto, irAPestana) {
  const rutas = { parcela: "parcelas", tanda: "tandas", corrida: "corridas", dop: "dops", dpp: "dpps" };
  if (rutas[sujeto.tipo] && sujeto.id) return h("a", { href: `#/${rutas[sujeto.tipo]}/${sujeto.id}` }, `Ver ${sujeto.codigo}`);
  switch (sujeto.detalle_tipo) {
    case "embarque":
      return irAPestana && h("button", { class: "btn-link", type: "button", onclick: () => irAPestana("embarque") }, "Ir a Embarque");
    case "cooperativa":
    case "expediente_cooperativa":
      return h("a", { href: "#/cooperativa/legal" }, "Ir al expediente de la cooperativa");
    case "importador":
      return h("a", { href: "#/exportacion/importadores" }, "Ir al importador");
    default:
      return null;
  }
}

/** Mensaje final: encabezado, los grupos con su número de hallazgos y una frase por código, contexto y cierre. */
export function mensajeFinal(bloques) {
  return h(
    "div",
    { class: "mf" },
    bloques.map((b) =>
      b.grupo
        ? h("div", { class: "mf-grupo" }, h("b", {}, b.titulo), h("ul", {}, b.frases.map((f) => h("li", {}, f))))
        : h("p", { class: b.titulo ? "mf-contexto" : null }, b.titulo && h("b", {}, `${b.titulo} `), b.frases.join(" ")),
    ),
  );
}

function tarjeta(hz, idioma, informe, irAPestana) {
  const criterio = informe.criterios[String(hz.criterio)]?.[idioma] ?? `Criterio ${hz.criterio}`;
  return h(
    "article",
    { class: "hz-f" },
    h("div", { class: "hz-f-h" }, h("b", {}, hz.hecho[idioma]), h("span", { class: "crit", title: criterio }, `Criterio ${hz.criterio}`)),
    hz.explicacion && h("p", {}, h("span", { class: "sec" }, idioma === "es" ? "Explicación: " : "Explanation (original text in Spanish): "), hz.explicacion),
    h(
      "div",
      { class: "hz-f-m" },
      h("span", {}, `Etapa ${hz.etapa}: ${ETAPAS[hz.etapa]}`),
      hz.peso_en_lote_pct && h("span", { class: "mono" }, `${hz.peso_en_lote_pct} % del lote`),
      enlaceSujeto(hz.sujeto, irAPestana),
    ),
  );
}

function selector(etiqueta, opciones, alCambiar) {
  return h("label", { class: "field hz-filtro" }, etiqueta, h("select", { class: "select", onchange: (e) => alCambiar(e.target.value) }, opciones.map(([v, t]) => h("option", { value: v }, t))));
}

/**
 * El informe completo. `preliminar` dice si cambia con los datos; `codigoDex`, en qué DEX quedó sellado.
 * `irAPestana` permite que un hallazgo lleve a otra pestaña del lote.
 */
export function vistaInforme(informe, { codigoDex = null, irAPestana = null } = {}) {
  let idioma = "es";
  const filtros = { etapa: "", criterio: "" };
  const raiz = h("div", { class: "hz" });
  const grupos = informe.preliminar ? GRUPOS : GRUPOS.slice(1);
  const alimentados = Object.keys(informe.criterios).filter((n) => !["8", "9", "10"].includes(n)).length;

  function copiar() {
    navigator.clipboard
      .writeText(informe.mensaje_texto[idioma])
      .then(() => toast("Mensaje final copiado."))
      .catch(() => toast("No se pudo copiar.", "bad"));
  }

  function hallazgosFiltrados() {
    return informe.hallazgos.filter((x) => (!filtros.etapa || String(x.etapa) === filtros.etapa) && (!filtros.criterio || String(x.criterio) === filtros.criterio));
  }

  const listaHallazgos = h("div", { class: "hz-lista" });
  function dibujarHallazgos() {
    const visibles = hallazgosFiltrados();
    listaHallazgos.replaceChildren(
      ...grupos.flatMap((g) => {
        const del = visibles.filter((x) => x.grupo === g);
        const nombre = informe.grupos[g].nombre[idioma];
        return [
          h("div", { class: "hz-sub" }, `${nombre} — ${del.length}`),
          ...(del.length ? del.map((x) => tarjeta(x, idioma, informe, irAPestana)) : [h("p", { class: "panel-sub" }, idioma === "es" ? "Ningún hallazgo en este grupo con estos filtros." : "No findings in this group with these filters.")]),
        ];
      }),
    );
  }

  function conteos(n) {
    const del = informe.hallazgos.filter((x) => x.criterio === Number(n));
    if (["8", "9", "10"].includes(n)) return idioma === "es" ? "No cubierto por el sistema: corresponde al operador" : "Not covered by the system: for the operator";
    if (!del.length) return "—";
    return grupos
      .map((g) => [informe.grupos[g].nombre[idioma], del.filter((x) => x.grupo === g).length])
      .filter(([, c]) => c)
      .map(([t, c]) => `${t}: ${c}`)
      .join(" · ");
  }

  function dibujar() {
    const t = informe.secciones[idioma];
    raiz.replaceChildren(
      h(
        "header",
        { class: "hz-h" },
        h(
          "div",
          {},
          h("span", { class: "eyebrow" }, codigoDex ? `Informe sellado en el DEX ${codigoDex}` : "Informe preliminar · cambia con los datos hasta que se emita el DEX"),
          h("h2", {}, informe.mensaje[idioma][0].frases[0]),
          h("p", {}, "Cuenta hechos y los ata a su origen. No puntúa el lote ni concluye: la evaluación de riesgo es del operador."),
        ),
        h(
          "div",
          { class: "hz-acts" },
          h(
            "div",
            { class: "seg", role: "tablist", "aria-label": "Idioma del informe" },
            IDIOMAS.map(([clave, texto]) =>
              h(
                "button",
                {
                  type: "button",
                  role: "tab",
                  "aria-selected": String(clave === idioma),
                  onclick: () => {
                    idioma = clave;
                    dibujar();
                  },
                },
                texto,
              ),
            ),
          ),
          h("button", { class: "btn btn-sm", type: "button", onclick: copiar }, icono("copy", "ic-sm"), "Copiar mensaje"),
        ),
      ),
      h(
        "div",
        { class: "hz-tiles" },
        grupos.map((g) => h("div", { class: "hz-tile" }, h("b", {}, String(informe.grupos[g].cantidad)), h("span", {}, informe.grupos[g].nombre[idioma]))),
        h("div", { class: "hz-tile" }, h("b", {}, String(alimentados), h("small", {}, ` de ${Object.keys(informe.criterios).length}`)), h("span", {}, "criterios del art. 10 alimentados desde el flujo")),
      ),
      h("section", { class: "hz-sec" }, h("h3", {}, t.mensaje), mensajeFinal(informe.mensaje[idioma].slice(1))),
      h(
        "section",
        { class: "hz-sec" },
        h("h3", {}, t.hallazgos, h("small", {}, "qué se observó, dónde, con qué dato y a qué criterio corresponde")),
        h(
          "div",
          { class: "hz-filtros" },
          selector("Etapa", [["", "Todas las etapas"], ...Object.entries(ETAPAS).map(([n, e]) => [n, `${n}. ${e}`])], (v) => {
            filtros.etapa = v;
            dibujarHallazgos();
          }),
          selector("Criterio", [["", "Todos los criterios"], ...Object.keys(informe.criterios).map((n) => [n, `Criterio ${n}`])], (v) => {
            filtros.criterio = v;
            dibujarHallazgos();
          }),
        ),
        listaHallazgos,
      ),
      h("section", { class: "hz-sec" }, h("h3", {}, t.no_verificado, h("small", {}, "lo que el sistema recibió sin poder comprobarlo")), h("ul", { class: "hz-nv" }, informe.no_verificado[idioma].map((f) => h("li", {}, f)))),
      h(
        "section",
        { class: "hz-sec" },
        h("h3", {}, t.datos_lote),
        rejilla(informe.datos_lote.map((f) => ({ etiqueta: f.etiqueta[idioma], valor: f.valor[idioma] }))),
      ),
      h("section", { class: "hz-sec" }, h("h3", {}, t.contexto), h("p", { class: "hz-ctx" }, informe.contexto.texto[idioma])),
      h(
        "section",
        { class: "hz-sec" },
        h("h3", {}, "Criterios del artículo 10", h("small", {}, `${alimentados} se alimentan desde el flujo; los otros se nombran para que el operador sepa qué le queda por cubrir`)),
        h(
          "div",
          { class: "tbl-box" },
          h(
            "table",
            { class: "hz-t" },
            h("thead", {}, h("tr", {}, h("th", {}, "N.º"), h("th", {}, "Criterio"), h("th", {}, "En este lote"))),
            h(
              "tbody",
              {},
              Object.entries(informe.criterios).map(([n, nombres]) => h("tr", {}, h("td", { class: "mono" }, n), h("td", {}, nombres[idioma]), h("td", { class: ["8", "9", "10"].includes(n) ? "out" : null }, conteos(n)))),
            ),
          ),
        ),
      ),
    );
    dibujarHallazgos();
  }

  dibujar();
  return raiz;
}
