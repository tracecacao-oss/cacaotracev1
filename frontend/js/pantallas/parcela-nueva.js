// Asistente de nueva parcela en 3 pasos: Geometría, Datos y Revisión.
// Lo usan el personal (#/productores/{id}/parcelas/nueva) y el productor (#/mis-parcelas/nueva).
// "Guardar parcela" solo está en el último paso.

import { llamarApi } from "../api.js";
import { estado } from "../estado.js";
import { COLORES, capaGeojson, crearMapa, editorGeometria, encuadrar, estilo, satelitalDisponible } from "../mapa.js";
import { ALERTAS, ESTADOS_MIDAGRI, hectareas, insigniaAlerta } from "../textos.js";
import { campo, conRetraso, h, reemplazar, toast } from "../ui.js";
import { camposUbigeo } from "../ubigeo.js";

const PASOS = ["Geometría", "Datos", "Revisión"];

function alertasPrevistas(geo, datos, conSustento) {
  const alertas = [];
  const calculada = geo?.area_ha != null ? Number(geo.area_ha) : null;
  const declarada = datos.area_declarada_ha ? Number(datos.area_declarada_ha) : null;
  if (geo?.tipo === "poligono" && declarada != null && calculada && Math.abs(declarada - calculada) / calculada > 0.2) {
    alertas.push("area_discrepante");
  }
  const total = geo?.tipo === "poligono" ? calculada : declarada;
  if (total != null && total >= 10) alertas.push("diez_hectareas_o_mas");
  if (geo?.superposiciones?.some((s) => !s.propia)) alertas.push("superposicion");
  if (datos.midagri_estado && datos.midagri_estado !== "no_registrada" && !conSustento) alertas.push("sin_sustento_midagri");
  return alertas;
}

