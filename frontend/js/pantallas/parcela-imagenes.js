// Adenda 2 de la Parte 4: pestaña Imágenes del detalle de parcela. Solo una parcela con la alerta de
// análisis tiene imágenes: las de Sentinel-2 antes y después del 31/12/2020, con el lindero dibujado, y
// las versiones de alta resolución de Esri Wayback. El administrador las mira y registra lo que observa.
// Principio: exponer, no concluir. La revisión es lo que una persona vio, no un veredicto del sistema.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { hoyLima as hoy } from "../fechas.js";
import { capaGeojson, cargarMapas, encuadrar, estilo } from "../mapa.js";
import { OBSERVACIONES_2020, OBSERVACIONES_CAMBIO, PAPELES_IMAGEN } from "../textos.js";
import { abrirModal, campo, enviarCon, fecha, h, icono, reemplazar, seccion, toast, vacio } from "../ui.js";

const CORTE = "2020-12-31";
const etiqueta = (lista, valor) => lista.find(([v]) => v === valor)?.[1] ?? valor;
const numero = (valor) => Number(valor).toLocaleString("es-PE", { maximumFractionDigits: 2 });

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

function permisos(ctx) {
  const rol = rolEfectivo();
  const activa = ctx.p.estado === "activa" && ctx.p.habilitacion_estado !== "excluida";
  return {
    regenera: !ctx.delProductor && activa && ["admin_cooperativa", "operador"].includes(rol),
    admin: !ctx.delProductor && activa && rol === "admin_cooperativa",
  };
}

function papel(f) {
  if (f.papel === "anual") return `Imagen de ${f.periodo}`;
  return PAPELES_IMAGEN[f.papel] ?? f.papel;
}

function respectoAlCorte(dias) {
  if (dias == null) return null;
  if (dias === 0) return "el día del corte";
  const n = Math.abs(dias);
  return `${numero(n)} ${n === 1 ? "día" : "días"} ${dias < 0 ? "antes" : "después"} del corte`;
}

function fuenteDe(f) {
  if (f.fuente === "sentinel2") return f.proveedor ?? "Sentinel-2";
  if (f.fuente === "esri_wayback") return `Esri Wayback${f.proveedor ? ` · ${f.proveedor}` : ""}`;
  return `Externa: ${f.proveedor}`;
}

