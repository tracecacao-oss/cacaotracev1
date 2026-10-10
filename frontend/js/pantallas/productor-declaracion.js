// Adenda 5 en la ficha del productor: pestaña Declaración, con el estado arriba y tres bloques (Respuestas,
// Requisitos y Papeles). Registran en nombre del productor, cargan la hoja firmada y los papeles, y revisan
// los productos el administrador y el operador; la nota de seguimiento la escribe solo el administrador.

import { descargarArchivo, llamarApi } from "../api.js";
import {
  DILIGENCIA,
  ESTADO_DECLARACION,
  ESTADO_REQUISITO_PRODUCTOR,
  NIVEL_ORIENTADOR,
  ayudaPregunta,
  casillasPapeles,
  contextoDe,
  controlPregunta,
  cuestionario,
  filasRespuestas,
  insignia,
  leerControl,
  mostradas,
} from "../declaracion.js";
import { listaDocumentos } from "../documentos.js";
import { rolEfectivo } from "../estado.js";
import { hoyLima } from "../fechas.js";
import { insigniaNivel } from "../textos.js";
import { abrirModal, campo, claseTono, enviarCon, fecha, h, icono, leyendaTonos, ordenarPorTono, rejilla, seccion, toast } from "../ui.js";

const kilos = (valor) => `${Number(valor ?? 0).toLocaleString("es-PE", { maximumFractionDigits: 2 })} kg`;
const ha = (valor) => `${Number(valor ?? 0).toLocaleString("es-PE", { maximumFractionDigits: 2 })} ha`;

function permisos() {
  const rol = rolEfectivo();
  return { registro: ["admin_cooperativa", "operador"].includes(rol), admin: rol === "admin_cooperativa" };
}

// ---------- Registrar la declaración ----------

