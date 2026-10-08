// Auditoría: tabla de acciones con filtros por fecha, usuario y acción.

import { llamarApi } from "../api.js";
import { ROTULOS_ROL } from "../estado.js";
import { campo, cargando, errorDeCarga, fecha, h, paginador, reemplazar, vacio } from "../ui.js";

const ACCIONES = [
  ["", "Todas las acciones"],
  ["cooperativa.", "Cooperativa"],
  ["usuario.", "Usuarios"],
  ["productor.", "Productores"],
  ["parcela.", "Parcelas"],
  ["documento.", "Documentos"],
  ["superposicion.", "Superposiciones"],
  ["analisis.", "Análisis de cobertura"],
  ["imagenes.", "Imágenes satelitales"],
  ["revision_imagenes.", "Revisiones de imágenes"],
  ["exencion.", "Exenciones"],
  ["configuracion.", "Configuración"],
  ["lugar.", "Lugares"],
  ["tanda.", "Tandas"],
  ["dop.", "DOP"],
  ["plantilla.", "Plantilla de proceso"],
  ["calidad.", "Calidades"],
  ["corrida.", "Corridas"],
  ["dpp.", "DPP"],
  ["importador.", "Importadores"],
  ["orden.", "Órdenes de compra"],
  ["lote.", "Lotes de exportación"],
  ["dex.", "DEX"],
  ["certificacion.", "Certificaciones"],
  ["superadmin.", "Consultas de soporte"],
];

const TEXTO_ACCION = {
  "cooperativa.crear": "Creó la cooperativa",
  "cooperativa.editar": "Editó la cooperativa",
  "cooperativa.suspender": "Suspendió la cooperativa",
  "cooperativa.reactivar": "Reactivó la cooperativa",
  "usuario.crear": "Creó una cuenta",
  "usuario.editar": "Editó una cuenta",
  "usuario.desactivar": "Desactivó una cuenta",
  "usuario.reactivar": "Reactivó una cuenta",
  "usuario.restablecer_clave": "Restableció una contraseña",
  "usuario.cambiar_clave": "Cambió su contraseña",
  "productor.crear": "Registró un productor",
  "productor.acceso_crear": "Creó el acceso de un productor",
  "productor.acceso_desactivar": "Desactivó el acceso de un productor",
  "productor.consentimiento": "Registró el consentimiento de datos",
  "productor.editar": "Editó la ficha de un productor",
  "productor.cerrar_afiliacion": "Cerró la afiliación de un productor",
  "documento.cargar": "Cargó un documento",
  "documento.anular": "Anuló un documento",
  "parcela.crear": "Registró una parcela",
  "parcela.editar": "Editó los datos de una parcela",
  "parcela.editar_geometria": "Cambió la geometría de una parcela",
  "parcela.desactivar": "Desactivó una parcela",
  "superposicion.aceptar": "Aceptó una superposición",
  "productor.carga_masiva": "Cargó productores desde una hoja",
  "analisis.solicitar": "Solicitó un análisis de cobertura",
  "visita.registrar": "Registró una visita de campo",
  "visita.anular": "Anuló una visita de campo",
  "imagenes.generar": "Pidió las imágenes satelitales de una parcela",
  "imagenes.cargar_externa": "Cargó una imagen externa",
  "revision_imagenes.registrar": "Registró una revisión de imágenes",
  "revision_imagenes.anular": "Anuló una revisión de imágenes",
  "documento.cotejar": "Cotejó un documento en fuente",
  "exencion.declarar": "Declaró que un documento no aplica",
  "exencion.retirar": "Retiró una exención",
  "parcela.habilitar": "Habilitó una parcela",
  "parcela.observar": "Pasó una parcela a observada (sistema)",
  "parcela.excluir": "Excluyó una parcela",
  "superadmin.consultar_cooperativa": "Consultó la cooperativa (soporte)",
  "configuracion.cambiar": "Cambió la configuración de la recepción",
  "lugar.crear": "Creó un lugar",
  "lugar.editar": "Editó un lugar",
  "tanda.registrar": "Registró una tanda",
  "tanda.editar": "Corrigió una tanda",
  "tanda.validar": "Validó una tanda",
  "tanda.observar": "Observó una tanda",
  "tanda.anular": "Anuló una tanda",
  "dop.emitir": "Emitió un DOP",
  "dop.anular": "Anuló un DOP",
  "plantilla.cambiar": "Cambió la plantilla de proceso",
  "calidad.crear": "Creó una calidad",
  "calidad.editar": "Editó una calidad",
  "corrida.crear": "Creó una corrida",
  "corrida.agregar_tanda": "Agregó una tanda a una corrida",
  "corrida.quitar_tanda": "Quitó una tanda de una corrida",
  "corrida.iniciar": "Inició una corrida",
  "corrida.registrar_etapa": "Registró una etapa",
  "corrida.consolidar": "Consolidó una corrida",
  "corrida.anular": "Anuló una corrida",
  "dpp.emitir": "Emitió un DPP",
  "dpp.anular": "Anuló un DPP",
  "importador.crear": "Registró un importador",
  "importador.editar": "Editó un importador",
  "orden.crear": "Registró una orden de compra",
  "orden.editar": "Editó una orden de compra",
  "orden.anular": "Anuló una orden de compra",
  "lote.crear": "Creó un lote de exportación",
  "lote.cambiar_seleccion": "Cambió la selección de un lote",
  "lote.confirmar": "Confirmó un lote de exportación",
  "lote.anular": "Anuló un lote de exportación",
  "lote.recomprobar": "Recomprobó un lote",
  "lote.cambiar_estado": "Cambió el estado de un lote (recomprobación)",
  "lote.alerta": "Alerta en un lote cerrado",
  "dex.emitir": "Emitió un DEX",
  "dex.descargar": "Descargó los archivos de un DEX",
  "dex.anular": "Anuló un DEX",
  "certificacion.registrar": "Registró una certificación",
  "certificacion.editar": "Editó o anuló una certificación",
  "plataforma.configurar": "Cambió la clasificación del país",
};

