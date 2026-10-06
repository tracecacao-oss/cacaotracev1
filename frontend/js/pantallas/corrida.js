// Detalle de una corrida, con el inspector del diseño y cuatro pestañas: Etapas, Tandas, Consolidación y
// DPP. Las etapas van en lista vertical agrupada por fase; cada una abre un formulario corto, ya lleno con la
// plantilla, que el operador confirma o corrige. Las que llena el sistema o no aplican se ven, pero no se
// editan.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import {
  ALERTAS_CORRIDA,
  ESTADOS_CORRIDA,
  FASES,
  RUTAS,
  SITUACIONES,
  abrirEtapa,
  datoPropio,
  etiqueta,
  horas,
  insignia,
  insigniaManejo,
  simbolo,
} from "../proceso.js";
import { PRODUCTO, kilos } from "../textos.js";
import { seccionesLotes } from "../tandas.js";
import { abrirModal, cabeceraFicha, campo, enviarCon, fecha, h, icono, reemplazar, rejilla, seccion, toast } from "../ui.js";

const PESTANAS = [
  ["etapas", "Etapas"],
  ["tandas", "Tandas"],
  ["consolidacion", "Consolidación"],
  ["dpp", "DPP"],
];
let recordada = { id: null, clave: "etapas" };

function tiempo(e) {
  if (!e.inicio) return null;
  return `${fecha(e.inicio, { hora: true })} a ${fecha(e.fin, { hora: true })}${e.duracion_horas != null ? ` · ${horas(e.duracion_horas)}` : ""}`;
}

function filaEtapa(e, catalogo, ctx) {
  const activa = e.situacion === "registrada";
  const dato = activa ? datoPropio(e) : "";
  const accion =
    ctx.opera && e.editable
      ? h(
          "button",
          { class: "btn btn-sm", type: "button", onclick: () => abrirEtapa({ corrida: ctx.c, etapa: e, catalogo, lugares: ctx.lugares, calidades: ctx.calidades, alGuardar: ctx.actualizar }) },
          e.situacion === "pendiente" ? "Registrar" : "Corregir",
        )
      : e.automatica
        ? h("span", { class: "sec" }, "La llena el sistema")
        : null;
  return h(
    "li",
    { class: `etapa ${e.situacion}` },
    h("span", { class: "etapa-n mono" }, String(e.numero)),
    simbolo(e.tipo, activa),
    h(
      "div",
      { class: "etapa-c" },
      h("span", { class: "etapa-h" }, h("b", {}, e.nombre), insignia(SITUACIONES[e.situacion] ?? ["", e.situacion]), e.desde_plantilla && h("span", { class: "badge", title: "Lugar, método y distancia iguales a la plantilla" }, h("span", { class: "dot" }), "Como la plantilla")),
      activa &&
        h(
          "span",
          { class: "sec" },
          [e.lugar_nombre, tiempo(e), e.distancia_m != null ? `${Number(e.distancia_m).toLocaleString("es-PE")} m` : null, e.responsable].filter(Boolean).join(" · "),
        ),
      dato && h("span", { class: "etapa-dato" }, dato),
      activa && e.metodo && h("span", { class: "sec" }, `Método: ${e.metodo}`),
      e.observacion && h("span", { class: "sec" }, `Observación: ${e.observacion}`),
    ),
    accion,
  );
}

function pestanaEtapas(ctx) {
  const porNumero = Object.fromEntries(ctx.catalogo.map((e) => [e.numero, e]));
  return seccion({
    titulo: "Etapas",
    sub: ctx.c.estado === "abierta" ? "Las etapas se registran cuando la corrida se inicia." : "Las 23 etapas del proceso, agrupadas por fase. El orden cronológico se comprueba al consolidar.",
    contenido: FASES.map(([clave, nombre]) =>
      h(
        "div",
        { class: "fase-grupo" },
        h("div", { class: "subtitulo-seccion" }, nombre),
        h(
          "ol",
          { class: "etapas" },
          ctx.c.etapas.filter((e) => e.fase === clave).map((e) => filaEtapa(e, porNumero[e.numero], ctx)),
        ),
      ),
    ),
  });
}

