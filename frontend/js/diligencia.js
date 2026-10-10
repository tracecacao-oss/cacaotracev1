// Actuaciones de diligencia de la organización (adenda 6, sección 6): el formulario corto para registrarlas,
// que cabe en la pantalla de un celular, y su ficha con los productores que alcanzó y su evidencia. Lo usan
// la pantalla Diligencia y la ficha del productor. El sistema no concluye: una actuación dice qué hizo la
// organización, con sus palabras; su nivel es "declarado" sin evidencia y "documentado" con ella.

import { llamarApi } from "./api.js";
import { listaDocumentos } from "./documentos.js";
import { rolEfectivo } from "./estado.js";
import { hoyLima as hoy } from "./fechas.js";
import { insigniaNivel } from "./textos.js";
import { camposUbigeo, lugares } from "./ubigeo.js";
import { abrirModal, avatar, buscador, campo, conRetraso, enviarCon, fecha, h, icono, reemplazar, rejilla, toast } from "./ui.js";

export const TEMAS = [
  ["integridad", "Integridad"],
  ["tierra_forestal", "Tierra forestal"],
  ["agroquimicos_y_envases", "Agroquímicos y envases"],
  ["trabajo", "Trabajo"],
  ["tenencia", "Tenencia"],
  ["areas_protegidas", "Áreas protegidas"],
  ["agua", "Agua"],
  ["derechos_humanos", "Derechos humanos"],
];
export const NOMBRE_TEMA = Object.fromEntries(TEMAS);
export const temasTexto = (codigos) => codigos.map((c) => NOMBRE_TEMA[c] ?? c).join(", ");

function insignia(clase, texto) {
  return h("span", { class: `badge ${clase}`.trim() }, h("span", { class: "dot" }), texto);
}

/** Vigente, vencida (pasaron los meses de vigencia) o anulada. */
export function insigniaActuacion(a) {
  if (a.anulada_en) return insignia("", "Anulada");
  return a.vigente ? insignia("ok", "Vigente") : insignia("warn", "Vencida");
}

/** Buscar y marcar productores afiliados (opcional). Devuelve [nodo, () => ids]. */
function selectorProductores() {
  const elegidos = new Map();
  const resultados = h("div", { class: "opciones" });
  const marcados = h("div", { class: "alcanzados" });
  function dibujar() {
    reemplazar(
      marcados,
      [...elegidos.values()].map((p) =>
        h("button", { class: "fchip", type: "button", "aria-pressed": "true", title: "Quitar", onclick: () => (elegidos.delete(p.id), dibujar()) }, `${p.nombres} ${p.apellidos}`, " ×"),
      ),
    );
  }
  async function buscar(texto) {
    if (!texto) return reemplazar(resultados);
    try {
      const { items } = await llamarApi("/productores", { parametros: { q: texto, por_pagina: 6 } });
      reemplazar(
        resultados,
        items.length
          ? items.map((p) =>
              h(
                "button",
                { class: "opcion", type: "button", onclick: () => (elegidos.set(p.id, p), dibujar()) },
                avatar(p.nombres, p.apellidos, "sm"),
                h("span", {}, h("b", {}, `${p.nombres} ${p.apellidos}`), h("span", { class: "sec mono" }, `DNI ${p.dni}`)),
              ),
            )
          : h("p", { class: "panel-sub" }, "Ningún productor afiliado coincide."),
      );
    } catch (error) {
      reemplazar(resultados, h("p", { class: "alerta bad" }, error.message));
    }
  }
  const nodo = h(
    "div",
    { class: "field" },
    "Productores que alcanzó (opcional)",
    buscador({ placeholder: "DNI o nombre", etiqueta: "Buscar productor", alEscribir: conRetraso((t) => buscar(t.trim())) }),
    resultados,
    marcados,
  );
  return [nodo, () => [...elegidos.keys()]];
}

/**
 * Registra una actuación. `catalogo`: lo que trae GET /cooperativa/diligencia (tipos y fuentes); `tema`: el
 * que llega marcado desde el cuadro de señales.
 */
