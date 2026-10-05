// Detalle de parcela, con el inspector del diseño: cabecera con código, estado y área; mapa con
// alertas y superposiciones al lado; datos, documentos e historial de cambios.
// El personal la ve en #/parcelas/{id}; el productor, la suya en #/mis-parcelas/{id}.

import { llamarApi } from "../api.js";
import { formularioCarga, listaDocumentos } from "../documentos.js";
import { puede } from "../estado.js";
import { COLORES, capaGeojson, crearMapa, editorGeometria, encuadrar, estilo } from "../mapa.js";
import { ESTADOS_MIDAGRI, hectareas, insigniaAlerta, insigniaNivel } from "../textos.js";
import { abrirModal, cabeceraFicha, campo, confirmar, enviarCon, fecha, h, icono, rejilla, seccion, toast } from "../ui.js";
import { camposUbigeo } from "../ubigeo.js";

const ACCIONES = {
  "parcela.crear": "Registró la parcela",
  "parcela.editar": "Editó los datos",
  "parcela.editar_geometria": "Cambió la geometría",
  "parcela.desactivar": "Desactivó la parcela",
  "documento.cargar": "Cargó un documento",
  "documento.anular": "Anuló un documento",
};

function abrirEdicion(p, ruta, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-parcela" }, "Guardar");
  const [departamento, provincia, distrito] = camposUbigeo(p);
  const formulario = h(
    "form",
    { class: "form", id: "form-parcela" },
    campo({ etiqueta: "Nombre", name: "nombre", value: p.nombre, required: true, maxlength: 200 }),
    h(
      "div",
      { class: "grid2" },
      departamento,
      provincia,
    ),
    h(
      "div",
      { class: "grid2" },
      distrito,
      campo({ etiqueta: "Caserío o centro poblado", name: "centro_poblado", value: p.centro_poblado ?? "" }),
    ),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Área total declarada (ha)", name: "area_declarada_ha", type: "number", step: "0.0001", min: "0", value: p.area_declarada_ha ?? "", required: p.tipo_geometria === "punto" }),
      campo({ etiqueta: "Área con cacao (ha)", name: "area_cultivada_ha", type: "number", step: "0.0001", min: "0.0001", value: p.area_cultivada_ha, required: true }),
    ),
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Estado en MIDAGRI", name: "midagri_estado", opciones: ESTADOS_MIDAGRI, value: p.midagri_estado }),
      campo({ etiqueta: "Código en MIDAGRI", name: "midagri_codigo", value: p.midagri_codigo ?? "" }),
    ),
  );
  const { cerrar } = abrirModal({
    titulo: "Editar datos de la parcela",
    subtitulo: `${p.codigo} · ${p.nombre}`,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    for (const k of ["centro_poblado", "midagri_codigo", "area_declarada_ha"]) if (datos[k] === "") datos[k] = null;
    await llamarApi(ruta, { metodo: "PATCH", cuerpo: datos });
    cerrar();
    toast("Parcela actualizada.");
    alGuardar();
  });
}

function pedirMotivo(geometria, ruta, alGuardar) {
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-motivo" }, "Guardar geometría");
  const formulario = h(
    "form",
    { class: "form", id: "form-motivo" },
    h("p", {}, "La geometría anterior queda guardada en el historial. Se repiten las validaciones y la búsqueda de superposiciones."),
    campo({ etiqueta: "Motivo del cambio", name: "motivo", required: true, maxlength: 200 }),
  );
  const { cerrar } = abrirModal({
    titulo: "Cambiar la geometría",
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(ruta, { metodo: "PATCH", cuerpo: { geometria, motivo } });
    cerrar();
    toast("Geometría actualizada.");
    alGuardar();
  });
}

async function exportar(p) {
  try {
    const feature = await llamarApi(`/parcelas/${p.id}/geojson`);
    const blob = new Blob([JSON.stringify(feature, null, 2)], { type: "application/geo+json" });
    const enlace = h("a", { href: URL.createObjectURL(blob), download: `${p.codigo}.geojson` });
    enlace.click();
    setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
  } catch (error) {
    toast(error.message, "bad");
  }
}