async function abrirAgregar(ctx) {
  const disponibles = await llamarApi("/corridas/tandas-disponibles", { parametros: { ruta: ctx.c.ruta } });
  const productores = new Set(ctx.c.tandas.map((t) => t.productor.id));
  const opciones = disponibles.filter((t) => ctx.c.tipo_manejo !== "segregado" || !productores.size || productores.has(t.productor.id));
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-agregar" }, "Agregar tanda");
  const formulario = h(
    "form",
    { class: "form", id: "form-agregar" },
    campo({
      etiqueta: "Tanda",
      name: "tanda_id",
      required: true,
      opciones: [["", opciones.length ? "Elige la tanda…" : "No hay tandas disponibles"], ...opciones.map((t) => [t.tanda_id, `${t.codigo} · ${t.productor.nombres} ${t.productor.apellidos} · ${kilos(t.peso_kg)}`])],
    }),
    h("label", { class: "field" }, "Observación de calidad (opcional)", h("textarea", { class: "input texto-libre", name: "observacion_calidad", maxlength: 4000, rows: 2 })),
  );
  const { cerrar } = abrirModal({ titulo: "Agregar tanda", subtitulo: ctx.c.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const c = await llamarApi(`/corridas/${ctx.c.id}/tandas`, { metodo: "POST", cuerpo: { tanda_id: datos.tanda_id, observacion_calidad: datos.observacion_calidad?.trim() || null } });
    cerrar();
    toast("Tanda agregada.");
    ctx.actualizar(c);
  });
}

function abrirAnular(ctx) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-corrida" }, "Anular corrida");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-corrida" },
    h("p", {}, "La corrida queda anulada como historial y sus tandas vuelven a estar disponibles para otra corrida."),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular corrida", subtitulo: ctx.c.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    const c = await llamarApi(`/corridas/${ctx.c.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Corrida anulada.", "warn");
    ctx.actualizar(c);
  });
}

function pestanaTandas(ctx) {
  const { c } = ctx;
  const abierta = c.estado === "abierta" && ctx.opera;
  const quitar = async (t) => {
    try {
      ctx.actualizar(await llamarApi(`/corridas/${c.id}/tandas/${t.tanda_id}`, { metodo: "DELETE" }));
      toast("Tanda quitada.");
    } catch (error) {
      toast(error.message, "bad");
    }
  };
  const iniciar = async (e) => {
    e.currentTarget.classList.add("is-loading");
    try {
      ctx.actualizar(await llamarApi(`/corridas/${c.id}/iniciar`, { metodo: "POST" }), "etapas");
      toast("Corrida iniciada.");
    } catch (error) {
      toast(error.message, "bad");
      e.target.closest("button")?.classList.remove("is-loading");
    }
  };
  return seccion({
    titulo: "Tandas",
    sub: abierta ? "Agrega o quita tandas; al iniciar, la lista ya no cambia." : "Cada tanda con su peso al entrar y, al consolidar, su proporción.",
    acciones: ctx.opera &&
      ["abierta", "en_proceso"].includes(c.estado) && [
        abierta && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirAgregar(ctx) }, icono("plus"), "Agregar tanda"),
        abierta && h("button", { class: "btn btn-primary btn-sm", type: "button", disabled: !c.tandas.length, onclick: iniciar }, icono("check"), "Iniciar"),
        h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnular(ctx) }, "Anular corrida"),
      ],
    contenido: c.tandas.length
      ? h(
          "div",
          { class: "tbl-box" },
          h(
            "table",
            { class: "tabla" },
            h("thead", {}, h("tr", {}, h("th", {}, "Tanda"), h("th", {}, "Productor"), h("th", { class: "ocultar-sm" }, "Parcela"), h("th", { class: "num" }, "Peso"), h("th", { class: "num" }, "Proporción"), abierta && h("th", {}, h("span", { class: "sr-only" }, "Quitar")))),
            h(
              "tbody",
              {},
              c.tandas.map((t) =>
                h(
                  "tr",
                  {},
                  h("td", {}, h("a", { href: `#/tandas/${t.tanda_id}`, class: "mono" }, t.codigo), t.dop && h("a", { href: `#/dops/${t.dop.id}`, class: "sec mono" }, t.dop.codigo), t.observacion_calidad && h("span", { class: "sec" }, t.observacion_calidad)),
                  h("td", {}, `${t.productor.nombres} ${t.productor.apellidos}`, h("span", { class: "sec mono" }, `DNI ${t.productor.dni}`)),
                  h("td", { class: "ocultar-sm" }, h("span", { class: "mono" }, t.parcela.codigo), h("span", { class: "sec" }, `${t.parcela.nombre} · ${t.parcela.habilitacion_estado}`)),
                  h("td", { class: "num" }, h("span", { class: "mono" }, kilos(t.peso_kg)), h("span", { class: "sec" }, PRODUCTO[t.estado_producto])),
                  h("td", { class: "num mono" }, t.proporcion ?? "—"),
                  abierta && h("td", {}, h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => quitar(t) }, "Quitar")),
                ),
              ),
            ),
          ),
        )
      : h("p", { class: "panel-sub" }, "La corrida todavía no tiene tandas."),
  });
}

