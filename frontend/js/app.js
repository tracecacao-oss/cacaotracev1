// Punto de entrada de la interfaz.

import { alEsperarServidor } from "./api.js";
import { aplicarPreferencias } from "./preferencias.js";
import { mostrar } from "./router.js";

aplicarPreferencias();

const aviso = document.getElementById("aviso-servidor");
alEsperarServidor((visible) => {
  aviso.hidden = !visible;
});

window.addEventListener("hashchange", mostrar);
mostrar();
