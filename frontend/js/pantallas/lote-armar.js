// Armado del lote: arriba la cantidad pedida, la tolerancia y la suma seleccionada en vivo; al centro las
// tandas finales de la calidad pedida, de la más antigua a la más nueva, con la sugerencia FIFO ya marcada.
// Si la selección se aparta del orden FIFO aparece el aviso y el campo del motivo; si el stock no alcanza,
// se muestran los kilos que faltan y "Confirmar lote" queda apagado.

import { llamarApi } from "../api.js";
import { seccionesExportacion } from "../exportacion.js";
import { kilos } from "../textos.js";
import { fecha, h, icono, seccion, toast } from "../ui.js";

const MOTIVO_MINIMO = 30;
const centimos = (v) => Math.round(Number(v || 0) * 100);

export default async function loteArmar({ parametros: [id], navegar }) {
  const [lote, sug] = await Promise.all([llamarApi(`/lotes/${id}`), llamarApi(`/lotes/${id}/sugerencia-fifo`)]);
  const migas = [["Exportación", "#/exportacion"], ["Lotes", "#/exportacion/lotes"], [lote.codigo, `#/lotes-exportacion/${lote.id}`], ["Armar"]];
  if (lote.estado !== "en_armado") {
    return {
      titulo: `Armar ${lote.codigo}`,
      migas,
      secciones: seccionesExportacion(),
      contenido: h("section", { class: "panel" }, h("p", { class: "panel-sub" }, "El lote ya no está en armado: su selección no cambia. "), h("a", { class: "btn", href: `#/lotes-exportacion/${lote.id}` }, "Ver el lote")),
    };
  }

  const elegidas = new Map(lote.asignaciones.map((a) => [a.tanda_final_id, a]));
  const sugeridas = new Map(sug.asignaciones.map((a) => [a.tanda_final_id, centimos(a.kg_asignados)]));
  // Las candidatas y, al final, lo que estaba elegido y ya no está en stock (se marca para quitarlo).
  const filas = [...sug.candidatas, ...lote.asignaciones.filter((a) => !sug.candidatas.some((c) => c.tanda_final_id === a.tanda_final_id))];
  const entradas = new Map();

  const suma = h("b", { class: "mono" });
  const estadoSuma = h("span", { class: "sec" });
  const aviso = h("div", { class: "alerta warn", hidden: true, role: "status" }, h("b", {}, "La selección se aparta del orden FIFO."), " Escribe por qué: el motivo queda en el lote y llega al informe de hallazgos.");
  const motivo = h("textarea", { class: "input texto-libre", name: "motivo_desviacion", maxlength: 4000, rows: 3, minlength: MOTIVO_MINIMO });
  const campoMotivo = h("label", { class: "field", hidden: true }, `Motivo (mínimo ${MOTIVO_MINIMO} caracteres)`, motivo);
  const mensaje = h("p", { class: "alerta bad", role: "alert", hidden: true });
  const confirmar = h("button", { class: "btn btn-primary", type: "button" }, icono("check"), "Confirmar lote");
  const guardar = h("button", { class: "btn", type: "button" }, "Guardar selección");
  const restablecer = h("button", { class: "btn btn-ghost", type: "button" }, "Volver a la sugerencia FIFO");

  function seleccion() {
    return filas
      .map((f) => ({ tanda_final_id: f.tanda_final_id, kg_asignados: entradas.get(f.tanda_final_id).value }))
      .filter((a) => centimos(a.kg_asignados) > 0)
      .map((a) => ({ ...a, kg_asignados: (centimos(a.kg_asignados) / 100).toFixed(2) }));
  }

  function actualizar() {
    const elegida = seleccion();
    const total = elegida.reduce((s, a) => s + centimos(a.kg_asignados), 0);
    const [min, max] = [centimos(sug.minimo_kg), centimos(sug.maximo_kg)];
    suma.textContent = kilos(total / 100);
    const dentro = total >= min && total <= max;
    estadoSuma.textContent = dentro ? "Dentro de lo que admite la orden." : total < min ? `Faltan ${kilos((min - total) / 100)} para el mínimo.` : `Sobran ${kilos((total - max) / 100)} sobre el máximo.`;
    estadoSuma.className = dentro ? "sec" : "sec texto-aviso";
    const desvia = elegida.length !== sugeridas.size || elegida.some((a) => sugeridas.get(a.tanda_final_id) !== centimos(a.kg_asignados));
    aviso.hidden = !desvia;
    campoMotivo.hidden = !desvia;
    motivo.required = desvia;
    for (const f of filas) {
      const entrada = entradas.get(f.tanda_final_id);
      entrada.closest("tr").classList.toggle("fila-elegida", centimos(entrada.value) > 0);
    }
    confirmar.disabled = !sug.alcanza || !dentro || (desvia && motivo.value.trim().length < MOTIVO_MINIMO);
    confirmar.title = !sug.alcanza ? "El stock de la calidad no alcanza para la orden." : !dentro ? "La suma está fuera de lo que admite la orden." : desvia && motivo.value.trim().length < MOTIVO_MINIMO ? "Escribe el motivo de la desviación." : "Confirma el lote y descuenta los saldos.";
  }

  const tabla = h(
    "div",
    { class: "tbl-box" },
    h(
      "table",
      { class: "tabla tabla-armado" },
      h("thead", {}, h("tr", {}, h("th", {}, "Tanda final"), h("th", { class: "ocultar-sm" }, "Ingreso al stock"), h("th", { class: "num" }, "Saldo"), h("th", { class: "num" }, "Sugerencia"), h("th", { class: "num" }, "Kilos a tomar"))),
      h(
        "tbody",
        {},
        filas.map((f) => {
          const fuera = !sug.candidatas.some((c) => c.tanda_final_id === f.tanda_final_id);
          const entrada = h("input", {
            class: "input mono",
            type: "number",
            step: "0.01",
            min: "0",
            max: fuera ? "0" : f.saldo_kg,
            inputmode: "decimal",
            "aria-label": `Kilos a tomar de ${f.codigo}`,
            value: elegidas.get(f.tanda_final_id)?.kg_asignados ?? "",
            oninput: actualizar,
          });
          entradas.set(f.tanda_final_id, entrada);
          return h(
            "tr",
            {},
            h("td", {}, h("a", { href: `#/tandas-finales/${f.tanda_final_id}`, class: "mono" }, f.codigo), h("span", { class: "sec" }, [f.corrida_codigo, f.dpp?.codigo].filter(Boolean).join(" · ")), fuera && h("span", { class: "badge bad" }, h("span", { class: "dot" }), "Ya no está en stock: quítala")),
            h("td", { class: "ocultar-sm" }, fecha(f.ingreso_stock_en, { hora: true })),
            h("td", { class: "num mono" }, kilos(f.saldo_kg)),
            h("td", { class: "num mono" }, f.kg_sugeridos && Number(f.kg_sugeridos) > 0 ? kilos(f.kg_sugeridos) : "—"),
            h("td", { class: "num" }, entrada),
          );
        }),
      ),
    ),
  );

  async function guardarSeleccion() {
    return llamarApi(`/lotes/${lote.id}/asignaciones`, { metodo: "PUT", cuerpo: { asignaciones: seleccion() } });
  }
  function avisar(texto) {
    mensaje.textContent = texto;
    mensaje.hidden = !texto;
  }
  restablecer.addEventListener("click", () => {
    for (const f of filas) entradas.get(f.tanda_final_id).value = sugeridas.has(f.tanda_final_id) ? (sugeridas.get(f.tanda_final_id) / 100).toFixed(2) : "";
    actualizar();
  });
  guardar.addEventListener("click", async () => {
    avisar("");
    guardar.classList.add("is-loading");
    try {
      await guardarSeleccion();
      toast("Selección guardada.");
    } catch (error) {
      avisar(error.message);
    } finally {
      guardar.classList.remove("is-loading");
    }
  });
  confirmar.addEventListener("click", async () => {
    avisar("");
    if (!motivo.closest("[hidden]") && !motivo.reportValidity()) return;
    confirmar.classList.add("is-loading");
    confirmar.disabled = true;
    try {
      await guardarSeleccion();
      const armado = await llamarApi(`/lotes/${lote.id}/confirmar`, { metodo: "POST", cuerpo: { motivo_desviacion: motivo.closest("[hidden]") ? null : motivo.value.trim() } });
      toast(`Lote ${armado.codigo} confirmado: los saldos se descontaron del stock.`);
      navegar(`#/lotes-exportacion/${armado.id}`);
    } catch (error) {
      avisar(error.message);
      confirmar.classList.remove("is-loading");
      actualizar();
    }
  });
  motivo.addEventListener("input", actualizar);
  actualizar();

  const resumen = h(
    "div",
    { class: "armado-resumen" },
    h("div", {}, h("span", { class: "sec" }, "Cantidad pedida"), h("b", { class: "mono" }, kilos(sug.cantidad_kg))),
    h("div", {}, h("span", { class: "sec" }, "Tolerancia"), h("b", { class: "mono" }, `± ${lote.tolerancia_pct} %`), h("span", { class: "sec" }, `${kilos(sug.minimo_kg)} a ${kilos(sug.maximo_kg)}`)),
    h("div", { "aria-live": "polite" }, h("span", { class: "sec" }, "Seleccionado"), suma, estadoSuma),
  );

  return {
    titulo: `Armar ${lote.codigo}`,
    antetitulo: "Exportación",
    descripcion: `Orden ${lote.orden.codigo} · ${lote.importador} · ${lote.calidad}. La sugerencia FIFO toma el stock del más antiguo al más nuevo y no reserva nada.`,
    migas,
    secciones: seccionesExportacion(),
    contenido: h(
      "section",
      { class: "panel inspector" },
      resumen,
      !sug.alcanza && h("div", { class: "verif bad" }, icono("alert"), h("div", {}, h("b", {}, `Faltan ${kilos(sug.faltan_kg)} de stock de ${lote.calidad}`), h("span", {}, `Hay ${kilos(sug.disponible_kg)} disponibles y la orden necesita al menos ${kilos(sug.minimo_kg)}. El lote no se puede confirmar.`))),
      seccion({
        titulo: `Tandas finales de ${lote.calidad}`,
        sub: "De la más antigua a la más nueva. Puedes quitar una, agregar otra o cambiar los kilos.",
        acciones: restablecer,
        contenido: filas.length ? tabla : h("p", { class: "panel-sub" }, `No hay stock de ${lote.calidad}.`),
      }),
      h("div", { class: "form armado-pie" }, aviso, campoMotivo, mensaje, h("div", { class: "fila-acciones" }, h("a", { class: "btn btn-ghost", href: `#/lotes-exportacion/${lote.id}` }, "Salir"), guardar, confirmar)),
    ),
  };
}
