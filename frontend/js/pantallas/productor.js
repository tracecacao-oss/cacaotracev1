// Ficha del productor: encabezado con nombre, DNI y pendientes, y pestañas Datos, Parcelas,
// Documentos y Acceso.

import { llamarApi } from "../api.js";
import { formularioCarga, listaDocumentos } from "../documentos.js";
import { puede, rolEfectivo } from "../estado.js";
import { ESTADOS_MIDAGRI, PENDIENTES_PERSONAL, hectareas, insigniaAlerta, insigniaNivel } from "../textos.js";
import { abrirModal, campo, confirmar, enviarCon, fecha, h, icono, mostrarClaveTemporal, toast, vacio } from "../ui.js";
import { camposFicha, cuerpoFicha, insigniaAcceso, seccionesProductores } from "./productores.js";

const PESTANAS = [
  ["datos", "Datos"],
  ["parcelas", "Parcelas"],
  ["documentos", "Documentos"],
  ["acceso", "Acceso"],
];
let pestanaRecordada = "datos";

function dato(etiqueta, valor, { nivel, mono = false } = {}) {
  return h(
    "div",
    {},
    h("dt", {}, etiqueta),
    h("dd", { class: mono ? "mono" : null }, valor || "—"),
    nivel && valor ? h("dd", {}, insigniaNivel(nivel)) : null,
  );
}

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
  return h(
    "section",
    { class: "panel" },
    h(
      "div",
      { class: "panel-h" },
      h("div", {}, h("h2", {}, "Datos del productor"), h("p", { class: "panel-sub" }, "Cada dato muestra qué tan respaldado está.")),
      h(
        "div",
        { class: "fila-acciones" },
        edita && h("button", { class: "btn btn-sm", type: "button", onclick: () => abrirEdicion(p, recargar) }, "Editar ficha"),
        rolEfectivo() === "admin_cooperativa" &&
          h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => cerrarAfiliacion(p, navegar) }, "Cerrar afiliación"),
      ),
    ),
    h(
      "dl",
      { class: "panel-b ficha" },
      dato("DNI", p.dni, { nivel: p.nivel_identidad, mono: true }),
      dato("Nombres", p.nombres, { nivel: p.nivel_identidad }),
      dato("Apellidos", p.apellidos, { nivel: p.nivel_identidad }),
      dato("RUC", p.ruc, { nivel: "declarado", mono: true }),
      dato("Dirección postal", p.direccion_postal, { nivel: "declarado" }),
      dato("Correo de contacto", p.correo_contacto, { nivel: "declarado" }),
      dato("Teléfono", p.telefono, { nivel: "declarado" }),
      h("div", {}, h("dt", {}, "Registro en el PPA de MIDAGRI"), h("dd", {}, p.ppa_registrado ? p.ppa_codigo || "Registrado" : "No registrado"), h("dd", {}, insigniaNivel(p.nivel_ppa))),
      dato("Código en Agro Digital", p.codigo_agrodigital, { nivel: "declarado", mono: true }),
      dato("Código de socio", p.codigo_socio, { mono: true }),
      dato("Afiliado desde", fecha(p.afiliado_desde)),
      dato(
        "Consentimiento de datos",
        p.consentimiento_datos_en
          ? `${fecha(p.consentimiento_datos_en)} · ${p.consentimiento_origen === "productor" ? "aceptado por el productor" : "firmado ante la cooperativa"}`
          : "Pendiente",
      ),
    ),
  );
}

