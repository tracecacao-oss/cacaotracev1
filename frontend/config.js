// Valores públicos de la interfaz. Aquí no va ningún secreto: este archivo se publica tal cual.
// La clave publicable es segura a la vista mientras RLS esté activo y el bucket sea privado.

const enLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_URL = enLocal ? "http://localhost:8000" : "https://cacaotrace-api.onrender.com";

// Proyecto de Supabase "cacaotrace". Solo la URL y la clave publicable; la secreta vive en Render.
export const SUPABASE_URL = "https://fbntvwuirklffsohrqoo.supabase.co";
export const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_kW2OS1Nto6mhXsn6-c7tJg_Q2kiI8Mg";

export const PRODUCTOR_EMAIL_DOMAIN = "productores.cacaotrace.local";

// Capa satelital: Esri World Imagery en ArcGIS Location Platform (elegida por el equipo).
// Clave pública "Public application", solo con el privilegio de Basemaps. Está restringida a
// https://cacaotrace.pages.dev, pero Esri no aplica esa restricción en las teselas (probado el
// 2026-10-05): la cuenta tiene alerta de uso y la clave se rota si hay abuso. Vence al año.
// Vacía = mapa solo con calles.
export const ESRI_API_KEY =
  "AAPTaAJQYBi9VfpTCTAq9NkdPBg..QjXk9h5GDq2Kr_RLVfqpzNVaBa-EVS9YwCcGMsml-yk-7CVRf3jmpEOMnzYMinwR-KK_eb9gWCB4_aa1s8D8cBGBQtWCMCaQG67nzg6K0asCChlYMbl-i6lEqpr2aSgVCub3OQ4d56IbETWgIZxPN13SpBMknu3xnpW5MwhPK_IqN1u6FcTDxcrzZp6VptsG7juRPv0ydD9Px6jH_RMIjNtic7SsglwGxbcxTKGGoz0YFfB4AmXECoN1ocEl1a0.AT1_wb3efEBF";
