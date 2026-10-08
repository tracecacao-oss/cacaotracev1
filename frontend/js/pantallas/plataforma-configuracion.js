// Configuración de plataforma (Parte 9, superadministrador): la clasificación de riesgo del país que el
// informe de hallazgos muestra como contexto (criterio 6), con su fecha y la publicación de la Comisión
// Europea de donde sale. Si está vacía, el informe dice "clasificación del país no registrada".

import { llamarApi } from "../api.js";
import { abrirModal, cabeceraFicha, campo, enviarCon, fecha, h, icono, rejilla, seccion, toast } from "../ui.js";

const CLASIFICACIONES = [
  ["", "Sin registrar"],
  ["bajo", "Riesgo bajo"],
  ["estandar", "Riesgo estándar"],
  ["alto", "Riesgo alto"],
];
const NOMBRE = Object.fromEntries(CLASIFICACIONES);

function abrirEdicion(c, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-clasificacion" }, "Guardar");
  const referencia = h("textarea", { class: "input texto-libre", name: "clasificacion_referencia", maxlength: 1000, rows: 3 });
  referencia.value = c.clasificacion_referencia ?? "";
  const formulario = h(
    "form",
    { class: "form", id: "form-clasificacion" },
    campo({ etiqueta: "Clasificación del Perú", name: "clasificacion_pais", opciones: CLASIFICACIONES, value: c.clasificacion_pais ?? "" }),
    campo({ etiqueta: "Fecha de la clasificación", name: "clasificacion_fecha", type: "date", value: c.clasificacion_fecha ?? "" }),
    h("label", { class: "field" }, "Referencia", referencia, h("small", {}, "La publicación de la Comisión Europea de donde sale: nombre, número y fecha.")),
    h("p", { class: "panel-sub" }, "Con una clasificación, la fecha y la referencia son obligatorias. Elige \"Sin registrar\" para borrarla: el informe lo dirá así."),
  );
  const { cerrar } = abrirModal({ titulo: "Clasificación del país", contenido: formulario, pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton] });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = datos.clasificacion_pais
      ? { clasificacion_pais: datos.clasificacion_pais, clasificacion_fecha: datos.clasificacion_fecha || null, clasificacion_referencia: datos.clasificacion_referencia || null }
      : { clasificacion_pais: null };
    await llamarApi("/admin/configuracion", { metodo: "PUT", cuerpo });
    cerrar();
    toast("Clasificación guardada.");
    alGuardar();
  });
}

export default async function plataformaConfiguracion({ recargar }) {
  const c = await llamarApi("/admin/configuracion", { sinConsulta: true });
  return {
    titulo: "Configuración de plataforma",
    migas: [["Plataforma", "#/plataforma/cooperativas"], ["Configuración"]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("plataforma")),
        titulo: "Clasificación de riesgo del país",
        detalle: "Contexto del informe de hallazgos para todas las cooperativas. El sistema no asume un valor.",
        accion: h("button", { class: "btn btn-primary", type: "button", onclick: () => abrirEdicion(c, recargar) }, "Cambiar"),
      }),
      seccion({
        titulo: "Registrada",
        contenido: [
          !c.clasificacion_pais && h("p", { class: "alerta warn" }, "Sin registrar: el informe dice \"Clasificación del país no registrada\"."),
          rejilla([
            { etiqueta: "Clasificación", valor: NOMBRE[c.clasificacion_pais ?? ""] },
            { etiqueta: "Fecha", valor: c.clasificacion_fecha ? fecha(c.clasificacion_fecha) : null },
            { etiqueta: "Referencia", valor: c.clasificacion_referencia },
            { etiqueta: "Último cambio", valor: c.actualizado_en ? `${fecha(c.actualizado_en, { hora: true })} · ${c.actualizado_por_nombre ?? "—"}` : null },
          ]),
        ],
      }),
    ),
  };
}
