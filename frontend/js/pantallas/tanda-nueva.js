// Asistente de nueva tanda en 4 pasos, pensado para el celular en cancha: 1) productor y parcela,
// 2) pesaje y cosecha, 3) documento de entrega, 4) revisión con requisitos, alertas y la decisión.
// La tanda se guarda al salir del paso 3 (queda "registrada"); validar emite su DOP.

import { llamarApi } from "../api.js";
import { ESTADOS_HABILITACION, PRODUCTO, REQUISITOS, REQUISITOS_TANDA, kilos } from "../textos.js";
import { campoArchivoDocumento, camposTanda, cuerpoTanda, descargarPdf, listaAlertas, listaRequisitos } from "../tandas.js";
import { lugar } from "../ubigeo.js";
import { abrirModal, avatar, buscador, conRetraso, enviarCon, fecha, h, icono, reemplazar, rejilla, toast, vacio } from "../ui.js";

const PASOS = ["Productor y parcela", "Pesaje y cosecha", "Documento de entrega", "Revisión"];
// Errores de la API que se corrigen en el paso de pesaje y cosecha.
const DEL_PASO_2 = new Set(["fecha_futura", "cosecha_invalida", "humedad_solo_en_seco", "variedad_requerida", "lugar_invalido"]);

/** Por qué una parcela no puede recibir la tanda, para mostrarla apagada. */
function motivoNoDisponible(p) {
  if (p.estado !== "activa") return "Parcela inactiva.";
  if (p.habilitacion_estado === "habilitada") return null;
  if (p.habilitacion_estado === "excluida") return "Excluida: no recibe tandas.";
  const estadoTexto = ESTADOS_HABILITACION[p.habilitacion_estado]?.[1] ?? p.habilitacion_estado;
  const faltan = p.requisitos_pendientes.map((r) => REQUISITOS[r] ?? r);
  return faltan.length ? `${estadoTexto}. Falta: ${faltan.join(", ").toLowerCase()}.` : `${estadoTexto}: falta la decisión del administrador.`;
}