function abrirRegistro(p, d, cuest, alGuardar) {
  const contexto = contextoDe(cuest, d.calculados);
  const anteriores = Object.fromEntries((d.vigente ?? d.por_firmar)?.respuestas.map((r) => [r.codigo, r.valor]) ?? []);
  const controles = new Map();
  const filas = new Map();
  for (const pregunta of cuest.preguntas) {
    const control = controlPregunta(pregunta, anteriores[pregunta.codigo], { cuest, sugerencias: d.sugerencias_productos });
    controles.set(pregunta.codigo, control);
    filas.set(
      pregunta.codigo,
      h(
        "div",
        { class: "field pregunta-declaracion" },
        h("span", { class: "pregunta-texto" }, pregunta.texto_personal),
        control,
        h("small", {}, ayudaPregunta(pregunta, cuest, d.calculados, { personal: true })),
      ),
    );
  }
  const leer = () => Object.fromEntries(cuest.preguntas.map((x) => [x.codigo, leerControl(x, controles.get(x.codigo))]));
  const actualizar = () => {
    const visibles = new Set(mostradas(cuest, leer(), contexto).map((x) => x.codigo));
    for (const [codigo, fila] of filas) {
      fila.hidden = !visibles.has(codigo);
      for (const control of fila.querySelectorAll("input, select")) control.disabled = fila.hidden;
    }
  };
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-declaracion" }, "Guardar declaración");
  const formulario = h(
    "form",
    { class: "form", id: "form-declaracion" },
    h(
      "div",
      { class: "alerta info" },
      `Lo que el sistema ya sabe: ${d.calculados.parcelas_activas} ${d.calculados.parcelas_activas === 1 ? "parcela activa" : "parcelas activas"} que suman ${ha(d.calculados.area_total_ha)}`,
      d.calculados.area_total_ha >= cuest.area_agricultura_familiar_ha ? " (5 ha o más)" : " (menos de 5 ha: se presume agricultura familiar)",
      `; ${d.calculados.tiene_ruc ? "tiene RUC en su ficha" : "no tiene RUC en su ficha"}; ${kilos(d.calculados.kilos_12_meses)} entregados en los últimos 12 meses.`,
    ),
    [...filas.values()],
    h("p", { class: "panel-sub" }, "Al guardar, la declaración queda por firmar: vale desde que se carga la hoja firmada por el productor."),
  );
  formulario.addEventListener("change", actualizar);
  formulario.addEventListener("input", actualizar);
  actualizar();
  const { cerrar } = abrirModal({
    titulo: "Registrar declaración anual",
    subtitulo: `${p.nombres} ${p.apellidos}`,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async () => {
    const todas = leer();
    const respuestas = Object.fromEntries(mostradas(cuest, todas, contexto).map((x) => [x.codigo, todas[x.codigo]]));
    const nueva = await llamarApi(`/productores/${p.id}/declaraciones`, { metodo: "POST", cuerpo: { respuestas } });
    cerrar();
    toast("Declaración registrada. Falta la hoja firmada.");
    await alGuardar();
    ofrecerHoja(p, nueva.por_firmar, alGuardar);
  });
}

function ofrecerHoja(p, porFirmar, alGuardar) {
  if (!porFirmar) return;
  const { cerrar } = abrirModal({
    titulo: "Hoja para firmar",
    subtitulo: `${p.nombres} ${p.apellidos}`,
    contenido: h(
      "div",
      { class: "form" },
      h("p", {}, "Descarga la hoja, imprímela y que el productor la firme y ponga su huella. Luego carga la foto o el escaneo con la fecha de firma."),
      h("div", { class: "fila-acciones" }, botonHoja(p, porFirmar, "Descargar hoja para firmar"), h("button", { class: "btn btn-sm", type: "button", onclick: () => (cerrar(), abrirHojaFirmada(p, porFirmar, alGuardar)) }, icono("upload"), "Cargar hoja firmada")),
    ),
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cerrar")],
  });
}

function botonHoja(p, declaracion, texto) {
  return h(
    "button",
    {
      class: "btn btn-sm",
      type: "button",
      onclick: async (e) => {
        const b = e.currentTarget;
        b.classList.add("is-loading");
        try {
          await descargarArchivo(`/productores/${p.id}/declaraciones/${declaracion.id}/hoja`, `declaracion-anual-${p.dni}.pdf`);
        } catch (error) {
          toast(error.message, "bad");
        } finally {
          b.classList.remove("is-loading");
        }
      },
    },
    icono("download"),
    texto,
  );
}

function abrirHojaFirmada(p, declaracion, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-hoja" }, "Cargar hoja firmada");
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf", required: true });
  const registrada = declaracion.registrada_en.slice(0, 10);
  const formulario = h(
    "form",
    { class: "form", id: "form-hoja" },
    h("p", {}, "La declaración vale desde que se carga la hoja firmada, por 12 meses desde la fecha de firma."),
    campo({ etiqueta: "Fecha de firma", name: "fecha_firma", type: "date", min: registrada, max: hoyLima(), value: hoyLima(), required: true, ayuda: "No puede ser futura ni anterior al día en que se registraron las respuestas." }),
    h("label", { class: "field" }, "Foto o escaneo de la hoja firmada (PDF o imagen, hasta 10 MB)", archivo),
  );
  const { cerrar } = abrirModal({ titulo: "Cargar hoja firmada", subtitulo: `${p.nombres} ${p.apellidos}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ fecha_firma }) => {
    const cuerpo = new FormData();
    cuerpo.append("fecha_firma", fecha_firma);
    cuerpo.append("archivo", archivo.files[0]);
    await llamarApi(`/productores/${p.id}/declaraciones/${declaracion.id}/hoja-firmada`, { metodo: "POST", formulario: cuerpo });
    cerrar();
    toast("Hoja firmada cargada: la declaración está vigente.");
    alGuardar();
  });
}

// ---------- Productos y seguimiento ----------

function textoRevision(x) {
  if (x.revision === "sin_revisar") return "Sin revisar en el registro de SENASA";
  const base = `${x.revision === "figura" ? "Figura" : "No figura"} en el registro de SENASA consultado el ${fecha(x.revisado_en)}`;
  return `${base}${x.registro ? ` (registro ${x.registro})` : ""}${x.revisado_por_nombre ? ` · ${x.revisado_por_nombre}` : ""}${x.copiada ? " · revisión copiada de otra declaración de la organización" : ""}`;
}

function revisar(p, declaracion, producto, revision, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-revision" }, revision === "figura" ? "Marcar: figura" : "Marcar: no figura");
  const formulario = h(
    "form",
    { class: "form", id: "form-revision" },
    h("p", {}, revision === "figura" ? `Buscaste «${producto.nombre}» en la consulta de SENASA y figura en el registro.` : `Buscaste «${producto.nombre}» en la consulta de SENASA y no figura en el registro.`),
    revision === "figura" && campo({ etiqueta: "Número de registro que muestra SENASA (opcional)", name: "registro", maxlength: 60, value: producto.registro ?? "" }),
  );
  const { cerrar } = abrirModal({ titulo: "Revisión en SENASA", subtitulo: producto.nombre, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    await llamarApi(`/productores/${p.id}/declaraciones/${declaracion.id}/productos/${producto.id}`, {
      metodo: "PATCH",
      cuerpo: { revision, registro: datos.registro || null },
    });
    cerrar();
    toast("Revisión guardada.");
    alGuardar();
  });
}

function abrirSeguimiento(p, declaracion, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-seguimiento" }, "Guardar nota");
  const texto = h("textarea", { class: "input texto-libre", name: "nota", required: true, minlength: 50, maxlength: 2000, rows: 5 });
  texto.value = declaracion.seguimiento?.nota ?? "";
  const formulario = h(
    "form",
    { class: "form", id: "form-seguimiento" },
    h("p", {}, "Qué hizo la organización ante lo declarado: informar al productor, capacitarlo o visitarlo. La nota aparece como explicación de sus hallazgos en el DEX; el productor no la ve."),
    h("label", { class: "field" }, "Nota (50 caracteres como mínimo)", texto),
  );
  const { cerrar } = abrirModal({ titulo: "Nota de seguimiento", subtitulo: `${p.nombres} ${p.apellidos}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ nota }) => {
    await llamarApi(`/productores/${p.id}/declaraciones/${declaracion.id}/seguimiento`, { metodo: "PUT", cuerpo: { nota } });
    cerrar();
    toast("Nota de seguimiento guardada.");
    alGuardar();
  });
}