function pestanaConsolidacion(ctx) {
  const { c } = ctx;
  if (c.estado === "consolidada") {
    return seccion({
      titulo: "Consolidación",
      sub: `Consolidada el ${fecha(c.consolidada_en, { hora: true })}; su tanda final entró al stock.`,
      contenido: rejilla([
        { etiqueta: "Tanda final", valor: c.tanda_final && h("a", { href: `#/tandas-finales/${c.tanda_final.id}`, class: "mono" }, c.tanda_final.codigo) },
        { etiqueta: "DPP", valor: c.dpp && h("a", { href: `#/dpps/${c.dpp.id}`, class: "mono" }, c.dpp.codigo) },
        { etiqueta: "Rendimiento", valor: c.rendimiento.rendimiento },
      ]),
    });
  }
  if (c.estado !== "en_proceso") {
    return seccion({ titulo: "Consolidación", contenido: h("p", { class: "panel-sub" }, c.estado === "anulada" ? `Corrida anulada: ${c.motivo_anulacion}` : "Se consolida cuando todas las etapas de su ruta estén registradas.") });
  }
  const r = c.rendimiento;
  const etapa = (n) => c.etapas.find((e) => e.numero === n);
  const completa = c.ruta === "completa";
  const peso = campo({ etiqueta: "Peso final (kg)", name: "peso_final_kg", type: "number", step: "0.01", min: "0.01", inputmode: "decimal", required: true, value: r.peso_final_kg ?? "", class: "input mono", ayuda: "El de la etapa 19. Si lo cambias, la etapa 19 se corrige con el nuevo valor." });
  const humedad = campo({ etiqueta: "Humedad final (%)", name: "humedad_pct", type: "number", step: "0.1", min: "0", max: "100", inputmode: "decimal", required: true, value: etapa(13)?.datos?.humedad_pct ?? "", class: "input mono", ayuda: completa ? "Propuesta: la de la etapa 13." : null });
  const almacen = campo({ etiqueta: "Almacén", name: "lugar_id", required: true, opciones: [["", "Elige el almacén…"], ...ctx.lugares.filter((l) => l.activo).map((l) => [l.id, l.nombre])], value: etapa(23)?.lugar_id ?? "" });
  const explicacion = h(
    "label",
    { class: "field", hidden: true },
    "Explicación (obligatoria, mínimo 50 caracteres)",
    h("textarea", { class: "input texto-libre", name: "explicacion", maxlength: 4000, rows: 3 }),
    h("small", {}, "Por qué salió más o menos grano de lo esperado. Llega al informe de hallazgos."),
  );
  const medida = h("div", { class: "rendimiento", "aria-live": "polite" });
  const entrada = Number(r.entrada_kg);

  function calcular() {
    const pf = Number(peso.querySelector("input").value);
    let alerta = null;
    let texto = "Escribe el peso final para calcular el rendimiento.";
    if (pf > 0 && entrada > 0) {
      const razon = pf / entrada;
      if (completa) {
        if (razon > Number(r.banda_max)) alerta = "rendimiento_sobre_banda";
        else if (razon < Number(r.banda_min)) alerta = "rendimiento_bajo_banda";
        texto = `Rendimiento ${razon.toFixed(3)}: ${kilos(pf)} de grano seco por ${kilos(entrada)} de baba. Banda de la cooperativa: ${r.banda_min} a ${r.banda_max}.`;
      } else {
        if (pf > entrada * 1.01) alerta = "peso_final_supera_entrada";
        texto = `${kilos(pf)} de salida por ${kilos(entrada)} de grano seco de entrada (${(razon * 100).toFixed(1)} %).`;
      }
    }
    reemplazar(medida, h("p", { class: alerta ? "alerta warn" : "panel-sub" }, texto, alerta && h("b", {}, ` ${ALERTAS_CORRIDA[alerta]}.`)));
    explicacion.hidden = !alerta;
    const area = explicacion.querySelector("textarea");
    area.required = Boolean(alerta);
    area.minLength = alerta ? 50 : 0;
  }
  peso.querySelector("input").addEventListener("input", calcular);
  calcular();

  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-consolidar", disabled: !c.puede_consolidar }, icono("check"), "Consolidar y emitir DPP");
  const formulario = h("form", { class: "form", id: "form-consolidar" }, h("div", { class: "grid2" }, peso, humedad), medida, almacen, explicacion, boton);
  enviarCon(formulario, boton, async (datos) => {
    const e19 = etapa(19);
    if (Number(datos.peso_final_kg) !== Number(e19.datos?.peso_final_kg)) {
      // El peso final es uno solo: si cambió, primero se corrige la etapa 19 (queda en la auditoría).
      await llamarApi(`/corridas/${c.id}/etapas/19`, {
        metodo: "PATCH",
        cuerpo: {
          lugar_id: e19.lugar_id,
          inicio: e19.inicio,
          fin: e19.fin,
          metodo: e19.metodo,
          responsable: e19.responsable,
          observacion: e19.observacion,
          datos: { peso_final_kg: datos.peso_final_kg },
        },
      });
    }
    const consolidada = await llamarApi(`/corridas/${c.id}/consolidar`, {
      metodo: "POST",
      cuerpo: { peso_final_kg: datos.peso_final_kg, humedad_pct: datos.humedad_pct, lugar_id: datos.lugar_id, explicacion: datos.explicacion?.trim() || null },
    });
    toast(`DPP emitido: ${consolidada.dpp.codigo}`);
    ctx.actualizar(consolidada, "consolidacion");
  });
  return seccion({
    titulo: "Consolidación",
    sub: "Cierra la corrida: fija la proporción de cada tanda, crea la tanda final que entra al stock y emite el DPP. Ninguna alerta lo impide.",
    contenido: [
      c.faltan_para_consolidar.length > 0 && h("div", { class: "alerta warn" }, h("b", {}, "Antes de consolidar falta:"), h("ul", { class: "lista-simple" }, c.faltan_para_consolidar.map((f) => h("li", {}, f)))),
      formulario,
    ],
  });
}

