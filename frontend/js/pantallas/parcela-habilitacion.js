// Parte 4 en el detalle de la parcela: pestañas Cobertura forestal, Visitas, Expediente y
// Habilitación. El operador y el productor arman el expediente; el administrador decide.
// Principio: exponer, no concluir. Cada tarjeta dice quién afirma qué y cuándo.

import { llamarApi } from "../api.js";
import { verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import {
  ESTADOS_CASILLA,
  FUENTES,
  MOTIVOS_VISITA,
  REQUISITOS,
  REQUISITOS_PRODUCTOR,
  USOS_OBSERVADOS,
  hectareas,
  insigniaAlerta,
  insigniaHabilitacion,
  insigniaNivel,
} from "../textos.js";
import { abrirModal, campo, cargando, enviarCon, errorDeCarga, fecha, h, icono, reemplazar, seccion, toast, vacio } from "../ui.js";

const hoy = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima" }).format(new Date());

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

/** ctx: { p, base, delProductor, recargar } — base es /parcelas/{id} o /mi/parcelas/{id}. */
function permisos(ctx) {
  const rol = rolEfectivo();
  const activa = ctx.p.estado === "activa" && ctx.p.habilitacion_estado !== "excluida";
  return {
    registro: activa && ["admin_cooperativa", "operador"].includes(rol),
    admin: activa && rol === "admin_cooperativa",
    // El productor carga documentos legales de sus propias parcelas.
    cargaDocumentos: activa && (ctx.delProductor || ["admin_cooperativa", "operador"].includes(rol)),
  };
}

// ---------- Cobertura forestal ----------

const INDICADORES_WHISP = {
  risk_pcrop: "Riesgo para cultivos permanentes (incluye cacao)",
  Ind_01_treecover: "Cobertura arbórea al 2020",
  Ind_02_commodities: "Cultivos o agricultura al 2020",
  Ind_03_disturbance_before_2020: "Perturbación antes de 2020",
  Ind_04_disturbance_after_2020: "Perturbación desde 2021",
  EUFO_2020: "Bosque al 2020 según JRC",
  GLAD_Primary: "Bosque primario (GLAD)",
  TMF_undist: "Bosque tropical no perturbado (TMF)",
  Cocoa_ETH: "Cacao (ETH)",
  Cocoa_FDaP: "Cacao (FDaP)",
  Cocoa_2024_FDaP: "Cacao 2024 (FDaP)",
  Area: "Área analizada",
  Country: "País",
  In_waterbody: "Dentro de un cuerpo de agua",
};

function valorIndicador(clave, valor, unidad) {
  if (valor === "yes") return "sí";
  if (valor === "no") return "no";
  if (typeof valor === "boolean") return valor ? "sí" : "no";
  if (typeof valor === "number" && !["Country"].includes(clave)) return `${valor.toLocaleString("es-PE", { maximumFractionDigits: 4 })}${unidad ? ` ${unidad}` : ""}`;
  return String(valor);
}

function indicadoresWhisp(ind) {
  const unidad = ind.Unit === "percent" ? "%" : "ha";
  return Object.entries(INDICADORES_WHISP)
    .filter(([clave]) => clave in ind)
    .map(([clave, etiqueta]) => h("div", {}, h("dt", {}, etiqueta, h("span", { class: "campo-fuente mono" }, clave)), h("dd", {}, valorIndicador(clave, ind[clave], unidad))));
}

function indicadoresGfw(ind) {
  const filas = [
    ["Alertas integradas de deforestación", ind.alertas_desde_2021 != null ? String(ind.alertas_desde_2021) : "—"],
    ["Pérdida de cobertura arbórea", hectareas(ind.perdida_ha_total)],
    ...Object.entries(ind.perdida_ha_por_anio ?? {}).map(([anio, ha]) => [`Pérdida en ${anio}`, hectareas(ha)]),
    ["Rango consultado", ind.desde ? `${ind.desde} a ${ind.hasta}` : "—"],
    ["Umbral de densidad arbórea 2000", ind.umbral_densidad_2000_porcentaje != null ? `${ind.umbral_densidad_2000_porcentaje} %` : "—"],
  ];
  return filas.map(([etiqueta, valor]) => h("div", {}, h("dt", {}, etiqueta), h("dd", {}, valor)));
}

const ESTADO_ANALISIS = {
  pendiente: ["info", "En proceso"],
  en_proceso: ["info", "En proceso"],
  completado: ["ok", "Completado"],
  error: ["bad", "Error"],
};

async function descargarRespuesta(analisis) {
  const ventana = window.open("about:blank", "_blank");
  try {
    const { respuesta_url: url } = await llamarApi(`/analisis/${analisis.id}`);
    if (!url) throw new Error("La respuesta completa no está disponible.");
    if (ventana) {
      ventana.opener = null;
      ventana.location.href = url;
    } else window.location.assign(url);
  } catch (error) {
    ventana?.close();
    toast(error.message, "bad");
  }
}

function tarjetaFuente(codigo, analisis, configurada, ctx) {
  const ultimo = analisis.find((a) => a.fuente === codigo);
  const nombre = FUENTES[codigo];
  if (!ultimo) {
    return h(
      "article",
      { class: "fuente" },
      h("div", { class: "fuente-h" }, h("b", {}, nombre), configurada === false ? insignia("", "Fuente no configurada") : insignia("", "Sin análisis")),
      h("p", { class: "panel-sub" }, configurada === false ? "Falta la clave de esta fuente en el servidor: no se crean análisis." : "Todavía no hay un análisis de esta fuente para la parcela."),
    );
  }
  const [clase, texto] = ESTADO_ANALISIS[ultimo.estado];
  const marcas = [
    insignia(clase, texto),
    ultimo.estado === "completado" && (ultimo.obsoleto ? insignia("warn", "Obsoleto: la geometría cambió") : ultimo.vigente ? insignia("ok", "Vigente") : insignia("warn", "Vencido")),
    ultimo.es_aproximacion && insignia("info", "Aproximación"),
  ];
  const ind = ultimo.indicadores ?? {};
  return h(
    "article",
    { class: "fuente" },
    h("div", { class: "fuente-h" }, h("b", {}, nombre), h("span", { class: "fila-acciones" }, marcas)),
    h(
      "p",
      { class: "fuente-meta" },
      ultimo.completado_en ? `Analizado el ${fecha(ultimo.completado_en, { hora: true })}` : `Solicitado el ${fecha(ultimo.solicitado_en, { hora: true })}`,
      ultimo.version_fuente && ` · versión ${ultimo.version_fuente}`,
    ),
    ultimo.estado === "completado" && h("p", { class: "fuente-resultado" }, ultimo.resultado_texto ?? `${nombre}: sin resultado`),
    ultimo.estado === "error" && h("p", { class: "alerta bad" }, ultimo.error_detalle ?? "La fuente falló."),
    ultimo.estado === "completado" &&
      ultimo.error_detalle &&
      h("p", { class: "alerta warn" }, `${ultimo.error_detalle}. La respuesta completa quedó guardada; una persona debe revisar la parcela.`),
    ultimo.estado !== "completado" && ultimo.estado !== "error" && h("p", { class: "panel-sub" }, `Consultando a ${nombre}… intento ${Math.max(ultimo.intentos, 1)}.`),
    ultimo.es_aproximacion && h("p", { class: "panel-sub" }, "La parcela es un punto: esta fuente analizó un círculo con el área declarada."),
    ultimo.estado === "completado" && h("dl", { class: "kv" }, codigo === "whisp" ? indicadoresWhisp(ind) : indicadoresGfw(ind)),
    !ctx.delProductor && ultimo.respuesta_documento_id && h("button", { class: "linkbtn", type: "button", onclick: () => descargarRespuesta(ultimo) }, "Descargar la respuesta completa"),
  );
}

export async function pestanaCobertura(ctx) {
  const { p, base } = ctx;
  const [analisis, fuentes] = await Promise.all([
    llamarApi(`${base}/analisis`),
    ctx.delProductor ? Promise.resolve(null) : llamarApi("/analisis/fuentes"),
  ]);
  const configurada = Object.fromEntries((fuentes ?? []).map((f) => [f.fuente, f.configurada]));
  const puedo = permisos(ctx);
  const repetir =
    puedo.registro &&
    h(
      "button",
      {
        class: "btn btn-sm",
        type: "button",
        onclick: async (e) => {
          e.currentTarget.classList.add("is-loading");
          try {
            await llamarApi(`/parcelas/${p.id}/analisis`, { metodo: "POST" });
            toast("Análisis solicitado. Se actualiza solo cuando las fuentes respondan.");
            ctx.recargarPestana();
          } catch (error) {
            toast(error.message, "bad");
          }
        },
      },
      icono("rotate"),
      "Repetir análisis",
    );
  // Mientras haya consultas en curso, la pestaña se refresca sola.
  if (analisis.some((a) => a.estado === "pendiente" || a.estado === "en_proceso")) {
    setTimeout(() => ctx.contenedor.isConnected && ctx.pestanaActual() === "cobertura" && ctx.recargarPestana(), 5000);
  }
  return seccion({
    titulo: "Cobertura forestal",
    sub: "Lo que dice cada fuente sobre la parcela, con su fecha y su versión. CacaoTrace no emite veredictos ni combina fuentes.",
    acciones: repetir,
    contenido: [
      h("div", { class: "fuentes" }, ["whisp", "gfw"].map((c) => tarjetaFuente(c, analisis, configurada[c], ctx))),
      analisis.length > 0 &&
        h(
          "details",
          { class: "historial-analisis" },
          h("summary", {}, `Historial de análisis (${analisis.length})`),
          h(
            "div",
            { class: "tbl-box" },
            h(
              "table",
              { class: "tabla" },
              h("thead", {}, h("tr", {}, h("th", {}, "Fuente"), h("th", {}, "Solicitado"), h("th", {}, "Estado"), h("th", {}, "Resultado"))),
              h(
                "tbody",
                {},
                analisis.map((a) =>
                  h(
                    "tr",
                    {},
                    h("td", {}, FUENTES[a.fuente], a.solicitado_por_nombre ? h("span", { class: "sec" }, a.solicitado_por_nombre) : h("span", { class: "sec" }, "Sistema")),
                    h("td", { class: "fecha" }, fecha(a.solicitado_en, { hora: true })),
                    h("td", {}, insignia(...ESTADO_ANALISIS[a.estado]), a.obsoleto && h("span", { class: "sec" }, "obsoleto")),
                    h("td", {}, a.resultado_texto ?? (a.error_detalle ? h("span", { class: "sec" }, a.error_detalle) : "—")),
                  ),
                ),
              ),
            ),
          ),
        ),
    ],
  });
}

// ---------- Visitas de campo ----------

const etiqueta = (lista, valor) => lista.find(([v]) => v === valor)?.[1] ?? valor;

function abrirNuevaVisita(ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-visita" }, "Registrar visita");
  const fotos = h("input", { class: "input", type: "file", name: "fotos", accept: "image/jpeg,image/png", capture: "environment", multiple: true, required: true });
  const formulario = h(
    "form",
    { class: "form", id: "form-visita" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Fecha de la visita", name: "fecha", type: "date", value: hoy(), max: hoy(), required: true }),
      campo({ etiqueta: "Motivo", name: "motivo", opciones: MOTIVOS_VISITA, value: ctx.p.alertas.includes("analisis_requiere_revision") ? "analisis_requiere_revision" : "verificacion_de_coordenadas" }),
    ),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Técnico que fue a campo", name: "realizada_por_nombre", required: true, maxlength: 200 }),
      campo({ etiqueta: "Cargo", name: "realizada_por_cargo", required: true, maxlength: 200 }),
    ),
    campo({ etiqueta: "Uso observado", name: "uso_observado", opciones: USOS_OBSERVADOS }),
    h("label", { class: "check" }, h("input", { type: "checkbox", name: "perimetro_recorrido", value: "si" }), h("span", {}, "El técnico caminó el lindero de la parcela")),
    h(
      "label",
      { class: "field" },
      "Qué se observó (mínimo 30 caracteres)",
      h("textarea", { class: "input texto-libre", name: "descripcion", required: true, minlength: 30, maxlength: 4000, rows: 4 }),
      h("small", {}, "Describe lo que se vio. La visita no declara que la parcela cumple ni que no cumple."),
    ),
    h("label", { class: "field" }, "Fotos de la parcela (JPG o PNG, al menos una)", fotos),
  );
  const { cerrar } = abrirModal({
    titulo: "Registrar visita de campo",
    subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    cuerpo.append(
      "datos",
      JSON.stringify({
        fecha: datos.fecha,
        motivo: datos.motivo,
        realizada_por_nombre: datos.realizada_por_nombre,
        realizada_por_cargo: datos.realizada_por_cargo,
        uso_observado: datos.uso_observado,
        perimetro_recorrido: datos.perimetro_recorrido === "si",
        descripcion: datos.descripcion,
      }),
    );
    for (const foto of fotos.files) cuerpo.append("fotos", foto);
    await llamarApi(`/parcelas/${ctx.p.id}/visitas`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Visita registrada.");
    ctx.recargar();
  });
}

function abrirAnulacion(visita, ctx) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-visita" }, "Anular visita");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-visita" },
    h("p", {}, "La visita no se borra: queda anulada y deja de contar. Si estaba mal, registra otra."),
    campo({ etiqueta: "Motivo", name: "motivo", required: true, maxlength: 200 }),
  );
  const { cerrar } = abrirModal({ titulo: "Anular visita", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/visitas/${visita.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Visita anulada.");
    ctx.recargar();
  });
}

