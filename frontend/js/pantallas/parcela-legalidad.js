// Adenda 4 en el detalle de la parcela: pestaña Legalidad, con tres bloques (Perfil, Requisitos e
// Incidencias). Dice qué requisitos le aplican a la parcela y con qué se sustentan; ningún texto dice que la
// parcela "cumple" la legalidad. Declaran el perfil el administrador y el operador; el productor lo ve y
// descarga sus plantillas para firmar.

import { descargarArchivo, llamarApi } from "../api.js";
import { verDocumento } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { hoyLima as hoy } from "../fechas.js";
import { COLORES, capaArcGIS, capaGeojson, crearMapa, encuadrar, estilo } from "../mapa.js";
import { ESTADOS_REQUISITO, REQUISITOS, insigniaAlerta, insigniaNivel } from "../textos.js";
import { abrirModal, campo, enviarCon, fecha, h, icono, seccion, toast } from "../ui.js";

// Lo que firma el productor o la comunidad no lleva número ni entidad emisora (adenda 4, sección 6).
const SIN_NUMERO = new Set(["declaracion_jurada_tenencia", "constancia_comunal", "acta_comunal"]);
const CLASES_TITULO = [
  ["", "Elige la clase…"],
  ["titulo_formalizacion", "Título de formalización"],
  ["escritura_publica", "Escritura pública"],
  ["minuta", "Minuta"],
];
const TIPOS_INCIDENCIA = [
  ["tenencia", "Tenencia: conflicto, litigio o reclamo sobre la tierra"],
  ["ambiental", "Ambiental: denuncia o daño ambiental"],
  ["otra", "Otra: por ejemplo, un mapa oficial que parece equivocado"],
];
const NOMBRE_INCIDENCIA = { tenencia: "De tenencia", ambiental: "Ambiental", otra: "Otra" };
const NIVEL_ORIENTADOR = { alto: "alto", bajo: "bajo" };
const DILIGENCIA = { aligerada: "aligerada", estandar: "estándar" };
const PLANTILLAS = {
  "declaracion-jurada-tenencia": "Descargar declaración jurada para firmar",
  "constancia-comunal": "Descargar constancia comunal para firmar",
};

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}` }, h("span", { class: "dot" }), texto);
}

function permisos(ctx) {
  const rol = rolEfectivo();
  const activa = ctx.p.estado === "activa" && ctx.p.habilitacion_estado !== "excluida";
  return {
    registro: activa && !ctx.delProductor && ["admin_cooperativa", "operador"].includes(rol),
    admin: activa && !ctx.delProductor && rol === "admin_cooperativa",
    cargaDocumentos: activa && (ctx.delProductor || ["admin_cooperativa", "operador"].includes(rol)),
  };
}

const ha = (valor) => `${Number(valor).toLocaleString("es-PE", { maximumFractionDigits: 2 })} ha`;

/** Lo que encontró el cruce de una variable, en frases cortas. Nunca "no está": no figura en la capa. */
function hallado(codigo, d) {
  if (!d) return [];
  const nombre = (e) => e.nombre ?? "sin nombre en la capa";
  const medida = (e) => (e.area_comun_ha != null ? ` · ${ha(e.area_comun_ha)} en común (${e.porcentaje} %)` : "");
  const lineas = [];
  if (codigo === "en_anp") {
    for (const e of d.areas ?? []) lineas.push(`Dentro de ${nombre(e)}${e.categoria ? ` (${e.categoria})` : ""}${medida(e)}`);
    for (const e of d.zonas_de_amortiguamiento ?? []) lineas.push(`Zona de amortiguamiento de ${nombre(e)}${medida(e)}`);
    for (const e of d.areas_de_conservacion ?? []) lineas.push(`También se superpone con ${nombre(e)} (${e.categoria})${medida(e)}`);
  } else if (codigo === "en_tierra_forestal") {
    for (const e of d.zonas ?? []) lineas.push(`${[e.categoria_nombre, e.subcategoria_nombre].filter(Boolean).join(" · ")}${e.resolucion ? ` (${e.resolucion})` : ""}${medida(e)}`);
    for (const e of d.otras ?? []) lineas.push(`Toca: ${[e.categoria_nombre, e.subcategoria_nombre].filter(Boolean).join(" · ")}`);
    if (d.zonificados && !d.zonas?.length && !d.otras?.length && !d.zonificados.length) lineas.push("La capa no clasifica el departamento de la parcela.");
    for (const e of d.cesiones ?? []) lineas.push(`SERFOR registra aquí el contrato de cesión en uso ${e.contrato ?? "sin número"}${e.situacion ? ` (${e.situacion})` : ""}`);
  } else if (codigo === "en_tierra_comunal") {
    for (const e of d.comunidades ?? []) lineas.push(`Comunidad ${e.tipo} ${nombre(e)}${medida(e)}`);
  } else if (codigo === "junto_a_cuerpo_de_agua") {
    for (const e of d.cuerpos ?? []) lineas.push(`${nombre(e)} (${e.tipo}) a ${Math.round(e.distancia_m)} m del lindero`);
    for (const e of d.fajas_marginales ?? []) lineas.push(`Faja marginal delimitada por la ANA${e.nombre ? `: ${e.nombre}` : ""}`);
  } else if (codigo === "en_patrimonio_cultural") {
    for (const e of d.monumentos ?? []) lineas.push(`${nombre(e)}${e.clase ? ` (${e.clase})` : ""}${medida(e)}`);
  }
  for (const e of d.roces ?? []) lineas.push(`Roce de lindero con ${nombre(e)}${medida(e)}: no cambia la respuesta`);
  return lineas;
}

// ---------- Declarar ----------

function abrirDeclaracion(v, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-perfil" }, "Guardar respuesta");
  const valorActual = v.declarado?.valor ?? v.valor ?? "";
  const control = v.opciones.length
    ? campo({ etiqueta: "Respuesta", name: "valor", required: true, value: valorActual, opciones: [["", "Elige…"], ...v.opciones.map((o) => [o.valor, o.etiqueta])] })
    : campo({ etiqueta: "Año (4 dígitos)", name: "valor", required: true, inputmode: "numeric", pattern: "\\d{4}", maxlength: 4, value: valorActual });
  const detalle = v.declarado?.detalle ?? {};
  const extra =
    v.codigo === "en_tierra_comunal"
      ? [
          campo({ etiqueta: "Nombre de la comunidad", name: "comunidad_nombre", maxlength: 200, value: detalle.comunidad_nombre ?? v.cruce?.detalle?.comunidad_nombre ?? "" }),
          h(
            "div",
            { class: "grid2" },
            campo({ etiqueta: "Tipo", name: "comunidad_tipo", value: detalle.comunidad_tipo ?? v.cruce?.detalle?.comunidad_tipo ?? "", opciones: [["", "—"], ["campesina", "Campesina"], ["nativa", "Nativa"]] }),
            campo({ etiqueta: "¿Inscrita en Registros Públicos?", name: "inscrita", value: detalle.inscrita ?? "", opciones: [["", "—"], ["si", "Sí"], ["no", "No"], ["no_se_sabe", "No se sabe"]] }),
          ),
        ]
      : v.codigo === "en_anp"
        ? [campo({ etiqueta: "Nombre del área (si se sabe)", name: "area_nombre", maxlength: 200, value: detalle.area_nombre ?? "" })]
        : [];
  const formulario = h(
    "form",
    { class: "form", id: "form-perfil" },
    h("p", { class: "panel-sub" }, v.ayuda),
    v.cruce && h("p", { class: "alerta info" }, `El cruce dice «${v.cruce.etiqueta}». Puedes declarar un valor más exigente, con una nota; uno menos exigente no: si el mapa se equivoca, registra una incidencia de tipo «Otra».`),
    control,
    extra,
    v.cruzable && h("label", { class: "field" }, "Nota (obligatoria si declaras algo distinto de lo que dijo el cruce)", h("textarea", { class: "input texto-libre", name: "nota", maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: v.pregunta, subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const extraDatos = Object.fromEntries(["comunidad_nombre", "comunidad_tipo", "inscrita", "area_nombre"].filter((k) => datos[k]).map((k) => [k, datos[k]]));
    await llamarApi(`/parcelas/${ctx.p.id}/perfil`, {
      metodo: "POST",
      cuerpo: { variable: v.codigo, valor: datos.valor, nota: datos.nota || null, detalle: Object.keys(extraDatos).length ? extraDatos : null },
    });
    cerrar();
    toast("Respuesta guardada.");
    ctx.recargar();
  });
}

function filaVariable(v, ctx, puedo) {
  const lineas = hallado(v.codigo, v.cruce?.detalle);
  const sinCruce = v.cruzable && !v.cruce;
  return h(
    "li",
    { class: "casilla" },
    h(
      "div",
      { class: "casilla-h" },
      h("div", {}, h("b", {}, v.pregunta), h("span", { class: "sec" }, v.ayuda)),
      h(
        "span",
        { class: "fila-acciones" },
        v.valor ? insignia(v.valor === "no" ? "" : "info", v.etiqueta) : insignia("", "Falta el dato"),
        v.nivel && insigniaNivel(v.nivel),
      ),
    ),
    v.cruce &&
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, h("b", {}, `Cruce: ${v.cruce.etiqueta}. `), v.cruce.fuente ?? ""),
        lineas.length ? h("ul", { class: "lista-simple" }, lineas.map((l) => h("li", {}, l))) : h("span", { class: "sec" }, "La parcela no figura en la capa consultada."),
        v.cruce.detalle?.aproximacion && h("span", { class: "sec" }, "Aproximación: la parcela es un punto y se cruzó como un círculo con su área declarada."),
      ),
    sinCruce && h("div", { class: "casilla-doc" }, h("span", { class: "sec" }, `Sin respuesta del cruce. Fuente que nombra el orientador: ${v.fuente_orientador}.`)),
    v.declarado &&
      h(
        "div",
        { class: "casilla-doc" },
        h("span", {}, h("b", {}, `Declarado: ${v.declarado.etiqueta}`), ` · ${[v.declarado.registrada_por_nombre, fecha(v.declarado.registrada_en)].filter(Boolean).join(" · ")}`),
        v.declarado.detalle?.comunidad_nombre && h("span", { class: "sec" }, `Comunidad: ${v.declarado.detalle.comunidad_nombre}${v.declarado.detalle.inscrita ? ` · inscrita: ${{ si: "sí", no: "no", no_se_sabe: "no se sabe" }[v.declarado.detalle.inscrita]}` : ""}`),
        v.declarado.detalle?.nota && h("span", { class: "sec" }, `Nota: ${v.declarado.detalle.nota}`),
      ),
    v.declarado_sin_cruce && h("p", { class: "alerta warn" }, "Manda lo declarado por una persona: el informe de hallazgos lo dice."),
    v.aviso && h("p", { class: "alerta warn" }, v.aviso),
    puedo.registro && v.se_pregunta && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirDeclaracion(v, ctx) }, v.declarado || v.cruce ? "Declarar otro valor" : "Responder")),
  );
}

async function mapaDelCruce(ctx, leg) {
  const contenedor = h("div", { class: "mapa mapa-legalidad" });
  const encontrados = leg.perfil.filter((v) => v.cruce).flatMap((v) => hallado(v.codigo, v.cruce.detalle).map((l) => [v.pregunta, l]));
  crearMapa(contenedor, { coordenadas: false })
    .then(({ L, mapa }) => {
      const parcela = capaGeojson(L, ctx.p.geometria, { style: estilo(COLORES.nueva, 0.15) }).addTo(mapa);
      const control = L.control.layers(null, null, { position: "topleft", collapsed: true }).addTo(mapa);
      for (const capa of leg.cruce.capas) {
        const variable = leg.perfil.find((v) => v.codigo === capa.variable);
        const capaMapa = capaArcGIS(L, { servicio: capa.servicio, numeros: capa.numeros, atribucion: capa.entidad });
        control.addOverlay(capaMapa, `${capa.nombre} (${capa.entidad})`);
        // Se encienden las capas en las que la parcela figura.
        if (variable?.cruce && variable.cruce.valor !== "no" && (variable.cruce.detalle?.capas ?? []).includes(capa.codigo)) capaMapa.addTo(mapa);
      }
      encuadrar(mapa, parcela);
    })
    .catch(() => contenedor.replaceChildren(h("p", { class: "alerta bad" }, "No se pudo cargar el mapa.")));
  return h(
    "div",
    { class: "legalidad-mapa" },
    contenedor,
    h(
      "div",
      { class: "legalidad-hallado" },
      h("b", {}, "Lo que encontró el cruce"),
      encontrados.length
        ? h("ul", { class: "lista-simple" }, encontrados.map(([pregunta, linea]) => h("li", {}, linea, h("span", { class: "sec" }, pregunta))))
        : h("p", { class: "sec" }, leg.cruce.capas.some((c) => c.estado === "hecho") ? "La parcela no figura en ninguna de las capas consultadas." : "Todavía no hay resultados del cruce."),
      h("p", { class: "sec" }, "Usa el control de capas del mapa para ver cada capa oficial. El mapa es ayuda visual: las respuestas salen del cruce."),
    ),
  );
}

async function bloquePerfil(leg, ctx, puedo) {
  const cruzables = leg.perfil.filter((v) => v.cruzable);
  const declaradas = leg.perfil.filter((v) => !v.cruzable && v.se_pregunta);
  const fallaron = leg.cruce.capas.filter((c) => c.estado === "fallo");
  const volver =
    puedo.registro &&
    h(
      "button",
      {
        class: "btn btn-sm",
        type: "button",
        onclick: async (e) => {
          e.currentTarget.classList.add("is-loading");
          try {
            await llamarApi(`/parcelas/${ctx.p.id}/cruce`, { metodo: "POST" });
            toast("La parcela volvió a la cola del cruce.");
            ctx.recargarPestana();
          } catch (error) {
            toast(error.message, "bad");
          }
        },
      },
      icono("rotate"),
      "Volver a cruzar",
    );
  return seccion({
    titulo: "Perfil legal",
    sub: "Nueve datos de los que sale qué requisitos aplican. Cinco los responde el cruce con capas oficiales; los otros los declara una persona.",
    acciones: [insignia(leg.perfil_completo ? "ok" : "warn", leg.perfil_completo ? "Completo" : "Incompleto"), volver],
    contenido: [
      leg.cruce.en_cola && h("p", { class: "nota-cola" }, icono("clock"), "La parcela está en la cola del cruce con las capas oficiales. Esta pestaña se actualiza sola."),
      fallaron.length > 0 &&
        h(
          "p",
          { class: "alerta warn" },
          `No respondió: ${fallaron.map((c) => `${c.nombre} (${c.entidad}${c.consultada_en ? `, ${fecha(c.consultada_en)}` : ""})`).join("; ")}. Puedes declarar la respuesta para no detener el trabajo; el sistema vuelve a intentar el cruce.`,
        ),
      leg.cruce.aproximacion && h("p", { class: "alerta info" }, "La parcela es un punto: se cruzó como un círculo con su área declarada, así que las respuestas son una aproximación."),
      await mapaDelCruce(ctx, leg),
      h("h4", { class: "subtitulo-bloque" }, "Lo que responde el cruce con capas oficiales"),
      h("ul", { class: "casillas" }, cruzables.map((v) => filaVariable(v, ctx, puedo))),
      h("h4", { class: "subtitulo-bloque" }, "Lo que declara una persona"),
      h("ul", { class: "casillas" }, declaradas.map((v) => filaVariable(v, ctx, puedo))),
    ],
  });
}

// ---------- Requisitos ----------

function abrirCarga(r, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-legal" }, "Cargar documento");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const tipo = campo({ etiqueta: "Documento", name: "tipo", required: true, value: r.aceptados[0].codigo, opciones: r.aceptados.map((a) => [a.codigo, a.nombre]) });
  const numero = campo({ etiqueta: "Número (partida, constancia o contrato)", name: "numero", maxlength: 200 });
  const entidad = campo({ etiqueta: "Entidad emisora", name: "entidad_emisora", maxlength: 200 });
  const vence = campo({ etiqueta: "Fecha de vencimiento (si tiene)", name: "fecha_vencimiento", type: "date" });
  const clase = campo({ etiqueta: "Clase del título", name: "clase", opciones: CLASES_TITULO });
  const nota = h("p", { class: "sec" });
  const ajustar = () => {
    const codigo = tipo.querySelector("select").value;
    const sinNumero = SIN_NUMERO.has(codigo);
    for (const [c, mostrar] of [
      [numero, !sinNumero],
      [entidad, !sinNumero],
      [vence, codigo !== "declaracion_jurada_tenencia"],
      [clase, codigo === "titulo_no_inscrito"],
    ]) {
      c.hidden = !mostrar;
      for (const input of c.querySelectorAll("input, select")) input.required = mostrar && (c === numero || c === entidad || c === clase);
    }
    nota.textContent =
      codigo === "declaracion_jurada_tenencia"
        ? "La fecha de emisión es la de la firma. El sistema le pone su vencimiento: 12 meses, salvo que la configuración diga otro plazo."
        : sinNumero
          ? "La fecha de emisión es la de la firma."
          : "";
  };
  tipo.querySelector("select").addEventListener("change", ajustar);
  const formulario = h(
    "form",
    { class: "form", id: "form-legal" },
    tipo,
    h("div", { class: "grid2" }, numero, entidad),
    clase,
    h("div", { class: "grid2" }, campo({ etiqueta: "Fecha de emisión o de firma", name: "fecha_emision", type: "date", max: hoy(), required: true }), vence),
    nota,
    h("label", { class: "field" }, "Archivo (foto o PDF, hasta 10 MB)", archivo),
  );
  ajustar();
  const { cerrar } = abrirModal({ titulo: `Cargar: ${r.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = new FormData();
    for (const clave of ["tipo", "numero", "entidad_emisora", "fecha_emision", "fecha_vencimiento", "clase"]) if (datos[clave]) cuerpo.append(clave, datos[clave]);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi(`${ctx.base}/documentos`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Documento cargado.");
    ctx.recargar();
  });
}