function datosDe(f) {
  return [
    fuenteDe(f),
    f.resolucion_m != null ? `Resolución: ${numero(f.resolucion_m)} m` : null,
    f.nubes_parcela_pct != null ? `nubes sobre la parcela ${numero(f.nubes_parcela_pct)} %` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function atribucion(salida, f) {
  if (f.fuente === "sentinel2") return salida.atribucion_sentinel.replace("{anio}", f.fecha_captura.slice(0, 4));
  if (f.fuente === "esri_wayback") return salida.atribucion_wayback;
  return null;
}

// Las que se comparan: con fecha y con archivo guardado (Sentinel-2 o externas).
const comparables = (imagenes) => imagenes.filter((f) => f.estado === "generada" && f.fecha_captura && f.url_natural);

// ---------- Tira ----------

function itemTira(f, alElegir) {
  if (f.estado === "pendiente") {
    return h("div", { class: "tira-item tira-hueco" }, h("b", { class: "tira-fecha" }, f.periodo ?? papel(f)), h("span", { class: "sec" }, "Generando…"));
  }
  if (f.estado !== "generada") {
    const titulo = f.papel === "anual" ? String(f.periodo) : papel(f);
    return h(
      "div",
      { class: "tira-item tira-hueco", title: f.error_detalle ?? "" },
      h("b", { class: "tira-fecha" }, titulo),
      h("span", { class: "sec" }, f.estado === "error" ? "No se pudo generar" : "Sin imagen utilizable"),
      f.estado === "error" && f.error_detalle && h("span", { class: "sec" }, f.error_detalle),
    );
  }
  return h(
    "button",
    { class: "tira-item", type: "button", onclick: () => alElegir(f), title: `Ver la imagen del ${fecha(f.fecha_captura)}` },
    f.url_natural ? h("img", { src: f.url_natural, alt: "", loading: "lazy" }) : h("span", { class: "tira-sin-vista" }, icono("layers"), "Esri Wayback"),
    h("b", { class: "tira-fecha" }, fecha(f.fecha_captura)),
    h("span", { class: "tira-papel" }, papel(f)),
    h("span", { class: "sec" }, respectoAlCorte(f.dias_respecto_al_corte)),
    h("span", { class: "sec" }, datosDe(f)),
  );
}

// ---------- Comparador ----------

/** Un panel con zoom y desplazamiento (Leaflet en coordenadas de la imagen). */
function panelImagen(L) {
  const caja = h("div", { class: "comp-mapa" });
  const mapa = L.map(caja, { crs: L.CRS.Simple, minZoom: -4, maxZoom: 4, zoomSnap: 0.25, attributionControl: false });
  let capa = null;
  new ResizeObserver(() => mapa.invalidateSize()).observe(caja);
  return {
    caja,
    mapa,
    /** Ancho fijo de 1000 unidades: imágenes del mismo recorte quedan alineadas punto a punto. */
    mostrar(url, alCargar) {
      const imagen = new Image();
      imagen.onload = () => {
        const limites = [
          [0, 0],
          [(1000 * imagen.naturalHeight) / imagen.naturalWidth, 1000],
        ];
        if (capa) mapa.removeLayer(capa);
        capa = L.imageOverlay(url, limites).addTo(mapa);
        alCargar?.(limites);
      };
      imagen.onerror = () => toast("No se pudo cargar la imagen. Vuelve a abrir la pestaña.", "bad");
      imagen.src = url;
    },
  };
}

function sincronizar(a, b) {
  let moviendo = false;
  const seguir = (origen, destino) =>
    origen.on("move zoom", () => {
      if (moviendo) return;
      moviendo = true;
      destino.setView(origen.getCenter(), origen.getZoom(), { animate: false });
      moviendo = false;
    });
  seguir(a, b);
  seguir(b, a);
}

async function comparador(salida) {
  const lista = comparables(salida.imagenes).sort((a, b) => a.fecha_captura.localeCompare(b.fecha_captura));
  if (lista.length < 2) return { nodo: null, elegir: () => {} };
  const L = await cargarMapas();
  const previas = lista.filter((f) => f.fecha_captura <= CORTE);
  const posteriores = lista.filter((f) => f.fecha_captura > CORTE);
  const reciente = posteriores.find((f) => f.papel === "reciente") ?? posteriores.at(-1);
  const estado = { modo: "natural", lados: [previas.at(-1) ?? lista[0], reciente ?? lista.at(-1)] };
  const paneles = [panelImagen(L), panelImagen(L)];
  sincronizar(paneles[0].mapa, paneles[1].mapa);
  let encuadrado = false;

  const opciones = lista.map((f) => [f.id, `${fecha(f.fecha_captura)} · ${papel(f)}`]);
  const selectores = [0, 1].map((i) =>
    campo({
      etiqueta: i === 0 ? "Imagen de la izquierda" : "Imagen de la derecha",
      name: `lado-${i}`,
      opciones,
      value: estado.lados[i].id,
      onchange: (e) => elegirEn(i, lista.find((f) => f.id === e.target.value)),
    }),
  );
  const pies = [h("div", { class: "comp-pie" }), h("div", { class: "comp-pie" })];

  function pintar(i) {
    const f = estado.lados[i];
    const sinInfrarrojo = estado.modo === "infrarrojo" && !f.url_infrarrojo;
    paneles[i].mostrar(estado.modo === "infrarrojo" && f.url_infrarrojo ? f.url_infrarrojo : f.url_natural, (limites) => {
      if (!encuadrado) {
        encuadrado = true;
        paneles[i].mapa.fitBounds(limites);
      }
    });
    reemplazar(
      pies[i],
      h("b", { class: "fecha-grande" }, fecha(f.fecha_captura)),
      h("span", {}, [papel(f), respectoAlCorte(f.dias_respecto_al_corte)].filter(Boolean).join(" · ")),
      h("span", { class: "sec" }, datosDe(f)),
      sinInfrarrojo && h("span", { class: "sec" }, "Esta imagen no tiene versión infrarroja: se muestra en color natural."),
      atribucion(salida, f) && h("span", { class: "sec" }, atribucion(salida, f)),
    );
  }
  function elegirEn(i, f) {
    if (!f) return;
    estado.lados[i] = f;
    selectores[i].querySelector("select").value = f.id;
    pintar(i);
  }
  const botonesModo = [
    ["natural", "Color natural"],
    ["infrarrojo", "Infrarrojo"],
  ].map(([modo, texto]) =>
    h(
      "button",
      {
        type: "button",
        role: "tab",
        "aria-selected": String(modo === estado.modo),
        onclick: () => {
          estado.modo = modo;
          for (const b of botonesModo) b.setAttribute("aria-selected", String(b.dataset.modo === modo));
          pintar(0);
          pintar(1);
        },
        "data-modo": modo,
      },
      texto,
    ),
  );
  pintar(0);
  pintar(1);

  const nodo = h(
    "div",
    { class: "comparador" },
    h(
      "div",
      { class: "comp-barra" },
      h("div", { class: "seg", role: "tablist", "aria-label": "Versión de la imagen" }, botonesModo),
      h("span", { class: "sec" }, "En infrarrojo la vegetación se ve roja; ayuda a distinguir tipos de vegetación. El zoom de las dos imágenes va junto."),
    ),
    h(
      "div",
      { class: "comp-lados" },
      [0, 1].map((i) => h("div", { class: "comp-lado" }, selectores[i], paneles[i].caja, pies[i])),
    ),
  );
  // Desde la tira: la anterior al corte va a la izquierda; la posterior, a la derecha.
  return { nodo, elegir: (f) => elegirEn(f.fecha_captura <= CORTE ? 0 : 1, f) };
}

// ---------- Alta resolución (Esri Wayback) ----------

async function altaResolucion(salida, ctx) {
  const versiones = salida.imagenes.filter((f) => f.fuente === "esri_wayback" && f.estado === "generada" && f.fecha_captura).sort((a, b) => a.fecha_captura.localeCompare(b.fecha_captura));
  if (!versiones.length) return { nodo: null, elegir: () => {} };
  const L = await cargarMapas();
  const caja = h("div", { class: "mapa mapa-wayback" });
  const esPunto = ctx.p.tipo_geometria === "punto";
  const lindero =
    esPunto && ctx.p.area_declarada_ha
      ? L.circle([ctx.p.geometria.coordinates[1], ctx.p.geometria.coordinates[0]], { radius: Math.sqrt((Number(ctx.p.area_declarada_ha) * 10000) / Math.PI), ...estilo("#facc15", 0) })
      : capaGeojson(L, ctx.p.geometria, { style: estilo("#facc15", 0) });
  // Con vista desde el inicio: Leaflet no reacomoda un mapa que todavía no tiene vista.
  const centro = esPunto ? L.latLng(ctx.p.geometria.coordinates[1], ctx.p.geometria.coordinates[0]) : lindero.getBounds().getCenter();
  const mapa = L.map(caja, { maxZoom: 19 }).setView(centro, 16);
  new ResizeObserver(() => mapa.invalidateSize()).observe(caja);
  lindero.addTo(mapa);
  encuadrar(mapa, lindero);
  let capa = null;
  const fechaGrande = h("b", { class: "fecha-grande" });
  const datos = h("span", { class: "sec" });
  const selector = campo({
    etiqueta: "Versión de alta resolución",
    name: "wayback",
    opciones: versiones.map((f) => [f.id, `Captura ${fecha(f.fecha_captura)} · ${f.proveedor ?? "sin proveedor"}`]),
    value: versiones.at(-1).id,
    onchange: (e) => mostrar(versiones.find((f) => f.id === e.target.value)),
  });
  function mostrar(f) {
    if (capa) mapa.removeLayer(capa);
    capa = L.tileLayer(salida.teselas_wayback.replace("{version}", f.identificador_fuente), {
      subdomains: salida.subdominios_wayback,
      maxNativeZoom: 17,
      maxZoom: 19,
      attribution: salida.atribucion_wayback,
    }).addTo(mapa);
    lindero.bringToFront?.();
    selector.querySelector("select").value = f.id;
    fechaGrande.textContent = `Captura del ${fecha(f.fecha_captura)}`;
    datos.textContent = [respectoAlCorte(f.dias_respecto_al_corte), datosDe(f)].filter(Boolean).join(" · ");
  }
  mostrar(versiones.at(-1));
  const nodo = h(
    "div",
    { class: "wayback" },
    h("div", { class: "subtitulo-seccion" }, "Alta resolución (Esri Wayback)"),
    h("p", { class: "panel-sub" }, "Imágenes de distintos proveedores. La fecha es la de captura, no la de publicación. Se ven desde Esri y no se guardan en CacaoTrace."),
    selector,
    h("div", { class: "comp-pie" }, fechaGrande, datos),
    caja,
  );
  return { nodo, elegir: mostrar };
}

// ---------- Acciones ----------

function abrirRevision(ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-revision" }, "Registrar revisión");
  const aviso = h("p", { class: "alerta info", hidden: true }, 'Con "No se distingue" la revisión queda registrada, pero no atiende la alerta. Puedes buscar más imágenes o cargar una imagen externa y registrar otra revisión.');
  const revisarAviso = () => {
    aviso.hidden = ![formulario.observacion_2020.value, formulario.observacion_cambio.value].includes("no_se_distingue");
  };
  const formulario = h(
    "form",
    { class: "form", id: "form-revision", onchange: () => revisarAviso() },
    h("p", {}, "Registra lo que ves en las imágenes, con tu nombre. No es un veredicto del sistema. Una revisión no se edita: si está mal, se anula y se registra otra."),
    campo({ etiqueta: "Qué se ve en la parcela en la imagen anterior al corte", name: "observacion_2020", opciones: [["", "Elige…"], ...OBSERVACIONES_2020], required: true }),
    campo({ etiqueta: "Si dentro del lindero se ve un cambio de cobertura después del corte", name: "observacion_cambio", opciones: [["", "Elige…"], ...OBSERVACIONES_CAMBIO], required: true }),
    aviso,
    h(
      "label",
      { class: "field" },
      "Qué observaste (mínimo 50 caracteres)",
      h("textarea", { class: "input texto-libre", name: "descripcion", required: true, minlength: 50, maxlength: 4000, rows: 4 }),
      h("small", {}, "Por ejemplo, qué se ve en cada fecha y en qué parte de la parcela."),
    ),
  );
  const { cerrar } = abrirModal({
    titulo: "Registrar revisión de imágenes",
    subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi(`/parcelas/${ctx.p.id}/revisiones-imagenes`, { metodo: "POST", cuerpo: datos });
    cerrar();
    toast("Revisión registrada.");
    ctx.recargarPestana();
  });
}

function abrirAnulacion(revision, ctx) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-revision" }, "Anular revisión");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-revision" },
    h("p", {}, "La revisión no se borra: queda anulada y deja de contar. Si estaba mal, registra otra."),
    campo({ etiqueta: "Motivo", name: "motivo", required: true, maxlength: 200 }),
  );
  const { cerrar } = abrirModal({ titulo: "Anular revisión", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/revisiones-imagenes/${revision.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Revisión anulada.");
    ctx.recargarPestana();
  });
}