export async function pestanaVisitas(ctx) {
  const { p, base } = ctx;
  const visitas = await llamarApi(`${base}/visitas`);
  const puedo = permisos(ctx);
  const pr = p.procedencia;
  const procedencia =
    pr &&
    h(
      "div",
      { class: `verif ${pr.recorrida_en_campo ? "" : "neutro"}` },
      icono("pin"),
      h(
        "div",
        {},
        h("b", {}, pr.recorrida_en_campo ? `Lindero recorrido en campo el ${fecha(pr.fecha_recorrido)}` : "Lindero sin recorrer en campo"),
        h("span", {}, `Geometría ${pr.origen_geometria === "archivo" ? "de archivo" : "dibujada"} · registrada por ${pr.registrada_por_rol === "productor" ? "el propio productor (coordenada declarada)" : "el personal de la cooperativa"}`),
      ),
    );
  return seccion({
    titulo: "Visitas de campo",
    sub: "Lo que un técnico vio en la parcela. Una visita no se edita: si está mal, se anula y se registra otra.",
    acciones: puedo.registro && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirNuevaVisita(ctx) }, icono("mas"), "Registrar visita"),
    contenido: [
      procedencia,
      visitas.length
        ? h(
            "ol",
            { class: "visitas" },
            visitas.map((v) =>
              h(
                "li",
                { class: `visita ${v.vigente ? "" : "anulada"}` },
                h(
                  "div",
                  { class: "visita-h" },
                  h("b", {}, fecha(v.fecha)),
                  h(
                    "span",
                    { class: "fila-acciones" },
                    insignia("", etiqueta(MOTIVOS_VISITA, v.motivo)),
                    insignia("info", etiqueta(USOS_OBSERVADOS, v.uso_observado)),
                    v.perimetro_recorrido && insignia("ok", "Lindero recorrido"),
                    !v.vigente && insignia("bad", "Anulada"),
                  ),
                ),
                h("p", {}, v.descripcion),
                h("p", { class: "sec" }, `${v.realizada_por_nombre} · ${v.realizada_por_cargo}${v.registrada_por_nombre ? ` · ingresada por ${v.registrada_por_nombre}` : ""}`),
                !v.vigente && v.motivo_anulacion && h("p", { class: "sec" }, `Motivo de la anulación: ${v.motivo_anulacion}`),
                h(
                  "div",
                  { class: "fila-acciones" },
                  v.fotos.map((f, i) => h("button", { class: "btn btn-sm", type: "button", onclick: () => verDocumento(f) }, icono("eye"), `Foto ${i + 1}`)),
                  puedo.admin && v.vigente && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirAnulacion(v, ctx) }, "Anular"),
                ),
              ),
            ),
          )
        : vacio({ titulo: "Sin visitas", texto: "Cuando un técnico vaya a la parcela, registra aquí lo que vio, con fotos." }),
    ],
  });
}

