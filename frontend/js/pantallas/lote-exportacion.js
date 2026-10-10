// Detalle de un lote de exportación con pestañas Selección, Genealogía, Indicadores, Embarque y
// Recomprobación (Parte 8), y Hallazgos y DEX (Parte 9). Un lote con desviación FIFO muestra su etiqueta y su
// motivo; uno bloqueado, una franja fija con las comprobaciones que fallan. Los resultados se nombran "sin
// observaciones" y "con observaciones". Un lote armado se anula con motivo; uno bloqueado o listo, solo un
// administrador. El DEX lo emite solo un administrador, sobre un lote listo, después de leer el mensaje final
// y marcar la casilla de entendimiento.

import { llamarApi } from "../api.js";
import { abrirCotejo, anularDocumento, verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { estadoLote, insignia, insigniaFifo, tarjetasIndicadores, vistaGenealogia } from "../exportacion.js";
import { hoyLima as hoy } from "../fechas.js";
import { mensajeFinal, vistaInforme } from "../informe.js";
import { codigoQr, huella } from "../tandas.js";
import { insigniaNivel, kilos } from "../textos.js";
import { abrirModal, cabeceraFicha, campo, cargando, claseTono, enviarCon, errorDeCarga, fecha, h, icono, leyendaTonos, ordenarPorTono, reemplazar, rejilla, seccion, toast } from "../ui.js";

const PESTANAS = [
  ["seleccion", "Selección"],
  ["genealogia", "Genealogía"],
  ["indicadores", "Indicadores"],
  ["embarque", "Embarque"],
  ["recomprobacion", "Recomprobación"],
  ["hallazgos", "Hallazgos"],
  ["dex", "DEX"],
];
const CASILLA = "Entiendo que el DEX no declara el nivel de riesgo ni reemplaza la DDS";
const ARCHIVOS = {
  paquete: "Paquete completo (.zip)",
  pdf_es: "Expediente en PDF, en español",
  pdf_en: "Expediente en PDF, en inglés",
  geojson: "GeoJSON de las parcelas",
  anexo_ii: "Datos del Anexo II (JSON)",
  hallazgos: "Informe de hallazgos (JSON)",
  leeme: "LEEME.txt",
};
const RESULTADO = {
  sin_observaciones: ["ok", "Sin observaciones"],
  con_observaciones: ["warn", "Con observaciones"],
};
let recordada = { id: null, clave: "seleccion" };

function abrirAnulacion(l, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-lote" }, "Anular lote");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-lote" },
    h(
      "p",
      { class: "alerta warn" },
      l.estado === "en_armado"
        ? "La selección se descarta y la orden queda abierta para otro lote."
        : "Los kilos vuelven al saldo de cada tanda final, las agotadas vuelven al stock y la orden queda abierta para otro lote. La genealogía se conserva como historial.",
    ),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular lote", subtitulo: l.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/lotes/${l.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Lote anulado.", "warn");
    alAnular();
  });
}

function puedeAnular(l) {
  const rol = rolEfectivo();
  if (["en_armado", "armado"].includes(l.estado)) return ["admin_cooperativa", "operador"].includes(rol);
  return ["bloqueado", "listo"].includes(l.estado) && rol === "admin_cooperativa";
}

