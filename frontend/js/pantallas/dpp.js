// Detalle de DPP: el contenido sellado por bloques, en el mismo orden que el PDF, con su huella, el código
// QR de la verificación pública y el botón de descargar el PDF. Solo el administrador lo anula.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { ALERTAS_CORRIDA, FASES, MANEJOS, RUTAS, SITUACIONES, datoPropio, etiqueta, horas, insignia, simbolo } from "../proceso.js";
import { PRODUCTO, kilos } from "../textos.js";
import { codigoQr, descargarPdf, huella, seccionesLotes } from "../tandas.js";
import { abrirModal, cabeceraFicha, enviarCon, fecha, h, icono, rejilla, seccion, toast } from "../ui.js";

function abrirAnulacion(d, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-dpp" }, "Anular DPP");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-dpp" },
    h(
      "p",
      { class: "alerta warn" },
      "El DPP anulado conserva su contenido y su PDF, y la verificación pública lo muestra como anulado. Su tanda final sale del stock y la corrida vuelve a quedar en proceso para corregirla y consolidarla de nuevo.",
    ),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular DPP", subtitulo: d.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/dpps/${d.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("DPP anulado. La corrida volvió a quedar en proceso.", "warn");
    alAnular();
  });
}

function diagrama(etapas) {
  return FASES.map(([clave, nombre]) =>
    h(
      "div",
      { class: "fase-grupo" },
      h("div", { class: "subtitulo-seccion" }, nombre),
      h(
        "ol",
        { class: "etapas" },
        etapas
          .filter((e) => e.fase === clave)
          .map((e) => {
            const activa = e.situacion === "registrada";
            const dato = activa ? datoPropio(e) : "";
            return h(
              "li",
              { class: `etapa ${e.situacion}` },
              h("span", { class: "etapa-n mono" }, String(e.numero)),
              simbolo(e.tipo, activa),
              h(
                "div",
                { class: "etapa-c" },
                h("span", { class: "etapa-h" }, h("b", {}, e.nombre), !activa && insignia(SITUACIONES[e.situacion] ?? ["", e.situacion]), e.desde_plantilla && h("span", { class: "badge" }, h("span", { class: "dot" }), "Como la plantilla")),
                activa &&
                  h(
                    "span",
                    { class: "sec" },
                    [e.lugar, e.inicio && `${fecha(e.inicio, { hora: true })} a ${fecha(e.fin, { hora: true })}`, e.duracion_horas != null ? horas(e.duracion_horas) : null, e.distancia_m != null ? `${Number(e.distancia_m).toLocaleString("es-PE")} m` : null, e.responsable].filter(Boolean).join(" · "),
                  ),
                dato && h("span", { class: "etapa-dato" }, dato),
                activa && e.metodo && h("span", { class: "sec" }, `Método: ${e.metodo}`),
              ),
            );
          }),
      ),
    ),
  );
}

