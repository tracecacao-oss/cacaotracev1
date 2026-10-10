// Ficha del productor, con el inspector del diseño: cabecera con nombre, DNI, pendientes y área
// total, y pestañas Datos, Parcelas (con mapa), Declaración (adenda 5), Documentos y Acceso.
// #/productores/{id}/declaracion abre la ficha en la pestaña Declaración.

import { llamarApi } from "../api.js";
import { formularioCarga, listaDocumentos } from "../documentos.js";
import { puede, rolEfectivo } from "../estado.js";
import { COLORES, capaGeojson, crearMapa, encuadrar, estilo } from "../mapa.js";
import { ESTADOS_MIDAGRI, PENDIENTES_PERSONAL, hectareas, insigniaAlerta, insigniaNivel } from "../textos.js";
import {
  abrirModal,
  avatar,
  cabeceraFicha,
  campo,
  confirmar,
  enviarCon,
  fecha,
  h,
  icono,
  mostrarClaveTemporal,
  rejilla,
  seccion,
  toast,
  vacio,
} from "../ui.js";
import { pestanaDeclaracion } from "./productor-declaracion.js";
import { camposFicha, cuerpoFicha, insigniaAcceso } from "./productores.js";

const PESTANAS = [
  ["datos", "Datos"],
  ["parcelas", "Parcelas"],
  ["declaracion", "Declaración"],
  ["documentos", "Documentos"],
  ["acceso", "Acceso"],
];
let pestanaRecordada = "datos";