function pestanaSeleccion(l, opera, recargar) {
  const total = l.asignaciones.reduce((s, a) => s + Number(a.kg_asignados), 0);
  return seccion({
    titulo: "Selección",
    sub: l.estado === "en_armado" ? "La selección todavía puede cambiar. Los saldos se descuentan al confirmar." : "Los kilos que el lote tomó de cada tanda final. Un lote confirmado ya no cambia su stock.",
    acciones: [
      opera && l.estado === "en_armado" && h("a", { class: "btn btn-sm", href: `#/lotes-exportacion/${l.id}/armar` }, icono("layers"), "Cambiar la selección"),
      puedeAnular(l) && h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacion(l, recargar) }, "Anular lote"),
    ].filter(Boolean),
    contenido: l.asignaciones.length
      ? h(
          "div",
          { class: "tbl-box" },
          h(
            "table",
            { class: "tabla" },
            h("thead", {}, h("tr", {}, h("th", {}, "Tanda final"), h("th", { class: "ocultar-sm" }, "Ingreso al stock"), h("th", { class: "num" }, "Saldo actual"), h("th", { class: "num" }, "Kilos del lote"))),
            h(
              "tbody",
              {},
              l.asignaciones.map((a) =>
                h(
                  "tr",
                  {},
                  h("td", {}, h("a", { href: `#/tandas-finales/${a.tanda_final_id}`, class: "mono" }, a.codigo), h("span", { class: "sec" }, [a.corrida_codigo, a.dpp?.codigo].filter(Boolean).join(" · "))),
                  h("td", { class: "ocultar-sm" }, fecha(a.ingreso_stock_en, { hora: true })),
                  h("td", { class: "num mono" }, kilos(a.saldo_kg)),
                  h("td", { class: "num mono" }, kilos(a.kg_asignados)),
                ),
              ),
            ),
            h("tfoot", {}, h("tr", {}, h("th", { colspan: 3 }, "Total"), h("th", { class: "num mono" }, kilos(total)))),
          ),
        )
      : h("p", { class: "panel-sub" }, "Sin tandas finales seleccionadas."),
  });
}

function pestanaGenealogia(l) {
  if (l.estado === "en_armado") return seccion({ titulo: "Genealogía", contenido: h("p", { class: "panel-sub" }, "La genealogía se calcula al confirmar el lote.") });
  const caja = h("div", {}, cargando());
  llamarApi(`/lotes/${l.id}/genealogia`)
    .then((g) => reemplazar(caja, vistaGenealogia(g, { lote: l, incrustada: true })))
    .catch((error) => reemplazar(caja, errorDeCarga(error)));
  return [seccion({ titulo: "Genealogía", sub: "De los kilos del lote, cuántos vienen de cada parcela, con las proporciones que fijó cada corrida." }), caja];
}

function pestanaIndicadores(l) {
  if (!l.indicadores) return seccion({ titulo: "Indicadores", contenido: h("p", { class: "panel-sub" }, "Los indicadores se calculan al confirmar el lote.") });
  return seccion({
    titulo: "Indicadores",
    sub: "Se calculan y se muestran tal cual. Ninguno califica el lote: todos pasan al informe de hallazgos.",
    contenido: tarjetasIndicadores(l.indicadores),
  });
}

// ---------- Embarque ----------

