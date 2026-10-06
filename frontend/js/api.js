// Único archivo que llama a fetch. Agrega el token, maneja el aviso de espera, cierra sesión
// ante un 401 y redirige ante cambio_clave_requerido.
// La API del plan gratuito puede estar dormida: si una llamada tarda más de 3 segundos se
// muestra "Conectando con el servidor" y se reintenta hasta 90 segundos.

import { API_URL } from "../config.js";
import { comprimirFormulario } from "./compresion.js";
import { enConsulta, estado } from "./estado.js";
import { cerrarSesion, tokenActual } from "./sesion.js";

const AVISO_TRAS_MS = 3000;
const LIMITE_TOTAL_MS = 90000;
const LIMITE_INTENTO_MS = 30000;
const PAUSA_REINTENTO_MS = 3000;
// Respuestas del proxy de Render mientras el servicio arranca o se redespliega.
const ESTADOS_REINTENTABLES = new Set([502, 504]);

export class ErrorApi extends Error {
  constructor(estadoHttp, codigo, mensaje, campos = []) {
    super(mensaje);
    this.estado = estadoHttp;
    this.codigo = codigo;
    this.campos = campos;
  }
}

let llamadasLentas = 0;
let mostrarAviso = () => {};
let alPerderSesion = () => {};

export function alEsperarServidor(funcion) {
  mostrarAviso = funcion;
}

/** Lo registra el router: qué hacer ante un 401 o un cambio de contraseña pendiente. */
export function alPerderLaSesion(funcion) {
  alPerderSesion = funcion;
}

const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

async function intentar(url, opciones, limiteMs) {
  const control = new AbortController();
  const corte = setTimeout(() => control.abort(), limiteMs);
  try {
    return await fetch(url, { ...opciones, signal: control.signal });
  } finally {
    clearTimeout(corte);
  }
}

async function leerRespuesta(respuesta) {
  if (respuesta.status === 204) return null;
  const datos = await respuesta.json().catch(() => null);
  if (respuesta.ok) return datos;
  const error = datos?.error ?? {};
  throw new ErrorApi(
    respuesta.status,
    error.codigo ?? "error",
    error.mensaje ?? `El servidor respondió ${respuesta.status}.`,
    error.campos ?? [],
  );
}

function armarUrl(ruta, parametros) {
  const url = new URL(API_URL + ruta);
  for (const [clave, valor] of Object.entries(parametros ?? {})) {
    if (valor !== undefined && valor !== null && valor !== "") url.searchParams.set(clave, valor);
  }
  return url;
}

/**
 * opciones: metodo, cuerpo, parametros, conToken (por defecto true),
 * sinConsulta (no enviar X-Cooperativa-Id aunque el superadmin esté consultando),
 * cooperativa (id que el superadmin lee en esta petición, sin entrar al modo consulta),
 * formulario (FormData con archivos; el navegador pone el Content-Type multipart),
 * unIntento (una sola petición con todo el tiempo: para lo que no debe repetirse, como emitir el DEX).
 */
export async function llamarApi(ruta, opciones = {}) {
  const { metodo = "GET", cuerpo, parametros, conToken = true, sinConsulta = false, cooperativa, formulario, unIntento = false } = opciones;
  const cabeceras = {};
  if (conToken) {
    const token = await tokenActual();
    if (token) cabeceras.Authorization = `Bearer ${token}`;
  }
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  // La cabecera solo vale en lecturas del superadmin; la API la ignora en cualquier otro caso.
  const consultada = cooperativa ?? (enConsulta() && !sinConsulta ? estado.consulta.id : null);
  if (metodo === "GET" && consultada) cabeceras["X-Cooperativa-Id"] = consultada;
  const pedido = {
    method: metodo,
    headers: cabeceras,
    // Las fotos se comprimen una vez, antes del primer intento (Parte 10).
    body: formulario ? await comprimirFormulario(formulario) : cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  };

  const inicio = Date.now();
  let lenta = false;
  const temporizador = setTimeout(() => {
    lenta = true;
    llamadasLentas += 1;
    mostrarAviso(true);
  }, AVISO_TRAS_MS);

  try {
    for (;;) {
      const restante = LIMITE_TOTAL_MS - (Date.now() - inicio);
      const quedaOtroIntento = !unIntento && restante > PAUSA_REINTENTO_MS;
      let respuesta;
      try {
        respuesta = await intentar(armarUrl(ruta, parametros), pedido, unIntento ? restante : Math.min(LIMITE_INTENTO_MS, restante));
      } catch {
        // Red caída o intento sin respuesta: se reintenta mientras quede tiempo.
        if (!quedaOtroIntento) {
          throw new ErrorApi(
            0,
            "servidor_no_disponible",
            "No se pudo conectar con el servidor. Intenta de nuevo en unos minutos.",
          );
        }
        await esperar(PAUSA_REINTENTO_MS);
        continue;
      }
      if (ESTADOS_REINTENTABLES.has(respuesta.status) && quedaOtroIntento) {
        await esperar(PAUSA_REINTENTO_MS);
        continue;
      }
      try {
        return await leerRespuesta(respuesta);
      } catch (error) {
        if (conToken && error.estado === 401) {
          await cerrarSesion();
          alPerderSesion("no_autenticado", error.message);
        } else if (error.codigo === "cambio_clave_requerido") {
          alPerderSesion("cambio_clave_requerido", error.message);
        }
        throw error;
      }
    }
  } finally {
    clearTimeout(temporizador);
    if (lenta) {
      llamadasLentas -= 1;
      if (llamadasLentas === 0) mostrarAviso(false);
    }
  }
}
