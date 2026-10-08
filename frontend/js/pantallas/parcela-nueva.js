// Asistente de nueva parcela en 3 pasos (decisión del equipo del 2026-10-06): Nombre, Ubicación en el mapa
// y Confirmar. La ubicación (departamento, provincia y distrito) sale de las coordenadas con los límites del
// INEI y las áreas vienen llenas: la persona solo confirma o corrige. El código PA-… lo pone CacaoTrace.
// Lo usan el personal (#/productores/{id}/parcelas/nueva) y el productor (#/mis-parcelas/nueva).
// "Guardar parcela" solo está en el último paso.

import { llamarApi } from "../api.js";
import { estado } from "../estado.js";
import { COLORES, capaGeojson, crearMapa, editorGeometria, encuadrar, estilo, satelitalDisponible } from "../mapa.js";
import { ALERTAS, ESTADOS_MIDAGRI, hectareas, insigniaAlerta } from "../textos.js";
import { campo, conRetraso, h, reemplazar, toast } from "../ui.js";
import { camposUbigeo, lugares } from "../ubigeo.js";

const PASOS = ["Nombre", "Ubicación en el mapa", "Confirmar"];
const AYUDA_MODO = {
  dibujar: "Dibuja un polígono tocando cada vértice, o marca un punto si la parcela mide menos de 4 ha.",
  archivo: "Sube el archivo y elige una geometría.",
  coordenadas: "Escribe o pega las coordenadas y pulsa «Revisar coordenadas».",
};
const ORIGEN = { dibujar: " (dibujada)", archivo: " (de archivo)", coordenadas: " (de coordenadas)" };

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

  const geometriaLista = () => {
    const geo = seleccion();
    return Boolean(geo && geo.valida && !geo.superposiciones.some((s) => s.propia));
  };

  // ---------- Paso 2: Ubicación en el mapa ----------
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
    if (st.paso === 1) siguiente.disabled = !geometriaLista();
    if (!geo) {
      estadoGeometria.replaceChildren(
        h("p", { class: "panel-sub" }, AYUDA_MODO[st.modo]),
      );
      return;
    }
    const items = [];
    if (!geo.valida) items.push(h("p", { class: "alerta bad" }, geo.errores[0].mensaje));
    else items.push(h("p", { class: "alerta info" }, geo.tipo === "poligono" ? `Polígono válido de ${hectareas(geo.area_ha)} (área calculada).` : "Punto válido. En el siguiente paso indica su área total; debe ser menor de 4 ha."));
    if (geo.valida && geo.ubicacion) items.push(h("p", { class: "panel-sub" }, `Queda en ${lugares(geo.ubicacion.distrito, geo.ubicacion.provincia, geo.ubicacion.departamento)}.`));
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
          h("span", {}, h("b", {}, g.nombre || `Geometría ${g.indice + 1}`), " · ", g.tipo === "poligono" ? "polígono" : g.tipo ?? "no admitida", g.area_ha ? ` · ${hectareas(g.area_ha)}` : "", !g.valida && h("span", { class: "sec" }, g.errores[0].mensaje)),
        );
      }),
    );
    const capa = L.featureGroup(candidatas.getLayers());
    if (capa.getLayers().length) encuadrar(mapa, capa);
  }

  // Archivo o coordenadas escritas: la API lee los dos igual y guarda el original como sustento.
  async function usarArchivo(archivo, lista) {
    st.archivo = archivo;
    const geometrias = await analizar(archivo);
    if (!geometrias) return;
    st.analisis = geometrias;
    const validas = geometrias.filter((g) => g.valida);
    st.indice = geometrias.length === 1 ? 0 : validas.length === 1 ? validas[0].indice : null;
    listaCandidatas.remove();
    lista.append(listaCandidatas);
    pintarCandidatas();
    mostrarResultado();
  }

  const archivoInput = h("input", { class: "input", type: "file", accept: ".geojson,.json,.kml,.kmz,.zip,.csv,.xlsx,.txt" });
  const candidatasArchivo = h("div");
  archivoInput.addEventListener("change", () => archivoInput.files[0] && usarArchivo(archivoInput.files[0], candidatasArchivo));
  const bloqueArchivo = h(
    "div",
    { class: "form", hidden: true },
    h(
      "label",
      { class: "field" },
      "Archivo de la parcela (hasta 2 MB, en WGS 84)",
      archivoInput,
      h("small", {}, "GeoJSON, KML, KMZ, Shapefile comprimido en .zip, o una lista de coordenadas en Excel, CSV o texto. Si trae varias geometrías, elige una."),
    ),
    candidatasArchivo,
  );

  const textoCoordenadas = h("textarea", {
    class: "input",
    id: "c-coordenadas",
    rows: 6,
    spellcheck: "false",
    placeholder: "-6.95120, -76.54870\n-6.95120, -76.54780\n-6.95030, -76.54780\n-6.95030, -76.54870",
  });
  const candidatasCoordenadas = h("div");
  const bloqueCoordenadas = h(
    "div",
    { class: "form", hidden: true },
    h(
      "label",
      { class: "field", for: "c-coordenadas" },
      "Coordenadas de la parcela",
      textoCoordenadas,
      h("small", {}, "Una línea por vértice: latitud y longitud en grados (también 6°57'12\"S 76°33'W). Un solo vértice es un punto. Para varias parcelas, deja una línea en blanco o escribe su nombre en una línea aparte. UTM no se acepta."),
    ),
    h(
      "button",
      {
        class: "btn",
        type: "button",
        onclick: () => {
          const texto = textoCoordenadas.value.trim();
          if (!texto) return textoCoordenadas.focus();
          usarArchivo(new File([texto], "coordenadas.txt", { type: "text/plain" }), candidatasCoordenadas);
        },
      },
      "Revisar coordenadas",
    ),
    candidatasCoordenadas,
  );

  const modos = h(
    "div",
    { class: "seg2", role: "group", "aria-label": "Cómo capturar la geometría" },
    [
      ["dibujar", "Dibujar"],
      ["archivo", "Subir archivo"],
      ["coordenadas", "Coordenadas"],
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
            bloqueCoordenadas.hidden = modo !== "coordenadas";
            st.analisis = [];
            st.indice = null;
            listaCandidatas.replaceChildren();
            candidatas.clearLayers();
            editor.reemplazar(null);
            // Sin dibujo se ocultan las herramientas de dibujo.
            if (modo === "dibujar") editor.mostrarControles();
            else mapa.pm.removeControls();
            mostrarResultado();
          },
        },
        texto,
      ),
    ),
  );
  const pasoMapa = h(
    "div",
    { class: "form", hidden: true },
    modos,
    !satelitalDisponible && h("p", { class: "alerta warn" }, "La capa satelital todavía no está activa: el mapa muestra solo calles."),
    bloqueArchivo,
    bloqueCoordenadas,
    estadoGeometria,
  );

  // ---------- Paso 1: Nombre ----------
  const formNombre = h(
    "form",
    { class: "form", novalidate: true, onsubmit: (e) => (e.preventDefault(), siguiente.click()) },
    campo({ etiqueta: "Nombre de la parcela", name: "nombre", required: true, maxlength: 200, ayuda: "Como la conoce el productor. El código (PA-…) lo pone CacaoTrace al guardar." }),
    campo({ etiqueta: "Caserío o centro poblado (opcional)", name: "centro_poblado", maxlength: 200 }),
  );
  const pasoNombre = h("div", { class: "form" }, formNombre);

  // ---------- Paso 3: Confirmar ----------
  // La ubicación y las áreas se llenan una vez por geometría elegida: si la persona corrige algo y vuelve a
  // este paso sin cambiar la geometría, lo corregido se queda.
  const ubicacion = h("div", { class: "form" });
  const areaTotal = h("div");
  const cultivada = campo({ etiqueta: "Área con cacao (ha)", name: "area_cultivada_ha", type: "number", step: "0.0001", min: "0.0001", required: true, inputmode: "decimal", ayuda: "Viene llena con toda la parcela: confírmala, o bájala si solo una parte tiene cacao." });
  const inputCultivada = cultivada.querySelector("input");
  inputCultivada.addEventListener("input", () => pintarResumen());
  let llenadaPara = null;

  function llenarConfirmacion(geo) {
    if (llenadaPara === geo) return;
    llenadaPara = geo;
    const [departamento, provincia, distrito] = camposUbigeo(geo.ubicacion ?? {});
    reemplazar(
      ubicacion,
      h("div", { class: "grid2" }, departamento, provincia),
      h("div", { class: "grid2" }, distrito),
      h(
        "p",
        { class: geo.ubicacion ? "panel-sub" : "alerta warn" },
        geo.ubicacion
          ? "Llenada desde las coordenadas, con los límites distritales del INEI (referenciales). Si no es así, corrígela."
          : "Las coordenadas no caen en ningún distrito de los límites del INEI: elige la ubicación.",
      ),
    );
    if (geo.tipo === "poligono") {
      reemplazar(areaTotal, h("div", { class: "field" }, h("span", {}, "Área total"), h("b", { class: "mono" }, hectareas(geo.area_ha)), h("small", {}, "La calcula CacaoTrace con el polígono dibujado.")));
      inputCultivada.value = Number(geo.area_ha).toFixed(4);
      return;
    }
    const declarada = campo({ etiqueta: "Área total de la parcela (ha)", name: "area_declarada_ha", type: "number", step: "0.0001", min: "0.0001", required: true, inputmode: "decimal", ayuda: "Un punto no tiene área: escríbela. Debe ser menor de 4 ha." });
    const inputDeclarada = declarada.querySelector("input");
    let anterior = "";
    inputDeclarada.addEventListener("input", () => {
      // El área con cacao sigue al total mientras la persona no la cambie.
      if (!inputCultivada.value || inputCultivada.value === anterior) inputCultivada.value = inputDeclarada.value;
      anterior = inputDeclarada.value;
      pintarResumen();
    });
    reemplazar(areaTotal, declarada);
    inputCultivada.value = "";
  }

  const sustento = h("input", { class: "input", type: "file", name: "sustento", accept: "image/jpeg,image/png,application/pdf" });
  const bloqueSustento = h("label", { class: "field", hidden: true }, "Documento de sustento de MIDAGRI (opcional)", sustento, h("small", {}, "Constancia, reporte o captura que muestra la parcela en MIDAGRI."));
  const estadoMidagri = campo({ etiqueta: "Estado en MIDAGRI", name: "midagri_estado", opciones: ESTADOS_MIDAGRI });
  estadoMidagri.querySelector("select").addEventListener("change", (e) => {
    bloqueSustento.hidden = e.target.value === "no_registrada";
    pintarResumen();
  });
  const formConfirmar = h(
    "form",
    { class: "form", novalidate: true },
    h("h3", { class: "subtitulo-seccion" }, "Ubicación"),
    ubicacion,
    h("h3", { class: "subtitulo-seccion" }, "Áreas"),
    h("div", { class: "grid2" }, areaTotal, cultivada),
    h(
      "details",
      { class: "historial-analisis" },
      h("summary", {}, "Registro en MIDAGRI (opcional)"),
      h("div", { class: "form" }, h("div", { class: "grid2" }, estadoMidagri, campo({ etiqueta: "Código en MIDAGRI (opcional)", name: "midagri_codigo", maxlength: 60 })), bloqueSustento),
    ),
  );
  const resumen = h("div", { class: "form" });
  const mensajeGuardar = h("p", { class: "alerta bad", role: "alert", hidden: true });
  const pasoConfirmar = h("div", { class: "form", hidden: true }, formConfirmar, resumen, mensajeGuardar);

  function leerDatos() {
    const datos = { ...Object.fromEntries(new FormData(formNombre)), ...Object.fromEntries(new FormData(formConfirmar)) };
    delete datos.sustento;
    for (const [k, v] of Object.entries(datos)) if (v === "") delete datos[k];
    return datos;
  }

  function validarConfirmacion() {
    const geo = seleccion();
    if (![...formConfirmar.querySelectorAll("input,select")].every((i) => i.reportValidity())) return false;
    const datos = leerDatos();
    const total = geo.tipo === "poligono" ? Number(geo.area_ha) : Number(datos.area_declarada_ha);
    if (geo.tipo === "punto" && total >= 4) return mostrarError("Una parcela de 4 ha o más debe registrarse como polígono. Vuelve al paso 2 y dibújala.");
    if (Number(datos.area_cultivada_ha) > total) return mostrarError(`El área con cacao no puede ser mayor que el área total (${hectareas(total)}).`);
    mensajeGuardar.hidden = true;
    st.datos = datos;
    st.sustento = bloqueSustento.hidden ? null : sustento.files[0] ?? null;
    return true;
  }
  function mostrarError(texto) {
    mensajeGuardar.textContent = texto;
    mensajeGuardar.hidden = false;
    return false;
  }

  /** Lo que se verá al habilitar: alertas previstas y superposiciones con otras parcelas. */
  function pintarResumen() {
    const geo = seleccion();
    if (!geo || st.paso !== 2) return;
    const datos = leerDatos();
    const alertas = alertasPrevistas(geo, datos, Boolean(!bloqueSustento.hidden && sustento.files[0]));
    const ajenas = geo.superposiciones.filter((s) => !s.propia);
    reemplazar(
      resumen,
      h("h3", { class: "subtitulo-seccion" }, "Antes de guardar"),
      h("p", { class: "panel-sub" }, `${geo.tipo === "poligono" ? "Polígono" : "Punto"}${ORIGEN[st.modo]}.`),
      alertas.length ? h("div", { class: "fila-acciones" }, alertas.map((a) => insigniaAlerta(a))) : h("p", { class: "panel-sub" }, "Sin alertas."),
      alertas.length ? h("p", { class: "panel-sub" }, "Las alertas no impiden guardar; se revisan al habilitar la parcela.") : null,
      ajenas.length
        ? h(
            "ul",
            { class: "lista-simple" },
            ajenas.map((s) =>
              h("li", {}, s.otra_cooperativa ? "Con una parcela de otra cooperativa" : `Con ${s.codigo ?? "otra parcela"} «${s.nombre ?? "de otro productor"}»`, s.area_ha ? ` · ${hectareas(s.area_ha)} en común (${s.porcentaje} %)` : " · el punto cae dentro de esa parcela"),
            ),
          )
        : h("p", { class: "panel-sub" }, "No se superpone con las parcelas activas de la plataforma."),
      ajenas.length ? h("p", { class: "alerta warn" }, ALERTAS.superposicion + ". Se guardará y quedará abierta para revisión.") : null,
    );
  }

  async function guardar() {
    const geo = seleccion();
    const formulario = new FormData();
    formulario.append("datos", JSON.stringify(st.datos));
    if (st.modo !== "dibujar") {
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
  const siguiente = h("button", { class: "btn btn-primary", type: "button" }, "Siguiente");

  function irA(paso) {
    st.paso = paso;
    [pasoNombre, pasoMapa, pasoConfirmar].forEach((p, i) => (p.hidden = i !== paso));
    [...indicador.children].forEach((s, i) => s.setAttribute("aria-current", i === paso ? "step" : "false"));
    atras.hidden = paso === 0;
    siguiente.textContent = paso === 2 ? "Guardar parcela" : "Siguiente";
    siguiente.disabled = paso === 1 && !geometriaLista();
    if (paso === 2) {
      llenarConfirmacion(seleccion());
      pintarResumen();
    }
    window.scrollTo(0, 0);
  }
  atras.addEventListener("click", () => irA(st.paso - 1));
  siguiente.addEventListener("click", () => {
    if (st.paso === 0) return formNombre.querySelector("[name=nombre]").reportValidity() && irA(1);
    if (st.paso === 1) return irA(2);
    if (validarConfirmacion()) guardar();
  });

  mostrarResultado();
  const nombreProductor = productor ? `${productor.nombres} ${productor.apellidos}` : null;
  return {
    titulo: "Nueva parcela",
    antetitulo: delProductor ? "Mis parcelas" : nombreProductor,
    descripcion: "Ponle nombre, ubícala en el mapa y confirma: la ubicación y las áreas se llenan solas.",
    migas: delProductor ? [["Mis parcelas", "#/mis-parcelas"], ["Nueva parcela"]] : [["Productores", "#/productores"], [nombreProductor, volver], ["Nueva parcela"]],
    contenido: h(
      "div",
      { class: "asistente" },
      h("div", { class: "asistente-mapa" }, contenedorMapa),
      h(
        "section",
        { class: "panel asistente-panel" },
        h("div", { class: "panel-h" }, indicador),
        h("div", { class: "panel-b" }, pasoNombre, pasoMapa, pasoConfirmar),
        h("div", { class: "modal-f" }, h("a", { class: "btn btn-ghost", href: volver }, "Cancelar"), atras, siguiente),
      ),
    ),
  };
}