// ---------- Bloques ----------

function estadoArriba(p, d, puedo, cuest, recargar) {
  const vigente = d.vigente;
  const textos = {
    sin_declaracion: "Sin declaración anual. Sus parcelas no se pueden habilitar hasta que tenga una vigente.",
    por_firmar: `Registrada el ${fecha(d.por_firmar?.registrada_en)}${d.por_firmar?.registrada_por_nombre ? ` por ${d.por_firmar.registrada_por_nombre}` : ""}. Falta cargar la hoja firmada.`,
    vigente: `Vigente hasta el ${fecha(vigente?.vigente_hasta)}.`,
    por_vencer: `Vence el ${fecha(vigente?.vigente_hasta)}: conviene registrar la siguiente.`,
    vencida: `Venció el ${fecha(vigente?.vigente_hasta)}. Sus parcelas habilitadas pasaron a observadas.`,
  };
  const valida = ["vigente", "por_vencer"].includes(d.estado);
  return seccion({
    titulo: "Declaración anual",
    sub: "Una vez al año, sobre el trabajo en sus parcelas, los agroquímicos y sus ventas. Ninguna respuesta impide habilitar; sin una declaración vigente, sí.",
    acciones: [
      insignia(ESTADO_DECLARACION[d.estado]),
      puedo.registro && h("button", { class: "btn btn-sm btn-primary", type: "button", onclick: () => abrirRegistro(p, d, cuest, recargar) }, icono("mas"), d.estado === "sin_declaracion" ? "Registrar declaración" : "Registrar otra"),
    ],
    contenido: [
      // Sin declaración vigente, sus parcelas no se habilitan: rojo suave.
      h("p", { class: `alerta ${d.estado === "vigente" ? "info" : d.estado === "por_vencer" ? "warn" : "bad"}` }, textos[d.estado]),
      valida && vigente && h("p", { class: "panel-sub" }, `Declarada el ${fecha(vigente.declarada_en)} ${vigente.origen === "productor" ? "por el productor desde su cuenta" : `con hoja firmada; la registró ${vigente.registrada_por_nombre ?? "el personal"}`}.`),
      d.aviso_area && h("p", { class: "alerta warn" }, d.aviso_area),
      d.por_firmar &&
        h(
          "div",
          { class: "casilla-doc" },
          h("span", {}, h("b", {}, "Por firmar: "), `registrada el ${fecha(d.por_firmar.registrada_en)}${d.por_firmar.registrada_por_nombre ? ` por ${d.por_firmar.registrada_por_nombre}` : ""}.`),
          h(
            "span",
            { class: "fila-acciones" },
            botonHoja(p, d.por_firmar, "Descargar hoja para firmar"),
            puedo.registro && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirHojaFirmada(p, d.por_firmar, recargar) }, icono("upload"), "Cargar hoja firmada"),
          ),
        ),
      vigente && h("div", { class: "fila-acciones" }, botonHoja(p, vigente, "Descargar copia de la declaración")),
    ],
  });
}