function abrirExterna(ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-externa" }, "Cargar imagen");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png", required: true });
  const formulario = h(
    "form",
    { class: "form", id: "form-externa" },
    h("p", {}, "Una imagen de otra fuente, por ejemplo de mayor resolución, cuando con las de Sentinel-2 no se distingue. Entra al juego de imágenes con su fuente y su fecha de captura."),
    campo({ etiqueta: "Fuente (proveedor o servicio)", name: "fuente", required: true, maxlength: 200 }),
    campo({ etiqueta: "Fecha de captura", name: "fecha_captura", type: "date", max: hoy(), required: true }),
    h("label", { class: "field" }, "Imagen (JPG o PNG, hasta 10 MB)", archivo),
  );
  const { cerrar } = abrirModal({ titulo: "Cargar imagen externa", subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    cuerpo.append("fuente", datos.fuente);
    cuerpo.append("fecha_captura", datos.fecha_captura);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi(`/parcelas/${ctx.p.id}/imagenes/externa`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Imagen cargada.");
    ctx.recargarPestana();
  });
}

function botonAccion(texto, iconoNombre, ruta, mensaje, ctx, clase = "btn btn-sm") {
  return h(
    "button",
    {
      class: clase,
      type: "button",
      onclick: async (e) => {
        e.currentTarget.classList.add("is-loading");
        try {
          await llamarApi(ruta, { metodo: "POST" });
          toast(mensaje);
          ctx.recargarPestana();
        } catch (error) {
          e.target.closest("button")?.classList.remove("is-loading");
          toast(error.message, "bad");
        }
      },
    },
    icono(iconoNombre),
    texto,
  );
}