function abrirEdicion(p, alGuardar) {
  const ficha = camposFicha(p);
  const motivo = campo({ etiqueta: "Motivo de la corrección del DNI", name: "motivo", maxlength: 200 });
  motivo.hidden = true;
  const dni = campo({ etiqueta: "DNI", name: "dni", value: p.dni, inputmode: "numeric", pattern: "[0-9]{8}", maxlength: 8, class: "input mono", required: true });
  dni.querySelector("input").addEventListener("input", (e) => {
    motivo.hidden = e.target.value === p.dni;
    motivo.querySelector("input").required = !motivo.hidden;
  });
  const boton = h("button", { class: "btn btn-primary", type: "submit", form: "form-ficha" }, "Guardar");
  const formulario = h(
    "form",
    { class: "form", id: "form-ficha" },
    dni,
    motivo,
    h(
      "div",
      { class: "grid2" },
      campo({ etiqueta: "Nombres", name: "nombres", value: p.nombres, required: true, maxlength: 200 }),
      campo({ etiqueta: "Apellidos", name: "apellidos", value: p.apellidos, required: true, maxlength: 200 }),
    ),
    ficha.contacto,
    ficha.registros,
  );
  const { cerrar } = abrirModal({
    titulo: "Editar ficha",
    subtitulo: `${p.nombres} ${p.apellidos}`,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async (datos) => {
    const cuerpo = cuerpoFicha(datos, { vaciosComoNulos: true });
    if (cuerpo.dni === p.dni) {
      delete cuerpo.dni;
      delete cuerpo.motivo;
    }
    await llamarApi(`/productores/${p.id}`, { metodo: "PATCH", cuerpo });
    cerrar();
    toast("Ficha actualizada.");
    alGuardar();
  });
}

function cerrarAfiliacion(p, navegar) {
  const boton = h("button", { class: "btn btn-danger", type: "submit", form: "form-cierre" }, "Cerrar afiliación");
  const formulario = h(
    "form",
    { class: "form", id: "form-cierre" },
    h("p", {}, "El productor no se elimina. Su afiliación queda cerrada con fecha de hoy y su acceso se desactiva."),
    campo({ etiqueta: "Motivo (opcional)", name: "motivo", maxlength: 200 }),
  );
  const { cerrar } = abrirModal({
    titulo: "Cerrar afiliación",
    subtitulo: `${p.nombres} ${p.apellidos}`,
    contenido: formulario,
    pie: [h("button", { class: "btn btn-ghost", type: "button", onclick: () => cerrar() }, "Cancelar"), boton],
  });
  enviarCon(formulario, boton, async ({ motivo }) => {
    await llamarApi(`/productores/${p.id}/afiliacion/cerrar`, { metodo: "POST", cuerpo: motivo ? { motivo } : {} });
    cerrar();
    toast("Afiliación cerrada.");
    navegar("#/productores");
  });
}

function pestanaDatos(p, { recargar, navegar }) {
  const edita = puede("registrarProductores");
  const nivel = (valor, n) => (valor ? insigniaNivel(n) : null);
  return seccion({
    titulo: "Datos del productor",
    sub: "Cada dato muestra qué tan respaldado está.",
    acciones: [
      edita && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirEdicion(p, recargar) }, icono("wrench"), "Editar ficha"),
      rolEfectivo() === "admin_cooperativa" &&
        h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => cerrarAfiliacion(p, navegar) }, "Cerrar afiliación"),
    ],
    contenido: rejilla([
      { grupo: "Identidad" },
      { etiqueta: "DNI", valor: p.dni, mono: true, extra: nivel(p.dni, p.nivel_identidad) },
      { etiqueta: "Nombres", valor: p.nombres, extra: nivel(p.nombres, p.nivel_identidad) },
      { etiqueta: "Apellidos", valor: p.apellidos, extra: nivel(p.apellidos, p.nivel_identidad) },
      { etiqueta: "RUC", valor: p.ruc, mono: true, extra: nivel(p.ruc, "declarado") },
      { grupo: "Contacto" },
      { etiqueta: "Dirección postal", valor: p.direccion_postal, extra: nivel(p.direccion_postal, "declarado") },
      { etiqueta: "Correo de contacto", valor: p.correo_contacto, extra: nivel(p.correo_contacto, "declarado") },
      { etiqueta: "Teléfono", valor: p.telefono, mono: true, extra: nivel(p.telefono, "declarado") },
      { grupo: "Cooperativa y MIDAGRI" },
      { etiqueta: "Código de socio", valor: p.codigo_socio, mono: true },
      { etiqueta: "Afiliado desde", valor: fecha(p.afiliado_desde) },
      {
        etiqueta: "Consentimiento de datos",
        valor: p.consentimiento_datos_en
          ? `${fecha(p.consentimiento_datos_en)} · ${p.consentimiento_origen === "productor" ? "aceptado por el productor" : "firmado ante la cooperativa"}`
          : "Pendiente",
      },
      {
        etiqueta: "Registro en el PPA de MIDAGRI",
        valor: p.ppa_registrado ? p.ppa_codigo || "Registrado" : "No registrado",
        mono: Boolean(p.ppa_codigo),
        // Sin registro, la insignia repetiría "No registrado".
        extra: p.ppa_registrado && insigniaNivel(p.nivel_ppa),
      },
      { etiqueta: "Código en Agro Digital (app del MIDAGRI)", valor: p.codigo_agrodigital, mono: true, extra: nivel(p.codigo_agrodigital, "declarado") },
    ]),
  });
}

