// Piezas de la Parte 5 que comparten el asistente, el detalle de la tanda, el DOP y "Mis entregas":
// campos de pesaje, cosecha y guía; requisitos y alertas; huella, código QR y descarga del PDF.

import { llamarApi } from "./api.js";
import { ALERTAS, ALERTAS_TANDA, REQUISITOS_TANDA, VARIEDADES, kilos } from "./textos.js";
import { campo, h, icono, toast } from "./ui.js";

export function seccionesLotes() {
  return [
    ["Recepción", "#/lotes/recepcion"],
    ["DOP", "#/lotes/dop"],
  ];
}

// ---------- Fechas en hora de Lima (Perú no cambia de hora: siempre UTC-5) ----------

const PARTES_LIMA = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Lima",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** "AAAA-MM-DDTHH:MM" en hora de Lima, para un campo datetime-local. */
export function momentoLima(valor = new Date()) {
  const p = Object.fromEntries(PARTES_LIMA.formatToParts(new Date(valor)).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

export const hoyLima = () => momentoLima().slice(0, 10);

/** El valor del campo datetime-local es hora de Lima: se envía con su desfase. */
const conDesfase = (local) => `${local}:00-05:00`;

// ---------- Campos de la tanda ----------

/**
 * Campos de pesaje y cosecha, y de la guía de remisión. t: tanda actual (para editar) o vacío.
 * Devuelve { pesaje, guia, actualizar } para ubicarlos en el asistente o en un formulario.
 */
export function camposTanda(t = {}, { lugares, configuracion }) {
  const canchas = lugares.filter((l) => l.tipo === "cancha_acopio" && (l.activo || l.id === t.lugar_id));
  const recibida = t.recibida_en ? momentoLima(t.recibida_en) : momentoLima();
  const producto = h("input", { type: "hidden", name: "estado_producto", value: t.estado_producto ?? "baba" });
  const botonesProducto = h(
    "div",
    { class: "seg2", role: "group", "aria-label": "Estado del producto" },
    [
      ["baba", "En baba"],
      ["seco", "Seco"],
    ].map(([valor, texto]) =>
      h("button", { type: "button", "data-valor": valor, "aria-pressed": String(producto.value === valor), onclick: () => elegirProducto(valor) }, texto),
    ),
  );
  const humedad = campo({ etiqueta: "Humedad (%)", name: "humedad_pct", type: "number", step: "0.1", min: "0", max: "100", inputmode: "decimal", value: t.humedad_pct ?? "", ayuda: "Opcional; solo en seco." });
  const peso = campo({ etiqueta: "Peso neto en balanza (kg)", name: "peso_kg", type: "number", step: "0.01", min: "0.01", inputmode: "decimal", required: true, value: t.peso_kg ?? "", class: "input mono" });
  const equivalente = h("p", { class: "equivalente", "aria-live": "polite" });
  const variedad = campo({ etiqueta: "Variedad", name: "variedad", opciones: [["", "Elige la variedad…"], ...VARIEDADES], required: true, value: t.variedad ?? "" });
  const variedadOtra = campo({ etiqueta: "Nombre de la variedad", name: "variedad_otra", maxlength: 200, value: t.variedad_otra ?? "" });
  const cosechaHasta = campo({ etiqueta: "Cosecha hasta", name: "cosecha_hasta", type: "date", required: true, value: t.cosecha_hasta ?? "" });
  const cosechaDesde = campo({ etiqueta: "Cosecha desde", name: "cosecha_desde", type: "date", required: true, value: t.cosecha_desde ?? "" });
  const recepcion = campo({ etiqueta: "Fecha y hora del pesaje", name: "recibida_en", type: "datetime-local", required: true, value: recibida, max: momentoLima() });
  const guiaFecha = campo({ etiqueta: "Fecha de emisión", name: "gre_fecha_emision", type: "date", value: t.gre_fecha_emision ?? "" });

  function elegirProducto(valor) {
    producto.value = valor;
    for (const b of botonesProducto.children) b.setAttribute("aria-pressed", String(b.dataset.valor === valor));
    humedad.hidden = valor !== "seco";
    if (valor !== "seco") humedad.querySelector("input").value = "";
    actualizar();
  }

  /** Equivalente en seco, fechas máximas y el campo de "otra" variedad, a medida que se escribe. */
  function actualizar() {
    const kg = Number(peso.querySelector("input").value);
    const factor = Number(configuracion.factor_baba_a_seco);
    equivalente.textContent =
      kg > 0
        ? producto.value === "baba"
          ? `Equivale a unos ${kilos(kg * factor)} de grano seco (factor ${configuracion.factor_baba_a_seco}). Es una estimación.`
          : `Peso seco: ${kilos(kg)}.`
        : "";
    const otra = variedad.querySelector("select").value === "otra";
    variedadOtra.hidden = !otra;
    variedadOtra.querySelector("input").required = otra;
    const dia = recepcion.querySelector("input").value.slice(0, 10) || hoyLima();
    for (const c of [cosechaDesde, cosechaHasta, guiaFecha]) c.querySelector("input").max = dia;
    cosechaDesde.querySelector("input").max = cosechaHasta.querySelector("input").value || dia;
  }
  for (const c of [peso, variedad, recepcion, cosechaHasta]) c.addEventListener("input", actualizar);
  humedad.hidden = producto.value !== "seco";

  const pesaje = h(
    "div",
    { class: "form" },
    canchas.length > 1 || !canchas.length
      ? campo({
          etiqueta: "Cancha de acopio",
          name: "lugar_id",
          required: true,
          value: t.lugar_id ?? "",
          opciones: [["", canchas.length ? "Elige dónde se pesó…" : "No hay canchas de acopio activas"], ...canchas.map((l) => [l.id, `${l.nombre} · ${l.distrito}`])],
        })
      : [h("input", { type: "hidden", name: "lugar_id", value: canchas[0].id }), h("p", { class: "panel-sub" }, `Pesada en ${canchas[0].nombre} (${canchas[0].distrito}).`)],
    recepcion,
    h("div", { class: "field" }, "Estado del producto", botonesProducto, producto),
    h("div", { class: "grid2" }, peso, campo({ etiqueta: "Sacos (opcional)", name: "numero_sacos", type: "number", step: "1", min: "1", inputmode: "numeric", value: t.numero_sacos ?? "" })),
    equivalente,
    humedad,
    h("div", { class: "grid2" }, variedad, campo({ etiqueta: "Tipo de semilla (opcional)", name: "tipo_semilla", maxlength: 200, value: t.tipo_semilla ?? "" })),
    variedadOtra,
    h("div", { class: "grid2" }, cosechaDesde, cosechaHasta),
    h("p", { class: "panel-sub" }, "El intervalo de cosecha es el que pide el artículo 9 del Reglamento: desde cuándo y hasta cuándo se cosechó este cacao."),
  );

  const guia = h(
    "div",
    { class: "form" },
    h(
      "div",
      { class: "grid2" },
      campo({
        etiqueta: "Serie y número",
        name: "gre_numero",
        value: t.gre_numero ?? "",
        maxlength: 20,
        autocomplete: "off",
        autocapitalize: "characters",
        placeholder: "T001-123",
        class: "input mono",
        ayuda: "Serie de 4 caracteres y número, como figura en la guía.",
      }),
      guiaFecha,
    ),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "RUC del emisor", name: "gre_ruc_emisor", value: t.gre_ruc_emisor ?? "", inputmode: "numeric", pattern: "[0-9]{11}", maxlength: 11, title: "11 dígitos", class: "input mono", ayuda: "Del productor o de la cooperativa, según quién la emitió." }),
      campo({ etiqueta: "Peso declarado en la guía (kg, opcional)", name: "gre_peso_kg", type: "number", step: "0.01", min: "0.01", inputmode: "decimal", value: t.gre_peso_kg ?? "", class: "input mono" }),
    ),
  );

  actualizar();
  return { pesaje, guia, actualizar };
}

