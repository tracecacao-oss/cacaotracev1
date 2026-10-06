// Verificación pública del DOP, del DPP y del DEX: la página a la que lleva el código QR. No pide sesión, no tiene
// barra lateral y no enlaza al resto de la aplicación. Muestra solo cinco datos: código, cooperativa, fecha
// de emisión, estado y huella. Un código que no existe dice solo eso.

import { llamarApi } from "../api.js";
import { fecha, h, icono, marca, rejilla } from "../ui.js";

const TIPOS = {
  dop: {
    sigla: "DOP",
    ruta: "/publico/dops/",
    vigente: "Este documento de origen fue emitido por la cooperativa y no ha sido anulado.",
    anulado: "La cooperativa anuló este documento de origen.",
    sub: "Documento de origen de una tanda de cacao. Esta página muestra solo si existe, si está vigente y su huella.",
  },
  dpp: {
    sigla: "DPP",
    ruta: "/publico/dpps/",
    vigente: "Este documento del procesamiento fue emitido por la cooperativa y no ha sido anulado.",
    anulado: "La cooperativa anuló este documento del procesamiento.",
    sub: "Documento del procesamiento de un lote de cacao. Esta página muestra solo si existe, si está vigente y su huella.",
  },
  dex: {
    sigla: "DEX",
    ruta: "/publico/dex/",
    vigente: "Este expediente de exportación fue emitido por la cooperativa y no ha sido anulado.",
    anulado: "La cooperativa anuló este expediente de exportación.",
    sub: "Expediente de exportación de un lote de cacao. Esta página muestra solo si existe, si está vigente y su huella. No declara un nivel de riesgo.",
  },
};

export default async function verificar({ parametros: [tipo, codigo] }) {
  const t = TIPOS[tipo];
  const texto = decodeURIComponent(codigo).trim().toUpperCase();
  let doc = null;
  let error = null;
  try {
    doc = await llamarApi(`${t.ruta}${encodeURIComponent(texto)}`, { conToken: false, sinConsulta: true });
  } catch (e) {
    error = e;
  }

  let cuerpo;
  if (doc) {
    const vigente = doc.estado === "vigente";
    cuerpo = [
      h(
        "div",
        { class: `verif ${vigente ? "" : "bad"}`.trim() },
        icono(vigente ? "check" : "alert"),
        h("div", {}, h("b", {}, `${t.sigla} ${vigente ? "vigente" : "anulado"}`), h("span", {}, vigente ? t.vigente : t.anulado)),
      ),
      rejilla([
        { etiqueta: "Código", valor: doc.codigo, mono: true },
        { etiqueta: "Cooperativa", valor: doc.cooperativa },
        { etiqueta: "Fecha de emisión", valor: fecha(doc.emitido_en, { hora: true }) },
        { etiqueta: "Huella SHA-256 del contenido", valor: doc.contenido_sha256, mono: true, extra: "Coincide con la impresa en el PDF si el documento no fue alterado." },
      ]),
    ];
  } else if (error?.estado === 404) {
    cuerpo = h("div", { class: "verif bad" }, icono("alert"), h("div", {}, h("b", {}, `No existe un ${t.sigla} con ese código`), h("span", { class: "mono" }, texto)));
  } else if (error?.estado === 429) {
    cuerpo = h("p", { class: "alerta warn" }, error.message);
  } else {
    cuerpo = h("p", { class: "alerta bad" }, error?.message ?? "No se pudo verificar.");
  }

  return {
    titulo: `Verificar ${t.sigla}`,
    contenido: h(
      "div",
      { class: "pantalla-sola" },
      h("main", { class: "panel tarjeta-sola verificacion" }, marca(), h("h1", {}, `Verificación de ${t.sigla}`), h("p", { class: "sub" }, t.sub), cuerpo),
    ),
  };
}
