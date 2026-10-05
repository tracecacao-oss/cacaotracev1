// Valores públicos de la interfaz. Aquí no va ningún secreto: este archivo se publica tal cual.
// La clave publicable es segura a la vista mientras RLS esté activo y el bucket sea privado.

const enLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_URL = enLocal ? "http://localhost:8000" : "https://cacaotrace-api.onrender.com";

// Proyecto de Supabase: https://<ref>.supabase.co. Lo completa el equipo (Parte 1, bloque C).
export const SUPABASE_URL = "";
export const SUPABASE_PUBLISHABLE_KEY = "";

export const PRODUCTOR_EMAIL_DOMAIN = "productores.cacaotrace.local";