/**
 * Convierte los campos del formulario al cuerpo de la API; los vacíos opcionales van como null.
 * Con `anterior` (al corregir), la hora del pesaje solo se envía si cambió: el campo no tiene segundos.
 */
export function cuerpoTanda(datos, anterior = null) {
  const opcional = (v) => (v === undefined || v === "" ? null : v);
  const cuerpo = {
    lugar_id: datos.lugar_id,
    recibida_en: conDesfase(datos.recibida_en),
    estado_producto: datos.estado_producto,
    peso_kg: datos.peso_kg,
    numero_sacos: opcional(datos.numero_sacos),
    humedad_pct: datos.estado_producto === "seco" ? opcional(datos.humedad_pct) : null,
    variedad: datos.variedad,
    variedad_otra: datos.variedad === "otra" ? opcional(datos.variedad_otra) : null,
    tipo_semilla: opcional(datos.tipo_semilla),
    cosecha_desde: datos.cosecha_desde,
    cosecha_hasta: datos.cosecha_hasta,
    gre_numero: opcional(datos.gre_numero?.trim()),
    gre_fecha_emision: opcional(datos.gre_fecha_emision),
    gre_ruc_emisor: opcional(datos.gre_ruc_emisor),
    gre_peso_kg: opcional(datos.gre_peso_kg),
  };
  if (anterior && momentoLima(anterior.recibida_en) === datos.recibida_en) delete cuerpo.recibida_en;
  return cuerpo;
}

