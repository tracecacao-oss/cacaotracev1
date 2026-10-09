// Detalle de DOP: el contenido sellado por bloques, en el mismo orden que el PDF, con su huella, el
// código QR de la verificación pública y el botón de descargar el PDF. Solo el administrador lo anula.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { ALERTAS, ALERTAS_TANDA, ESTADOS_CASILLA, ESTADOS_HABILITACION, ESTADOS_MIDAGRI, OBSERVACIONES_2020, OBSERVACIONES_CAMBIO, PRODUCTO, REQUISITOS, hectareas, insigniaDop, insigniaNivel, kilos } from "../textos.js";
import { codigoQr, descargarPdf, huella } from "../tandas.js";
import { lugares } from "../ubigeo.js";
import { abrirModal, cabeceraFicha, enviarCon, fecha, h, icono, rejilla, seccion, toast } from "../ui.js";
import { historialMapbiomas } from "./parcela-habilitacion.js";

/** Desde la versión 4 del DOP, la pérdida de bosque y la alteración de la vegetación van por separado. */
function marcasCambio(fila) {
  if (!("registra_perdida" in fila)) return fila.registra_cambio ? ["Registra cambios"] : [];
  return [fila.registra_perdida && "Registra pérdida de bosque", fila.registra_alteracion && "Registra alteración de la vegetación"].filter(Boolean);
}

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

/** Croquis de la parcela desde su geometría, sin mapa de fondo y con el norte arriba (como en el PDF). */
function croquis(geometria) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("class", "croquis");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Croquis de la parcela, con el norte arriba");
  const trazo = (etiqueta, atributos) => {
    const el = document.createElementNS(ns, etiqueta);
    for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
    svg.append(el);
  };
  if (geometria.type === "Point") {
    trazo("circle", { cx: 50, cy: 50, r: 6, style: "fill: none; stroke: var(--emerald); stroke-width: 2" });
    trazo("path", { d: "M40 50h20M50 40v20", style: "stroke: var(--emerald); stroke-width: 1.5" });
    return svg;
  }
  const anillos = geometria.type === "Polygon" ? [geometria.coordinates[0]] : geometria.coordinates.map((p) => p[0]);
  const puntos = anillos.flat();
  const escala = Math.cos((puntos.reduce((s, p) => s + p[1], 0) / puntos.length) * (Math.PI / 180));
  const xs = puntos.map((p) => p[0] * escala);
  const ys = puntos.map((p) => p[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const tam = Math.max(maxX - minX, maxY - minY) || 1e-9;
  const factor = 80 / tam;
  const ox = 10 + (80 - (maxX - minX) * factor) / 2;
  const oy = 10 + (80 - (maxY - minY) * factor) / 2;
  for (const anillo of anillos) {
    const d = anillo.map((p, i) => `${i ? "L" : "M"}${(ox + (p[0] * escala - minX) * factor).toFixed(2)} ${(oy + (maxY - p[1]) * factor).toFixed(2)}`).join("") + "Z";
    trazo("path", { d, style: "fill: var(--emerald-soft); stroke: var(--emerald); stroke-width: 1.5", "vector-effect": "non-scaling-stroke" });
  }
  trazo("text", { x: 93, y: 9, "font-size": 7, "text-anchor": "middle", style: "fill: var(--ink-3)" });
  svg.lastChild.textContent = "N";
  return svg;
}

function abrirAnulacion(d, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-dop" }, "Anular DOP");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-dop" },
    h(
      "p",
      { class: "alerta warn" },
      "El DOP anulado conserva su contenido y su PDF, y la verificación pública lo muestra como anulado. Su tanda sigue validada como registro, pero ya no cuenta en ningún cálculo. La entrega corregida se registra como una tanda nueva.",
    ),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular DOP", subtitulo: d.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/dops/${d.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("DOP anulado.", "warn");
    alAnular();
  });
}

function medidas(lista) {
  if (!lista?.length) return "—";
  const visibles = lista.filter((m) => !m.serie);
  return (visibles.length ? visibles : lista).map((m) => `${m.valor} ${m.unidad ?? ""} (${m.nombre}, ${m.via})`.replace("  ", " ")).join("; ");
}