function bloqueRespuestas(d) {
  const decl = d.vigente ?? d.por_firmar;
  if (!decl) return null;
  const ctx = decl.contexto ?? {};
  return seccion({
    titulo: "Respuestas",
    sub: d.vigente ? "Las de la declaración vigente. Son la palabra del productor: su nivel de verificación es siempre declarado." : "Las de la declaración por firmar: todavía no cuentan.",
    contenido: rejilla([
      ...filasRespuestas(decl),
      { grupo: "Lo que el sistema sabía al registrarla" },
      { etiqueta: "Parcelas activas", valor: `${ctx.parcelas_activas ?? "—"} · ${ha(ctx.area_total_ha)}` },
      { etiqueta: "Entregado en los 12 meses anteriores", valor: kilos(ctx.kilos_12_meses) },
      { etiqueta: "UIT de referencia", valor: ctx.uit_soles ? `S/ ${Number(ctx.uit_soles).toLocaleString("es-PE", { minimumFractionDigits: 2 })} (${ctx.uit_anio})` : "No registrada" },
      { etiqueta: "Jornal de referencia", valor: ctx.jornal_minimo_referencia ? `S/ ${Number(ctx.jornal_minimo_referencia).toLocaleString("es-PE", { minimumFractionDigits: 2 })}` : "No registrado", extra: ctx.jornal_referencia_nota },
      { etiqueta: "Versión", valor: `Cuestionario ${decl.version_cuestionario} · texto ${decl.version_texto}` },
    ]),
  });
}

/** Ninguno impide habilitar: amarillo si queda algo por atender o sin sustento, verde si está declarado o
 * sustentado. Sin declaración vigente, sin color: lo que falta es la declaración, arriba en rojo. */
function tonoRequisito(r) {
  if (["por_atender", "sin_sustento"].includes(r.estado)) return "falta";
  if (["declarado", "sustentado"].includes(r.estado)) return "listo";
  return null;
}