/** Selector de la foto o el PDF de la guía. En el celular ofrece tomar la foto con la cámara. */
export function campoArchivoGuia({ requerido = false } = {}) {
  return h(
    "label",
    { class: "field" },
    "Foto o PDF de la guía (hasta 10 MB)",
    h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: requerido }),
    h("small", {}, "En el celular puedes tomar la foto con la cámara."),
  );
}

// ---------- Requisitos y alertas ----------

export function listaRequisitos(requisitos) {
  return h(
    "div",
    { class: "steps" },
    requisitos.map((r) =>
      h(
        "div",
        { class: `stp ${r.cumple ? "ok" : "bad"}` },
        h("span", { class: "stp-n", "aria-hidden": "true" }, icono(r.cumple ? "check" : "x")),
        h("div", {}, h("b", {}, REQUISITOS_TANDA[r.codigo] ?? r.codigo, h("span", { class: "sr-only" }, r.cumple ? " (se cumple)" : " (falta)")), h("span", {}, r.detalle)),
      ),
    ),
  );
}

/** Cada alerta con las cifras que la produjeron y el valor configurado. */
function cifrasDeAlerta(codigo, detalle = {}, configuracion) {
  const conf = configuracion ?? {};
  switch (codigo) {
    case "volumen_acumulado_excede_tope":
      return `${kilos(detalle.kg_seco_por_ha_365_dias)} secos por hectárea en 365 días; el tope es ${kilos(conf.tope_kg_seco_ha_anio)} por hectárea al año.`;
    case "dias_cosecha_entrega_altos":
      return `${detalle.dias_cosecha_entrega} días entre el fin de la cosecha y la entrega.`;
    case "peso_difiere_de_guia":
      return `Diferencia de ${detalle.diferencia_peso_guia_pct} %; la tolerancia es ${conf.tolerancia_peso_guia_pct ?? "—"} %.`;
    case "parcela_con_alertas":
      return detalle.alertas_parcela ? `${detalle.alertas_parcela.map((a) => ALERTAS[a] ?? a).join("; ")}.` : null;
    default:
      return null;
  }
}

export function listaAlertas(alertas, detalle, configuracion) {
  if (!alertas.length) return h("p", { class: "panel-sub" }, "Sin alertas.");
  return h(
    "div",
    { class: "opciones" },
    alertas.map((a) => {
      const cifras = cifrasDeAlerta(a, detalle, configuracion);
      return h("div", { class: "hintbox warn" }, icono("alert"), h("span", {}, h("b", {}, ALERTAS_TANDA[a] ?? a), cifras && [". ", cifras]));
    }),
  );
}

// ---------- Huella, código QR y PDF ----------

export function huella(texto) {
  return h(
    "span",
    { class: "hash" },
    h("span", { class: "mono" }, texto),
    h(
      "button",
      {
        type: "button",
        title: "Copiar la huella",
        "aria-label": "Copiar la huella",
        onclick: async () => {
          try {
            await navigator.clipboard.writeText(texto);
            toast("Huella copiada.");
          } catch {
            toast("No se pudo copiar.", "bad");
          }
        },
      },
      icono("copy"),
    ),
  );
}

/** Dibuja el código QR desde la matriz que entrega la API (una cadena de 0 y 1 por fila). */
export function codigoQr(matriz, etiqueta) {
  const ns = "http://www.w3.org/2000/svg";
  const lado = matriz.length;
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${lado} ${lado}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", etiqueta);
  svg.setAttribute("shape-rendering", "crispEdges");
  const trazos = [];
  matriz.forEach((fila, y) => {
    let x = 0;
    while (x < fila.length) {
      if (fila[x] === "1") {
        const inicio = x;
        while (x < fila.length && fila[x] === "1") x += 1;
        trazos.push(`M${inicio} ${y}h${x - inicio}v1h-${x - inicio}z`);
      } else {
        x += 1;
      }
    }
  });
  const camino = document.createElementNS(ns, "path");
  camino.setAttribute("d", trazos.join(""));
  camino.setAttribute("fill", "#000");
  svg.append(camino);
  return svg;
}

/** Abre el PDF del DOP con su URL firmada. ruta: /dops/{id}/pdf o /mi/dops/{id}/pdf. */
export async function descargarPdf(ruta) {
  // La ventana se abre en el mismo clic para que el navegador no la bloquee.
  const ventana = window.open("about:blank", "_blank");
  try {
    const { url } = await llamarApi(ruta);
    if (ventana) {
      ventana.opener = null;
      ventana.location.href = url;
    } else {
      window.location.assign(url);
    }
  } catch (error) {
    ventana?.close();
    toast(error.message, "bad");
  }
}