async function pestanaParcelas(p, { navegar }) {
  const parcelas = await llamarApi(`/productores/${p.id}/parcelas`);
  const nueva =
    puede("registrarProductores") &&
    h("button", { class: "btn btn-sm", type: "button", onclick: () => navegar(`#/productores/${p.id}/parcelas/nueva`) }, icono("mas"), "Nueva parcela");
  if (!parcelas.length) {
    return seccion({
      titulo: "Parcelas y geolocalización",
      contenido: vacio({ titulo: "Sin parcelas", texto: "Registra cada parcela por separado: dibujándola, subiendo un archivo o escribiendo sus coordenadas.", accion: nueva }),
    });
  }

  // Mapa con las parcelas activas del productor, con los colores del mapa de la cooperativa.
  const contenedor = h("div", { class: "mapa mapa-ficha" });
  const activas = parcelas.filter((x) => x.estado === "activa");
  if (activas.length) {
    crearMapa(contenedor, { coordenadas: false }).then(({ L, mapa }) => {
      const color = (x) => COLORES[x.alertas.includes("superposicion") ? "superposicion" : x.alertas.length ? "con_alertas" : "sin_alertas"];
      const coleccion = { type: "FeatureCollection", features: activas.map((x) => ({ type: "Feature", geometry: x.geometria, properties: x })) };
      const capa = capaGeojson(L, coleccion, {
        style: (f) => estilo(color(f.properties), 0.3),
        pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 8, ...estilo(color(f.properties), 0.6) }),
        onEachFeature: (f, layer) => {
          layer.bindTooltip(`${f.properties.codigo} · ${f.properties.nombre}`);
          layer.on("click", () => navegar(`#/parcelas/${f.properties.id}`));
        },
      }).addTo(mapa);
      encuadrar(mapa, capa);
    });
  }

  return seccion({
    titulo: "Parcelas y geolocalización",
    sub: "Toca una parcela en el mapa o en la lista para ver su detalle.",
    acciones: nueva,
    contenido: [
      activas.length ? contenedor : null,
      h(
        "div",
        { class: "tbl-box" },
        h(
          "table",
          { class: "tabla" },
          h("thead", {}, h("tr", {}, h("th", {}, "Parcela"), h("th", {}, "Área"), h("th", { class: "ocultar-sm" }, "MIDAGRI"), h("th", {}, "Alertas"))),
          h(
            "tbody",
            {},
            parcelas.map((x) =>
              h(
                "tr",
                { class: "clic", onclick: () => navegar(`#/parcelas/${x.id}`) },
                h(
                  "td",
                  {},
                  h("a", { href: `#/parcelas/${x.id}` }, x.nombre),
                  h("span", { class: "sec mono" }, `${x.codigo} · ${x.tipo_geometria === "poligono" ? "polígono" : "punto"}${x.estado === "inactiva" ? " · inactiva" : ""}`),
                ),
                h("td", { class: "mono" }, hectareas(x.area_total_ha)),
                h("td", { class: "ocultar-sm" }, ESTADOS_MIDAGRI.find(([v]) => v === x.midagri_estado)?.[1], h("span", { class: "sec" }, insigniaNivel(x.nivel_midagri))),
                h("td", {}, x.alertas.length ? h("span", { class: "fila-acciones" }, x.alertas.map((a) => insigniaAlerta(a))) : h("span", { class: "sec" }, "Sin alertas")),
              ),
            ),
          ),
        ),
      ),
    ],
  });
}

function pestanaDocumentos(p, { recargar }) {
  const gestiona = puede("registrarProductores");
  return seccion({
    titulo: "Documentos",
    sub: "Respaldo de la identidad y del registro en el PPA.",
    contenido: [
      h("div", { class: "tbl-box" }, listaDocumentos(p.documentos, { puedeAnular: gestiona, alCambiar: recargar })),
      gestiona &&
        formularioCarga({
          tipos: [
            ["dni", "Copia del DNI"],
            ["constancia_ppa", "Constancia o captura del PPA"],
          ],
          ruta: `/productores/${p.id}/documentos`,
          alCargar: recargar,
        }),
    ],
  });
}