function abrirCargaEmbarque(l, tipo, alCargar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-embarque" }, "Cargar documento");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  // Adenda 6, sección 7: la declaración aduanera pide número y fecha de numeración; la emite SUNAT.
  const dam = tipo.codigo === "dam";
  const formulario = h(
    "form",
    { class: "form", id: "form-embarque" },
    dam
      ? h(
          "div",
          { class: "grid2" },
          campo({ etiqueta: "Número de la declaración", name: "numero", required: true, minlength: 5, maxlength: 30, class: "input mono", ayuda: "Como lo da SUNAT: aduana, año, régimen y número." }),
          campo({ etiqueta: "Fecha de numeración", name: "fecha_emision", type: "date", max: hoy(), required: true }),
        )
      : [
          h("div", { class: "grid2" }, campo({ etiqueta: "Número", name: "numero", required: true, maxlength: 200 }), campo({ etiqueta: "Entidad emisora", name: "entidad_emisora", required: true, maxlength: 200, ayuda: `Habitualmente: ${tipo.emisor_habitual}.` })),
          campo({ etiqueta: "Fecha de emisión", name: "fecha_emision", type: "date", max: hoy(), required: true }),
        ],
    h("label", { class: "field" }, "Archivo (foto o PDF, hasta 10 MB)", archivo),
    h("p", { class: "panel-sub" }, dam && l.estado === "cerrado" ? "El DEX emitido no cambia: la declaración aduanera se muestra aparte, en la pestaña DEX y en su página pública." : "El sistema no lee el documento ni compara sus cifras con las del lote: eso lo revisa una persona."),
  );
  const { cerrar } = abrirModal({ titulo: `Cargar: ${tipo.nombre}`, subtitulo: l.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    cuerpo.append("tipo", tipo.codigo);
    for (const clave of ["numero", "entidad_emisora", "fecha_emision"]) if (datos[clave]) cuerpo.append(clave, datos[clave]);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi(`/lotes/${l.id}/documentos`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast(dam ? "Declaración aduanera cargada." : "Documento cargado. Recomprueba el lote para que lo tome en cuenta.");
    alCargar();
  });
}

/** Los obligatorios: rojo mientras falta (el lote no queda listo), verde cargado. La declaración aduanera no
 * frena: sin color mientras falta, verde cargada; va después de los obligatorios (adenda 6, sección 10). */
function tonoEmbarque(t) {
  if (t.cargado) return "listo";
  return t.obligatorio ? "bloquea" : "opcional";
}

function filaEmbarque(l, t, opera, recargar) {
  const vigentes = t.documentos.filter((d) => d.vigente);
  const cerrado = l.estado === "cerrado";
  const consultas = t.consultas.map((c) => [c.url, c.nombre]);
  return h(
    "li",
    { class: claseTono(tonoEmbarque(t)) },
    h(
      "div",
      { class: "casilla-h" },
      h("div", {}, h("b", {}, t.nombre), h("span", { class: "sec" }, `Emisor habitual: ${t.emisor_habitual}`)),
      h("span", { class: "fila-acciones" }, insignia(t.cargado ? ["ok", "Cargado"] : t.obligatorio ? ["bad", "Falta"] : ["", "No frena el lote"]), vigentes.some((d) => d.cotejado_en) && insigniaNivel("verificado_en_fuente")),
    ),
    !t.obligatorio && consultas.length > 0 && h("p", { class: "panel-sub fila-acciones" }, "Consulta pública: ", consultas.map(([url, nombre]) => h("a", { href: url, target: "_blank", rel: "noopener" }, nombre))),
    vigentes.map((d) =>
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, `N.º ${d.numero ?? "—"} · ${d.entidad_emisora ?? "—"} · ${t.codigo === "dam" ? "numerada" : "emitido"} ${fecha(d.fecha_emision)}`),
        d.cotejado_en && h("span", { class: "sec" }, `Cotejada el ${fecha(d.cotejado_en)}: ${d.cotejo_nota}`),
        h(
          "span",
          { class: "fila-acciones" },
          h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
          opera && t.registro_consultable && !d.cotejado_en && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCotejo(d, { titulo: t.nombre, consultas, ayuda: "Anota qué consulta usaste y si el número, la fecha y el exportador coinciden." }, recargar) }, "Cotejar en fuente"),
          opera && t.editable && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => anularDocumento(d, recargar) }, "Anular"),
        ),
      ),
    ),
    opera && t.editable && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCargaEmbarque(l, t, recargar) }, icono("upload"), cerrado && !vigentes.length ? "Agregar la declaración aduanera" : vigentes.length ? "Cargar otro" : "Cargar documento")),
  );
}

function pestanaEmbarque(l, opera, recargar) {
  const caja = h("div", {}, cargando());
  llamarApi(`/lotes/${l.id}/documentos`)
    .then((e) =>
      reemplazar(
        caja,
        e.faltan.length > 0 && h("p", { class: "alerta bad" }, `Falta: ${e.faltan.join(", ")}.`),
        leyendaTonos({ bloquea: "falta: el lote no queda listo", falta: null, listo: "cargado", opcional: "no frena el lote" }),
        h(
          "ul",
          { class: "casillas" },
          [...ordenarPorTono(e.tipos.filter((t) => t.obligatorio), tonoEmbarque), ...e.tipos.filter((t) => !t.obligatorio)].map((t) => filaEmbarque(l, t, opera, recargar)),
        ),
      ),
    )
    .catch((error) => reemplazar(caja, errorDeCarga(error)));
  return seccion({
    titulo: "Documentos de embarque",
    sub:
      l.estado === "cerrado"
        ? "El lote tiene DEX: sus documentos de embarque ya no cambian. Solo se puede agregar la declaración aduanera, que se muestra aparte sin cambiar el DEX."
        : "Los cuatro obligatorios deben estar cargados antes de emitir el DEX. Si falta uno, el lote deja de estar listo. La declaración aduanera no frena el lote y se puede agregar también después del DEX.",
    contenido: caja,
  });
}