/** Adenda 3: el documento de entrega con su tipo. Los DOP de antes guardan "guia_remision": se leen igual. */
function filasDocumentoEntrega(t) {
  if (t.documento_entrega) {
    const d = t.documento_entrega;
    return [
      { etiqueta: "Documento de entrega", valor: [d.nombre_tipo, d.numero].filter(Boolean).join(", "), extra: insigniaNivel(d.nivel) },
      { etiqueta: "Emisión del documento", valor: fecha(d.fecha_emision) },
      { etiqueta: "RUC del emisor", valor: d.ruc_emisor, mono: true },
      { etiqueta: "Peso declarado en el documento", valor: d.peso_kg == null ? null : kilos(d.peso_kg), mono: true },
      { etiqueta: "Huella del archivo del documento", valor: d.documento_sha256, mono: true },
    ];
  }
  const g = t.guia_remision;
  return [
    { etiqueta: "Guía de remisión", valor: g.numero, mono: true, extra: insigniaNivel(g.nivel) },
    { etiqueta: "Emisión de la guía", valor: fecha(g.fecha_emision) },
    { etiqueta: "RUC del emisor", valor: g.ruc_emisor, mono: true },
    { etiqueta: "Peso declarado en la guía", valor: g.peso_kg == null ? null : kilos(g.peso_kg), mono: true },
    { etiqueta: "Huella del archivo de la guía", valor: g.documento_sha256, mono: true },
  ];
}

/** Adenda 2: solo si la parcela tuvo la alerta de análisis. Las imágenes van dibujadas en el PDF. */
function bloqueImagenes(im) {
  const n = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });
  const imagen = (titulo, f) =>
    f
      ? {
          etiqueta: titulo,
          valor: `${fecha(f.fecha_captura)} (${f.dias_respecto_al_corte > 0 ? "+" : ""}${f.dias_respecto_al_corte} días respecto al corte)`,
          extra: [
            [f.proveedor ?? "Sentinel-2", `resolución ${n(f.resolucion_m ?? 10)} m`, f.nubes_parcela_pct != null ? `nubes sobre la parcela ${n(f.nubes_parcela_pct)} %` : null].filter(Boolean).join(" · "),
            h("span", { class: "sec mono" }, `SHA-256 ${f.sha256}`),
            h("span", { class: "sec" }, f.atribucion),
          ],
        }
      : { etiqueta: titulo, valor: "Sin imagen al emitirse" };
  const r = im.revision;
  return seccion({
    titulo: "Imágenes de la parcela",
    sub: "La parcela tuvo la alerta de análisis. Las dos imágenes de Sentinel-2 (10 m) van dibujadas en el PDF, con el lindero.",
    contenido: [
      rejilla([
        imagen("Anterior al corte", im.anterior_al_corte),
        imagen("Reciente", im.reciente),
        im.alta_resolucion?.length > 0 && {
          etiqueta: "Alta resolución (Esri Wayback)",
          valor: im.alta_resolucion.map((a) => `${fecha(a.fecha_captura)}${a.proveedor ? ` · ${a.proveedor}` : ""}`).join("; "),
          extra: `Se listan solo sus datos. ${im.atribucion_alta_resolucion ?? ""}`,
        },
      ]),
      r
        ? rejilla([
            { etiqueta: "Revisó las imágenes", valor: r.revisada_por },
            { etiqueta: "Fecha de la revisión", valor: fecha(r.revisada_en, { hora: true }) },
            { etiqueta: "En la imagen anterior al corte", valor: OBSERVACIONES_2020.find(([v]) => v === r.observacion_2020)?.[1] ?? r.observacion_2020 },
            { etiqueta: "Cambio después del corte", valor: OBSERVACIONES_CAMBIO.find(([v]) => v === r.observacion_cambio)?.[1] ?? r.observacion_cambio },
            { etiqueta: "Lo que observó", valor: r.descripcion },
          ])
        : h("p", { class: "panel-sub" }, "Sin revisión de imágenes vigente al emitirse."),
    ],
  });
}