export function abrirActuacion(catalogo, { tema, alGuardar }) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-actuacion" }, "Registrar actuación");
  const tipo = campo({ etiqueta: "Tipo", name: "tipo", required: true, opciones: catalogo.tipos.map((t) => [t.codigo, t.nombre]) });
  const selectTipo = tipo.querySelector("select");
  const ejemplos = h("small", {});
  tipo.append(ejemplos);
  const temas = TEMAS.map(([codigo, nombre]) => h("label", { class: "check" }, h("input", { type: "checkbox", value: codigo, checked: codigo === tema }), nombre));
  const contraparte = campo({ etiqueta: "Fuente revisada", name: "contraparte", maxlength: 400, list: "fuentes-sugeridas" });
  const inputContraparte = contraparte.querySelector("input");
  const fuentes = h("datalist", { id: "fuentes-sugeridas" }, catalogo.fuentes.map((f) => h("option", { value: f.nombre })));
  const enlaces = h("p", { class: "panel-sub fila-acciones" });
  const participantes = campo({ etiqueta: "Participantes", name: "participantes", type: "number", min: 1, max: 100000, inputmode: "numeric" });
  const ubicacion = camposUbigeo();
  for (const c of ubicacion) c.querySelector("select").required = false;
  const [productores, idsProductores] = selectorProductores();
  const archivo = h("input", { class: "input", type: "file", name: "archivo", accept: "image/jpeg,image/png,application/pdf" });

  function alCambiarTipo() {
    const t = catalogo.tipos.find((x) => x.codigo === selectTipo.value);
    ejemplos.textContent = `${t.que_es} Ejemplos: ${t.ejemplos}`;
    contraparte.hidden = !t.pide_contraparte && !inputContraparte.value;
    inputContraparte.required = t.pide_contraparte;
    contraparte.firstChild.textContent = t.codigo === "revision_de_fuente_publica" ? "Fuente revisada" : "Con quién se habló";
    const sugeridas = t.codigo === "revision_de_fuente_publica" ? catalogo.fuentes.filter((f) => f.enlace) : [];
    reemplazar(enlaces, sugeridas.map((f) => h("a", { href: f.enlace, target: "_blank", rel: "noopener" }, f.nombre)));
    participantes.hidden = t.codigo !== "capacitacion";
  }
  selectTipo.addEventListener("change", alCambiarTipo);

  const formulario = h(
    "form",
    { class: "form", id: "form-actuacion" },
    tipo,
    h("fieldset", { class: "field" }, h("legend", {}, "Temas"), h("div", { class: "checks" }, temas)),
    campo({ etiqueta: "Fecha", name: "fecha", type: "date", max: hoy(), value: hoy(), required: true }),
    h("label", { class: "field" }, "Qué se hizo", h("textarea", { class: "input texto-libre", name: "descripcion", required: true, minlength: 50, maxlength: 4000, rows: 3 }), h("small", {}, "Mínimo 50 caracteres.")),
    contraparte,
    fuentes,
    enlaces,
    h("label", { class: "field" }, "Qué se encontró o qué se acordó", h("textarea", { class: "input texto-libre", name: "resultado", required: true, minlength: 20, maxlength: 4000, rows: 2 }), h("small", {}, "Mínimo 20 caracteres.")),
    participantes,
    h("details", { class: "no-aplican" }, h("summary", {}, "Dónde y a quiénes alcanzó (opcional)"), h("div", { class: "grid2" }, ubicacion[0], ubicacion[1]), ubicacion[2], productores),
    h("label", { class: "field" }, "Evidencia (opcional): lista de asistencia, foto, captura o informe", archivo, h("small", {}, "Con evidencia, la actuación queda documentada. Se puede agregar después.")),
  );
  alCambiarTipo();
  const { cerrar } = abrirModal({ titulo: "Registrar actuación", subtitulo: "Algo que la organización hizo para conocer o reducir un riesgo en su zona.", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const marcados = temas.map((t) => t.querySelector("input")).filter((x) => x.checked).map((x) => x.value);
    if (!marcados.length) throw new Error("Marca al menos un tema.");
    const cuerpo = {
      tipo: datos.tipo,
      temas: marcados,
      fecha: datos.fecha,
      descripcion: datos.descripcion,
      resultado: datos.resultado,
      contraparte: datos.contraparte || null,
      participantes: datos.participantes ? Number(datos.participantes) : null,
      departamento: datos.departamento || null,
      provincia: datos.provincia || null,
      distrito: datos.distrito || null,
      productor_ids: idsProductores(),
    };
    const actuacion = await llamarApi("/actuaciones", { metodo: "POST", cuerpo });
    if (archivo.files[0]) {
      const evidencia = new FormData();
      evidencia.append("archivo", archivo.files[0]);
      try {
        await llamarApi(`/actuaciones/${actuacion.id}/evidencias`, { metodo: "POST", formulario: evidencia });
      } catch (error) {
        toast(`La actuación se registró, pero la evidencia no se cargó: ${error.message}`, "warn");
      }
    }
    cerrar();
    toast("Actuación registrada.");
    alGuardar();
  });
}

