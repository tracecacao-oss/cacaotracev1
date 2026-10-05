// Sesión con Supabase Auth. supabase-js se usa solo para iniciar y cerrar sesión, leer la sesión
// y renovar el token; él guarda la sesión. El código propio no guarda tokens.

import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/+esm";
import { PRODUCTOR_EMAIL_DOMAIN, SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "../config.js";

export const configurado = Boolean(SUPABASE_URL && SUPABASE_PUBLISHABLE_KEY);

const supabase = configurado
  ? createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    })
  : null;

/** El productor entra con su DNI; Supabase Auth lo identifica por un correo técnico. */
export function correoTecnico(dni) {
  return `${dni}@${PRODUCTOR_EMAIL_DOMAIN}`;
}

export async function iniciarSesion(correo, clave) {
  const { error } = await supabase.auth.signInWithPassword({ email: correo, password: clave });
  if (!error) return;
  if (error.code === "invalid_credentials" || error.status === 400) {
    throw new Error("Los datos de ingreso no son correctos.");
  }
  if (error.code === "user_banned") {
    throw new Error("Tu cuenta está desactivada. Consulta con tu cooperativa.");
  }
  throw new Error("No se pudo iniciar sesión. Revisa tu conexión e intenta de nuevo.");
}

export async function cerrarSesion() {
  if (supabase) await supabase.auth.signOut({ scope: "local" });
}

export async function tokenActual() {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