export default async function dpp({ parametros: [id], recargar }) {
  const d = await llamarApi(`/dpps/${id}`);
  const c = d.contenido;
  const ident = c.identificacion;
  const r = c.rendimiento;
  const vigente = d.estado === "vigente";

  const sello = seccion({
    titulo: "Sello",
    sub: "SHA-256 del contenido en forma canónica: claves ordenadas, UTF-8 y sin espacios sobrantes. Cualquiera con el contenido puede recalcularla.",
    acciones: vigente && rolEfectivo() === "admin_cooperativa" && h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacion(d, recargar) }, "Anular DPP"),
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

  const bloques = [
    seccion({
      titulo: "Identificación",
      contenido: rejilla([
        { etiqueta: "Código", valor: ident.codigo, mono: true },
        { etiqueta: "Cooperativa", valor: `${ident.cooperativa.razon_social} (${ident.cooperativa.codigo})` },
        { etiqueta: "RUC de la cooperativa", valor: ident.cooperativa.ruc, mono: true },
        { etiqueta: "Fecha de emisión", valor: fecha(ident.emitido_en, { hora: true }) },
        { etiqueta: "Corrida", valor: h("a", { href: `#/corridas/${d.corrida_id}`, class: "mono" }, ident.corrida) },
        { etiqueta: "Ruta y manejo", valor: `Ruta ${etiqueta(RUTAS, ident.ruta).toLowerCase()} · ${etiqueta(MANEJOS, ident.tipo_manejo).toLowerCase()}` },
        { etiqueta: "Consolidó", valor: ident.consolidada_por },
      ]),
    }),
    seccion({
      titulo: "Entrada",
      sub: `Las tandas que entraron, con su DOP y su proporción sobre la masa de entrada (${kilos(c.entrada.peso_total_kg)}).`,
      contenido: h(
        "div",
        { class: "tbl-box" },
        h(
          "table",
          { class: "tabla tabla-compacta" },
          h("thead", {}, h("tr", {}, h("th", {}, "Tanda y DOP"), h("th", {}, "Productor"), h("th", { class: "ocultar-sm" }, "Parcela"), h("th", { class: "num" }, "Peso"), h("th", { class: "num" }, "Proporción"))),
          h(
            "tbody",
            {},
            c.entrada.tandas.map((t) =>
              h(
                "tr",
                {},
                h("td", {}, h("span", { class: "mono" }, t.tanda), h("span", { class: "sec mono" }, t.dop)),
                h("td", {}, t.productor.nombres, h("span", { class: "sec mono" }, `DNI ${t.productor.dni}`)),
                h("td", { class: "ocultar-sm" }, h("span", { class: "mono" }, t.parcela.codigo), h("span", { class: "sec" }, t.parcela.nombre)),
                h("td", { class: "num" }, h("span", { class: "mono" }, kilos(t.peso_kg)), h("span", { class: "sec" }, PRODUCTO[t.estado_producto])),
                h("td", { class: "num mono" }, t.proporcion),
              ),
            ),
          ),
        ),
      ),
    }),
    seccion({ titulo: "Diagrama de análisis de proceso", sub: "Las 23 etapas con su símbolo: operación, inspección, transporte, espera o almacenamiento.", contenido: diagrama(c.etapas) }),
    seccion({
      titulo: "Salida",
      contenido: rejilla([
        { etiqueta: "Tanda final", valor: h("a", { href: `#/tandas-finales/${d.tanda_final_id}`, class: "mono" }, c.salida.tanda_final) },
        { etiqueta: "Peso final", valor: kilos(c.salida.peso_final_kg), mono: true },
        { etiqueta: "Humedad", valor: c.salida.humedad_pct == null ? null : `${c.salida.humedad_pct} %`, mono: true },
        { etiqueta: "Calidad", valor: c.salida.calidad },
        { etiqueta: "Sacos", valor: String(c.salida.numero_sacos), mono: true },
        { etiqueta: "Almacén", valor: c.salida.almacen },
      ]),
    }),
    seccion({
      titulo: "Rendimiento",
      sub: r.ruta === "completa" ? "Grano seco que salió entre la baba que entró, junto a la banda de la cooperativa." : "Ruta seco: el peso final se compara con el seco que entró.",
      contenido: rejilla([
        { etiqueta: "Entrada", valor: kilos(r.entrada_kg), mono: true },
        { etiqueta: "Peso final", valor: kilos(r.peso_final_kg), mono: true },
        { etiqueta: "Rendimiento", valor: r.rendimiento, mono: true },
        r.ruta === "completa" && { etiqueta: "Banda", valor: `${r.banda_min} a ${r.banda_max}`, mono: true },
      ]),
    }),
    seccion({
      titulo: "Alertas y explicación",
      sub: "Las alertas no impiden consolidar: el rendimiento fuera de banda obliga a dejar una explicación.",
      contenido: [
        c.alertas.alertas.length ? h("ul", { class: "lista-simple" }, c.alertas.alertas.map((a) => h("li", {}, `${ALERTAS_CORRIDA[a] ?? a}.`))) : h("p", { class: "panel-sub" }, "Sin alertas al consolidarse."),
        c.alertas.explicacion && rejilla([{ etiqueta: "Explicación", valor: c.alertas.explicacion }]),
      ],
    }),
    seccion({ titulo: "No verificado", sub: "Lo que el sistema no comprobó.", contenido: h("ul", { class: "lista-simple" }, c.no_verificado.map((linea) => h("li", {}, linea))) }),
  ];

  return {
    titulo: d.codigo,
    migas: [["Lotes y proceso", "#/lotes"], ["Corridas", "#/lotes/corridas"], [d.corrida_codigo, `#/corridas/${d.corrida_id}`], [d.codigo]],
    secciones: seccionesLotes(),
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("file")),
        titulo: d.codigo,
        codigo: true,
        insignias: [insignia(vigente ? ["ok", "DPP vigente"] : ["bad", "DPP anulado"])],
        detalle: [`${ident.cooperativa.razon_social} · `, h("span", { class: "mono" }, d.corrida_codigo), ` · emitido el ${fecha(d.emitido_en, { hora: true })}`],
        cifra: kilos(d.peso_seco_kg),
        cifraTexto: "de grano seco",
        accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => descargarPdf(`/dpps/${d.id}/pdf`) }, icono("download"), "Descargar PDF"),
      }),
      !vigente &&
        h(
          "div",
          { class: "verif bad franja-excluida" },
          icono("alert"),
          h("div", {}, h("b", {}, `DPP anulado el ${fecha(d.anulado_en, { hora: true })}${d.anulado_por_nombre ? ` por ${d.anulado_por_nombre}` : ""}`), h("span", {}, `Motivo: ${d.motivo_anulacion.replace(/\.$/, "")}. Conserva su contenido y su PDF.`)),
        ),
      sello,
      bloques,
    ),
  };
}