// ---------- Expediente legal ----------

function abrirCargaLegal(casilla, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-legal" }, "Cargar documento");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const formulario = h(
    "form",
    { class: "form", id: "form-legal" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Número (partida, constancia o contrato)", name: "numero", required: true, maxlength: 200 }),
      campo({ etiqueta: "Entidad emisora", name: "entidad_emisora", required: true, maxlength: 200 }),
    ),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Fecha de emisión", name: "fecha_emision", type: "date", max: hoy(), required: true }),
      campo({ etiqueta: "Fecha de vencimiento (si tiene)", name: "fecha_vencimiento", type: "date" }),
    ),
    h("label", { class: "field" }, "Archivo (foto o PDF, hasta 10 MB)", archivo),
  );
  const { cerrar } = abrirModal({ titulo: `Cargar: ${casilla.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    cuerpo.append("tipo", casilla.codigo);
    for (const clave of ["numero", "entidad_emisora", "fecha_emision", "fecha_vencimiento"]) if (datos[clave]) cuerpo.append(clave, datos[clave]);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi(`${ctx.base}/documentos`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Documento cargado.");
    ctx.recargar();
  });
}

function abrirCotejo(documento, casilla, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-cotejo" }, "Registrar cotejo");
  const formulario = h(
    "form",
    { class: "form", id: "form-cotejo" },
    h("p", {}, `Cotejar es comprobar el documento en el registro público de quien lo emitió. Queda constancia de quién lo hizo y cuándo.`),
    h("label", { class: "field" }, "Qué consultaste y qué encontraste", h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 10, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: `Cotejar: ${casilla.nombre}`, subtitulo: `N.º ${documento.numero ?? "—"} · ${documento.entidad_emisora ?? ""}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/documentos/${documento.id}/cotejo`, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Cotejo registrado.");
    ctx.recargar();
  });
}

function abrirExencion(casilla, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-exencion" }, "Declarar que no aplica");
  const formulario = h(
    "form",
    { class: "form", id: "form-exencion" },
    h("p", {}, "La exención declara que este documento no aplica a la parcela. Aparecerá, con su motivo, en el informe de hallazgos."),
    h("label", { class: "field" }, "Por qué no aplica (mínimo 30 caracteres)", h("textarea", { class: "input texto-libre", name: "motivo", required: true, minlength: 30, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: `No aplica: ${casilla.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/parcelas/${ctx.p.id}/exenciones`, { metodo: "POST", cuerpo: { tipo: casilla.codigo, motivo } });
    cerrar();
    toast("Exención declarada.");
    ctx.recargar();
  });
}

function filaCasilla(c, ctx, puedo, tenenciaCubierta) {
  // La tenencia se cumple con el título o con la constancia: la otra no falta.
  const [clase, texto] = c.tenencia && c.estado === "faltante" && tenenciaCubierta ? ["", "No necesaria"] : ESTADOS_CASILLA[c.estado];
  const vigentes = c.documentos.filter((d) => d.vigente);
  const exencion = c.exencion && !c.exencion.retirada_en ? c.exencion : null;
  return h(
    "li",
    { class: "casilla" },
    h(
      "div",
      { class: "casilla-h" },
      h("div", {}, h("b", {}, c.nombre), h("span", { class: "sec" }, `${c.grupo}${c.registro_consultable ? " · con registro público" : " · sin registro público consultable"}`)),
      h("span", { class: "fila-acciones" }, insignia(clase, texto), c.nivel && insigniaNivel(c.nivel), c.vence_en && h("span", { class: "badge" }, `vence ${fecha(c.vence_en)}`)),
    ),
    vigentes.map((d) =>
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, `N.º ${d.numero ?? "—"} · ${d.entidad_emisora ?? "—"} · emitido ${fecha(d.fecha_emision)}${d.fecha_vencimiento ? ` · vence ${fecha(d.fecha_vencimiento)}` : ""}`),
        d.cotejado_en && h("span", { class: "sec" }, `Cotejado el ${fecha(d.cotejado_en)}: ${d.cotejo_nota}`),
        h(
          "span",
          { class: "fila-acciones" },
          h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
          puedo.registro && c.registro_consultable && !d.cotejado_en && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCotejo(d, c, ctx) }, "Cotejar en fuente"),
        ),
      ),
    ),
    exencion &&
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, `No aplica: ${exencion.motivo}`),
        h("span", { class: "sec" }, `Declarada el ${fecha(exencion.declarada_en)}${exencion.declarada_por_nombre ? ` por ${exencion.declarada_por_nombre}` : ""}`),
        puedo.admin &&
          h(
            "button",
            {
              class: "btn btn-sm btn-ghost",
              type: "button",
              onclick: async () => {
                try {
                  await llamarApi(`/exenciones/${exencion.id}/retirar`, { metodo: "POST" });
                  toast("Exención retirada.");
                  ctx.recargar();
                } catch (error) {
                  toast(error.message, "bad");
                }
              },
            },
            "Retirar exención",
          ),
      ),
    h(
      "div",
      { class: "fila-acciones" },
      puedo.cargaDocumentos && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCargaLegal(c, ctx) }, icono("upload"), vigentes.length ? "Cargar otro" : "Cargar documento"),
      puedo.admin && c.admite_exencion && !exencion && !vigentes.length && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirExencion(c, ctx) }, "Declarar que no aplica"),
    ),
  );
}

export async function pestanaExpediente(ctx) {
  const exp = await llamarApi(`${ctx.base}/expediente`);
  const puedo = permisos(ctx);
  const nombres = Object.fromEntries(exp.casillas.map((c) => [c.codigo, c.nombre]));
  return seccion({
    titulo: "Expediente legal",
    sub: "La tenencia exige el título o la constancia de posesión. Las otras cinco casillas se cubren con un documento o con una exención motivada.",
    acciones: insignia(exp.estado === "completo" ? "ok" : "warn", exp.estado === "completo" ? "Completo" : "Incompleto"),
    contenido: [
      exp.faltan.length > 0 && h("p", { class: "alerta warn" }, `Falta: ${exp.faltan.map((c) => (c === "tenencia" ? "tenencia (título o constancia de posesión)" : nombres[c])).join(", ")}.`),
      exp.tenencia_solo_posesion && h("p", { class: "alerta info" }, "La tenencia se apoya solo en una constancia de posesión, que no tiene registro público contra el cual cotejarse."),
      h("ul", { class: "casillas" }, exp.casillas.map((c) => filaCasilla(c, ctx, puedo, !exp.faltan.includes("tenencia")))),
    ],
  });
}

// ---------- Habilitación ----------

function abrirHabilitar(hab, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-habilitar" }, "Habilitar parcela");
  const formulario = h(
    "form",
    { class: "form", id: "form-habilitar" },
    h("p", {}, "Habilitar no declara que la parcela cumple el Reglamento: es la decisión de la cooperativa de aceptar cacao de ella, con las evidencias a la vista."),
    hab.alertas.length > 0 && h("div", { class: "fila-acciones" }, hab.alertas.map((a) => insigniaAlerta(a))),
    h(
      "label",
      { class: "field" },
      hab.nota_obligatoria ? "Nota (obligatoria, mínimo 50 caracteres): por qué se habilita a pesar de las alertas" : "Nota (opcional)",
      h("textarea", { class: "input texto-libre", name: "nota", required: hab.nota_obligatoria, minlength: hab.nota_obligatoria ? 50 : 0, maxlength: 4000, rows: 4 }),
    ),
  );
  const { cerrar } = abrirModal({ titulo: "Habilitar parcela", subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/parcelas/${ctx.p.id}/habilitar`, { metodo: "POST", cuerpo: { nota: nota || null } });
    cerrar();
    toast("Parcela habilitada.");
    ctx.recargar();
  });
}

