// Sesión con Supabase Auth. supabase-js se usa solo para iniciar y cerrar sesión, leer la sesión
// y renovar el token. Todo dato pasa por la API.

import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/+esm";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "../config.js";

export const configurado = Boolean(SUPABASE_URL && SUPABASE_PUBLISHABLE_KEY);

const supabase = configurado
  ? createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    })
  : null;

export async function iniciarSesion(correo, clave) {
  const { error } = await supabase.auth.signInWithPassword({ email: correo, password: clave });
  if (!error) return;
  if (error.status === 400 || error.code === "invalid_credentials") {
    throw new Error("Correo o contraseña incorrectos.");
  }
  throw new Error("No se pudo iniciar sesión. Revisa tu conexión e intenta de nuevo.");
}

export async function cerrarSesion() {
  if (supabase) await supabase.auth.signOut();
}

export async function tokenActual() {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
