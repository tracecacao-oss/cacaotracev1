// Plantilla de proceso (Cooperativa): los valores habituales de cada una de las 23 etapas (lugar, método,
// distancia y duración) con que nace cada corrida, y el catálogo de calidades que usan la etapa 17 y la
// tanda final. Solo el administrador los cambia; el resto del personal los consulta.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { campoMetodo, FASES, horas, simbolo } from "../proceso.js";
import { abrirModal, campo, enviarCon, h, icono, seccion, toast, vacio } from "../ui.js";

function abrirCalidad(calidad, alGuardar) {
  const nueva = !calidad;
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-calidad" }, nueva ? "Crear calidad" : "Guardar");
  const formulario = h(
    "form",
    { class: "form", id: "form-calidad" },
    campo({ etiqueta: "Nombre", name: "nombre", value: calidad?.nombre ?? "", required: true, maxlength: 200 }),
    !nueva && h("label", { class: "check" }, h("input", { type: "checkbox", name: "activo", value: "si", checked: calidad.activo }), h("span", {}, "Activa. Una calidad inactiva ya no se elige en la etapa 17; las tandas finales que la usan la conservan.")),
  );
  const { cerrar } = abrirModal({
    titulo: nueva ? "Nueva calidad" : "Editar calidad",
    subtitulo: nueva ? "Un valor del catálogo de calidades de la cooperativa." : calidad.nombre,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    if (nueva) await llamarApi("/calidades", { metodo: "POST", cuerpo: { nombre: datos.nombre } });
    else await llamarApi(`/calidades/${calidad.id}`, { metodo: "PATCH", cuerpo: { nombre: datos.nombre, activo: datos.activo === "si" } });
    cerrar();
    toast(nueva ? "Calidad creada." : "Calidad actualizada.");
    alGuardar();
  });
}