async function abrirExcluir(ctx) {
  const [visitas, analisis] = await Promise.all([llamarApi(`${ctx.base}/visitas`), llamarApi(`${ctx.base}/analisis`)]);
  const evidencias = [
    ["", "Elige la evidencia…"],
    ...visitas.filter((v) => v.vigente).map((v) => [`visita:${v.id}`, `Visita del ${fecha(v.fecha)} · ${v.realizada_por_nombre}`]),
    ...analisis.filter((a) => a.estado === "completado").map((a) => [`analisis:${a.id}`, `${FUENTES[a.fuente]} del ${fecha(a.completado_en)} · ${a.resultado_texto ?? "sin resultado"}`]),
  ];
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-excluir" }, "Excluir definitivamente");
  const formulario = h(
    "form",
    { class: "form", id: "form-excluir" },
    h("p", { class: "alerta bad" }, "La exclusión es definitiva: nadie puede revertirla, tampoco el equipo CacaoTrace. La parcela ya no se edita, no recibe documentos ni respalda tandas nuevas. Su historial sigue visible."),
    h("p", {}, "El único motivo admitido es la deforestación confirmada después del 31 de diciembre de 2020. A una parcela a la que le falta un documento no se la excluye."),
    h("label", { class: "field" }, "Qué se confirmó (mínimo 50 caracteres)", h("textarea", { class: "input texto-libre", name: "descripcion", required: true, minlength: 50, maxlength: 4000, rows: 4 })),
    campo({ etiqueta: "Evidencia de esta parcela", name: "evidencia", opciones: evidencias, required: true }),
    campo({ etiqueta: "Escribe EXCLUIR para confirmar", name: "confirmacion", required: true, autocomplete: "off", pattern: "EXCLUIR" }),
  );
  const { cerrar } = abrirModal({ titulo: "Excluir parcela", subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ descripcion, evidencia, confirmacion }) => {
    const [tipo, id] = evidencia.split(":");
    await llamarApi(`/parcelas/${ctx.p.id}/excluir`, {
      metodo: "POST",
      cuerpo: { descripcion, confirmacion, [tipo === "visita" ? "evidencia_visita_id" : "evidencia_analisis_id"]: id },
    });
    cerrar();
    toast("Parcela excluida.", "warn");
    ctx.recargar();
  });
}