// ---------- Revisiones ----------

function historial(revisiones, ctx, puedo) {
  if (!revisiones.length) {
    return h("p", { class: "panel-sub" }, ctx.delProductor ? "La cooperativa todavía no revisó las imágenes de tu parcela." : "Todavía no hay revisiones de estas imágenes.");
  }
  return h(
    "ol",
    { class: "revisiones" },
    revisiones.map((r) =>
      h(
        "li",
        { class: `revision ${r.vigente ? "" : "no-vigente"}` },
        h(
          "div",
          { class: "revision-h" },
          h("b", {}, fecha(r.revisada_en, { hora: true })),
          h(
            "span",
            { class: "fila-acciones" },
            insignia(r.observacion_2020 === "no_se_distingue" ? "warn" : "", `Al corte: ${etiqueta(OBSERVACIONES_2020, r.observacion_2020)}`),
            insignia(r.observacion_cambio === "cambio_visible" ? "bad" : r.observacion_cambio === "no_se_distingue" ? "warn" : "ok", etiqueta(OBSERVACIONES_CAMBIO, r.observacion_cambio)),
            r.anulada_en ? insignia("bad", "Anulada") : !r.vigente && insignia("", "Ya no vigente"),
          ),
        ),
        h("p", {}, r.descripcion),
        h("p", { class: "sec" }, `Revisó ${r.revisada_por_nombre ?? "—"} · ${r.imagenes.length === 1 ? "1 imagen" : `${r.imagenes.length} imágenes`}`),
        r.anulada_en && h("p", { class: "sec" }, `Anulada el ${fecha(r.anulada_en)}${r.anulada_por_nombre ? ` por ${r.anulada_por_nombre}` : ""}: ${r.motivo_anulacion}`),
        !r.anulada_en && !r.vigente && h("p", { class: "sec" }, "Dejó de estar vigente porque cambió la geometría de la parcela."),
        puedo.admin && !r.anulada_en && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirAnulacion(r, ctx) }, "Anular")),
      ),
    ),
  );
}