function abrirNota(r, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-nota" }, "Guardar nota");
  const ayuda =
    r.codigo === "faja_marginal"
      ? "Escribe a qué distancia del río, quebrada o laguna está el cultivo y cómo es la orilla."
      : "Escribe cómo se respeta el sitio arqueológico o de patrimonio cultural.";
  const formulario = h(
    "form",
    { class: "form", id: "form-nota" },
    h("p", {}, ayuda),
    h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 10, maxlength: 4000, rows: 4 }, r.nota ?? ""),
  );
  const { cerrar } = abrirModal({ titulo: r.nombre, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/parcelas/${ctx.p.id}/requisitos/${r.codigo}/nota`, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Nota guardada.");
    ctx.recargar();
  });
}

function abrirCotejo(documento, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-cotejo" }, "Registrar cotejo");
  const formulario = h(
    "form",
    { class: "form", id: "form-cotejo" },
    h("p", {}, "Cotejar es comprobar el documento en el registro público de quien lo emitió. Queda constancia de quién lo hizo y cuándo."),
    h("label", { class: "field" }, "Qué consultaste y qué encontraste", h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 10, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Cotejar en fuente", subtitulo: `N.º ${documento.numero ?? "—"} · ${documento.entidad_emisora ?? ""}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/documentos/${documento.id}/cotejo`, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Cotejo registrado.");
    ctx.recargar();
  });
}

async function bajarPlantilla(nombre, ctx) {
  try {
    await descargarArchivo(`${ctx.base}/plantillas/${nombre}`, `${nombre}-${ctx.p.codigo}.pdf`);
  } catch (error) {
    toast(error.message, "bad");
  }
}

function lineaDocumento(d, ctx, puedo, consultables) {
  return h(
    "div",
    { class: "casilla-doc" },
    h(
      "span",
      {},
      h("b", {}, d.nombre_tipo ?? ""),
      `${d.numero ? `N.º ${d.numero} · ` : ""}${d.entidad_emisora ? `${d.entidad_emisora} · ` : ""}emitido ${fecha(d.fecha_emision)}${d.fecha_vencimiento ? ` · vence ${fecha(d.fecha_vencimiento)}` : ""}`,
    ),
    d.cotejado_en && h("span", { class: "sec" }, `Cotejado el ${fecha(d.cotejado_en)}: ${d.cotejo_nota}`),
    h(
      "span",
      { class: "fila-acciones" },
      h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"),
      puedo.registro && consultables.has(d.tipo) && !d.cotejado_en && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCotejo(d, ctx) }, "Cotejar en fuente"),
    ),
  );
}

function filaRequisito(r, ctx, puedo) {
  const [clase, texto] = ESTADOS_REQUISITO[r.estado] ?? ["", r.estado];
  const nombres = Object.fromEntries(r.aceptados.map((a) => [a.codigo, a.nombre]));
  const consultables = new Set(["titulo_sunarp", "cusaf"]);
  const conNombre = (d) => ({ ...d, nombre_tipo: nombres[d.tipo] ?? d.tipo });
  const otros = r.documentos.filter((d) => d.vigente && d.id !== r.sustento?.id);
  const aplica = !["no_aplica", "sin_dato"].includes(r.estado);
  return h(
    "li",
    { class: `casilla requisito-legal estado-${r.estado}` },
    h(
      "div",
      { class: "casilla-h" },
      h(
        "div",
        {},
        h("b", {}, r.nombre),
        h("span", { class: "sec" }, `Orientador, ref. ${r.referencias.join(" y ")} · implementación ${NIVEL_ORIENTADOR[r.nivel_orientador]} · diligencia ${DILIGENCIA[r.diligencia]}${r.bloquea ? " · sin sustento impide habilitar" : " · no impide habilitar"}`),
      ),
      h("span", { class: "fila-acciones" }, insignia(clase, texto), r.sustento_nivel && insigniaNivel(r.sustento_nivel)),
    ),
    h("p", { class: "requisito-motivo" }, r.motivo),
    h("details", { class: "que-pide" }, h("summary", {}, "Qué pide el orientador"), h("p", {}, r.que_pide)),
    r.por_excepcion && h("p", { class: "alerta info" }, "Se sustenta por la excepción de la Ley N.º 31973: un título o una constancia anteriores a la ley, o el saneamiento de la Ley N.º 31145. Se pregunta si la parcela mantiene 30 % de bosque."),
    r.sustento && lineaDocumento(conNombre(r.sustento), ctx, puedo, consultables),
    r.nota && h("div", { class: "casilla-doc" }, h("span", {}, h("b", {}, "Nota: "), r.nota)),
    r.registro_oficial.length > 0 &&
      h(
        "p",
        { class: "alerta info" },
        `SERFOR registra aquí: ${r.registro_oficial
          .map((x) => (x.tipo === "cesion_en_uso" ? `contrato de cesión en uso ${x.contrato ?? "sin número"}${x.situacion ? ` (${x.situacion})` : ""}` : `autorización de cambio de uso ${x.autorizacion ?? "sin número"}`))
          .join("; ")}. Compáralo con el documento cargado: no lo reemplaza.`,
      ),
    otros.length > 0 && h("details", {}, h("summary", { class: "sec" }, `Otros documentos cargados (${otros.length})`), otros.map((d) => lineaDocumento(conNombre(d), ctx, puedo, consultables))),
    h(
      "div",
      { class: "fila-acciones" },
      aplica && puedo.cargaDocumentos && r.aceptados.length > 0 && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCarga(r, ctx) }, icono("upload"), r.sustento ? "Cargar otro" : "Cargar documento"),
      aplica && puedo.registro && r.pide_nota && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirNota(r, ctx) }, r.nota ? "Cambiar la nota" : "Registrar nota"),
      r.plantilla && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => bajarPlantilla(r.plantilla, ctx) }, icono("download"), PLANTILLAS[r.plantilla]),
    ),
  );
}

function bloqueRequisitos(leg, ctx, puedo) {
  const aplican = leg.requisitos.filter((r) => r.estado !== "no_aplica");
  const noAplican = leg.requisitos.filter((r) => r.estado === "no_aplica");
  return seccion({
    titulo: "Requisitos",
    sub: "Cada requisito aplica según el perfil. Dice por qué aplica, qué pide el orientador, con qué se sustenta y qué sigue.",
    contenido: [
      h("ul", { class: "casillas" }, aplican.map((r) => filaRequisito(r, ctx, puedo))),
      noAplican.length > 0 &&
        h(
          "details",
          { class: "no-aplican" },
          h("summary", {}, `No aplican (${noAplican.length})`),
          h("ul", { class: "casillas" }, noAplican.map((r) => filaRequisito(r, ctx, puedo))),
        ),
    ],
  });
}

// ---------- Incidencias ----------

function abrirIncidencia(ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-incidencia" }, "Registrar incidencia");
  const formulario = h(
    "form",
    { class: "form", id: "form-incidencia" },
    h("p", {}, "Registra lo que la organización encontró: un conflicto, un litigio o una denuncia. Una incidencia de tenencia abierta impide habilitar la parcela."),
    campo({ etiqueta: "Tipo", name: "tipo", required: true, opciones: TIPOS_INCIDENCIA }),
    h("label", { class: "field" }, "Qué se encontró (mínimo 50 caracteres)", h("textarea", { class: "input texto-libre", name: "descripcion", required: true, minlength: 50, maxlength: 4000, rows: 4 })),
    campo({ etiqueta: "De dónde salió", name: "fuente", required: true, minlength: 3, maxlength: 400, placeholder: "Autoridad local, Defensoría del Pueblo, OEFA, prensa, vecino…" }),
  );
  const { cerrar } = abrirModal({ titulo: "Registrar incidencia", subtitulo: `${ctx.p.codigo} · ${ctx.p.nombre}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi(`/parcelas/${ctx.p.id}/incidencias`, { metodo: "POST", cuerpo: datos });
    cerrar();
    toast("Incidencia registrada.");
    ctx.recargar();
  });
}