const DECISION = { habilitar: "Habilitó la parcela", observar: "La pasó a observada (sistema)", excluir: "Excluyó la parcela" };

export async function pestanaHabilitacion(ctx) {
  const hab = await llamarApi(`${ctx.base}/habilitacion`);
  const puedo = permisos(ctx);
  const faltan = hab.requisitos.filter((r) => !r.cumple);
  const botonHabilitar =
    puedo.admin &&
    hab.estado !== "habilitada" &&
    h(
      "button",
      {
        class: "btn btn-primary btn-sm",
        type: "button",
        disabled: !hab.puede_habilitar,
        title: hab.puede_habilitar ? "Habilitar la parcela" : `Falta: ${faltan.map((r) => REQUISITOS[r.codigo]).join(", ")}`,
        onclick: () => abrirHabilitar(hab, ctx),
      },
      icono("check"),
      "Habilitar",
    );
  const botonExcluir = puedo.admin && h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirExcluir(ctx) }, "Excluir");
  const lista = ctx.delProductor
    ? faltan.length
      ? h("ul", { class: "lista-simple" }, faltan.map((r) => h("li", {}, REQUISITOS_PRODUCTOR[r.codigo] ?? r.detalle)))
      : h("p", { class: "alerta info" }, hab.estado === "habilitada" ? "Tu parcela está habilitada." : "Tu parcela tiene todo lo necesario; falta que la cooperativa decida.")
    : h(
        "ul",
        { class: "requisitos" },
        hab.requisitos.map((r) =>
          h("li", { class: r.cumple ? "cumple" : "falta" }, h("span", { class: "requisito-marca", "aria-hidden": "true" }, icono(r.cumple ? "check" : "x")), h("div", {}, h("b", {}, REQUISITOS[r.codigo] ?? r.codigo), h("span", { class: "sec" }, r.detalle))),
        ),
      );
  return seccion({
    titulo: "Habilitación",
    sub: ctx.delProductor ? "Lo que le falta a tu parcela para recibir tu cacao." : "Solo un administrador decide. Habilitar o excluir queda registrado con los requisitos y las alertas del momento.",
    acciones: [insigniaHabilitacion(hab.estado), botonHabilitar, botonExcluir],
    contenido: [
      lista,
      !ctx.delProductor && hab.alertas.length > 0 && h("div", { class: "fila-acciones" }, hab.alertas.map((a) => insigniaAlerta(a))),
      hab.decisiones.length > 0 &&
        h(
          "ol",
          { class: "linea-tiempo" },
          hab.decisiones.map((d) =>
            h(
              "li",
              {},
              h("b", {}, DECISION[d.decision] ?? d.decision),
              h("span", { class: "sec" }, [fecha(d.decidida_en, { hora: true }), d.decidida_por_nombre].filter(Boolean).join(" · ")),
              d.nota && h("span", { class: "sec" }, d.nota),
            ),
          ),
        ),
    ],
  });
}

const pedidos = new WeakMap();

/** Contenedor de una pestaña que se carga al abrirla. Solo pinta la respuesta del último pedido. */
export function cargarPestana(contenedor, generador) {
  const turno = (pedidos.get(contenedor) ?? 0) + 1;
  pedidos.set(contenedor, turno);
  const pintar = (nodo) => pedidos.get(contenedor) === turno && reemplazar(contenedor, nodo);
  reemplazar(contenedor, h("div", { class: "sect" }, cargando()));
  generador()
    .then(pintar)
    .catch((error) => pintar(h("div", { class: "sect" }, errorDeCarga(error))));
}
