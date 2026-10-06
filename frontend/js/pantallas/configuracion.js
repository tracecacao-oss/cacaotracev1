// Configuración de la cooperativa (Parte 5): los parámetros de la recepción, con una explicación breve
// de cada uno. Todo el personal la ve; solo el administrador la cambia. Un cambio no altera las
// tandas ya validadas: cada decisión guarda los valores con que se evaluó.

import { llamarApi } from "../api.js";
import { rolEfectivo } from "../estado.js";
import { campo, enviarCon, h, icono, rejilla, seccion, toast } from "../ui.js";
import { seccionesCooperativa } from "./vacia.js";

const PARAMETROS = [
  {
    nombre: "tope_kg_seco_ha_anio",
    etiqueta: "Tope de kilos secos por hectárea al año",
    ayuda: "Kilos de grano seco por hectárea al año que la cooperativa considera creíbles. Si el volumen de una parcela en 365 días lo supera, la tanda muestra una alerta. Sin tope no se registran tandas.",
    atributos: { type: "number", step: "0.01", min: "0.01", inputmode: "decimal" },
    unidad: "kg/ha/año",
  },
  {
    nombre: "factor_baba_a_seco",
    etiqueta: "Factor de baba a seco",
    ayuda: "Convierte los kilos en baba a su equivalente en seco para compararlos contra el tope. Es una estimación; el peso seco real se mide en el proceso.",
    atributos: { type: "number", step: "0.001", min: "0.001", max: "0.999", inputmode: "decimal" },
  },
  {
    nombre: "rendimiento_min",
    etiqueta: "Rendimiento mínimo de baba a seco",
    ayuda: "Límite inferior de la banda de rendimiento. Se usa en el proceso (Parte 6).",
    atributos: { type: "number", step: "0.001", min: "0.001", max: "0.999", inputmode: "decimal" },
  },
  {
    nombre: "rendimiento_max",
    etiqueta: "Rendimiento máximo de baba a seco",
    ayuda: "Límite superior de la banda de rendimiento. Se usa en el proceso (Parte 6).",
    atributos: { type: "number", step: "0.001", min: "0.001", max: "0.999", inputmode: "decimal" },
  },
  {
    nombre: "dias_max_cosecha_entrega_baba",
    etiqueta: "Días máximos entre cosecha y entrega, en baba",
    ayuda: "Si pasan más días entre el fin de la cosecha y la entrega en baba, la tanda muestra una alerta.",
    atributos: { type: "number", step: "1", min: "0", max: "3650", inputmode: "numeric" },
    unidad: "días",
  },
  {
    nombre: "dias_max_cosecha_entrega_seco",
    etiqueta: "Días máximos entre cosecha y entrega, en seco",
    ayuda: "Lo mismo para el cacao entregado seco.",
    atributos: { type: "number", step: "1", min: "0", max: "3650", inputmode: "numeric" },
    unidad: "días",
  },
  {
    nombre: "tolerancia_peso_guia_pct",
    etiqueta: "Tolerancia entre el peso del documento de entrega y el de la balanza",
    ayuda: "Diferencia admitida, en porcentaje. Si el peso que declara el documento difiere más, la tanda muestra una alerta.",
    atributos: { type: "number", step: "0.1", min: "0", max: "100", inputmode: "decimal" },
    unidad: "%",
  },
  {
    nombre: "dias_max_emision_doc_entrega",
    etiqueta: "Días para emitir la liquidación de compra",
    ayuda: "La liquidación de compra se emite el día de la recepción o hasta estos días después.",
    atributos: { type: "number", step: "1", min: "0", max: "365", inputmode: "numeric" },
    unidad: "días",
  },
];

function aviso(configuracion) {
  const faltas = [];
  if (configuracion.tope_kg_seco_ha_anio == null) faltas.push("Falta fijar el tope de kilos por hectárea: sin él no se registran tandas.");
  if (!configuracion.codigo_cooperativa) faltas.push("Falta el código de la cooperativa, que va en cada DOP. Lo fija el equipo CacaoTrace.");
  if (!faltas.length) return null;
  return h("div", { class: "verif warn" }, icono("alert"), h("div", {}, h("b", {}, "La recepción todavía no está lista"), faltas.map((f) => h("div", { class: "sec" }, f))));
}

export default async function configuracion({ recargar }) {
  const conf = await llamarApi("/configuracion");
  const admin = rolEfectivo() === "admin_cooperativa";

  let contenido;
  if (admin) {
    const boton = h("button", { class: "btn btn-primary", type: "submit" }, "Guardar configuración");
    const formulario = h(
      "form",
      { class: "form formulario-angosto" },
      PARAMETROS.map((p) =>
        campo({
          etiqueta: p.unidad ? `${p.etiqueta} (${p.unidad})` : p.etiqueta,
          name: p.nombre,
          value: conf[p.nombre] ?? "",
          required: true,
          class: "input mono",
          ayuda: p.ayuda,
          ...p.atributos,
        }),
      ),
      h("p", { class: "panel-sub" }, "Los valores iniciales, salvo la banda de rendimiento, son propuestas por confirmar. Cada cambio queda en la auditoría con el valor anterior y no altera las tandas ya validadas."),
      boton,
    );
    enviarCon(formulario, boton, async (datos) => {
      if (Number(datos.rendimiento_min) > Number(datos.rendimiento_max)) throw new Error("El rendimiento mínimo no puede superar al máximo.");
      await llamarApi("/configuracion", { metodo: "PUT", cuerpo: datos });
      toast("Configuración guardada.");
      recargar();
    });
    contenido = formulario;
  } else {
    contenido = rejilla(
      PARAMETROS.map((p) => ({
        etiqueta: p.etiqueta,
        valor: conf[p.nombre] == null ? null : `${conf[p.nombre]}${p.unidad ? ` ${p.unidad}` : ""}`,
        mono: true,
        extra: p.ayuda,
      })),
    );
  }

  return {
    titulo: "Configuración",
    antetitulo: "Cooperativa",
    descripcion: admin ? "Los parámetros con que se evalúa cada tanda en la recepción." : "Los parámetros con que se evalúa cada tanda. Solo el administrador los cambia.",
    migas: [["Cooperativa", "#/cooperativa"], ["Configuración"]],
    secciones: seccionesCooperativa(),
    contenido: [
      aviso(conf),
      h(
        "section",
        { class: "panel inspector" },
        seccion({ titulo: "Código de la cooperativa", sub: "Va en el código de cada DOP. Lo fija el equipo CacaoTrace y no cambia.", contenido: rejilla([{ etiqueta: "Código", valor: conf.codigo_cooperativa, mono: true }]) }),
        seccion({ titulo: "Recepción de tandas", contenido }),
      ),
    ],
  };
}