export default async function parcela({ hash, parametros, recargar }) {
  const delProductor = hash.startsWith("#/mis-parcelas");
  const ruta = delProductor ? `/mi/parcelas/${parametros[0]}` : `/parcelas/${parametros[0]}`;
  const p = await llamarApi(ruta);
  const edita = (delProductor || puede("registrarProductores")) && p.estado === "activa";

  // ---------- Mapa ----------
  const contenedorMapa = h("div", { class: "mapa" });
  const { L, mapa } = await crearMapa(contenedorMapa);
  const color = p.alertas.includes("superposicion") ? COLORES.superposicion : p.alertas.length ? COLORES.con_alertas : COLORES.sin_alertas;
  const capa = capaGeojson(L, p.geometria, { style: estilo(color, 0.25) }).addTo(mapa);
  encuadrar(mapa, capa);

  let editando = null;
  const botonGeometria = edita && h("button", { class: "btn btn-sm", type: "button" }, icono("pin"), "Cambiar geometría");
  botonGeometria?.addEventListener("click", () => {
    if (!editando) {
      mapa.removeLayer(capa);
      let nueva = p.geometria;
      editando = editorGeometria(L, mapa, { inicial: p.geometria, alCambiar: (g) => (nueva = g) });
      botonGeometria.textContent = "Guardar geometría…";
      botonGeometria.onclick = () => (nueva ? pedirMotivo(nueva, ruta, recargar) : toast("Dibuja la parcela antes de guardar.", "bad"));
    }
  });

  // ---------- Ficha ----------
  const midagri = ESTADOS_MIDAGRI.find(([v]) => v === p.midagri_estado)?.[1];
  const esPoligono = p.tipo_geometria === "poligono";

  const estadoAlertas = p.alertas.length
    ? h(
        "div",
        { class: "verif warn" },
        icono("alert"),
        h(
          "div",
          {},
          h("b", {}, p.alertas.length === 1 ? "1 alerta" : `${p.alertas.length} alertas`),
          h("span", { class: "fila-acciones alertas-lista" }, p.alertas.map((a) => insigniaAlerta(a))),
          h("span", {}, "Las alertas no impiden guardar; se revisan al habilitar la parcela."),
        ),
      )
    : h("div", { class: "verif" }, icono("shield"), h("div", {}, h("b", {}, "Sin alertas"), h("span", {}, "Geometría válida y sin superposiciones abiertas.")));

  const superposiciones = p.superposiciones.map((s) =>
    h(
      "div",
      { class: `verif ${s.estado === "abierta" ? "bad" : ""}` },
      icono("layers"),
      h(
        "div",
        {},
        h(
          "b",
          {},
          s.otra_cooperativa
            ? "Superposición con una parcela de otra cooperativa"
            : s.otra_parcela
              ? `Superposición con ${s.otra_parcela.codigo} «${s.otra_parcela.nombre}»`
              : "Superposición con otra parcela",
        ),
        h("span", {}, [s.area_ha ? `${hectareas(s.area_ha)} en común (${s.porcentaje} %)` : null, s.estado].filter(Boolean).join(" · ")),
      ),
    ),
  );

  const geometria = seccion({
    titulo: "Geometría",
    sub: `${esPoligono ? "Polígono" : "Punto"} · ${p.origen_geometria === "archivo" ? "de archivo" : "dibujado"} · registrada el ${fecha(p.creado_en)}`,
    acciones: [botonGeometria, !delProductor && h("button", { class: "btn btn-sm", type: "button", onclick: () => exportar(p) }, icono("download"), "Exportar GeoJSON")],
    contenido: h(
      "div",
      { class: "geo" },
      h("div", { class: "detalle-mapa" }, contenedorMapa),
      h(
        "div",
        { class: "geo-lado" },
        estadoAlertas,
        superposiciones,
        h(
          "dl",
          { class: "kv" },
          h("div", {}, h("dt", {}, "Área calculada"), h("dd", { class: "mono" }, esPoligono ? hectareas(p.area_calculada_ha) : "No aplica")),
          h("div", {}, h("dt", {}, "Área declarada"), h("dd", { class: "mono" }, hectareas(p.area_declarada_ha))),
          h("div", {}, h("dt", {}, "Área con cacao"), h("dd", { class: "mono" }, hectareas(p.area_cultivada_ha))),
          h("div", {}, h("dt", {}, "Estado en MIDAGRI"), h("dd", {}, midagri)),
        ),
      ),
    ),
  });

  const datos = seccion({
    titulo: "Datos de la parcela",
    acciones: [
      edita && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirEdicion(p, ruta, recargar) }, icono("wrench"), "Editar datos"),
      edita &&
        !delProductor &&
        h(
          "button",
          {
            class: "btn btn-sm btn-danger",
            type: "button",
            onclick: async () => {
              if (!(await confirmar({ titulo: "Desactivar parcela", texto: "La parcela no se elimina: pasa a inactiva y sus superposiciones abiertas se cierran.", boton: "Desactivar", peligro: true }))) return;
              try {
                await llamarApi(`/parcelas/${p.id}/desactivar`, { metodo: "POST" });
                toast("Parcela desactivada.");
                recargar();
              } catch (error) {
                toast(error.message, "bad");
              }
            },
          },
          "Desactivar parcela",
        ),
    ],
    contenido: rejilla([
      { etiqueta: "Nombre", valor: p.nombre },
      { etiqueta: "Productor", valor: `${p.productor.nombres} ${p.productor.apellidos}` },
      { etiqueta: "Ubicación", valor: [p.centro_poblado, p.distrito, p.provincia, p.departamento].filter(Boolean).join(", ") },
      { etiqueta: "Estado en MIDAGRI", valor: midagri, extra: insigniaNivel(p.nivel_midagri) },
      { etiqueta: "Código en MIDAGRI", valor: p.midagri_codigo, mono: true },
      { etiqueta: "Estado", valor: p.estado === "activa" ? "Activa" : "Inactiva" },
    ]),
  });

  const documentos = seccion({
    titulo: "Documentos",
    sub: "Sustento del estado en MIDAGRI y archivo de origen de la geometría.",
    contenido: [
      h("div", { class: "tbl-box" }, listaDocumentos(p.documentos, { puedeAnular: !delProductor && puede("registrarProductores"), alCambiar: recargar })),
      edita &&
        formularioCarga({
          tipos: [["sustento_midagri", "Sustento de MIDAGRI"]],
          ruta: `${ruta}/documentos`,
          alCargar: recargar,
          textoBoton: "Cargar sustento de MIDAGRI",
        }),
    ],
  });

  const historial =
    !delProductor &&
    seccion({
      titulo: "Historial de cambios",
      contenido: p.historial.length
        ? h(
            "ol",
            { class: "linea-tiempo" },
            p.historial.map((x) =>
              h(
                "li",
                {},
                h("b", {}, ACCIONES[x.accion] ?? x.accion),
                h("span", { class: "sec" }, [fecha(x.ocurrido_en, { hora: true }), x.usuario_nombre].filter(Boolean).join(" · ")),
                x.detalle?.motivo ? h("span", { class: "sec" }, `Motivo: ${x.detalle.motivo}`) : null,
              ),
            ),
          )
        : h("p", { class: "panel-sub" }, "Sin cambios registrados."),
    });

  const n = p.alertas.length;
  return {
    titulo: `${p.codigo} · ${p.nombre}`,
    migas: delProductor
      ? [["Mis parcelas", "#/mis-parcelas"], [p.nombre]]
      : [["Productores", "#/productores"], [`${p.productor.nombres} ${p.productor.apellidos}`, `#/productores/${p.productor.id}`], [p.codigo]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: h("span", { class: "ins-icono" }, icono("pin")),
        titulo: p.codigo,
        codigo: true,
        insignias: [
          p.estado === "activa" ? h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Activa") : h("span", { class: "badge" }, h("span", { class: "dot" }), "Inactiva"),
          n ? h("span", { class: "badge warn" }, h("span", { class: "dot" }), n === 1 ? "1 alerta" : `${n} alertas`) : null,
        ],
        detalle: [
          h("b", {}, p.nombre),
          " · ",
          delProductor ? `${p.productor.nombres} ${p.productor.apellidos}` : h("a", { href: `#/productores/${p.productor.id}` }, `${p.productor.nombres} ${p.productor.apellidos}`),
          ` · ${p.distrito}, ${p.provincia}`,
        ],
        cifra: hectareas(p.area_total_ha),
        cifraTexto: esPoligono ? "área calculada" : "área declarada (punto)",
      }),
      geometria,
      datos,
      documentos,
      historial,
    ),
  };
}