// ---------- Recomprobación ----------

function enlaceCaso(c, irAPestana) {
  switch (c.tipo) {
    case "parcela":
      return h("a", { href: `#/parcelas/${c.id}` }, "Ir a la parcela");
    case "dop":
      return h("a", { href: `#/dops/${c.id}` }, "Ir al DOP");
    case "dpp":
      return h("a", { href: `#/dpps/${c.id}` }, "Ir al DPP");
    case "cooperativa":
    case "expediente_cooperativa":
      return h("a", { href: "#/cooperativa/legal" }, "Ir al expediente de la cooperativa");
    case "importador":
      return h("a", { href: "#/exportacion/importadores" }, "Ir al importador");
    case "embarque":
      return h("button", { class: "btn-link", type: "button", onclick: () => irAPestana("embarque") }, "Cargar el documento");
    default:
      return null;
  }
}

function comprobaciones(r, irAPestana) {
  return h(
    "ul",
    { class: "comprobaciones" },
    r.comprobaciones.map((c) =>
      h(
        "li",
        { class: `comprobacion ${c.resultado}` },
        h("span", { class: "comprobacion-marca", "aria-hidden": "true" }, icono(c.resultado === "sin_observaciones" ? "check" : "alert")),
        h(
          "div",
          {},
          h("div", { class: "comprobacion-h" }, h("b", {}, c.nombre), insignia(RESULTADO[c.resultado]), h("span", { class: "sec" }, c.sobre)),
          c.casos.length > 0 &&
            h(
              "ul",
              { class: "casos" },
              c.casos.map((caso) => h("li", {}, h("span", {}, caso.texto), caso.detalle && h("span", { class: "sec" }, caso.detalle), enlaceCaso(caso, irAPestana))),
            ),
        ),
      ),
    ),
  );
}

function pestanaRecomprobacion(l, opera, recargar, irAPestana) {
  const r = l.recomprobacion;
  const historial = h("div", {});
  const recomprobable = ["armado", "bloqueado", "listo"].includes(l.estado);
  async function recomprobar(e) {
    const boton = e.currentTarget;
    boton.classList.add("is-loading");
    try {
      const res = await llamarApi(`/lotes/${l.id}/recomprobar`, { metodo: "POST" });
      toast(res.resultado === "sin_observaciones" ? "Recomprobación sin observaciones: el lote está listo." : "Recomprobación con observaciones: el lote quedó bloqueado.", res.resultado === "sin_observaciones" ? "ok" : "warn");
      recargar();
    } catch (error) {
      toast(error.message, "bad");
      boton.classList.remove("is-loading");
    }
  }
  llamarApi(`/lotes/${l.id}/recomprobaciones`)
    .then((lista) =>
      reemplazar(
        historial,
        lista.length > 1 &&
          h(
            "details",
            { class: "historial" },
            h("summary", {}, `Historial (${lista.length} recomprobaciones)`),
            h(
              "ul",
              { class: "lista-simple" },
              lista.map((x) => h("li", {}, `${fecha(x.ejecutada_en, { hora: true })} · `, insignia(RESULTADO[x.resultado]), ` · ${x.ejecutada_por_nombre ?? "Sistema (tarea diaria)"}`)),
            ),
          ),
      ),
    )
    .catch(() => null);
  return seccion({
    titulo: "Recomprobación",
    sub: "Las nueve comprobaciones con la fecha del día: confirma que cada requisito que ya se cumplió sigue en pie. No es una evaluación de riesgo. El lote queda listo solo si todas salen sin observaciones.",
    acciones: opera && recomprobable && h("button", { class: "btn btn-primary btn-sm", type: "button", onclick: recomprobar }, icono("rotate"), "Recomprobar"),
    contenido: r
      ? [
          h("p", { class: "panel-sub" }, `Última: ${fecha(r.ejecutada_en, { hora: true })} · ${r.ejecutada_por_nombre ?? "Sistema (tarea diaria)"} · `, insignia(RESULTADO[r.resultado])),
          comprobaciones(r, irAPestana),
          historial,
        ]
      : h("p", { class: "panel-sub" }, recomprobable ? "Todavía no se recomprobó este lote." : "Se recomprueba un lote armado, bloqueado o listo."),
  });
}