export default async function parcelaNueva({ hash, parametros, navegar }) {
  const delProductor = hash.startsWith("#/mis-parcelas");
  const productorId = delProductor ? estado.usuario.productor_id : parametros[0];
  const productor = delProductor ? null : await llamarApi(`/productores/${productorId}`);
  const volver = delProductor ? "#/mis-parcelas" : `#/productores/${productorId}`;
  const rutaCrear = delProductor ? "/mi/parcelas" : `/productores/${productorId}/parcelas`;
  const rutaSustento = (id) => (delProductor ? `/mi/parcelas/${id}/documentos` : `/parcelas/${id}/documentos`);

  const st = { paso: 0, modo: "dibujar", archivo: null, analisis: [], indice: null, dibujada: null, datos: {}, sustento: null };
  const seleccion = () => (st.indice == null ? null : st.analisis[st.indice]);

  // ---------- Mapa ----------
  const contenedorMapa = h("div", { class: "mapa mapa-grande", role: "application", "aria-label": "Mapa para dibujar la parcela" });
  const { L, mapa } = await crearMapa(contenedorMapa);
  const vecinas = L.layerGroup().addTo(mapa);
  const candidatas = L.layerGroup().addTo(mapa);
  try {
    const existentes = delProductor
      ? { type: "FeatureCollection", features: (await llamarApi("/mi/parcelas")).map((p) => ({ type: "Feature", geometry: p.geometria })) }
      : await llamarApi("/parcelas", { parametros: { formato: "geojson", estado: "activa" } });
    const capa = capaGeojson(L, existentes, { style: estilo("#64748b", 0.08), interactive: false });
    capa.addTo(vecinas);
    if (existentes.features.length) encuadrar(mapa, capa);
  } catch {
    // Sin parcelas vecinas el asistente sigue funcionando.
  }

  // ---------- Paso 1: Geometría ----------
  const estadoGeometria = h("div", { class: "geometria-estado", "aria-live": "polite" });
  const listaCandidatas = h("div", { class: "candidatas" });

  async function analizar(archivo) {
    const formulario = new FormData();
    formulario.append("archivo", archivo);
    formulario.append("productor_id", productorId);
    estadoGeometria.replaceChildren(h("p", { class: "panel-sub" }, "Revisando la geometría…"));
    try {
      const { geometrias } = await llamarApi("/parcelas/analizar-archivo", { metodo: "POST", formulario });
      return geometrias;
    } catch (error) {
      estadoGeometria.replaceChildren(h("p", { class: "alerta bad" }, error.message));
      return null;
    }
  }

  function mostrarResultado() {
    const geo = seleccion();
    siguiente.disabled = !(geo && geo.valida && !geo.superposiciones.some((s) => s.propia));
    if (!geo) {
      estadoGeometria.replaceChildren(
        h("p", { class: "panel-sub" }, st.modo === "dibujar" ? "Dibuja un polígono tocando cada vértice, o marca un punto si la parcela mide menos de 4 ha." : "Sube el archivo y elige una geometría."),
      );
      return;
    }
    const items = [];
    if (!geo.valida) items.push(h("p", { class: "alerta bad" }, geo.errores[0].mensaje));
    else items.push(h("p", { class: "alerta info" }, geo.tipo === "poligono" ? `Polígono válido de ${hectareas(geo.area_ha)} (área calculada).` : "Punto válido. En el siguiente paso indica su área total; debe ser menor de 4 ha."));
    for (const s of geo.superposiciones.filter((x) => x.propia)) {
      items.push(h("p", { class: "alerta bad" }, `Se superpone con otra parcela del mismo productor: ${s.codigo} «${s.nombre}». Corrige el dibujo.`));
    }
    estadoGeometria.replaceChildren(...items);
  }

  // Dibujo: cada cambio se valida en la API como un GeoJSON, sin guardar nada.
  const validarDibujo = conRetraso(async (geometria) => {
    if (!geometria) {
      st.analisis = [];
      st.indice = null;
      mostrarResultado();
      return;
    }
    const archivo = new File([JSON.stringify({ type: "Feature", properties: {}, geometry: geometria })], "dibujo.geojson", { type: "application/geo+json" });
    const geometrias = await analizar(archivo);
    if (geometrias) {
      st.analisis = geometrias;
      st.indice = 0;
      st.dibujada = geometria;
      mostrarResultado();
    }
  }, 400);
  const editor = editorGeometria(L, mapa, { alCambiar: (g) => st.modo === "dibujar" && validarDibujo(g) });

  function pintarCandidatas() {
    candidatas.clearLayers();
    listaCandidatas.replaceChildren(
      ...st.analisis.map((g) => {
        if (g.geometria) {
          const color = !g.valida ? COLORES.superposicion : g.indice === st.indice ? COLORES.nueva : "#94a3b8";
          capaGeojson(L, g.geometria, { style: { ...estilo(color, 0.2), dashArray: g.valida ? null : "4 4" } }).addTo(candidatas);
        }
        return h(
          "label",
          { class: "check" },
          h("input", {
            type: "radio",
            name: "candidata",
            checked: g.indice === st.indice,
            onchange: () => {
              st.indice = g.indice;
              pintarCandidatas();
              mostrarResultado();
            },
          }),
          h("span", {}, h("b", {}, g.nombre || `Geometría ${g.indice + 1}`), " · ", g.tipo ?? "no admitida", g.area_ha ? ` · ${hectareas(g.area_ha)}` : "", !g.valida && h("span", { class: "sec" }, g.errores[0].mensaje)),
        );
      }),
    );
    const capa = L.featureGroup(candidatas.getLayers());
    if (capa.getLayers().length) encuadrar(mapa, capa);
  }

  const archivoInput = h("input", { class: "input", type: "file", accept: ".geojson,.json,.kml" });
  archivoInput.addEventListener("change", async () => {
    const archivo = archivoInput.files[0];
    if (!archivo) return;
    st.archivo = archivo;
    const geometrias = await analizar(archivo);
    if (!geometrias) return;
    st.analisis = geometrias;
    const validas = geometrias.filter((g) => g.valida);
    st.indice = geometrias.length === 1 ? 0 : validas.length === 1 ? validas[0].indice : null;
    pintarCandidatas();
    mostrarResultado();
  });
  const bloqueArchivo = h(
    "div",
    { class: "form", hidden: true },
    h("label", { class: "field" }, "Archivo GeoJSON o KML (hasta 2 MB, en WGS 84)", archivoInput),
    h("small", { class: "panel-sub" }, "Si el archivo trae varias geometrías, elige una. KMZ y Shapefile no se aceptan: expórtalos como KML o GeoJSON."),
    listaCandidatas,
  );

  const modos = h(
    "div",
    { class: "seg2", role: "group", "aria-label": "Cómo capturar la geometría" },
    [
      ["dibujar", "Dibujar en el mapa"],
      ["archivo", "Subir archivo"],
    ].map(([modo, texto]) =>
      h(
        "button",
        {
          type: "button",
          "aria-pressed": String(modo === st.modo),
          onclick: (e) => {
            st.modo = modo;
            for (const b of modos.children) b.setAttribute("aria-pressed", String(b === e.currentTarget));
            bloqueArchivo.hidden = modo !== "archivo";
            st.analisis = [];
            st.indice = null;
            candidatas.clearLayers();
            editor.reemplazar(null);
            // Con archivo no se dibuja: se ocultan las herramientas de dibujo.
            if (modo === "archivo") mapa.pm.removeControls();
            else editor.mostrarControles();
            mostrarResultado();
          },
        },
        texto,
      ),
    ),
  );
  const paso1 = h(
    "div",
    { class: "form" },
    modos,
    !satelitalDisponible && h("p", { class: "alerta warn" }, "La capa satelital todavía no está activa: el mapa muestra solo calles."),
    bloqueArchivo,
    estadoGeometria,
  );

  // ---------- Paso 2: Datos ----------
  const sustento = h("input", { class: "input", type: "file", name: "sustento", accept: "image/jpeg,image/png,application/pdf" });
  const bloqueSustento = h("label", { class: "field", hidden: true }, "Documento de sustento de MIDAGRI (opcional)", sustento, h("small", {}, "Constancia, reporte o captura que muestra la parcela en MIDAGRI."));
  const estadoMidagri = campo({ etiqueta: "Estado en MIDAGRI", name: "midagri_estado", opciones: ESTADOS_MIDAGRI });
  estadoMidagri.querySelector("select").addEventListener("change", (e) => {
    bloqueSustento.hidden = e.target.value === "no_registrada";
  });
  const areaDeclarada = campo({ etiqueta: "Área total declarada (ha)", name: "area_declarada_ha", type: "number", step: "0.0001", min: "0" });
  const [departamento, provincia, distrito] = camposUbigeo();
  const formDatos = h(
    "form",
    { class: "form", novalidate: true },
    campo({ etiqueta: "Nombre de la parcela", name: "nombre", required: true, maxlength: 200, ayuda: "Como la conoce el productor." }),
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
      campo({ etiqueta: "Caserío o centro poblado (opcional)", name: "centro_poblado", maxlength: 200 }),
    ),
    h(
      "div",
      { class: "grid2" },
      areaDeclarada,
      campo({ etiqueta: "Área con cacao (ha)", name: "area_cultivada_ha", type: "number", step: "0.0001", min: "0.0001", required: true }),
    ),
    h("div", { class: "grid2" }, estadoMidagri, campo({ etiqueta: "Código en MIDAGRI (opcional)", name: "midagri_codigo", maxlength: 60 })),
    bloqueSustento,
  );
  const mensajeDatos = h("p", { class: "alerta bad", role: "alert", hidden: true });

  function leerDatos() {
    const datos = Object.fromEntries(new FormData(formDatos));
    delete datos.sustento;
    for (const [k, v] of Object.entries(datos)) if (v === "") delete datos[k];
    return datos;
  }

  function validarDatos() {
    const geo = seleccion();
    const input = areaDeclarada.querySelector("input");
    input.required = geo?.tipo === "punto";
    if (![...formDatos.querySelectorAll("input,select")].every((i) => i.reportValidity())) return false;
    const datos = leerDatos();
    const total = geo.tipo === "poligono" ? Number(geo.area_ha) : Number(datos.area_declarada_ha);
    if (geo.tipo === "punto" && total >= 4) return mostrarError("Una parcela de 4 ha o más debe registrarse como polígono. Vuelve al paso 1 y dibújala.");
    if (Number(datos.area_cultivada_ha) > total) return mostrarError(`El área con cacao no puede ser mayor que el área total (${hectareas(total)}).`);
    mensajeDatos.hidden = true;
    st.datos = datos;
    st.sustento = bloqueSustento.hidden ? null : sustento.files[0] ?? null;
    return true;
  }
  function mostrarError(texto) {
    mensajeDatos.textContent = texto;
    mensajeDatos.hidden = false;
    return false;
  }
  const paso2 = h("div", { class: "form", hidden: true }, formDatos, mensajeDatos);

  // ---------- Paso 3: Revisión ----------
  const resumen = h("div", { class: "form" });
  const mensajeGuardar = h("p", { class: "alerta bad", role: "alert", hidden: true });
  const paso3 = h("div", { class: "form", hidden: true }, resumen, mensajeGuardar);

  function pintarResumen() {
    const geo = seleccion();
    const alertas = alertasPrevistas(geo, st.datos, Boolean(st.sustento));
    const ajenas = geo.superposiciones.filter((s) => !s.propia);
    reemplazar(
      resumen,
      h(
        "dl",
        { class: "ficha" },
        h("div", {}, h("dt", {}, "Nombre"), h("dd", {}, st.datos.nombre)),
        h("div", {}, h("dt", {}, "Ubicación"), h("dd", {}, [st.datos.centro_poblado, st.datos.distrito, st.datos.provincia, st.datos.departamento].filter(Boolean).join(", "))),
        h("div", {}, h("dt", {}, "Geometría"), h("dd", {}, geo.tipo === "poligono" ? "Polígono" : "Punto", st.modo === "archivo" ? " (de archivo)" : " (dibujada)")),
        h("div", {}, h("dt", {}, "Área calculada"), h("dd", { class: "mono" }, geo.tipo === "poligono" ? hectareas(geo.area_ha) : "No aplica (punto)")),
        h("div", {}, h("dt", {}, "Área declarada"), h("dd", { class: "mono" }, hectareas(st.datos.area_declarada_ha))),
        h("div", {}, h("dt", {}, "Área con cacao"), h("dd", { class: "mono" }, hectareas(st.datos.area_cultivada_ha))),
      ),
      h("h3", { class: "subtitulo-seccion" }, "Alertas"),
      alertas.length ? h("div", { class: "fila-acciones" }, alertas.map((a) => insigniaAlerta(a))) : h("p", { class: "panel-sub" }, "Sin alertas."),
      alertas.length ? h("p", { class: "panel-sub" }, "Las alertas no impiden guardar; se revisan al habilitar la parcela.") : null,
      h("h3", { class: "subtitulo-seccion" }, "Superposiciones detectadas"),
      ajenas.length
        ? h(
            "ul",
            { class: "lista-simple" },
            ajenas.map((s) =>
              h("li", {}, s.otra_cooperativa ? "Con una parcela de otra cooperativa" : `Con ${s.codigo ?? "otra parcela"} «${s.nombre ?? "de otro productor"}»`, s.area_ha ? ` · ${hectareas(s.area_ha)} en común (${s.porcentaje} %)` : " · el punto cae dentro de esa parcela"),
            ),
          )
        : h("p", { class: "panel-sub" }, "Ninguna con las parcelas activas de la plataforma."),
      ajenas.length ? h("p", { class: "alerta warn" }, ALERTAS.superposicion + ". Se guardará y quedará abierta para revisión.") : null,
    );
  }

  async function guardar() {
    const geo = seleccion();
    const formulario = new FormData();
    formulario.append("datos", JSON.stringify(st.datos));
    if (st.modo === "archivo") {
      formulario.append("archivo", st.archivo);
      formulario.append("indice", String(geo.indice));
    } else {
      formulario.append("geometria", JSON.stringify(st.dibujada));
    }
    siguiente.classList.add("is-loading");
    siguiente.disabled = true;
    mensajeGuardar.hidden = true;
    try {
      const parcela = await llamarApi(rutaCrear, { metodo: "POST", formulario });
      if (st.sustento) {
        const doc = new FormData();
        doc.append("tipo", "sustento_midagri");
        doc.append("archivo", st.sustento);
        try {
          await llamarApi(rutaSustento(parcela.id), { metodo: "POST", formulario: doc });
        } catch (error) {
          toast(`La parcela se guardó, pero el sustento no se cargó: ${error.message}`, "bad");
        }
      }
      toast(`Parcela ${parcela.codigo} guardada.`);
      navegar(delProductor ? `#/mis-parcelas/${parcela.id}` : `#/parcelas/${parcela.id}`);
    } catch (error) {
      mensajeGuardar.textContent = error.message;
      mensajeGuardar.hidden = false;
      siguiente.disabled = false;
    } finally {
      siguiente.classList.remove("is-loading");
    }
  }

  // ---------- Navegación entre pasos ----------
  const indicador = h("div", { class: "pasos" }, PASOS.map((p, i) => h("span", { "aria-current": i === 0 ? "step" : "false" }, `${i + 1}. ${p}`)));
  const atras = h("button", { class: "btn btn-ghost", type: "button", hidden: true }, "Atrás");
  const siguiente = h("button", { class: "btn btn-primary", type: "button", disabled: true }, "Siguiente");

  function irA(paso) {
    st.paso = paso;
    [paso1, paso2, paso3].forEach((p, i) => (p.hidden = i !== paso));
    [...indicador.children].forEach((s, i) => s.setAttribute("aria-current", i === paso ? "step" : "false"));
    atras.hidden = paso === 0;
    siguiente.textContent = paso === 2 ? "Guardar parcela" : "Siguiente";
    siguiente.disabled = paso === 0 && !seleccion()?.valida;
    if (paso === 1) {
      const nombre = formDatos.querySelector("[name=nombre]");
      if (!nombre.value && seleccion()?.nombre) nombre.value = seleccion().nombre;
      areaDeclarada.querySelector("small")?.remove();
      areaDeclarada.append(h("small", {}, seleccion()?.tipo === "punto" ? "Obligatoria para un punto; debe ser menor de 4 ha." : "Opcional para un polígono."));
    }
    if (paso === 2) pintarResumen();
    window.scrollTo(0, 0);
  }
  atras.addEventListener("click", () => irA(st.paso - 1));
  siguiente.addEventListener("click", () => {
    if (st.paso === 0) return irA(1);
    if (st.paso === 1) return validarDatos() && irA(2);
    guardar();
  });

  mostrarResultado();
  const nombreProductor = productor ? `${productor.nombres} ${productor.apellidos}` : null;
  return {
    titulo: "Nueva parcela",
    migas: delProductor ? [["Mis parcelas", "#/mis-parcelas"], ["Nueva parcela"]] : [["Productores", "#/productores"], [nombreProductor, volver], ["Nueva parcela"]],
    contenido: h(
      "div",
      { class: "asistente" },
      h("div", { class: "asistente-mapa" }, contenedorMapa),
      h(
        "section",
        { class: "panel asistente-panel" },
        h("div", { class: "panel-h" }, indicador),
        h("div", { class: "panel-b" }, paso1, paso2, paso3),
        h("div", { class: "modal-f" }, h("a", { class: "btn btn-ghost", href: volver }, "Cancelar"), atras, siguiente),
      ),
    ),
  };
}