function abrirCierre(incidencia, ctx) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-cierre" }, "Cerrar incidencia");
  const formulario = h(
    "form",
    { class: "form", id: "form-cierre" },
    h("p", {}, incidencia.descripcion),
    h("label", { class: "field" }, "Cómo se resolvió", h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 10, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Cerrar incidencia", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/incidencias/${incidencia.id}/cerrar`, { metodo: "POST", cuerpo: { nota } });
    cerrar();
    toast("Incidencia cerrada.");
    ctx.recargar();
  });
}

function bloqueIncidencias(leg, ctx, puedo) {
  return seccion({
    titulo: "Incidencias",
    sub: "Conflictos, litigios o denuncias que la organización encontró. No se borran: se cierran con una nota.",
    acciones: puedo.registro && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirIncidencia(ctx) }, icono("plus"), "Registrar incidencia"),
    contenido: leg.incidencias.length
      ? h(
          "ul",
          { class: "casillas" },
          leg.incidencias.map((i) =>
            h(
              "li",
              { class: "casilla" },
              h(
                "div",
                { class: "casilla-h" },
                h("div", {}, h("b", {}, NOMBRE_INCIDENCIA[i.tipo]), h("span", { class: "sec" }, `Fuente: ${i.fuente} · ${[i.registrada_por_nombre, fecha(i.registrada_en)].filter(Boolean).join(" · ")}`)),
                insignia(i.estado === "abierta" ? (i.tipo === "tenencia" ? "bad" : "warn") : "", i.estado === "abierta" ? "Abierta" : "Cerrada"),
              ),
              h("p", {}, i.descripcion),
              i.estado === "cerrada" && h("div", { class: "casilla-doc" }, h("span", {}, h("b", {}, "Cierre: "), i.cierre_nota), h("span", { class: "sec" }, [i.cerrada_por_nombre, fecha(i.cerrada_en)].filter(Boolean).join(" · "))),
              puedo.admin && i.estado === "abierta" && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCierre(i, ctx) }, "Cerrar incidencia")),
            ),
          ),
        )
      : h("p", { class: "panel-sub" }, "Sin incidencias registradas."),
  });
}