// ---------- Hallazgos ----------

function pestanaHallazgos(l, irAPestana) {
  if (["en_armado", "anulado"].includes(l.estado)) {
    return seccion({ titulo: "Hallazgos", contenido: h("p", { class: "panel-sub" }, "El informe se calcula para un lote armado, bloqueado o listo, y queda sellado en su DEX.") });
  }
  const caja = h("div", {}, cargando());
  const sellado = l.estado === "cerrado" && l.dex;
  const pedido = sellado ? llamarApi(`/dex/${l.dex.id}`).then((d) => d.contenido.informe) : llamarApi(`/lotes/${l.id}/hallazgos`);
  pedido.then((informe) => reemplazar(caja, vistaInforme(informe, { codigoDex: sellado ? l.dex.codigo : null, irAPestana }))).catch((error) => reemplazar(caja, errorDeCarga(error)));
  return caja;
}

// ---------- DEX ----------

/** Abre la URL firmada de un archivo del DEX. La ventana se abre en el mismo clic para que no la bloqueen. */
async function descargar(dexId, clave) {
  const ventana = window.open("about:blank", "_blank");
  try {
    const lista = await llamarApi(`/dex/${dexId}/descargas`);
    const archivo = lista.find((x) => x.clave === clave);
    if (!archivo) throw new Error("El archivo no está disponible.");
    if (ventana) {
      ventana.opener = null;
      ventana.location.href = archivo.url;
    } else {
      window.location.assign(archivo.url);
    }
  } catch (error) {
    ventana?.close();
    toast(error.message, "bad");
  }
}

