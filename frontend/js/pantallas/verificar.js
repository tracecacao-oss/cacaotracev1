// Verificación pública del DOP, del DPP y del DEX: la página a la que lleva el código QR. No pide sesión, no tiene
// barra lateral y no enlaza al resto de la aplicación. Muestra solo cinco datos: código, cooperativa, fecha
// de emisión, estado y huella. Un código que no existe dice solo eso. Desde la adenda 6, la de un DEX suma
// aparte la declaración aduanera que se agregó al lote después de emitirlo.

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
      // Parte 10: un documento de la cooperativa de demostración lo dice antes que cualquier dato.
      doc.es_demo && h("p", { class: "alerta warn" }, h("b", {}, "Documento de demostración. "), "Sus datos son ficticios y no respaldan ningún cacao real."),
      rejilla([
        { etiqueta: "Código", valor: doc.codigo, mono: true },
        { etiqueta: "Cooperativa", valor: doc.cooperativa },
        { etiqueta: "Fecha de emisión", valor: fecha(doc.emitido_en, { hora: true }) },
        { etiqueta: "Huella SHA-256 del contenido", valor: doc.contenido_sha256, mono: true, extra: "Coincide con la impresa en el PDF si el documento no fue alterado." },
      ]),
      // Adendas 6 y 7: la declaración aduanera que se agregó al lote después de emitir el DEX, aparte, con tres
      // datos: su número, su fecha de numeración y la fecha en que se agregó. Sin pesos ni archivo.
      doc.agregado?.length > 0 && [
        h("h2", { class: "verif-sub" }, "Agregado después de la emisión"),
        h("p", { class: "sub" }, "No forma parte del DEX: su contenido y su huella no cambian."),
        rejilla(
          doc.agregado.flatMap((a) => [
            { etiqueta: a.nombre, valor: a.numero, mono: true },
            { etiqueta: "Fecha de numeración", valor: fecha(a.fecha_numeracion) },
            { etiqueta: "Agregada el", valor: fecha(a.agregado_en, { hora: true }) },
          ]),
        ),
      ],
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