// ---------- Pestaña ----------

function resumen(leg, ctx) {
  return h(
    "div",
    { class: "sect legalidad-resumen" },
    h(
      "ul",
      { class: "requisitos" },
      leg.compuerta.map((r) =>
        h("li", { class: r.cumple ? "cumple" : "falta" }, h("span", { class: "requisito-marca", "aria-hidden": "true" }, icono(r.cumple ? "check" : "x")), h("div", {}, h("b", {}, REQUISITOS[r.codigo] ?? r.codigo), h("span", { class: "sec" }, r.detalle))),
      ),
    ),
    !ctx.delProductor && leg.alertas.length > 0 && h("div", { class: "fila-acciones" }, leg.alertas.map((a) => insigniaAlerta(a))),
    h("p", { class: "sec" }, `Marco: ${leg.orientador}. El propio documento dice que no es jurídicamente vinculante ni asesoría legal.`),
  );
}

function historial(leg) {
  if (!leg.documentos_anteriores.length && !leg.exenciones.length) return null;
  return h(
    "details",
    { class: "sect historial-analisis" },
    h("summary", {}, "Documentos y exenciones anteriores a la adenda 4"),
    h("p", { class: "panel-sub" }, "Se conservan como historial: no sustentan ningún requisito."),
    leg.documentos_anteriores.map((d) => h("div", { class: "casilla-doc" }, h("span", {}, `${d.nombre_original} · N.º ${d.numero ?? "—"} · emitido ${fecha(d.fecha_emision)}`), h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => verDocumento(d) }, icono("eye"), "Ver"))),
    leg.exenciones.map((e) => h("div", { class: "casilla-doc" }, h("span", {}, `Exención (${e.tipo}): ${e.motivo}`), h("span", { class: "sec" }, `${fecha(e.declarada_en)}${e.retirada_en ? ` · retirada el ${fecha(e.retirada_en)}` : ""}`))),
  );
}

export async function pestanaLegalidad(ctx) {
  const leg = await llamarApi(`${ctx.base}/legalidad`);
  const puedo = permisos(ctx);
  // Mientras el cruce está en la cola, la pestaña se refresca sola.
  if (leg.cruce.en_cola) {
    setTimeout(() => ctx.contenedor.isConnected && ctx.pestanaActual() === "legalidad" && ctx.recargarPestana(), 8000);
  }
  return h("div", { class: "legalidad" }, resumen(leg, ctx), await bloquePerfil(leg, ctx, puedo), bloqueRequisitos(leg, ctx, puedo), bloqueIncidencias(leg, ctx, puedo), historial(leg));
}
