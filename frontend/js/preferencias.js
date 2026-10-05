// Preferencias de cada navegador: tema claro u oscuro y barra lateral contraída.
// Son comodidades locales: si el almacenamiento falla, la interfaz funciona igual.

const CLAVE_TEMA = "cacaotrace.tema";
const CLAVE_MENU = "cacaotrace.menu";

function leer(clave) {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function guardar(clave, valor) {
  try {
    if (valor == null) localStorage.removeItem(clave);
    else localStorage.setItem(clave, valor);
  } catch {
    // Sin almacenamiento la preferencia dura solo esta visita.
  }
}

const oscuroDelSistema = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

/** Sin elección guardada se sigue al sistema operativo. */
export function temaActual() {
  return document.documentElement.dataset.theme ?? (oscuroDelSistema() ? "dark" : "light");
}

export function cambiarTema() {
  const nuevo = temaActual() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = nuevo;
  guardar(CLAVE_TEMA, nuevo);
  return nuevo;
}

export function menuContraido() {
  return document.body.classList.contains("side-min");
}

export function alternarMenu() {
  const contraido = document.body.classList.toggle("side-min");
  guardar(CLAVE_MENU, contraido ? "min" : null);
}

/** Se llama una vez al cargar la app, antes de pintar. */
export function aplicarPreferencias() {
  const tema = leer(CLAVE_TEMA);
  if (tema === "light" || tema === "dark") document.documentElement.dataset.theme = tema;
  document.body.classList.toggle("side-min", leer(CLAVE_MENU) === "min");
}