function filaRequisito(r) {
  return h(
    "li",
    { class: `${claseTono(tonoRequisito(r))} requisito-legal estado-${r.estado}` },
    h(
      "div",
      { class: "casilla-h" },
      h("div", {}, h("b", {}, r.nombre), h("span", { class: "sec" }, `Orientador, ref. ${r.referencias.join(", ")} · ${r.nivel_texto || `implementación ${NIVEL_ORIENTADOR[r.nivel]}, diligencia ${DILIGENCIA[r.diligencia]}`} · no impide habilitar`)),
      // Una respuesta siempre es declarada: el nivel se muestra solo cuando un papel la documenta.
      h("span", { class: "fila-acciones" }, insignia(ESTADO_REQUISITO_PRODUCTOR[r.estado] ?? ["", r.etiqueta]), r.nivel_verificacion === "documentado" && insigniaNivel(r.nivel_verificacion)),
    ),
    h("p", { class: "requisito-motivo" }, r.motivo),
    r.hechos.length > 0 && h("ul", { class: "hechos" }, r.hechos.map((x) => h("li", {}, h("span", { class: "sec" }, x.texto), " ", h("b", {}, x.valor)))),
    r.siguiente && h("p", { class: "sec" }, r.siguiente),
  );
}

function bloqueRequisitos(d) {
  const aplican = ordenarPorTono(
    d.requisitos.filter((r) => r.estado !== "no_aplica"),
    tonoRequisito,
  );
  const noAplican = d.requisitos.filter((r) => r.estado === "no_aplica");
  const sub = "Lo que el orientador pide al productor. Ninguno impide habilitar: lo que queda por atender pide una nota al habilitar y llega al informe de hallazgos.";
  // Sin declaración vigente, los siete quedan sin dato: una línea basta y la lista va plegada.
  if (d.requisitos.every((r) => r.estado === "sin_dato")) {
    return seccion({
      titulo: "Requisitos",
      sub,
      contenido: [
        h("p", { class: "panel-sub" }, "Los siete requisitos del productor quedan sin dato hasta que tenga una declaración vigente."),
        h("details", { class: "no-aplican" }, h("summary", {}, `Ver los requisitos (${d.requisitos.length})`), h("ul", { class: "casillas" }, d.requisitos.map(filaRequisito))),
      ],
    });
  }
  return seccion({
    titulo: "Requisitos",
    sub,
    contenido: [
      leyendaTonos({ bloquea: null, falta: "por atender o sin sustento, no impide", listo: "declarado o sustentado" }),
      h("ul", { class: "casillas" }, aplican.map(filaRequisito)),
      noAplican.length > 0 && h("details", { class: "no-aplican" }, h("summary", {}, `No aplican (${noAplican.length})`), h("ul", { class: "casillas" }, noAplican.map(filaRequisito))),
    ],
  });
}