export default async function tandaNueva({ navegar, recargar }) {
  const [configuracion, lugares] = await Promise.all([llamarApi("/configuracion"), llamarApi("/lugares", { parametros: { activos: true } })]);
  const volver = "#/lotes/recepcion";
  const vista = {
    titulo: "Nueva tanda",
    antetitulo: "Recepción",
    descripcion: "Productor y parcela, pesaje, documento de entrega y revisión. Cada tanda viene de una sola parcela.",
    migas: [["Lotes y proceso", "#/lotes"], ["Recepción", volver], ["Nueva tanda"]],
  };
  if (!configuracion.lista || !lugares.some((l) => l.tipo === "cancha_acopio")) {
    return {
      ...vista,
      contenido: h(
        "section",
        { class: "panel" },
        vacio({ titulo: "Todavía no se pueden recibir tandas", texto: "Falta configurar el tope de kilos por hectárea, el código de la cooperativa o una cancha de acopio.", accion: h("a", { class: "btn", href: volver }, "Volver a Recepción") }),
      ),
    };
  }

  const st = { paso: 0, productor: null, parcela: null, tanda: null };
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });
  const avisar = (texto) => {
    mensaje.textContent = texto;
    mensaje.hidden = !texto;
  };

  // ---------- Paso 1: productor y parcela ----------
  const resultados = h("div", { class: "opciones" });
  const elegido = h("div");
  const listaParcelas = h("div", { class: "opciones" });
  const busqueda = buscador({
    placeholder: "DNI o nombre del productor",
    etiqueta: "Buscar productor",
    alEscribir: conRetraso((texto) => buscarProductores(texto.trim())),
  });
  const paso1 = h("div", { class: "form" }, busqueda, resultados, elegido, listaParcelas);

  async function buscarProductores(texto) {
    reemplazar(resultados, h("p", { class: "panel-sub" }, "Buscando…"));
    try {
      const { items } = await llamarApi("/productores", { parametros: { q: texto, por_pagina: 8 } });
      reemplazar(
        resultados,
        items.length
          ? items.map((p) =>
              h(
                "button",
                { class: "opcion", type: "button", onclick: () => elegirProductor(p) },
                avatar(p.nombres, p.apellidos, "sm"),
                h("span", {}, h("b", {}, `${p.nombres} ${p.apellidos}`), h("span", { class: "sec mono" }, `DNI ${p.dni}`)),
                icono("chev", "chev-derecha"),
              ),
            )
          : h("p", { class: "panel-sub" }, "Ningún productor afiliado coincide con esa búsqueda."),
      );
    } catch (error) {
      reemplazar(resultados, h("p", { class: "alerta bad" }, error.message));
    }
  }

  async function elegirProductor(p) {
    st.productor = p;
    st.parcela = null;
    busqueda.hidden = true;
    resultados.hidden = true;
    reemplazar(
      elegido,
      h(
        "div",
        { class: "opcion", "aria-pressed": "true" },
        avatar(p.nombres, p.apellidos, "sm"),
        h("span", {}, h("b", {}, `${p.nombres} ${p.apellidos}`), h("span", { class: "sec mono" }, `DNI ${p.dni}`)),
        h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: cambiarProductor }, "Cambiar"),
      ),
    );
    reemplazar(listaParcelas, h("p", { class: "panel-sub" }, "Cargando sus parcelas…"));
    actualizarBotones();
    try {
      const parcelas = await llamarApi(`/productores/${p.id}/parcelas`);
      if (st.productor !== p) return;
      reemplazar(
        listaParcelas,
        parcelas.length
          ? [
              h("b", {}, "¿De qué parcela es este cacao?"),
              parcelas.map((pa) => {
                const motivo = motivoNoDisponible(pa);
                return h(
                  "button",
                  { class: "opcion", type: "button", disabled: Boolean(motivo), "aria-pressed": "false", "data-id": pa.id, onclick: () => elegirParcela(pa) },
                  icono("pin"),
                  h(
                    "span",
                    {},
                    h("b", {}, pa.nombre),
                    h("span", { class: "sec" }, h("span", { class: "mono" }, pa.codigo), ` · ${Number(pa.area_cultivada_ha).toLocaleString("es-PE")} ha con cacao · ${lugar(pa.distrito)}`),
                    motivo && h("span", { class: "motivo" }, motivo),
                  ),
                  !motivo && icono("chev", "chev-derecha"),
                );
              }),
            ]
          : h("p", { class: "alerta warn" }, "Este productor no tiene parcelas registradas."),
      );
    } catch (error) {
      reemplazar(listaParcelas, h("p", { class: "alerta bad" }, error.message));
    }
  }

  function cambiarProductor() {
    st.productor = null;
    st.parcela = null;
    busqueda.hidden = false;
    resultados.hidden = false;
    reemplazar(elegido);
    reemplazar(listaParcelas);
    busqueda.querySelector("input").focus();
    actualizarBotones();
  }

  function elegirParcela(pa) {
    st.parcela = pa;
    for (const b of listaParcelas.querySelectorAll("button.opcion")) b.setAttribute("aria-pressed", String(b.dataset.id === pa.id));
    actualizarBotones();
  }

  // ---------- Pasos 2 y 3: pesaje, cosecha y documento de entrega ----------
  const campos = camposTanda({}, { lugares, configuracion });
  const formPesaje = h("form", { class: "form", novalidate: true }, campos.pesaje);
  const archivo = campoArchivoDocumento();
  const formDocumento = h("form", { class: "form", novalidate: true }, h("p", { class: "panel-sub" }, "Sin documento de entrega la tanda se guarda, pero no se valida."), campos.documento, archivo);
  const paso2 = h("div", { hidden: true }, formPesaje);
  const paso3 = h("div", { hidden: true }, formDocumento);

  function validos(formulario) {
    const controles = [...formulario.querySelectorAll("input,select,textarea")].filter((c) => !c.closest("[hidden]"));
    return controles.every((c) => c.reportValidity());
  }

  function datosDeLaTanda() {
    return cuerpoTanda({ ...Object.fromEntries(new FormData(formPesaje)), ...Object.fromEntries(new FormData(formDocumento)) }, st.tanda);
  }

  async function guardar() {
    const cuerpo = datosDeLaTanda();
    let tanda = st.tanda
      ? await llamarApi(`/tandas/${st.tanda.id}`, { metodo: "PATCH", cuerpo })
      : await llamarApi("/tandas", { metodo: "POST", cuerpo: { productor_id: st.productor.id, parcela_id: st.parcela.id, ...cuerpo } });
    st.tanda = tanda;
    const elegidoArchivo = archivo.querySelector("input");
    if (elegidoArchivo.files.length) {
      const datos = new FormData();
      datos.append("tipo", "documento_entrega");
      datos.append("archivo", elegidoArchivo.files[0]);
      tanda = await llamarApi(`/tandas/${tanda.id}/documentos`, { metodo: "POST", formulario: datos });
      elegidoArchivo.value = "";
      st.tanda = tanda;
    }
    return tanda;
  }

  // ---------- Paso 4: revisión y decisión ----------
  const paso4 = h("div", { hidden: true, class: "form" });
  const nota = h("textarea", { class: "input texto-libre", name: "nota", maxlength: 4000, rows: 4 });

  function documentoVigente(t) {
    return t.documentos.find((d) => d.tipo === "documento_entrega" && d.vigente);
  }

  function pintarRevision() {
    const t = st.tanda;
    nota.required = t.nota_obligatoria;
    nota.minLength = t.nota_obligatoria ? 50 : 0;
    const archivoDoc = documentoVigente(t);
    reemplazar(
      paso4,
      h("div", { class: "tarjeta-r" }, h("b", { class: "mono" }, t.codigo), h("span", { class: "badge info" }, h("span", { class: "dot" }), "Registrada, sin validar")),
      rejilla([
        { etiqueta: "Productor", valor: `${t.productor.nombres} ${t.productor.apellidos} · DNI ${t.productor.dni}` },
        { etiqueta: "Parcela", valor: `${t.parcela.codigo} · ${t.parcela.nombre}` },
        { etiqueta: "Pesaje", valor: `${fecha(t.recibida_en, { hora: true })} · ${t.lugar_nombre}` },
        { etiqueta: "Peso en balanza", valor: `${kilos(t.peso_kg)} · ${PRODUCTO[t.estado_producto]}`, mono: true },
        { etiqueta: "Peso seco equivalente", valor: kilos(t.peso_seco_equivalente_kg), mono: true, extra: t.estado_producto === "baba" ? "Estimado con el factor de la cooperativa." : null },
        { etiqueta: "Variedad", valor: t.variedad_nombre },
        { etiqueta: "Cosecha", valor: `Del ${fecha(t.cosecha_desde)} al ${fecha(t.cosecha_hasta)}` },
        {
          etiqueta: t.doc_entrega_tipo_nombre ?? "Documento de entrega",
          valor: t.doc_entrega_numero ? `${t.doc_entrega_numero} · RUC ${t.doc_entrega_ruc_emisor ?? "—"}` : null,
          mono: true,
          extra: archivoDoc ? `Archivo: ${archivoDoc.nombre_original}` : "Sin archivo",
        },
      ]),
      h("b", {}, "Requisitos para validar"),
      listaRequisitos(t.requisitos),
      h("b", {}, "Alertas"),
      listaAlertas(t.alertas, t.alertas_detalle, configuracion),
      t.alertas.length > 0 &&
        h(
          "label",
          { class: "field" },
          "Nota de validación (obligatoria con alertas, mínimo 50 caracteres)",
          nota,
          h("small", {}, "Explica por qué se valida a pesar de las alertas. Queda en el DOP."),
        ),
      t.alertas.length === 0 && h("label", { class: "field" }, "Nota de validación (opcional)", nota),
    );
    actualizarBotones();
  }

  async function validar() {
    if (!nota.reportValidity()) return;
    avisar("");
    validarBoton.classList.add("is-loading");
    validarBoton.disabled = true;
    try {
      const t = await llamarApi(`/tandas/${st.tanda.id}/validar`, { metodo: "POST", cuerpo: { nota: nota.value.trim() || null } });
      mostrarResultado(t);
    } catch (error) {
      avisar(error.message);
      // Los requisitos o las alertas pudieron cambiar: se vuelven a pedir.
      if (["requisitos_incompletos", "nota_requerida"].includes(error.codigo)) {
        st.tanda = await llamarApi(`/tandas/${st.tanda.id}`).catch(() => st.tanda);
        pintarRevision();
      }
    } finally {
      validarBoton.classList.remove("is-loading");
      actualizarBotones();
    }
  }

  function observar() {
    const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-observar" }, "Observar tanda");
    const formulario = h(
      "form",
      { class: "form", id: "form-observar" },
      h("p", {}, "La tanda queda observada con tu motivo. Se corrige y se valida después."),
      h("label", { class: "field" }, "Motivo", h("textarea", { class: "input texto-libre", name: "motivo", required: true, maxlength: 200, rows: 3 })),
    );
    const { cerrar } = abrirModal({ titulo: "Observar tanda", subtitulo: st.tanda.codigo, contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
    enviarCon(formulario, boton, async ({ motivo }) => {
      await llamarApi(`/tandas/${st.tanda.id}/observar`, { metodo: "POST", cuerpo: { motivo } });
      cerrar();
      toast("Tanda observada.", "warn");
      navegar(`#/tandas/${st.tanda.id}`);
    });
  }

  /** Tras validar ya no hay botones de edición: el código del DOP y su PDF. */
  function mostrarResultado(t) {
    reemplazar(
      panel,
      h(
        "div",
        { class: "resultado-dop" },
        h("span", { class: "ins-icono" }, icono("check")),
        h("b", {}, "Tanda validada y DOP emitido"),
        h("span", { class: "codigo-dop" }, t.dop.codigo),
        h("span", { class: "sec" }, `Tanda ${t.codigo} · ${kilos(t.peso_kg)} · ${t.parcela.codigo}`),
        h("button", { class: "btn btn-primary btn-lg", type: "button", onclick: () => descargarPdf(`/dops/${t.dop.id}/pdf`) }, icono("download"), "Descargar PDF del DOP"),
        h("div", { class: "fila-acciones" }, h("a", { class: "btn", href: `#/dops/${t.dop.id}` }, "Ver el DOP"), h("button", { class: "btn btn-ghost", type: "button", onclick: recargar }, "Registrar otra tanda")),
      ),
    );
    window.scrollTo(0, 0);
  }

  // ---------- Navegación entre pasos ----------
  const indicador = h("div", { class: "pasos" }, PASOS.map((p, i) => h("span", { "aria-current": i === 0 ? "step" : "false" }, `${i + 1}.`, h("span", { class: "paso-t" }, ` ${p}`))));
  const salir = h("a", { class: "btn btn-ghost", href: volver }, "Cancelar");
  const atras = h("button", { class: "btn btn-ghost", type: "button", hidden: true }, "Atrás");
  const siguiente = h("button", { class: "btn btn-primary", type: "button" }, "Siguiente");
  const observarBoton = h("button", { class: "btn", type: "button", hidden: true, onclick: observar }, "Observar");
  const guardarBoton = h("button", { class: "btn", type: "button", hidden: true, onclick: () => navegar(`#/tandas/${st.tanda.id}`) }, "Guardar sin validar");
  const validarBoton = h("button", { class: "btn btn-primary", type: "button", hidden: true, onclick: validar }, icono("check"), "Validar y emitir DOP");
  nota.addEventListener("input", () => actualizarBotones());

  function actualizarBotones() {
    const revision = st.paso === 3;
    siguiente.hidden = revision;
    siguiente.disabled = st.paso === 0 && !st.parcela;
    observarBoton.hidden = !revision || st.tanda?.estado !== "registrada";
    guardarBoton.hidden = !revision;
    validarBoton.hidden = !revision;
    if (revision) {
      const t = st.tanda;
      const faltan = t.requisitos.filter((r) => !r.cumple).map((r) => REQUISITOS_TANDA[r.codigo] ?? r.codigo);
      const faltaNota = t.nota_obligatoria && nota.value.trim().length < 50;
      validarBoton.disabled = !t.puede_validar || faltaNota;
      validarBoton.title = faltan.length ? `Falta: ${faltan.join(", ")}` : faltaNota ? "Escribe la nota de validación (mínimo 50 caracteres)." : "Valida la tanda y emite su DOP";
    }
    // Una vez guardada, la tanda queda registrada aunque se salga del asistente. En la revisión,
    // "Guardar sin validar" ya cumple esa función.
    salir.textContent = st.tanda ? "Salir" : "Cancelar";
    salir.hidden = revision;
  }

  function irA(paso) {
    st.paso = paso;
    [paso1, paso2, paso3, paso4].forEach((p, i) => (p.hidden = i !== paso));
    [...indicador.children].forEach((s, i) => s.setAttribute("aria-current", i === paso ? "step" : "false"));
    atras.hidden = paso === 0;
    avisar("");
    if (paso === 3) pintarRevision();
    if (paso === 1) campos.actualizar();
    actualizarBotones();
    window.scrollTo(0, 0);
  }
  atras.addEventListener("click", () => irA(st.paso - 1));
  siguiente.addEventListener("click", async () => {
    if (st.paso === 0) return irA(1);
    if (st.paso === 1) {
      if (!validos(formPesaje)) return;
      const d = Object.fromEntries(new FormData(formPesaje));
      if (d.cosecha_desde > d.cosecha_hasta) return avisar("La cosecha empieza después de terminar: revisa las fechas.");
      return irA(2);
    }
    if (!validos(formDocumento)) return;
    avisar("");
    siguiente.classList.add("is-loading");
    siguiente.disabled = true;
    try {
      await guardar();
      irA(3);
    } catch (error) {
      if (DEL_PASO_2.has(error.codigo)) irA(1);
      avisar(error.message);
    } finally {
      siguiente.classList.remove("is-loading");
      actualizarBotones();
    }
  });

  buscarProductores("");
  actualizarBotones();
  const panel = h(
    "section",
    { class: "panel asistente-tanda" },
    h("div", { class: "panel-h" }, indicador),
    h("div", { class: "panel-b" }, paso1, paso2, paso3, paso4, mensaje),
    h("div", { class: "modal-f" }, salir, atras, observarBoton, guardarBoton, siguiente, validarBoton),
  );
  return { ...vista, contenido: panel };
}
