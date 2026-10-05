// Verificación pública del DOP: la página a la que lleva el código QR. No pide sesión, no tiene barra
// lateral y no enlaza al resto de la aplicación. Muestra solo cinco datos: código, cooperativa, fecha de
// emisión, estado y huella. Un código que no existe dice solo eso.

import { llamarApi } from "../api.js";
import { fecha, h, icono, marca, rejilla } from "../ui.js";

export default async function verificarDop({ parametros: [codigo] }) {
  const texto = decodeURIComponent(codigo).trim().toUpperCase();
  let dop = null;
  let error = null;
  try {
    dop = await llamarApi(`/publico/dops/${encodeURIComponent(texto)}`, { conToken: false, sinConsulta: true });
  } catch (e) {
    error = e;
  }

  let cuerpo;
  if (dop) {
    const vigente = dop.estado === "vigente";
    cuerpo = [
      h(
        "div",
        { class: `verif ${vigente ? "" : "bad"}`.trim() },
        icono(vigente ? "check" : "alert"),
        h(
          "div",
          {},
          h("b", {}, vigente ? "DOP vigente" : "DOP anulado"),
          h("span", {}, vigente ? "Este documento de origen fue emitido por la cooperativa y no ha sido anulado." : "La cooperativa anuló este documento de origen."),
        ),
      ),
      rejilla([
        { etiqueta: "Código", valor: dop.codigo, mono: true },
        { etiqueta: "Cooperativa", valor: dop.cooperativa },
        { etiqueta: "Fecha de emisión", valor: fecha(dop.emitido_en, { hora: true }) },
        { etiqueta: "Huella SHA-256 del contenido", valor: dop.contenido_sha256, mono: true, extra: "Coincide con la impresa en el PDF si el documento no fue alterado." },
      ]),
    ];
  } else if (error?.estado === 404) {
    cuerpo = h("div", { class: "verif bad" }, icono("alert"), h("div", {}, h("b", {}, "No existe un DOP con ese código"), h("span", { class: "mono" }, texto)));
  } else if (error?.estado === 429) {
    cuerpo = h("p", { class: "alerta warn" }, error.message);
  } else {
    cuerpo = h("p", { class: "alerta bad" }, error?.message ?? "No se pudo verificar.");
  }

  return {
    titulo: "Verificar DOP",
    contenido: h(
      "div",
      { class: "pantalla-sola" },
      h(
        "main",
        { class: "panel tarjeta-sola verificacion" },
        marca(),
        h("h1", {}, "Verificación de DOP"),
        h("p", { class: "sub" }, "Documento de origen de una tanda de cacao. Esta página muestra solo si existe, si está vigente y su huella."),
        cuerpo,
      ),
    ),
  };
}