// ---------- Pestaña ----------

export async function pestanaImagenes(ctx) {
  const [salida, revisiones] = await Promise.all([llamarApi(`${ctx.base}/imagenes`), llamarApi(`${ctx.base}/revisiones-imagenes`)]);
  const puedo = permisos(ctx);
  const sub = "Imágenes satelitales de la parcela antes y después del 31/12/2020, para revisar la alerta de análisis. Sentinel-2 tiene 10 m de resolución: no muestra árboles sueltos.";

  if (salida.estado === "sin_alerta" && !salida.imagenes.length) {
    return seccion({
      titulo: "Imágenes",
      sub,
      contenido: [vacio({ titulo: "Sin imágenes", texto: "Esta parcela no tiene alertas de análisis; no se generaron imágenes." }), revisiones.length > 0 && historial(revisiones, ctx, puedo)],
    });
  }
  // Mientras se generan, la pestaña se refresca sola.
  if (salida.estado === "pendiente") {
    setTimeout(() => ctx.contenedor.isConnected && ctx.pestanaActual() === "imagenes" && ctx.recargarPestana(), 8000);
  }
  const avisos = {
    pendiente: ["info", "Generando las imágenes. La pestaña se actualiza sola."],
    pausada: ["warn", "Se usó el 80 % de la cuota mensual de Copernicus: las imágenes nuevas esperan al próximo mes."],
    no_configurada: ["info", "La fuente de imágenes (Copernicus) no está configurada en el servidor: no se generan imágenes."],
  };
  const aviso = avisos[salida.estado];
  const [comp, wayback] = await Promise.all([comparador(salida), altaResolucion(salida, ctx)]);
  const elegir = (f) => (f.fuente === "esri_wayback" ? wayback.elegir(f) : comp.elegir(f));
  const tira = salida.imagenes.length > 0 && h("div", { class: "tira", role: "list", "aria-label": "Imágenes en orden de fecha" }, salida.imagenes.map((f) => itemTira(f, elegir)));
  const alguna = salida.imagenes.some((f) => f.estado === "generada" && f.fuente !== "esri_wayback");

  const acciones = [
    puedo.admin && alguna && h("button", { class: "btn btn-primary btn-sm", type: "button", onclick: () => abrirRevision(ctx) }, icono("check"), "Registrar revisión"),
    puedo.admin && salida.tiene_alerta && salida.estado === "generada" && botonAccion("Buscar más imágenes", "search", `/parcelas/${ctx.p.id}/imagenes/buscar-mas`, "Buscando más imágenes. La pestaña se actualiza sola.", ctx),
    puedo.admin && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirExterna(ctx) }, icono("upload"), "Cargar imagen externa"),
    puedo.regenera && salida.tiene_alerta && salida.estado === "generada" && botonAccion("Generar de nuevo", "rotate", `/parcelas/${ctx.p.id}/imagenes`, "Se pidió un juego nuevo de imágenes.", ctx, "btn btn-sm btn-ghost"),
  ];

  return seccion({
    titulo: "Imágenes",
    sub,
    acciones,
    contenido: [
      aviso && h("p", { class: `alerta ${aviso[0]}` }, aviso[1]),
      !salida.tiene_alerta && h("p", { class: "alerta info" }, "La parcela ya no tiene la alerta de análisis; estas imágenes quedan como historial."),
      tira,
      comp.nodo,
      wayback.nodo,
      h("div", { class: "subtitulo-seccion" }, "Revisiones de imágenes"),
      historial(revisiones, ctx, puedo),
    ],
  });
}
