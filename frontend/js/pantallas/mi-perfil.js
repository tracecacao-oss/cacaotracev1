// Mi perfil: datos propios y cambio de contraseña. El productor ve además su ficha, sus
// pendientes en lenguaje simple y carga la foto de su DNI desde el celular.

import { llamarApi } from "../api.js";
import { formularioCarga, listaDocumentos } from "../documentos.js";
import { estado, nombreCooperativa, ROTULOS_ROL } from "../estado.js";
import { PENDIENTES_PRODUCTOR, insigniaNivel } from "../textos.js";
import { campo, enviarCon, h, toast } from "../ui.js";
import { formularioClave } from "./formulario-clave.js";

function dato(etiqueta, valor, extra = null, mono = false) {
  return h("div", {}, h("dt", {}, etiqueta), h("dd", { class: mono ? "mono" : null }, valor || "—"), extra && h("dd", {}, extra));
}

function seccionClave(recargarUsuario, recargar) {
  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-h" }, h("h2", {}, "Cambiar contraseña")),
    h(
      "div",
      { class: "panel-b" },
      formularioClave({
        alTerminar: async () => {
          await recargarUsuario();
          toast("Tu contraseña se cambió.");
          recargar();
        },
      }),
    ),
  );
}

async function perfilProductor({ recargarUsuario, recargar }) {
  const f = await llamarApi("/mi/productor");
  const boton = h("button", { class: "btn btn-sm", type: "submit" }, "Guardar teléfono");
  const telefono = h("form", { class: "form fila-form" }, campo({ etiqueta: "Mi teléfono", name: "telefono", type: "tel", value: f.telefono ?? "", maxlength: 30 }), boton);
  enviarCon(telefono, boton, async ({ telefono: valor }) => {
    await llamarApi("/mi/productor", { metodo: "PATCH", cuerpo: { telefono: valor || null } });
    toast("Teléfono guardado.");
    recargar();
  });

  return [
    h(
      "section",
      { class: "panel" },
      h("div", { class: "panel-h" }, h("h2", {}, "Lo que falta")),
      h(
        "div",
        { class: "panel-b form" },
        f.pendientes.length
          ? f.pendientes.map((p) =>
              h("p", { class: "alerta warn" }, PENDIENTES_PRODUCTOR[p], p === "sin_parcelas" ? h("a", { href: "#/mis-parcelas/nueva", class: "enlace-accion" }, " Registrar ahora") : null),
            )
          : h("p", { class: "alerta info" }, "Tu ficha está completa."),
      ),
    ),
    h(
      "section",
      { class: "panel" },
      h("div", { class: "panel-h" }, h("h2", {}, "Mis datos")),
      h(
        "dl",
        { class: "panel-b ficha" },
        dato("DNI", f.dni, insigniaNivel(f.nivel_identidad), true),
        dato("Nombres", f.nombres),
        dato("Apellidos", f.apellidos),
        dato("Dirección", f.direccion_postal),
        dato("Registro en el PPA", f.ppa_registrado ? f.ppa_codigo || "Registrado" : "No registrado", insigniaNivel(f.nivel_ppa)),
        dato("Cooperativa", nombreCooperativa()),
      ),
      h("div", { class: "panel-b" }, telefono),
    ),
    h(
      "section",
      { class: "panel" },
      h("div", { class: "panel-h" }, h("div", {}, h("h2", {}, "Mi DNI"), h("p", { class: "panel-sub" }, "Toma una foto clara del DNI o sube un PDF."))),
      listaDocumentos(f.documentos, { alCambiar: recargar }),
      h(
        "div",
        { class: "panel-b" },
        formularioCarga({
          tipos: [
            ["dni", "Foto de mi DNI"],
            ["constancia_ppa", "Constancia del PPA"],
          ],
          ruta: "/mi/documentos",
          alCargar: recargar,
          textoBoton: "Subir",
        }),
      ),
    ),
    seccionClave(recargarUsuario, recargar),
  ];
}

export default async function miPerfil({ recargarUsuario, recargar }) {
  const u = estado.usuario;
  if (u.rol === "productor") {
    return { titulo: "Mi perfil", contenido: await perfilProductor({ recargarUsuario, recargar }) };
  }
  return {
    titulo: "Mi perfil",
    contenido: [
      h(
        "section",
        { class: "panel" },
        h("div", { class: "panel-h" }, h("h2", {}, "Mis datos")),
        h(
          "dl",
          { class: "panel-b ficha" },
          dato("Nombres", u.nombres),
          dato("Apellidos", u.apellidos),
          dato("Correo", u.correo),
          dato("Rol", ROTULOS_ROL[u.rol]),
          u.cooperativa && dato("Cooperativa", nombreCooperativa()),
        ),
      ),
      seccionClave(recargarUsuario, recargar),
    ],
  };
}