export default async function dop({ parametros: [id], recargar }) {
  const d = await llamarApi(`/dops/${id}`);
  const c = d.contenido;
  const ident = c.identificacion;
  const p = c.productor;
  const pa = c.parcela;
  const t = c.tanda;
  const vigente = d.estado === "vigente";
  const ubicacion = [pa.ubicacion.centro_poblado, lugares(pa.ubicacion.distrito, pa.ubicacion.provincia, pa.ubicacion.departamento)].filter(Boolean).join(", ");
  const procedencia = pa.procedencia ?? {};

  const sello = seccion({
    titulo: "Sello",
    sub: "SHA-256 del contenido en forma canónica: claves ordenadas, UTF-8 y sin espacios sobrantes. Cualquiera con el contenido puede recalcularla.",
    acciones: vigente && rolEfectivo() === "admin_cooperativa" && h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacion(d, recargar) }, "Anular DOP"),
    contenido: h(
      "div",
      { class: "sello" },
      h(
        "div",
        { class: "form" },
        h("p", { class: "frase-conteo" }, `${c.leyenda}.`),
        rejilla([
          { etiqueta: "Huella del contenido", valor: huella(d.contenido_sha256) },
          { etiqueta: "Verificación pública", valor: d.url_verificacion, mono: true, extra: "La página muestra solo el código, el estado, la fecha, la huella y la cooperativa." },
        ]),
      ),
      h("div", { class: "qr-big" }, codigoQr(d.qr, `Código QR de la verificación pública de ${d.codigo}`), h("span", { class: "mono" }, d.codigo)),
    ),
  });

  const habilitacion = c.habilitacion;
  const decision = habilitacion.decision;
  const requisitosHab = decision?.requisitos?.requisitos ?? [];

  const bloques = [
    seccion({
      titulo: "Identificación",
      contenido: rejilla([
        { etiqueta: "Código", valor: ident.codigo, mono: true },
        { etiqueta: "Cooperativa", valor: `${ident.cooperativa.razon_social} (${ident.cooperativa.codigo})` },
        { etiqueta: "RUC de la cooperativa", valor: ident.cooperativa.ruc, mono: true },
        { etiqueta: "Fecha de emisión", valor: fecha(ident.emitido_en, { hora: true }) },
        { etiqueta: "Registró la tanda", valor: ident.registrada_por },
        { etiqueta: "Validó la tanda", valor: ident.validada_por, extra: ident.misma_persona ? "La misma persona registró y validó la tanda." : null },
      ]),
    }),
    seccion({
      titulo: "Productor",
      sub: "Cada dato con su nivel de verificación.",
      contenido: rejilla([
        { etiqueta: "DNI", valor: p.dni.valor, mono: true, extra: insigniaNivel(p.dni.nivel) },
        { etiqueta: "Nombres y apellidos", valor: p.nombres.valor, extra: insigniaNivel(p.nombres.nivel) },
        { etiqueta: "Dirección postal", valor: p.direccion_postal.valor, extra: insigniaNivel(p.direccion_postal.nivel) },
        { etiqueta: "Correo", valor: p.correo.valor, extra: insigniaNivel(p.correo.nivel) },
        { etiqueta: "RUC", valor: p.ruc.valor, mono: true, extra: insigniaNivel(p.ruc.nivel) },
        { etiqueta: "Registro en el PPA", valor: p.ppa.registrado ? p.ppa.codigo || "Registrado" : "No registrado", extra: p.ppa.registrado && insigniaNivel(p.ppa.nivel) },
      ]),
    }),
    seccion({
      titulo: "Parcela",
      sub: "Croquis dibujado desde la geometría sellada, sin mapa de fondo.",
      contenido: h(
        "div",
        { class: "sello" },
        rejilla([
          { etiqueta: "Código", valor: pa.codigo, mono: true },
          { etiqueta: "Nombre", valor: pa.nombre },
          { etiqueta: "Ubicación", valor: ubicacion },
          { etiqueta: "Geometría", valor: pa.tipo_geometria === "poligono" ? "Polígono" : "Punto" },
          { etiqueta: "Área calculada", valor: hectareas(pa.area_calculada_ha) },
          { etiqueta: "Área declarada", valor: hectareas(pa.area_declarada_ha) },
          { etiqueta: "Área con cacao", valor: hectareas(pa.area_cultivada_ha) },
          {
            etiqueta: "Estado en MIDAGRI",
            valor: [ESTADOS_MIDAGRI.find(([v]) => v === pa.midagri.estado)?.[1] ?? pa.midagri.estado, pa.midagri.codigo].filter(Boolean).join(" · "),
            extra: insigniaNivel(pa.midagri.nivel),
          },
          {
            etiqueta: "Procedencia",
            valor: `${procedencia.origen_geometria === "archivo" ? "Archivo" : "Dibujo"}; registrada por ${procedencia.registrada_por_rol === "productor" ? "el productor" : "la cooperativa"}.`,
            extra: procedencia.recorrida_en_campo ? `Lindero recorrido en campo el ${fecha(procedencia.fecha_recorrido)}.` : "Lindero sin recorrer en campo.",
          },
        ]),
        croquis(pa.geometria),
      ),
    }),
    seccion({
      titulo: "Habilitación",
      sub: "La decisión vigente de la cooperativa sobre la parcela.",
      acciones: insignia(ESTADOS_HABILITACION[habilitacion.estado]?.[0] ?? "", ESTADOS_HABILITACION[habilitacion.estado]?.[1] ?? habilitacion.estado),
      contenido: decision
        ? [
            rejilla([
              { etiqueta: "Decidió", valor: decision.decidida_por_nombre },
              { etiqueta: "Fecha", valor: fecha(decision.decidida_en, { hora: true }) },
              { etiqueta: "Nota", valor: decision.nota },
            ]),
            requisitosHab.length > 0 &&
              h(
                "ul",
                { class: "requisitos" },
                requisitosHab.map((r) =>
                  h("li", { class: r.cumple ? "cumple" : "falta" }, h("span", { class: "requisito-marca", "aria-hidden": "true" }, icono(r.cumple ? "check" : "x")), h("div", {}, h("b", {}, REQUISITOS[r.codigo] ?? r.codigo), h("span", { class: "sec" }, r.detalle))),
                ),
              ),
          ]
        : h("p", { class: "panel-sub" }, "Sin decisión de habilitar registrada."),
    }),
    seccion({
      titulo: "Cobertura forestal",
      sub: "Lo que dijo cada fuente, tal como lo entregó, con su fecha, su versión y la huella de su respuesta.",
      contenido: [
        c.cobertura.map((f) =>
          h(
            "div",
            { class: "form" },
            h("div", { class: "subtitulo-seccion" }, f.nombre),
            rejilla([
              { etiqueta: "Resultado", valor: f.resultado_texto },
              { etiqueta: "Valor de la fuente", valor: f.resultado_fuente, mono: true },
              { etiqueta: "Fecha", valor: fecha(f.completado_en, { hora: true }) },
              { etiqueta: "Versión", valor: f.version, mono: true },
              { etiqueta: "Huella de la respuesta", valor: f.respuesta_sha256, mono: true },
              f.es_aproximacion && { etiqueta: "Geometría analizada", valor: "Círculo con el área declarada (la parcela es un punto)" },
            ]),
            // Pedido del equipo del 2026-10-08: el historial de uso del suelo, que ya va en el contenido sellado.
            f.fuente === "mapbiomas" &&
              f.indicadores?.anios &&
              h(
                "div",
                {},
                h("p", { class: "panel-sub" }, `Hectáreas de cada clase de la leyenda de MapBiomas Perú (Colección 3) dentro de la parcela, año por año. Píxeles de 30 m en la parcela: ${f.indicadores.pixeles ?? "—"}. Ninguna clase de la leyenda corresponde solo al cacao.`),
                historialMapbiomas(f.indicadores),
              ),
          ),
        ),
        c.convergencia?.filas?.length > 0 &&
          h(
            "div",
            { class: "convergencia" },
            h("h4", {}, "Conjuntos de datos y las dos preguntas del Reglamento"),
            h(
              "div",
              { class: "tbl-box" },
              h(
                "table",
                { class: "tabla tabla-compacta" },
                h("thead", {}, h("tr", {}, h("th", {}, "Conjunto de datos"), h("th", {}, "Vía"), h("th", {}, "Al 31/12/2020"), h("th", {}, "Después de 2020"))),
                h(
                  "tbody",
                  {},
                  c.convergencia.filas.map((fila) =>
                    h(
                      "tr",
                      {},
                      h("td", {}, fila.nombre),
                      h("td", {}, fila.vias.join(" y ")),
                      h("td", {}, medidas(fila.al_2020), fila.registra_bosque_2020 && h("span", { class: "sec" }, "Registra bosque")),
                      h("td", {}, medidas(fila.despues_2020), marcasCambio(fila).map((m) => h("span", { class: "sec" }, m))),
                    ),
                  ),
                ),
              ),
            ),
            h("p", { class: "frase-conteo" }, c.convergencia.frase),
          ),
      ],
    }),
    c.imagenes && bloqueImagenes(c.imagenes),
    seccion({
      titulo: "Expediente legal",
      sub: "Las 7 casillas, con su documento o su exención.",
      contenido: h(
        "div",
        { class: "tbl-box" },
        h(
          "table",
          { class: "tabla tabla-compacta" },
          h("thead", {}, h("tr", {}, h("th", {}, "Casilla"), h("th", {}, "Estado"), h("th", { class: "ocultar-sm" }, "Documento o exención"))),
          h(
            "tbody",
            {},
            c.expediente.casillas.map((cas) => {
              const [clase, texto] = ESTADOS_CASILLA[cas.estado] ?? ["", cas.estado];
              const doc = cas.documento;
              return h(
                "tr",
                {},
                h("td", {}, cas.nombre, cas.nivel && h("span", { class: "sec" }, insigniaNivel(cas.nivel))),
                h("td", {}, insignia(clase, texto)),
                h(
                  "td",
                  { class: "ocultar-sm" },
                  doc
                    ? [`N.º ${doc.numero} · ${doc.entidad_emisora}`, h("span", { class: "sec" }, `Emitido ${fecha(doc.fecha_emision)}${doc.fecha_vencimiento ? ` · vence ${fecha(doc.fecha_vencimiento)}` : ""}`)]
                    : cas.exencion
                      ? `No aplica: ${cas.exencion.motivo}`
                      : cas.cubierta_por_nombre
                        ? `No requerida: la tenencia está cubierta por ${cas.cubierta_por_nombre}`
                        : "—",
                ),
              );
            }),
          ),
        ),
      ),
    }),
    seccion({
      titulo: "Tanda",
      contenido: rejilla([
        { etiqueta: "Código", valor: h("a", { href: `#/tandas/${d.tanda_id}`, class: "mono" }, t.codigo) },
        { etiqueta: "Lugar", valor: `${t.lugar.nombre} (${lugares(t.lugar.distrito, t.lugar.provincia)})` },
        { etiqueta: "Recepción", valor: fecha(t.recibida_en, { hora: true }) },
        { etiqueta: "Producto", valor: PRODUCTO[t.estado_producto] },
        { etiqueta: "Peso en balanza", valor: kilos(t.peso_kg), mono: true },
        { etiqueta: "Peso seco equivalente (estimado)", valor: kilos(t.peso_seco_equivalente_kg), mono: true },
        { etiqueta: "Sacos", valor: t.numero_sacos == null ? null : String(t.numero_sacos), mono: true },
        t.humedad_pct != null && { etiqueta: "Humedad", valor: `${t.humedad_pct} %`, mono: true },
        { etiqueta: "Variedad", valor: t.variedad },
        { etiqueta: "Tipo de semilla", valor: t.tipo_semilla },
        { etiqueta: "Cosecha", valor: `Del ${fecha(t.cosecha_desde)} al ${fecha(t.cosecha_hasta)}` },
        ...filasDocumentoEntrega(t),
      ]),
    }),
    seccion({
      titulo: "Alertas y nota",
      sub: "Las alertas no impiden validar: obligan a dejar una nota.",
      contenido: [
        c.alertas.tanda.length || c.alertas.parcela.length
          ? h(
              "ul",
              { class: "lista-simple" },
              c.alertas.tanda.map((a) => h("li", {}, `Tanda: ${ALERTAS_TANDA[a] ?? a}.`)),
              c.alertas.parcela.map((a) => h("li", {}, `Parcela: ${ALERTAS[a] ?? a}.`)),
            )
          : h("p", { class: "panel-sub" }, "Sin alertas al validarse."),
        rejilla([{ etiqueta: "Nota de validación", valor: c.alertas.nota }]),
      ],
    }),
    seccion({
      titulo: "No verificado",
      sub: "Lo que el sistema no comprobó.",
      contenido: h("ul", { class: "lista-simple" }, c.no_verificado.map((linea) => h("li", {}, linea))),
    }),
  ];

  return {
    titulo: d.codigo,
    migas: [["Lotes y proceso", "#/lotes"], ["DOP", "#/lotes/dop"], [d.codigo]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("file")),
        titulo: d.codigo,
        codigo: true,
        insignias: [insigniaDop(d.estado), c.es_demo && insignia("info", "Demostración")],
        detalle: [`${ident.cooperativa.razon_social} · ${d.productor.nombres} ${d.productor.apellidos} · `, h("span", { class: "mono" }, d.parcela_codigo), ` · emitido el ${fecha(d.emitido_en, { hora: true })}`],
        cifra: kilos(d.peso_kg),
        cifraTexto: PRODUCTO[d.estado_producto].toLowerCase(),
        accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => descargarPdf(`/dops/${d.id}/pdf`) }, icono("download"), "Descargar PDF"),
      }),
      !vigente &&
        h(
          "div",
          { class: "verif bad franja-excluida" },
          icono("alert"),
          h("div", {}, h("b", {}, `DOP anulado el ${fecha(d.anulado_en, { hora: true })}${d.anulado_por_nombre ? ` por ${d.anulado_por_nombre}` : ""}`), h("span", {}, `Motivo: ${d.motivo_anulacion.replace(/\.$/, "")}. Conserva su contenido y su PDF; ya no cuenta en ningún cálculo.`)),
        ),
      sello,
      bloques,
    ),
  };
}
