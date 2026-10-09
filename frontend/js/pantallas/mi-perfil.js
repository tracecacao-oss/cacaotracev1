// Mi perfil, con el inspector del diseño: datos propios y cambio de contraseña. El productor ve
// además su ficha, sus pendientes en lenguaje simple y carga la foto de su DNI desde el celular.

import { llamarApi } from "../api.js";
import { formularioCarga, listaDocumentos } from "../documentos.js";
import { estado, nombreCooperativa, ROTULOS_ROL } from "../estado.js";
import { PENDIENTES_PRODUCTOR, insigniaNivel } from "../textos.js";
import { avatar, cabeceraFicha, campo, enviarCon, h, rejilla, seccion, toast } from "../ui.js";
import { formularioClave } from "./formulario-clave.js";

function seccionClave(recargarUsuario, recargar) {
  return seccion({
    titulo: "Cambiar contraseña",
    contenido: h(
      "div",
      { class: "formulario-angosto" },
      formularioClave({
        alTerminar: async () => {
          await recargarUsuario();
          toast("Tu contraseña se cambió.");
          recargar();
        },
      }),
    ),
  });
}

async function perfilProductor({ recargarUsuario, recargar }) {
  const f = await llamarApi("/mi/productor");
  const boton = h("button", { class: "btn btn-sm", type: "submit" }, "Guardar teléfono");
  const telefono = h("form", { class: "form fila-form formulario-angosto" }, campo({ etiqueta: "Mi teléfono", name: "telefono", type: "tel", value: f.telefono ?? "", maxlength: 30 }), boton);
  enviarCon(telefono, boton, async ({ telefono: valor }) => {
    await llamarApi("/mi/productor", { metodo: "PATCH", cuerpo: { telefono: valor || null } });
    toast("Teléfono guardado.");
    recargar();
  });

  return h(
    "section",
    { class: "panel inspector" },
    cabeceraFicha({
      inicio: avatar(f.nombres, f.apellidos, "lg"),
      titulo: `${f.nombres} ${f.apellidos}`,
      insignias: f.pendientes.length
        ? h("span", { class: "badge warn" }, h("span", { class: "dot" }), f.pendientes.length === 1 ? "1 pendiente" : `${f.pendientes.length} pendientes`)
        : h("span", { class: "badge ok" }, h("span", { class: "dot" }), "Ficha completa"),
      detalle: [h("span", { class: "mono" }, `DNI ${f.dni}`), ` · ${nombreCooperativa()}`],
    }),
    seccion({
      titulo: "Lo que falta",
      contenido: f.pendientes.length
        ? h(
            "div",
            { class: "form" },
            f.pendientes.map((p) =>
              h("p", { class: "alerta warn" }, PENDIENTES_PRODUCTOR[p], p === "sin_parcelas" ? h("a", { href: "#/mis-parcelas/nueva", class: "enlace-accion" }, " Registrar ahora") : null),
            ),
          )
        : h("p", { class: "alerta info" }, "Tu ficha está completa."),
    }),
    seccion({
      titulo: "Mis datos",
      contenido: [
        rejilla([
          { etiqueta: "DNI", valor: f.dni, mono: true, extra: insigniaNivel(f.nivel_identidad) },
          { etiqueta: "Nombres", valor: f.nombres },
          { etiqueta: "Apellidos", valor: f.apellidos },
          { etiqueta: "Dirección", valor: f.direccion_postal },
          { etiqueta: "Registro en el PPA", valor: f.ppa_registrado ? f.ppa_codigo || "Registrado" : "No registrado", extra: f.ppa_registrado && insigniaNivel(f.nivel_ppa) },
          { etiqueta: "Cooperativa", valor: nombreCooperativa() },
        ]),
        telefono,
      ],
    }),
    seccion({
      titulo: "Mi DNI",
      sub: "Toma una foto clara del DNI o sube un PDF.",
      contenido: [
        h("div", { class: "tbl-box" }, listaDocumentos(f.documentos, { alCambiar: recargar })),
        formularioCarga({
          tipos: [
            ["dni", "Foto de mi DNI"],
            ["constancia_ppa", "Constancia del PPA"],
          ],
          ruta: "/mi/documentos",
          alCargar: recargar,
          textoBoton: "Subir",
        }),
      ],
    }),
    seccionClave(recargarUsuario, recargar),
  );
}

export default async function miPerfil({ recargarUsuario, recargar }) {
  const u = estado.usuario;
  if (u.rol === "productor") {
    return { titulo: "Mi perfil", cabecera: null, contenido: await perfilProductor({ recargarUsuario, recargar }) };
  }
  return {
    titulo: "Mi perfil",
    cabecera: null,
    contenido: h(
      "section",
      { class: "panel inspector" },
      cabeceraFicha({
        inicio: avatar(u.nombres, u.apellidos, "lg"),
        titulo: `${u.nombres} ${u.apellidos}`,
        insignias: h("span", { class: "badge" }, ROTULOS_ROL[u.rol]),
        detalle: [u.correo, u.cooperativa ? ` · ${nombreCooperativa()}` : ""],
      }),
      seccion({
        titulo: "Mis datos",
        contenido: rejilla([
          { etiqueta: "Nombres", valor: u.nombres },
          { etiqueta: "Apellidos", valor: u.apellidos },
          { etiqueta: "Correo", valor: u.correo },
          { etiqueta: "Rol", valor: ROTULOS_ROL[u.rol] },
          u.cooperativa && { etiqueta: "Cooperativa", valor: nombreCooperativa() },
        ]),
      }),
      seccionClave(recargarUsuario, recargar),
    ),
  };
}
