// Adenda 5, pantalla del productor (#/mi-declaracion): una pregunta por pantalla, en lenguaje simple y de tú.
// Al final, el resumen de sus respuestas, el texto del Anexo A y el botón "Declaro". Con declaración vigente
// muestra sus respuestas, hasta cuándo vale y "Descargar mi declaración". El productor no ve la nota de
// seguimiento: la API no se la envía.

import { descargarArchivo, llamarApi } from "../api.js";
import {
  ESTADO_DECLARACION,
  PAPELES,
  ayudaPregunta,
  conNegritas,
  contextoDe,
  controlPregunta,
  cuestionario,
  etiquetaRespuesta,
  insignia,
  leerControl,
  mostradas,
} from "../declaracion.js";
import { formularioCarga, listaDocumentos } from "../documentos.js";
import { nombreCooperativa } from "../estado.js";
import { cabeceraFicha, fecha, h, icono, rejilla, seccion, toast } from "../ui.js";

const ha = (valor) => `${Number(valor ?? 0).toLocaleString("es-PE", { maximumFractionDigits: 2 })} ha`;
const kilos = (valor) => `${Number(valor ?? 0).toLocaleString("es-PE", { maximumFractionDigits: 2 })} kg`;

export default async function miDeclaracion({ recargar }) {
  const [d, cuest] = await Promise.all([llamarApi("/mi/declaracion"), cuestionario()]);
  const contexto = contextoDe(cuest, d.calculados);
  const contenedor = h("div", {});
  // Para renovar, las respuestas de la última declaración vienen marcadas.
  const respuestas = Object.fromEntries((d.vigente ?? d.por_firmar)?.respuestas.map((r) => [r.codigo, r.valor]) ?? []);
  const valida = ["vigente", "por_vencer"].includes(d.estado);

  const visibles = () => mostradas(cuest, respuestas, contexto);
  const pintar = (...nodos) => {
    contenedor.replaceChildren(...nodos);
    contenedor.scrollIntoView?.({ block: "start" });
  };

  // ---------- Portada: el estado y lo que falta ----------

  function portada() {
    const mensajes = {
      sin_declaracion: "Todavía no tienes tu declaración anual. Son pocas preguntas sobre quién trabaja en tus parcelas, los productos que usas y tus ventas. Sin ella, la organización no puede recibir cacao de tus parcelas.",
      por_firmar: `La organización registró tus respuestas el ${fecha(d.por_firmar?.registrada_en)}. Falta que firmes la hoja en la organización. También puedes declararla tú mismo desde aquí: eso reemplaza a la que espera tu firma.`,
      vencida: `Tu declaración venció el ${fecha(d.vigente?.vigente_hasta)}. Respóndela de nuevo para que la organización pueda seguir recibiendo tu cacao.`,
      vigente: `Tu declaración vale hasta el ${fecha(d.vigente?.vigente_hasta)}.`,
      por_vencer: `Tu declaración vence el ${fecha(d.vigente?.vigente_hasta)}. Puedes renovarla desde ya.`,
    };
    const responder = h("button", { class: "btn btn-primary", type: "button", onclick: () => irA(visibles()[0].codigo) }, valida ? "Responder de nuevo" : "Responder ahora");
    const r = d.vigente ? Object.fromEntries(d.vigente.respuestas.map((x) => [x.codigo, x.valor])) : {};
    const pedidos = [
      r.quien_trabaja === "permanentes" && ["relacion_trabajadores", PAPELES.relacion_trabajadores],
      r.ventas_superan_75_uit && r.ventas_superan_75_uit !== "no" && ["declaracion_renta", PAPELES.declaracion_renta],
    ].filter(Boolean);
    return h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("file")),
        titulo: "Mi declaración anual",
        insignias: insignia(ESTADO_DECLARACION[d.estado]),
        detalle: nombreCooperativa(),
      }),
      seccion({
        titulo: valida ? "Tu declaración" : "Lo que falta",
        contenido: [
          h("p", { class: `alerta ${valida ? "info" : "warn"}` }, mensajes[d.estado]),
          d.aviso_area && h("p", { class: "alerta warn" }, "El área de tus parcelas cambió desde que declaraste: conviene responder de nuevo."),
          h(
            "div",
            { class: "fila-acciones" },
            responder,
            valida &&
              h(
                "button",
                {
                  class: "btn",
                  type: "button",
                  onclick: async (e) => {
                    const b = e.currentTarget;
                    b.classList.add("is-loading");
                    try {
                      await descargarArchivo("/mi/declaracion/hoja", "mi-declaracion-anual.pdf");
                    } catch (error) {
                      toast(error.message, "bad");
                    } finally {
                      b.classList.remove("is-loading");
                    }
                  },
                },
                icono("download"),
                "Descargar mi declaración",
              ),
          ),
        ],
      }),
      valida &&
        seccion({
          titulo: "Mis respuestas",
          sub: `Declarada el ${fecha(d.vigente.declarada_en)}${d.vigente.origen === "productor" ? " desde tu cuenta" : " con tu firma"}.`,
          contenido: rejilla(d.vigente.respuestas.map((x) => ({ etiqueta: x.pregunta, valor: x.etiqueta }))),
        }),
      valida &&
        pedidos.length > 0 &&
        seccion({
          titulo: "Papeles que piden tus respuestas",
          sub: `${pedidos.map(([, texto]) => texto).join(". ")}. Toma una foto clara o sube un PDF.`,
          contenido: [
            h("div", { class: "tbl-box" }, listaDocumentos(d.vigente.documentos.filter((x) => x.tipo !== "hoja_declaracion_productor"), { alCambiar: recargar })),
            formularioCarga({ tipos: pedidos, ruta: "/mi/declaracion/documentos", alCargar: recargar, textoBoton: "Subir" }),
          ],
        }),
      !valida &&
        seccion({
          titulo: "Lo que ya sabemos",
          contenido: rejilla([
            { etiqueta: "Mis parcelas activas", valor: `${d.calculados.parcelas_activas} · ${ha(d.calculados.area_total_ha)}` },
            { etiqueta: "Cacao entregado en los últimos 12 meses", valor: kilos(d.calculados.kilos_12_meses) },
          ]),
        }),
    );
  }

  // ---------- Una pregunta por pantalla ----------

  function irA(codigo) {
    const lista = visibles();
    const i = lista.findIndex((x) => x.codigo === codigo);
    const p = lista[i];
    const control = controlPregunta(p, respuestas[p.codigo], { cuest, sugerencias: d.sugerencias_productos, grande: true });
    const atras = h("button", { class: "btn", type: "button", onclick: () => (i > 0 ? irA(lista[i - 1].codigo) : pintar(portada())) }, "Atrás");
    const siguiente = h("button", { class: "btn btn-primary", type: "submit" }, "Siguiente");
    const formulario = h(
      "form",
      { class: "form pregunta-grande" },
      h("p", { class: "sec" }, `Pregunta ${i + 1} de ${lista.length}`),
      h("h2", { class: "pregunta-titulo" }, p.texto),
      h("p", { class: "panel-sub" }, ayudaPregunta(p, cuest, d.calculados, { personal: false })),
      control,
      h("div", { class: "fila-acciones" }, atras, siguiente),
    );
    formulario.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!formulario.reportValidity()) return;
      respuestas[p.codigo] = leerControl(p, control);
      // Las preguntas que siguen dependen de esta respuesta: se calculan otra vez.
      const nuevas = visibles();
      const j = nuevas.findIndex((x) => x.codigo === p.codigo);
      if (j + 1 < nuevas.length) irA(nuevas[j + 1].codigo);
      else pintar(resumen());
    });
    pintar(h("section", { class: "panel" }, seccion({ titulo: "Mi declaración anual", contenido: formulario })));
    formulario.querySelector("input, select")?.focus();
  }

  // ---------- Resumen, texto del Anexo A y "Declaro" ----------

  function resumen() {
    const lista = visibles();
    const declaro = h("button", { class: "btn btn-primary", type: "button" }, "Declaro");
    declaro.addEventListener("click", async () => {
      declaro.classList.add("is-loading");
      try {
        const cuerpo = { respuestas: Object.fromEntries(lista.map((x) => [x.codigo, respuestas[x.codigo]])), declaro: true };
        await llamarApi("/mi/declaracion", { metodo: "POST", cuerpo });
        toast("Tu declaración quedó vigente.");
        recargar();
      } catch (error) {
        toast(error.message, "bad");
        declaro.classList.remove("is-loading");
      }
    });
    const organizacion = nombreCooperativa();
    const texto = cuest.anexo
      .filter((b) => b.en_pantalla)
      .map((b) => h("p", { class: b.tipo === "literal" ? "anexo-literal" : "anexo-parrafo" }, conNegritas(b.texto.replaceAll("{organizacion}", organizacion))));
    return h(
      "section",
      { class: "panel" },
      seccion({
        titulo: "Revisa tus respuestas",
        contenido: h(
          "ul",
          { class: "casillas" },
          lista.map((x) =>
            h(
              "li",
              { class: "casilla" },
              h(
                "div",
                { class: "casilla-h" },
                h("div", {}, h("span", { class: "sec" }, x.texto), h("b", {}, etiquetaRespuesta(x, respuestas[x.codigo], cuest))),
                h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => irA(x.codigo) }, "Cambiar"),
              ),
            ),
          ),
        ),
      }),
      seccion({
        titulo: "Lo que declaras",
        sub: "Lee el texto antes de tocar «Declaro».",
        contenido: h("div", { class: "anexo-texto" }, texto),
      }),
      seccion({
        titulo: "Confirmar",
        contenido: [
          h("p", { class: "panel-sub" }, "Al tocar «Declaro», tu declaración vale por 12 meses y la organización la puede mostrar a sus compradores."),
          h("div", { class: "fila-acciones" }, h("button", { class: "btn", type: "button", onclick: () => irA(lista[lista.length - 1].codigo) }, "Atrás"), declaro),
        ],
      }),
    );
  }

  pintar(portada());
  return {
    titulo: "Mi declaración",
    migas: [["Mi declaración"]],
    cabecera: null,
    contenido: contenedor,
  };
}
