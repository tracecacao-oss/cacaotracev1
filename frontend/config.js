// Valores públicos de la interfaz. Aquí no va ningún secreto: este archivo se publica tal cual.
// La clave publicable es segura a la vista mientras RLS esté activo y el bucket sea privado.

const enLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_URL = enLocal ? "http://localhost:8000" : "https://cacaotrace-api.onrender.com";

// Proyecto de Supabase "cacaotrace". Solo la URL y la clave publicable; la secreta vive en Render.
export const SUPABASE_URL = "https://fbntvwuirklffsohrqoo.supabase.co";
export const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_kW2OS1Nto6mhXsn6-c7tJg_Q2kiI8Mg";

export const PRODUCTOR_EMAIL_DOMAIN = "productores.cacaotrace.local";

// Capa satelital: Esri World Imagery en ArcGIS Location Platform (aprobada por el equipo).
// Es una clave pública, restringida al dominio de la interfaz; vacía = mapa solo con calles.
export const ESRI_API_KEY = "";