function pestanaDpp(ctx) {
  const { c } = ctx;
  return seccion({
    titulo: "DPP",
    sub: "La copia sellada de la corrida consolidada. Un DPP anulado queda en el historial.",
    contenido: c.dpps.length
      ? h("ul", { class: "lista-simple" }, c.dpps.map((d) => h("li", {}, h("a", { href: `#/dpps/${d.id}`, class: "mono" }, d.codigo), " ", insignia(d.estado === "vigente" ? ["ok", "Vigente"] : ["bad", "Anulado"]))))
      : h("p", { class: "panel-sub" }, "Se emite al consolidar la corrida."),
  });
}

export default async function corrida({ parametros: [id] }) {
  const [c, catalogo, lugares, calidades] = await Promise.all([llamarApi(`/corridas/${id}`), llamarApi("/proceso/etapas"), llamarApi("/lugares"), llamarApi("/calidades")]);
  const ctx = { c, catalogo, lugares, calidades, opera: ["admin_cooperativa", "operador"].includes(rolEfectivo()) };
  if (recordada.id !== id) recordada = { id, clave: c.estado === "abierta" ? "tandas" : "etapas" };
  const cuerpo = h("div", { class: "contenido-pestana" });
  const barra = h("div", { class: "seg", role: "tablist", "aria-label": "Secciones de la corrida" });
  const cabecera = h("div");
  const generadores = { etapas: pestanaEtapas, tandas: pestanaTandas, consolidacion: pestanaConsolidacion, dpp: pestanaDpp };

  function pintarCabecera() {
    reemplazar(
      cabecera,
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("layers")),
        titulo: ctx.c.codigo,
        codigo: true,
        insignias: [insignia(ESTADOS_CORRIDA[ctx.c.estado]), insigniaManejo(ctx.c.tipo_manejo), h("span", { class: "badge" }, h("span", { class: "dot" }), `Ruta ${etiqueta(RUTAS, ctx.c.ruta).toLowerCase()}`)],
        detalle: [
          `${ctx.c.fase_nombre}`,
          ctx.c.etapa_actual ? ` · etapa ${ctx.c.etapa_actual}: ${ctx.c.etapa_actual_nombre}` : ctx.c.estado === "en_proceso" ? " · todas las etapas registradas" : "",
          ` · abierta por ${ctx.c.abierta_por_nombre ?? "—"} el ${fecha(ctx.c.abierta_en)}`,
        ],
        cifra: kilos(ctx.c.entrada_kg),
        cifraTexto: `de entrada · ${ctx.c.numero_tandas} ${ctx.c.numero_tandas === 1 ? "tanda" : "tandas"}`,
      }),
      ctx.c.alertas.length > 0 && h("div", { class: "verif warn" }, icono("alert"), h("div", {}, h("b", {}, "Alertas"), ctx.c.alertas.map((a) => h("span", {}, ALERTAS_CORRIDA[a] ?? a)))),
    );
  }

  function mostrar(clave) {
    recordada = { id, clave };
    for (const b of barra.children) b.setAttribute("aria-selected", String(b.dataset.clave === clave));
    reemplazar(cuerpo, generadores[clave](ctx));
  }
  ctx.actualizar = (nueva, clave = recordada.clave) => {
    ctx.c = nueva;
    pintarCabecera();
    mostrar(clave);
  };
  for (const [clave, texto] of PESTANAS) barra.append(h("button", { type: "button", role: "tab", "data-clave": clave, onclick: () => mostrar(clave) }, texto));
  pintarCabecera();
  mostrar(recordada.clave);

  return {
    titulo: c.codigo,
    migas: [["Lotes y proceso", "#/lotes"], ["Corridas", "#/lotes/corridas"], [c.codigo]],
    secciones: seccionesLotes(),
    cabecera: null,
    contenido: h("section", { class: "panel inspector" }, cabecera, h("div", { class: "ins-tabs seg-scroll" }, barra), cuerpo),
  };
}