function pestanaAcceso(p, { recargar }) {
  const nombre = `${p.nombres} ${p.apellidos}`;
  const gestiona = puede("gestionarAccesos");
  const verClave = mostrarClaveTemporal({ titulo: "Contraseña temporal del productor", persona: nombre, usuario: `DNI ${p.dni}` });
  const accion = (texto, clase, fn) => {
    const boton = h("button", { class: `btn ${clase}`, type: "button" }, texto);
    boton.addEventListener("click", async () => {
      boton.classList.add("is-loading");
      try {
        await fn();
      } catch (error) {
        toast(error.message, "bad");
      } finally {
        boton.classList.remove("is-loading");
      }
    });
    return boton;
  };
  const acciones = [];
  if (gestiona && (!p.acceso.existe || !p.acceso.activo)) {
    acciones.push(
      accion("Crear acceso", "btn-primary", async () => {
        verClave(await llamarApi(`/productores/${p.id}/acceso`, { metodo: "POST" }));
        recargar();
      }),
    );
  }
  if (gestiona && p.acceso.existe && p.acceso.activo) {
    acciones.push(
      accion("Restablecer contraseña", "", async () => {
        if (!(await confirmar({ titulo: "Restablecer contraseña", texto: `Se generará una nueva contraseña temporal para ${nombre} y se cerrarán sus sesiones abiertas.`, boton: "Restablecer" }))) return;
        verClave(await llamarApi(`/productores/${p.id}/acceso/restablecer-clave`, { metodo: "POST" }));
        recargar();
      }),
      accion("Desactivar acceso", "btn-danger", async () => {
        if (!(await confirmar({ titulo: "Desactivar acceso", texto: `${nombre} ya no podrá ingresar. Sus datos se conservan.`, boton: "Desactivar", peligro: true }))) return;
        await llamarApi(`/productores/${p.id}/acceso`, { metodo: "DELETE" });
        toast("Acceso desactivado.");
        recargar();
      }),
    );
  }
  return seccion({
    titulo: "Acceso a CacaoTrace",
    sub: "Ingresa desde su celular con su DNI y contraseña.",
    acciones: insigniaAcceso(p.acceso),
    contenido: [
      p.acceso.existe
        ? rejilla([
            { etiqueta: "Usuario", valor: `DNI ${p.dni}`, mono: true },
            { etiqueta: "Último ingreso", valor: fecha(p.acceso.ultimo_acceso_en, { hora: true }) },
          ])
        : h("p", { class: "panel-sub" }, "Todavía no tiene acceso. Al crearlo verás una contraseña temporal para entregarle."),
      acciones.length ? h("div", { class: "fila-acciones" }, acciones) : null,
    ],
  });
}

export default async function productor(ctx) {
  const p = await llamarApi(`/productores/${ctx.parametros[0]}`);
  const nombre = `${p.nombres} ${p.apellidos}`;
  const cuerpo = h("div", { class: "contenido-pestana" });
  const barra = h("div", { class: "seg", role: "tablist", "aria-label": "Secciones de la ficha" });

  async function mostrarPestana(clave) {
    pestanaRecordada = clave;
    // La dirección sigue a la pestaña Declaración, para enlazarla desde los pendientes del inicio.
    const direccion = clave === "declaracion" ? `#/productores/${p.id}/declaracion` : `#/productores/${p.id}`;
    if (location.hash !== direccion) history.replaceState(null, "", direccion);
    for (const b of barra.children) b.setAttribute("aria-selected", String(b.dataset.clave === clave));
    const generadores = { datos: pestanaDatos, parcelas: pestanaParcelas, declaracion: pestanaDeclaracion, documentos: pestanaDocumentos, acceso: pestanaAcceso };
    try {
      cuerpo.replaceChildren(await generadores[clave](p, ctx));
    } catch (error) {
      cuerpo.replaceChildren(vacio({ titulo: "No se pudo cargar", texto: error.message }));
    }
  }
  for (const [clave, texto] of PESTANAS) {
    barra.append(h("button", { type: "button", role: "tab", "data-clave": clave, onclick: () => mostrarPestana(clave) }, texto));
  }
  if (ctx.parametros[1]) pestanaRecordada = ctx.parametros[1];
  mostrarPestana(PESTANAS.some(([c]) => c === pestanaRecordada) ? pestanaRecordada : "datos");

  const n = p.parcelas.activas;
  return {
    titulo: nombre,
    migas: [["Productores", "#/productores"], ["Padrón", "#/productores"], [nombre]],
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: avatar(p.nombres, p.apellidos, "lg"),
        titulo: nombre,
        insignias: p.pendientes.length
          ? p.pendientes.map((x) => h("span", { class: "badge warn" }, h("span", { class: "dot" }), PENDIENTES_PERSONAL[x]))
          : h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Sin pendientes"),
        detalle: [h("span", { class: "mono" }, `DNI ${p.dni}`), p.codigo_socio && ` · Socio ${p.codigo_socio}`, ` · Afiliado desde ${fecha(p.afiliado_desde)}`],
        cifra: hectareas(p.parcelas.area_total_ha),
        cifraTexto: `${n} ${n === 1 ? "parcela activa" : "parcelas activas"}`,
      }),
      h("div", { class: "ins-tabs seg-scroll" }, barra),
      cuerpo,
    ),
  };
}