async function pestanaParcelas(p, { navegar }) {
  const parcelas = await llamarApi(`/productores/${p.id}/parcelas`);
  const nueva =
    puede("registrarProductores") &&
    h("button", { class: "btn btn-primary btn-sm", type: "button", onclick: () => navegar(`#/productores/${p.id}/parcelas/nueva`) }, icono("mas"), "Nueva parcela");
  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-h" }, h("h2", {}, "Parcelas"), nueva),
    parcelas.length
      ? h(
          "div",
          { class: "tabla-caja" },
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
                  h("td", {}, h("a", { href: `#/parcelas/${x.id}` }, x.nombre), h("span", { class: "sec mono" }, `${x.codigo} · ${x.tipo_geometria}${x.estado === "inactiva" ? " · inactiva" : ""}`)),
                  h("td", { class: "mono" }, hectareas(x.area_total_ha)),
                  h("td", { class: "ocultar-sm" }, ESTADOS_MIDAGRI.find(([v]) => v === x.midagri_estado)?.[1], h("span", { class: "sec" }, insigniaNivel(x.nivel_midagri))),
                  h("td", {}, x.alertas.length ? x.alertas.map((a) => insigniaAlerta(a)) : h("span", { class: "sec" }, "Sin alertas")),
                ),
              ),
            ),
          ),
        )
      : vacio({ titulo: "Sin parcelas", texto: "Registra cada parcela por separado: dibujándola en el mapa o subiendo un archivo.", accion: nueva }),
  );
}

function pestanaDocumentos(p, { recargar }) {
  const gestiona = puede("registrarProductores");
  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-h" }, h("div", {}, h("h2", {}, "Documentos"), h("p", { class: "panel-sub" }, "Respaldo de la identidad y del registro en el PPA."))),
    listaDocumentos(p.documentos, { puedeAnular: gestiona, alCambiar: recargar }),
    gestiona &&
      h(
        "div",
        { class: "panel-b" },
        formularioCarga({
          tipos: [
            ["dni", "Copia del DNI"],
            ["constancia_ppa", "Constancia o captura del PPA"],
          ],
          ruta: `/productores/${p.id}/documentos`,
          alCargar: recargar,
        }),
      ),
  );
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
  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-h" }, h("div", {}, h("h2", {}, "Acceso a CacaoTrace"), h("p", { class: "panel-sub" }, "Ingresa desde su celular con su DNI y contraseña.")), insigniaAcceso(p.acceso)),
    h(
      "div",
      { class: "panel-b form" },
      p.acceso.existe
        ? h("dl", { class: "ficha" }, dato("Usuario", `DNI ${p.dni}`, { mono: true }), dato("Último ingreso", fecha(p.acceso.ultimo_acceso_en, { hora: true })))
        : h("p", { class: "panel-sub" }, "Todavía no tiene acceso. Al crearlo verás una contraseña temporal para entregarle."),
      acciones.length ? h("div", { class: "fila-acciones" }, acciones) : null,
    ),
  );
}

export default async function productor(ctx) {
  const p = await llamarApi(`/productores/${ctx.parametros[0]}`);
  const nombre = `${p.nombres} ${p.apellidos}`;
  const cuerpo = h("div", { class: "contenido-pestana" });
  const barra = h("div", { class: "pestanas", role: "tablist", "aria-label": "Secciones de la ficha" });

  async function mostrarPestana(clave) {
    pestanaRecordada = clave;
    for (const b of barra.children) b.setAttribute("aria-selected", String(b.dataset.clave === clave));
    const generadores = { datos: pestanaDatos, parcelas: pestanaParcelas, documentos: pestanaDocumentos, acceso: pestanaAcceso };
    try {
      cuerpo.replaceChildren(await generadores[clave](p, ctx));
    } catch (error) {
      cuerpo.replaceChildren(vacio({ titulo: "No se pudo cargar", texto: error.message }));
    }
  }
  for (const [clave, texto] of PESTANAS) {
    barra.append(h("button", { type: "button", role: "tab", "data-clave": clave, onclick: () => mostrarPestana(clave) }, texto));
  }
  mostrarPestana(PESTANAS.some(([c]) => c === pestanaRecordada) ? pestanaRecordada : "datos");

  return {
    titulo: nombre,
    migas: [["Productores", "#/productores"], [nombre]],
    secciones: seccionesProductores(),
    contenido: [
      h(
        "div",
        { class: "cabecera-ficha" },
        h("span", { class: "mono" }, `DNI ${p.dni}`),
        p.pendientes.length
          ? p.pendientes.map((x) => h("span", { class: "badge warn" }, h("span", { class: "dot" }), PENDIENTES_PERSONAL[x]))
          : h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Sin pendientes"),
      ),
      barra,
      cuerpo,
    ],
  };
}