export default async function plantillaProceso({ recargar }) {
  const [catalogo, plantilla, lugares, calidades] = await Promise.all([llamarApi("/proceso/etapas"), llamarApi("/proceso/plantilla"), llamarApi("/lugares"), llamarApi("/calidades")]);
  const admin = rolEfectivo() === "admin_cooperativa";
  const porNumero = Object.fromEntries(plantilla.map((p) => [p.numero, p]));
  const nombreLugar = Object.fromEntries(lugares.map((l) => [l.id, l.nombre]));

  function fila(e, valores) {
    const p = valores[e.numero] ?? {};
    const lugar = admin
      ? h(
          "select",
          { class: "select", name: `lugar_${e.numero}`, "aria-label": `Lugar de la etapa ${e.numero}` },
          h("option", { value: "" }, "Sin lugar"),
          lugares.filter((l) => l.activo || l.id === p.lugar_id).map((l) => h("option", { value: l.id }, l.activo ? l.nombre : `${l.nombre} (inactivo)`)),
        )
      : nombreLugar[p.lugar_id] ?? "—";
    if (admin) lugar.value = p.lugar_id ?? "";
    const entrada = (nombre, valor, extra) => h("input", { class: "input", name: `${nombre}_${e.numero}`, value: valor ?? "", ...extra });
    // Decisión del 2026-10-06: la cooperativa desactiva las etapas que no usa, salvo las fijas.
    const usada = p.activa !== false;
    const usa = e.fija
      ? h("span", { class: "badge", title: "La llena el sistema o se usa al consolidar: no se desactiva." }, "Fija")
      : admin
        ? h("input", {
            type: "checkbox",
            name: `activa_${e.numero}`,
            value: "si",
            checked: usada,
            "aria-label": `Se usa la etapa ${e.numero}`,
            onchange: (evento) => evento.target.closest("tr").classList.toggle("fila-inactiva", !evento.target.checked),
          })
        : usada
          ? "Sí"
          : "No";
    return h(
      "tr",
      { class: usada ? false : "fila-inactiva" },
      h("td", { class: "mono" }, String(e.numero)),
      h("td", { class: "celda-usa" }, usa),
      h("td", {}, h("span", { class: "etapa-h" }, simbolo(e.tipo), h("b", {}, e.nombre)), h("span", { class: "sec" }, [e.tipo_nombre, e.automatica && "la llena el sistema", e.opcional && "puede no ocurrir", !e.en_ruta_seco && "solo ruta completa"].filter(Boolean).join(" · "))),
      h("td", {}, lugar),
      h(
        "td",
        {},
        e.automatica
          ? h("span", { class: "sec" }, "Lo pone el sistema")
          : admin
            ? campoMetodo({ metodos: e.metodos, valor: p.metodo, name: `metodo_${e.numero}`, vacio: "Sin método", etiqueta: `Método de la etapa ${e.numero}` })
            : (p.metodo ?? "—"),
      ),
      h(
        "td",
        { class: "num" },
        e.transporte
          ? admin
            ? entrada("distancia", p.distancia_m, { type: "number", step: "0.1", min: "0", inputmode: "decimal", class: "input mono", "aria-label": `Distancia en metros de la etapa ${e.numero}` })
            : p.distancia_m != null ? `${Number(p.distancia_m).toLocaleString("es-PE")} m` : "—"
          : h("span", { class: "sec" }, "—"),
      ),
      h("td", { class: "num" }, admin ? entrada("duracion", p.duracion_horas, { type: "number", step: "0.01", min: "0", inputmode: "decimal", class: "input mono", "aria-label": `Duración en horas de la etapa ${e.numero}` }) : p.duracion_horas != null ? horas(p.duracion_horas) : "—"),
    );
  }

  const armarTabla = (valores) =>
    h(
      "div",
      { class: "tbl-box" },
      h(
        "table",
        { class: "tabla tabla-plantilla" },
        h("thead", {}, h("tr", {}, h("th", {}, "N.º"), h("th", {}, "Se usa"), h("th", {}, "Etapa"), h("th", {}, "Lugar"), h("th", {}, "Método"), h("th", { class: "num" }, "Distancia (m)"), h("th", { class: "num" }, "Duración (h)"))),
        FASES.map(([clave, nombre]) => h("tbody", {}, h("tr", { class: "fila-fase" }, h("th", { colspan: 7, scope: "rowgroup" }, nombre)), catalogo.filter((e) => e.fase === clave).map((e) => fila(e, valores)))),
      ),
    );
  let tabla = armarTabla(porNumero);
  const guardar = h("button", { class: "btn btn-primary", type: "submit", form: "form-plantilla" }, icono("check"), "Guardar plantilla");
  const formulario = h("form", { class: "form", id: "form-plantilla" }, tabla, admin && h("div", { class: "fila-acciones" }, guardar));

  /** Lo que hay escrito ahora en la tabla, sin guardar, por número de etapa. */
  function escrito() {
    const datos = new FormData(formulario);
    const valor = (nombre) => (datos.get(nombre) ?? "").toString().trim() || null;
    return Object.fromEntries(
      catalogo.map((e) => [
        e.numero,
        {
          lugar_id: valor(`lugar_${e.numero}`),
          metodo: valor(`metodo_${e.numero}`),
          distancia_m: valor(`distancia_${e.numero}`),
          duracion_horas: valor(`duracion_${e.numero}`),
          activa: e.fija || datos.get(`activa_${e.numero}`) === "si",
        },
      ]),
    );
  }

  /** Llena solo las casillas vacías con la plantilla sugerida. No guarda: el administrador revisa y guarda. */
  async function llenarConSugerida(evento) {
    const boton = evento.currentTarget;
    boton.classList.add("is-loading");
    try {
      const sugerida = await llamarApi("/proceso/plantilla/sugerida");
      const valores = escrito();
      let llenadas = 0;
      for (const s of sugerida) {
        const actual = valores[s.numero];
        for (const clave of ["lugar_id", "metodo", "duracion_horas"]) {
          if (actual[clave] == null && s[clave] != null) {
            actual[clave] = String(s[clave]);
            llenadas += 1;
          }
        }
      }
      const nueva = armarTabla(valores);
      tabla.replaceWith(nueva);
      tabla = nueva;
      const sinLugar = sugerida.some((s) => s.lugar_id == null && valores[s.numero].lugar_id == null);
      const aviso = sinLugar ? " Algunas etapas quedaron sin lugar: crea en Lugares una cancha de acopio, una planta y un almacén." : "";
      toast(`${llenadas ? `Se llenaron ${llenadas} casillas vacías. Revisa y guarda la plantilla.` : "No había casillas vacías que la sugerencia pudiera llenar."}${aviso}`);
    } catch (error) {
      toast(error.message, "bad");
    } finally {
      boton.classList.remove("is-loading");
    }
  }
  const sugerir = admin && h("button", { class: "btn btn-sm", type: "button", onclick: llenarConSugerida }, icono("zap"), "Llenar con la plantilla sugerida");
  if (admin) {
    enviarCon(formulario, guardar, async (datos) => {
      const filas = catalogo.map((e) => ({
        numero: e.numero,
        lugar_id: datos[`lugar_${e.numero}`] || null,
        metodo: datos[`metodo_${e.numero}`]?.trim() || null,
        distancia_m: e.transporte ? datos[`distancia_${e.numero}`] || null : null,
        duracion_horas: datos[`duracion_${e.numero}`] || null,
        activa: e.fija || datos[`activa_${e.numero}`] === "si",
      }));
      await llamarApi("/proceso/plantilla", { metodo: "PUT", cuerpo: { filas } });
      toast("Plantilla guardada. Las corridas nuevas nacen con estos valores.");
    });
  }

  const listaCalidades = calidades.length
    ? h(
        "ul",
        { class: "lista-simple" },
        calidades.map((c) =>
          h(
            "li",
            { class: "fila-calidad" },
            h("b", {}, c.nombre),
            " ",
            c.activo ? h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Activa") : h("span", { class: "badge" }, h("span", { class: "dot" }), "Inactiva"),
            admin && h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => abrirCalidad(c, recargar) }, "Editar"),
          ),
        ),
      )
    : vacio({ titulo: "Sin calidades", texto: "Una corrida no se consolida hasta que la cooperativa tenga al menos una calidad activa." });

  return {
    titulo: "Plantilla de proceso",
    antetitulo: "Cooperativa",
    descripcion: "Los valores habituales de cada etapa. Cada corrida nace con ellos y el operador los confirma o corrige.",
    migas: [["Cooperativa", "#/cooperativa"], ["Plantilla de proceso"]],
    contenido: h(
      "section",
      { class: "panel inspector" },
      seccion({
        titulo: "Etapas",
        sub: admin
          ? "Desmarca las etapas que tu cooperativa no usa: las corridas nuevas no las piden. Las fijas las necesita el sistema. \"Llenar con la plantilla sugerida\" completa lo vacío con valores habituales; la distancia de los traslados es opcional. Lo que quede vacío lo llena el operador en cada corrida."
          : "Solo el administrador cambia la plantilla.",
        acciones: sugerir,
        contenido: formulario,
      }),
      seccion({
        titulo: "Calidades",
        sub: "El catálogo que usan la etapa 17 y la tanda final. Las órdenes de compra de la Parte 7 lo usan para emparejar el stock.",
        acciones: admin && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirCalidad(null, recargar) }, icono("plus"), "Nueva calidad"),
        contenido: listaCalidades,
      }),
    ),
  };
}