function abrirEmision(l, alEmitir) {
  const casilla = h("input", { type: "checkbox", name: "entiendo", required: true });
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-emitir-dex", disabled: true }, icono("shield"), "Emitir DEX");
  const mensaje = h("div", { class: "mf-caja" }, cargando());
  casilla.addEventListener("change", () => {
    boton.disabled = !casilla.checked;
  });
  const formulario = h(
    "form",
    { class: "form", id: "form-emitir-dex" },
    h("p", { class: "panel-sub" }, "Este es el mensaje final del informe que quedará sellado en el expediente. Léelo antes de emitir: el sistema recomprueba el lote en ese instante y, si algo falla, lo bloquea y no emite nada."),
    mensaje,
    h("label", { class: "check casilla-entiendo" }, casilla, h("span", {}, CASILLA)),
  );
  llamarApi(`/lotes/${l.id}/hallazgos`)
    .then((informe) => reemplazar(mensaje, mensajeFinal(informe.mensaje.es)))
    .catch((error) => reemplazar(mensaje, errorDeCarga(error)));
  const { cerrar } = abrirModal({ titulo: "Emitir DEX", subtitulo: `${l.codigo} · orden ${l.orden.codigo}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async () => {
    try {
      const dex = await llamarApi(`/lotes/${l.id}/dex`, { metodo: "POST", cuerpo: { entiendo: casilla.checked }, unIntento: true });
      cerrar();
      toast(`DEX emitido: ${dex.codigo}.`);
      alEmitir();
    } catch (error) {
      if (error.codigo === "lote_bloqueado") {
        cerrar();
        toast(error.message, "bad");
        alEmitir();
        return;
      }
      throw error;
    }
  });
  // enviarCon vuelve a habilitar el botón al terminar: sin la casilla marcada, sigue apagado.
  formulario.addEventListener("submit", () => setTimeout(() => (boton.disabled = !casilla.checked), 0));
}

function abrirAnulacionDex(dex, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-dex" }, "Anular DEX");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-dex" },
    h("p", { class: "alerta warn" }, "El DEX conserva su contenido y sus archivos, y la verificación pública lo mostrará como anulado. El lote vuelve a armado y la orden a con lote: para emitir de nuevo hay que recomprobar, y la nueva emisión recibe un código nuevo."),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular DEX", subtitulo: dex.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/dex/${dex.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("DEX anulado.", "warn");
    alAnular();
  });
}

/** Adenda 6, sección 7, regla 7: lo que se cargó en el lote después de emitir el DEX. El DEX no cambia. */
export function bloqueAgregado(agregado) {
  return [
    h("h4", { class: "dex-sub" }, "Agregado después de la emisión"),
    h("p", { class: "panel-sub" }, "No forma parte del DEX: su contenido y su huella no cambian."),
    rejilla(
      agregado.flatMap((a) => [
        { etiqueta: a.nombre, valor: a.numero, mono: true, extra: a.cotejado ? insigniaNivel("verificado_en_fuente") : "Sin cotejo en fuente" },
        { etiqueta: "Fecha de numeración", valor: fecha(a.fecha_numeracion) },
        { etiqueta: "Cargada", valor: fecha(a.cargado_en, { hora: true }) },
      ]),
    ),
  ];
}

function fichaDex(dex, alAnular) {
  const rol = rolEfectivo();
  const descarga = ["admin_cooperativa", "operador"].includes(rol);
  const vigente = dex.estado === "vigente";
  return h(
    "div",
    { class: "dex-ficha" },
    h(
      "div",
      { class: `verif ${vigente ? "" : "bad"}`.trim() },
      icono(vigente ? "check" : "alert"),
      h(
        "div",
        {},
        h("b", {}, `${dex.codigo} · ${vigente ? "vigente" : "anulado"}`),
        h(
          "span",
          {},
          vigente
            ? "La cooperativa descarga el paquete y lo envía al importador por su cuenta. El sistema no envía nada ni guarda si se entregó."
            : `Anulado el ${fecha(dex.anulado_en, { hora: true })}${dex.anulado_por_nombre ? ` por ${dex.anulado_por_nombre}` : ""}. Motivo: ${dex.motivo_anulacion}`,
        ),
      ),
    ),
    h(
      "div",
      { class: "dex-cuerpo" },
      rejilla([
        { etiqueta: "Código", valor: dex.codigo, mono: true },
        { etiqueta: "Emitido", valor: `${fecha(dex.emitido_en, { hora: true })}${dex.emitido_por_nombre ? ` · ${dex.emitido_por_nombre}` : ""}` },
        { etiqueta: "Importador", valor: dex.importador },
        { etiqueta: "Masa neta", valor: kilos(dex.masa_neta_kg) },
        { etiqueta: "Huella SHA-256 del contenido", valor: huella(dex.contenido_sha256), extra: "Es la misma que llevan impresa los dos PDF y la que muestra la página pública." },
        { etiqueta: "Verificación pública", valor: h("a", { href: dex.url_verificacion, target: "_blank", rel: "noopener" }, "Abrir la página de verificación") },
      ]),
      h("figure", { class: "dex-qr" }, codigoQr(dex.qr, `Código QR de verificación del ${dex.codigo}`), h("figcaption", {}, "Lleva a la página pública de verificación")),
    ),
    dex.agregado?.length > 0 && bloqueAgregado(dex.agregado),
    h("h4", { class: "dex-sub" }, "Archivos"),
    h("p", { class: "panel-sub" }, descarga ? "Cada descarga queda en la auditoría. Las direcciones vencen a los 5 minutos. Los PDF en español y en inglés tienen las mismas secciones y las mismas cifras." : "Descargan el administrador y el operador."),
    h(
      "ul",
      { class: "dex-archivos" },
      [...dex.archivos].sort((a, b) => (b.clave === "paquete") - (a.clave === "paquete")).map((a) =>
        h(
          "li",
          {},
          h("span", {}, h("b", {}, ARCHIVOS[a.clave] ?? a.clave), h("span", { class: "sec mono" }, a.nombre)),
          descarga && h("button", { class: `btn btn-sm ${a.clave === "paquete" ? "btn-primary" : ""}`.trim(), type: "button", onclick: () => descargar(dex.id, a.clave) }, icono("download", "ic-sm"), a.clave.startsWith("pdf_") ? "Ver" : "Descargar"),
        ),
      ),
    ),
    vigente && rol === "admin_cooperativa" && h("div", { class: "fila-acciones dex-anular" }, h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacionDex(dex, alAnular) }, "Anular DEX")),
  );
}

function pestanaDex(l, alCambiar, irAPestana) {
  const admin = rolEfectivo() === "admin_cooperativa";
  const partes = [];
  if (l.estado === "listo") {
    partes.push(
      h(
        "div",
        { class: "verif" },
        icono("shield"),
        h("div", {}, h("b", {}, "El lote está listo para emitir su DEX"), h("span", {}, admin ? "Antes de confirmar se muestra el mensaje final del informe. El sistema recomprueba el lote al emitir." : "Solo un administrador de la cooperativa emite el DEX.")),
        admin && h("button", { class: "btn btn-primary btn-sm", type: "button", onclick: () => abrirEmision(l, alCambiar) }, icono("shield"), "Emitir DEX"),
      ),
    );
  } else if (l.estado === "bloqueado") {
    partes.push(
      h(
        "div",
        { class: "verif bad" },
        icono("alert"),
        h("div", {}, h("b", {}, "No se puede emitir el DEX de un lote bloqueado"), h("span", {}, "Corrige lo que falla, recomprueba el lote y, cuando quede listo, emite el DEX.")),
        h("button", { class: "btn btn-sm", type: "button", onclick: () => irAPestana("recomprobacion") }, "Ver la recomprobación"),
      ),
    );
  } else if (l.estado === "armado") {
    partes.push(
      h(
        "div",
        { class: "verif" },
        icono("rotate"),
        h("div", {}, h("b", {}, "El DEX se emite sobre un lote listo"), h("span", {}, "Carga los cuatro documentos de embarque obligatorios y recomprueba el lote: si las nueve comprobaciones salen sin observaciones, queda listo.")),
        h("button", { class: "btn btn-sm", type: "button", onclick: () => irAPestana("recomprobacion") }, "Ir a Recomprobación"),
      ),
    );
  } else if (!l.dex) {
    partes.push(h("p", { class: "panel-sub" }, "Este lote no tiene DEX."));
  }
  if (l.dex) {
    const caja = h("div", {}, cargando());
    llamarApi(`/dex/${l.dex.id}`)
      .then((dex) => reemplazar(caja, fichaDex(dex, alCambiar)))
      .catch((error) => reemplazar(caja, errorDeCarga(error)));
    partes.push(caja);
  }
  return seccion({
    titulo: "DEX",
    sub: "El expediente que la cooperativa entrega al importador: no declara un nivel de riesgo, no lleva firma y no reemplaza la DDS.",
    contenido: partes,
  });
}

export default async function loteExportacion({ parametros: [id, pestana], recargar, navegar }) {
  const l = await llamarApi(`/lotes/${id}`);
  const opera = ["admin_cooperativa", "operador"].includes(rolEfectivo());
  if (pestana) recordada = { id, clave: pestana };
  else if (recordada.id !== id) recordada = { id, clave: l.estado === "bloqueado" ? "recomprobacion" : l.estado === "cerrado" ? "dex" : "seleccion" };
  const cuerpo = h("div", { class: "contenido-pestana" });
  const barra = h("div", { class: "seg", role: "tablist", "aria-label": "Secciones del lote" });
  const generadores = {
    seleccion: () => pestanaSeleccion(l, opera, recargar),
    genealogia: () => pestanaGenealogia(l),
    indicadores: () => pestanaIndicadores(l),
    embarque: () => pestanaEmbarque(l, opera, recargar),
    recomprobacion: () => pestanaRecomprobacion(l, opera, recargar, mostrar),
    hallazgos: () => pestanaHallazgos(l, mostrar),
    dex: () => pestanaDex(l, alCambiarDex, mostrar),
  };
  // Tras emitir o anular, la pantalla vuelve a cargarse en la pestaña DEX.
  function alCambiarDex() {
    recordada = { id, clave: "dex" };
    if (location.hash === `#/lotes-exportacion/${id}/dex`) recargar();
    else navegar(`#/lotes-exportacion/${id}/dex`);
  }
  function mostrar(clave) {
    recordada = { id, clave };
    for (const b of barra.children) b.setAttribute("aria-selected", String(b.dataset.clave === clave));
    reemplazar(cuerpo, generadores[clave]());
  }
  for (const [clave, texto] of PESTANAS) barra.append(h("button", { type: "button", role: "tab", "data-clave": clave, onclick: () => mostrar(clave) }, texto));
  mostrar(recordada.clave);

  const fallan = l.recomprobacion ? l.recomprobacion.comprobaciones.filter((c) => c.resultado === "con_observaciones").length : 0;
  const franja =
    l.estado === "bloqueado" &&
    h(
      "div",
      { class: "verif bad franja-fija", role: "status" },
      icono("alert"),
      h("div", {}, h("b", {}, `Lote bloqueado: ${fallan} ${fallan === 1 ? "comprobación" : "comprobaciones"} con observaciones`), h("span", {}, "No puede recibir DEX hasta que se corrija lo que falla y se recompruebe.")),
      h("button", { class: "btn btn-sm", type: "button", onclick: () => mostrar("recomprobacion") }, "Ver la recomprobación"),
    );

  return {
    titulo: l.codigo,
    migas: [["Exportación", "#/exportacion"], ["Lotes", "#/exportacion/lotes"], [l.codigo]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      franja,
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("container")),
        titulo: l.codigo,
        codigo: true,
        insignias: [estadoLote(l.estado), l.desviacion_fifo && insigniaFifo()],
        detalle: ["Orden ", h("a", { href: `#/ordenes/${l.orden.id}`, class: "mono" }, l.orden.codigo), ` · ${l.importador} · ${l.calidad}`, l.armado_en ? ` · armado el ${fecha(l.armado_en, { hora: true })} por ${l.armado_por_nombre ?? "—"}` : ""],
        cifra: kilos(l.masa_neta_kg ?? l.seleccionado_kg),
        cifraTexto: l.masa_neta_kg ? `masa neta · ${l.numero_parcelas} ${l.numero_parcelas === 1 ? "parcela" : "parcelas"}` : `seleccionado de ${kilos(l.cantidad_kg)}`,
        accion:
          (opera && l.estado === "en_armado" && h("a", { class: "btn btn-primary", href: `#/lotes-exportacion/${l.id}/armar` }, icono("layers"), "Armar lote")) ||
          (rolEfectivo() === "admin_cooperativa" && l.estado === "listo" && h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirEmision(l, alCambiarDex) }, icono("shield"), "Emitir DEX")),
      }),
      l.alertas
        .filter((a) => a.codigo === "exclusion_posterior_al_cierre")
        .map((a) => h("div", { class: "verif warn" }, icono("alert"), h("div", {}, h("b", {}, `La parcela ${a.parcela_codigo} se excluyó después de cerrar el lote`), h("span", {}, "El DEX no cambia porque está sellado. Informar al importador corresponde a la cooperativa.")))),
      l.desviacion_fifo && h("div", { class: "verif warn" }, icono("alert"), h("div", {}, h("b", {}, "La selección se apartó del orden FIFO"), h("span", {}, `Motivo: ${l.motivo_desviacion}`))),
      l.estado === "anulado" && h("div", { class: "verif bad" }, icono("alert"), h("div", {}, h("b", {}, `Lote anulado el ${fecha(l.anulado_en, { hora: true })}${l.anulado_por_nombre ? ` por ${l.anulado_por_nombre}` : ""}`), h("span", {}, `Motivo: ${l.motivo_anulacion}`))),
      h("div", { class: "ins-tabs seg-scroll" }, barra),
      cuerpo,
    ),
  };
}