function bloquePapeles(p, d, cuest, puedo, recargar) {
  const decl = d.vigente ?? d.por_firmar;
  if (!decl) return null;
  const tonoProducto = (x) => (x.revision === "figura" ? "listo" : "falta");
  const otros = decl.documentos.filter((doc) => !["relacion_trabajadores", "declaracion_renta"].includes(doc.tipo));
  const productos =
    decl.productos.length > 0 &&
    h(
      "div",
      {},
      h("h4", { class: "subtitulo-bloque" }, "Productos declarados"),
      h(
        "p",
        { class: "panel-sub" },
        "Búscalos en la consulta pública de SENASA y marca si figuran en el registro: ",
        cuest.consultas_senasa.flatMap((c, i) => [i ? " · " : "", h("a", { href: c.valor, target: "_blank", rel: "noopener noreferrer" }, c.etiqueta)]),
        ".",
      ),
      h(
        "ul",
        { class: "casillas" },
        ordenarPorTono(decl.productos, tonoProducto).map((x) =>
          h(
            "li",
            { class: claseTono(tonoProducto(x)) },
            h(
              "div",
              { class: "casilla-h" },
              h("div", {}, h("b", {}, x.nombre), h("span", { class: "sec" }, cuest.tipos_producto.find((t) => t.valor === x.tipo)?.etiqueta ?? x.tipo)),
              insignia(x.revision === "figura" ? ["ok", "Figura"] : x.revision === "no_figura" ? ["warn", "No figura"] : ["", "Sin revisar"]),
            ),
            h("p", { class: "sec" }, textoRevision(x)),
            puedo.registro &&
              h(
                "div",
                { class: "fila-acciones" },
                h("button", { class: "btn btn-sm", type: "button", onclick: () => revisar(p, decl, x, "figura", recargar) }, "Figura"),
                h("button", { class: "btn btn-sm", type: "button", onclick: () => revisar(p, decl, x, "no_figura", recargar) }, "No figura"),
              ),
          ),
        ),
      ),
    );
  return seccion({
    titulo: "Papeles",
    sub: "Los papeles pertenecen a esta declaración: al renovarla se piden otra vez si la respuesta los vuelve a pedir.",
    contenido: [
      productos,
      h("h4", { class: "subtitulo-bloque" }, "Documentos que piden sus respuestas"),
      casillasPapeles(decl, {
        ruta: `/productores/${p.id}/declaraciones/${decl.id}/documentos`,
        puedeCargar: puedo.registro,
        puedeAnular: puedo.registro,
        alCambiar: recargar,
      }) ?? h("p", { class: "panel-sub" }, "Sus respuestas no piden ningún papel."),
      otros.length > 0 && h("h4", { class: "subtitulo-bloque" }, "Otros documentos"),
      otros.length > 0 && h("div", { class: "tbl-box" }, listaDocumentos(otros, { puedeAnular: puedo.registro, alCambiar: recargar })),
    ],
  });
}

function bloqueSeguimiento(p, d, puedo, recargar) {
  if (!d.vigente) return null;
  const s = d.vigente.seguimiento;
  return seccion({
    titulo: "Nota de seguimiento",
    sub: "Lo que hizo la organización ante lo declarado. Aparece como explicación de los hallazgos del productor en el DEX; el productor no la ve.",
    acciones: puedo.admin && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirSeguimiento(p, d.vigente, recargar) }, s ? "Cambiar la nota" : "Escribir nota"),
    contenido: s ? h("div", { class: "casilla-doc" }, h("span", {}, s.nota), h("span", { class: "sec" }, `${s.por_nombre ?? "—"} · ${fecha(s.en, { hora: true })}`)) : h("p", { class: "panel-sub" }, "Sin nota."),
  });
}

function bloqueHistorial(p, d) {
  const anteriores = d.historial.filter((x) => x.id !== d.vigente?.id && x.id !== d.por_firmar?.id);
  if (!anteriores.length) return null;
  return h(
    "details",
    { class: "no-aplican" },
    h("summary", {}, `Declaraciones anteriores (${anteriores.length})`),
    h(
      "ul",
      { class: "casillas" },
      anteriores.map((x) =>
        h(
          "li",
          { class: "casilla" },
          h(
            "div",
            { class: "casilla-h" },
            h("span", {}, `Registrada el ${fecha(x.registrada_en)}${x.declarada_en ? ` · declarada el ${fecha(x.declarada_en)}` : ""}`),
            h("span", { class: "fila-acciones" }, insignia(ESTADO_DECLARACION[x.estado]), x.declarada_en && botonHoja(p, x, "Copia")),
          ),
        ),
      ),
    ),
  );
}

export async function pestanaDeclaracion(p, { recargar }) {
  const [d, cuest] = await Promise.all([llamarApi(`/productores/${p.id}/declaracion`), cuestionario()]);
  const puedo = permisos();
  return h(
    "div",
    {},
    estadoArriba(p, d, puedo, cuest, recargar),
    bloqueRespuestas(d),
    bloqueRequisitos(d),
    bloquePapeles(p, d, cuest, puedo, recargar),
    bloqueSeguimiento(p, d, puedo, recargar),
    bloqueHistorial(p, d),
  );
}
