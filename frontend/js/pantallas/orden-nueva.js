// Nueva orden en dos pasos: 1) el importador (uno registrado o uno nuevo) y 2) cantidad, tolerancia, calidad,
// destino y entrega. La partida del Sistema Armonizado es siempre 1801, cacao en grano.

import { llamarApi } from "../api.js";
import { seccionesExportacion } from "../exportacion.js";
import { campo, h, icono, toast } from "../ui.js";
import { camposImportador, cuerpoImportador } from "./importadores.js";

const PASOS = ["Importador", "Cantidad, calidad, destino y entrega"];

export default async function ordenNueva({ navegar }) {
  const [importadores, calidades] = await Promise.all([llamarApi("/importadores"), llamarApi("/calidades")]);
  const activos = importadores.filter((i) => i.activo);
  const st = { paso: 0, importador: null };
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });
  const avisar = (texto) => {
    mensaje.textContent = texto;
    mensaje.hidden = !texto;
  };

  // ---------- Paso 1: importador ----------
  const nuevo = h("form", { class: "form", hidden: activos.length > 0 }, camposImportador());
  const opciones = h(
    "div",
    { class: "opciones", role: "radiogroup", "aria-label": "Importador" },
    activos.map((i) =>
      h(
        "label",
        { class: "opcion opcion-doc" },
        h("input", { type: "radio", name: "importador", value: i.id, onchange: () => ((nuevo.hidden = true), actualizar()) }),
        h("span", {}, h("b", {}, i.razon_social), h("span", { class: "sec" }, `${i.pais} · ${i.correo}`)),
      ),
    ),
    h(
      "label",
      { class: "opcion opcion-doc" },
      h("input", { type: "radio", name: "importador", value: "nuevo", checked: !activos.length, onchange: () => ((nuevo.hidden = false), actualizar()) }),
      h("span", {}, h("b", {}, "Registrar un importador nuevo"), h("span", { class: "sec" }, "Nombre, dirección, país, correo y EORI.")),
    ),
  );
  const paso1 = h("div", { class: "form" }, opciones, nuevo);
  const elegido = () => opciones.querySelector("input:checked")?.value ?? null;

  // ---------- Paso 2: cantidad, calidad, destino y entrega ----------
  const activas = calidades.filter((c) => c.activo);
  const pais = campo({ etiqueta: "País de destino", name: "pais_destino", required: true, maxlength: 200 });
  const formOrden = h(
    "form",
    { class: "form" },
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Cantidad (kg de masa neta)", name: "cantidad_kg", type: "number", step: "0.01", min: "0.01", inputmode: "decimal", required: true, class: "input mono" }),
      campo({ etiqueta: "Tolerancia (%)", name: "tolerancia_pct", type: "number", step: "0.1", min: "0", max: "100", inputmode: "decimal", value: "0", required: true, class: "input mono", ayuda: "Variación admitida sobre la cantidad." }),
    ),
    campo({
      etiqueta: "Calidad",
      name: "calidad_id",
      required: true,
      opciones: [["", activas.length ? "Elige la calidad…" : "La cooperativa no tiene calidades activas"], ...activas.map((c) => [c.id, c.nombre])],
      ayuda: "El lote solo toma stock de esta calidad.",
    }),
    h("div", { class: "grid2" }, pais, campo({ etiqueta: "Puerto o ciudad de destino", name: "lugar_destino", required: true, maxlength: 200 })),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Fecha de entrega", name: "fecha_entrega", type: "date", required: true }),
      campo({ etiqueta: "Referencia del importador (opcional)", name: "referencia_importador", maxlength: 200, ayuda: "El número de orden que usa el importador." }),
    ),
    h("p", { class: "panel-sub" }, "Partida del Sistema Armonizado: 1801, cacao en grano."),
  );
  const paso2 = h("div", { hidden: true }, formOrden);

  // ---------- Navegación ----------
  const indicador = h("div", { class: "pasos" }, PASOS.map((p, i) => h("span", { "aria-current": i === 0 ? "step" : "false" }, `${i + 1}.`, h("span", { class: "paso-t" }, ` ${p}`))));
  const salir = h("a", { class: "btn btn-ghost", href: "#/exportacion/ordenes" }, "Cancelar");
  const atras = h("button", { class: "btn btn-ghost", type: "button", hidden: true }, "Atrás");
  const siguiente = h("button", { class: "btn btn-primary", type: "button" }, "Siguiente");
  const crear = h("button", { class: "btn btn-primary", type: "button", hidden: true }, icono("check"), "Crear orden");

  const validos = (formulario) => [...formulario.querySelectorAll("input,select,textarea")].filter((c) => !c.closest("[hidden]")).every((c) => c.reportValidity());

  function actualizar() {
    siguiente.hidden = st.paso === 1;
    crear.hidden = st.paso === 0;
    siguiente.disabled = st.paso === 0 && !elegido();
  }
  function irA(paso) {
    st.paso = paso;
    paso1.hidden = paso !== 0;
    paso2.hidden = paso !== 1;
    [...indicador.children].forEach((s, i) => s.setAttribute("aria-current", i === paso ? "step" : "false"));
    atras.hidden = paso === 0;
    avisar("");
    actualizar();
    window.scrollTo(0, 0);
  }
  atras.addEventListener("click", () => irA(0));
  siguiente.addEventListener("click", async () => {
    const valor = elegido();
    if (valor !== "nuevo") {
      st.importador = activos.find((i) => i.id === valor);
    } else {
      if (!validos(nuevo)) return;
      siguiente.classList.add("is-loading");
      try {
        // Un importador nuevo se registra al pasar al segundo paso; queda en la lista aunque se cancele.
        st.importador = await llamarApi("/importadores", { metodo: "POST", cuerpo: cuerpoImportador(Object.fromEntries(new FormData(nuevo))) });
        activos.push(st.importador);
      } catch (error) {
        avisar(error.message);
        return;
      } finally {
        siguiente.classList.remove("is-loading");
      }
    }
    const entrada = pais.querySelector("input");
    if (!entrada.value) entrada.value = st.importador.pais;
    irA(1);
  });
  crear.addEventListener("click", async () => {
    if (!validos(formOrden)) return;
    const d = Object.fromEntries(new FormData(formOrden));
    crear.classList.add("is-loading");
    crear.disabled = true;
    try {
      const orden = await llamarApi("/ordenes", {
        metodo: "POST",
        cuerpo: {
          importador_id: st.importador.id,
          cantidad_kg: d.cantidad_kg,
          tolerancia_pct: d.tolerancia_pct || "0",
          calidad_id: d.calidad_id,
          pais_destino: d.pais_destino,
          lugar_destino: d.lugar_destino,
          fecha_entrega: d.fecha_entrega,
          referencia_importador: d.referencia_importador?.trim() || null,
        },
      });
      toast(`Orden ${orden.codigo} registrada.`);
      navegar(`#/ordenes/${orden.id}`);
    } catch (error) {
      avisar(error.message);
    } finally {
      crear.classList.remove("is-loading");
      crear.disabled = false;
    }
  });
  actualizar();

  return {
    titulo: "Nueva orden",
    antetitulo: "Exportación",
    descripcion: "Registra lo que pidió el importador y a dónde va. El lote se arma después, desde la orden.",
    migas: [["Exportación", "#/exportacion"], ["Órdenes", "#/exportacion/ordenes"], ["Nueva"]],
    secciones: seccionesExportacion(),
    contenido: h(
      "section",
      { class: "panel asistente-tanda" },
      h("div", { class: "panel-h" }, indicador),
      h("div", { class: "panel-b" }, paso1, paso2, mensaje),
      h("div", { class: "modal-f" }, salir, atras, siguiente, crear),
    ),
  };
}
