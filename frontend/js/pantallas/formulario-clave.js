// Formulario de cambio de contraseña, compartido por "Cambio de contraseña" y "Mi perfil".
// Supabase cierra todas las sesiones al cambiarla, así que se vuelve a iniciar sesión con la nueva.

import { llamarApi } from "../api.js";
import { estado } from "../estado.js";
import { correoTecnico, iniciarSesion } from "../sesion.js";
import { campo, enviarCon, h } from "../ui.js";

export function reglasDeClave() {
  return estado.usuario?.rol === "productor"
    ? "Al menos 6 caracteres."
    : "Al menos 8 caracteres, con al menos una letra y un dígito.";
}

export function formularioClave({ alTerminar, textoBoton = "Cambiar contraseña" }) {
  const productor = estado.usuario?.rol === "productor";
  const minimo = productor ? 6 : 8;
  const boton = h("button", { class: "btn btn-primary", type: "submit" }, textoBoton);
  const formulario = h(
    "form",
    { class: "form" },
    campo({ etiqueta: "Contraseña actual", name: "clave_actual", type: "password", autocomplete: "current-password", required: true }),
    campo({
      etiqueta: "Nueva contraseña",
      name: "clave_nueva",
      type: "password",
      autocomplete: "new-password",
      minlength: minimo,
      maxlength: 72,
      required: true,
      ayuda: reglasDeClave(),
    }),
    campo({ etiqueta: "Confirma la nueva contraseña", name: "confirmacion", type: "password", autocomplete: "new-password", required: true }),
    boton,
  );

  enviarCon(formulario, boton, async ({ clave_actual, clave_nueva, confirmacion }) => {
    if (clave_nueva !== confirmacion) throw new Error("La confirmación no coincide con la nueva contraseña.");
    await llamarApi("/me/clave", { metodo: "POST", cuerpo: { clave_actual, clave_nueva } });
    const usuario = estado.usuario;
    await iniciarSesion(usuario.rol === "productor" ? correoTecnico(usuario.dni) : usuario.correo, clave_nueva);
    formulario.reset();
    await alTerminar();
  });
  return formulario;
}