/** Un valor ISO del detalle se muestra dd/mm/aaaa (con hora de Lima si la trae); lo demás, tal cual. */
function legible(valor) {
  if (typeof valor !== "string") return valor;
  if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) return fecha(valor);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(valor) && !Number.isNaN(Date.parse(valor))) return fecha(valor, { hora: true });
  return valor;
}

function resumen(detalle) {
  const partes = Object.entries(detalle ?? {}).map(([campo, valor]) => {
    if (valor && typeof valor === "object" && "antes" in valor) return `${campo}: ${legible(valor.antes) ?? "—"} → ${legible(valor.despues) ?? "—"}`;
    if (campo === "geometria_anterior") return "geometría anterior guardada";
    return `${campo}: ${typeof valor === "object" ? JSON.stringify(valor) : legible(valor)}`;
  });
  return partes.join(" · ");
}

export default async function auditoria() {
  const filtros = { desde: "", hasta: "", usuario_id: "", accion: "" };
  let pagina = 1;
  const lista = h("div", {}, cargando());

  // El filtro por usuario lista al personal de la cooperativa.
  const personal = await llamarApi("/usuarios", { parametros: { por_pagina: 100 } }).catch(() => ({ items: [] }));

  async function cargar() {
    try {
      const datos = await llamarApi("/auditoria", { parametros: { ...filtros, pagina, por_pagina: 50 } });
      reemplazar(lista, tabla(datos));
    } catch (error) {
      lista.replaceChildren(errorDeCarga(error));
    }
  }

  function tabla(datos) {
    if (datos.total === 0) {
      return vacio({ titulo: "Sin registros", texto: "Aquí queda cada acción que crea o cambia un dato, con su autor y la hora." });
    }
    return [
      h(
        "div",
        { class: "tabla-caja" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Fecha y hora"), h("th", {}, "Usuario"), h("th", {}, "Acción"), h("th", { class: "ocultar-sm" }, "Detalle"))),
          h(
            "tbody",
            {},
            datos.items.map((a) =>
              h(
                "tr",
                {},
                h("td", { class: "mono fecha" }, fecha(a.ocurrido_en, { hora: true })),
                h("td", { class: "sin-corte" }, a.usuario_nombre?.trim() || "Sistema", a.rol && h("span", { class: "sec" }, ROTULOS_ROL[a.rol] ?? a.rol)),
                h("td", { class: "sin-corte" }, TEXTO_ACCION[a.accion] ?? a.accion, h("span", { class: "sec mono" }, a.accion)),
                h("td", { class: "ocultar-sm detalle" }, h("span", { class: "sec" }, resumen(a.detalle))),
              ),
            ),
          ),
        ),
      ),
      paginador(datos, (nueva) => {
        pagina = nueva;
        cargar();
      }),
    ];
  }

  function filtro(nombre, control) {
    control.addEventListener("change", () => {
      filtros[nombre] = control.value;
      pagina = 1;
      cargar();
    });
    return control;
  }

  // Fecha dd/mm/aaaa: filtra cuando la fecha escrita queda completa o se borra (el oculto lleva el ISO).
  function filtroFecha(nombre, etiqueta) {
    const control = campo({ etiqueta, type: "date", id: `filtro-${nombre}` });
    control.addEventListener("input", () => {
      const valor = control.querySelector("input").value;
      if (valor === filtros[nombre]) return;
      filtros[nombre] = valor;
      pagina = 1;
      cargar();
    });
    // Sin formulario que la muestre, una fecha que no existe se avisa al salir del campo.
    control.addEventListener("change", (evento) => evento.target.reportValidity());
    return control;
  }

  cargar();
  return {
    titulo: "Auditoría",
    antetitulo: "Cooperativa",
    descripcion: "Cada acción que crea o cambia un dato, con su autor y la hora.",
    migas: [["Cooperativa", "#/cooperativa"], ["Auditoría"]],
    contenido: h(
      "section",
      { class: "panel" },
      h(
        "div",
        { class: "barra-lista filtros" },
        filtroFecha("desde", "Desde"),
        filtroFecha("hasta", "Hasta"),
        h(
          "label",
          { class: "field" },
          "Usuario",
          filtro(
            "usuario_id",
            h("select", { class: "select" }, h("option", { value: "" }, "Todos"), personal.items.map((u) => h("option", { value: u.id }, `${u.nombres} ${u.apellidos}`))),
          ),
        ),
        h("label", { class: "field" }, "Acción", filtro("accion", h("select", { class: "select" }, ACCIONES.map(([v, t]) => h("option", { value: v }, t))))),
      ),
      lista,
    ),
  };
}