function abrirAnulacion(a, alAnular) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-anular-actuacion" }, "Anular actuación");
  const formulario = h(
    "form",
    { class: "form", id: "form-anular-actuacion" },
    h("p", {}, "La actuación no se edita ni se borra: queda anulada con su motivo y deja de contar."),
    h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, minlength: 10, maxlength: 4000, rows: 3 })),
  );
  const { cerrar } = abrirModal({ titulo: "Anular actuación", subtitulo: `${a.tipo_nombre} · ${fecha(a.fecha)}`, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/actuaciones/${a.id}/anular`, { metodo: "POST", cuerpo: { motivo } });
    cerrar();
    toast("Actuación anulada.", "warn");
    alAnular();
  });
}

/** La ficha de una actuación en un modal, con sus productores y su evidencia. */
export async function abrirFicha(id, alCambiar) {
  const rol = rolEfectivo();
  const registra = ["admin_cooperativa", "operador"].includes(rol);
  const cuerpo = h("div", { class: "form" });
  const { cerrar } = abrirModal({ titulo: "Actuación de diligencia", contenido: cuerpo, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cerrar")] });
  async function dibujar() {
    let a;
    try {
      a = await llamarApi(`/actuaciones/${id}`);
    } catch (error) {
      reemplazar(cuerpo, h("p", { class: "alerta bad" }, error.message));
      return;
    }
    const cambio = () => {
      dibujar();
      alCambiar?.();
    };
    const carga = h("input", { class: "input", type: "file", accept: "image/jpeg,image/png,application/pdf" });
    const subir = h("button", { class: "btn btn-sm", type: "button" }, icono("upload"), "Agregar evidencia");
    subir.addEventListener("click", async () => {
      if (!carga.files[0]) return toast("Elige una foto o un PDF.", "warn");
      const datos = new FormData();
      datos.append("archivo", carga.files[0]);
      subir.disabled = true;
      try {
        await llamarApi(`/actuaciones/${a.id}/evidencias`, { metodo: "POST", formulario: datos });
        toast("Evidencia cargada.");
        cambio();
      } catch (error) {
        toast(error.message, "bad");
        subir.disabled = false;
      }
    });
    reemplazar(
      cuerpo,
      a.anulada_en && h("p", { class: "alerta warn" }, `Anulada el ${fecha(a.anulada_en, { hora: true })}${a.anulada_por_nombre ? ` por ${a.anulada_por_nombre}` : ""}. Motivo: ${a.motivo_anulacion}`),
      rejilla([
        { etiqueta: "Tipo", valor: a.tipo_nombre, extra: insigniaActuacion(a) },
        { etiqueta: "Temas", valor: temasTexto(a.temas) },
        { etiqueta: "Fecha", valor: fecha(a.fecha), extra: a.anulada_en ? null : `Cuenta para sus temas hasta el ${fecha(a.vigente_hasta)}.` },
        { etiqueta: "Qué se hizo", valor: a.descripcion },
        a.contraparte && { etiqueta: a.tipo === "revision_de_fuente_publica" ? "Fuente revisada" : "Contraparte", valor: a.contraparte },
        { etiqueta: "Qué se encontró o se acordó", valor: a.resultado },
        a.participantes && { etiqueta: "Participantes", valor: String(a.participantes) },
        a.distrito && { etiqueta: "Lugar", valor: lugares(a.distrito, a.provincia, a.departamento) },
        { etiqueta: "Nivel", valor: a.nivel === "documentado" ? "Documentado: tiene evidencia" : "Declarado: sin evidencia" },
        { etiqueta: "Registrada", valor: `${fecha(a.registrada_en, { hora: true })}${a.registrada_por_nombre ? ` · ${a.registrada_por_nombre}` : ""}` },
      ]),
      h("h4", { class: "dex-sub" }, `Productores que alcanzó (${a.productores_alcanzados.length})`),
      a.productores_alcanzados.length
        ? h("div", { class: "alcanzados" }, a.productores_alcanzados.map((p) => h("a", { class: "fchip", href: `#/productores/${p.id}`, onclick: () => cerrar() }, p.nombre)))
        : h("p", { class: "panel-sub" }, "No se marcó ninguno."),
      h("h4", { class: "dex-sub" }, "Evidencia"),
      h("p", { class: "panel-sub" }, "No sale del sistema: el DEX dice si existe, no la incluye."),
      listaDocumentos(a.documentos, { puedeAnular: rol === "admin_cooperativa", alCambiar: cambio }),
      registra && !a.anulada_en && h("div", { class: "fila-form" }, carga, subir),
      rol === "admin_cooperativa" && !a.anulada_en && h("div", { class: "fila-acciones" }, h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => abrirAnulacion(a, () => (cerrar(), alCambiar?.())) }, "Anular actuación")),
    );
  }
  dibujar();
}

/** Tabla de actuaciones; cada fila abre su ficha. */
export function tablaActuaciones(lista, alCambiar) {
  return h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, "Fecha"), h("th", {}, "Actuación"), h("th", { class: "ocultar-sm" }, "Temas"), h("th", {}, "Estado"), h("th", {}, h("span", { class: "sr-only" }, "Acciones")))),
      h(
        "tbody",
        {},
        lista.map((a) =>
          h(
            "tr",
            {},
            h("td", { class: "fecha" }, fecha(a.fecha)),
            h("td", {}, h("b", {}, a.tipo_nombre), h("span", { class: "sec" }, a.descripcion.length > 120 ? `${a.descripcion.slice(0, 117)}…` : a.descripcion)),
            h("td", { class: "ocultar-sm" }, temasTexto(a.temas)),
            h("td", {}, insigniaActuacion(a), " ", insigniaNivel(a.nivel)),
            h("td", {}, h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirFicha(a.id, alCambiar) }, "Ver")),
          ),
        ),
      ),
    ),
  );
}
