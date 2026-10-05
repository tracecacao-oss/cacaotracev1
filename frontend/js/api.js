// Llamadas a la API. La API del plan gratuito puede estar dormida: si una llamada tarda más de
// 3 segundos se muestra "Conectando con el servidor" y se reintenta hasta 90 segundos.

import { API_URL } from "../config.js";

const AVISO_TRAS_MS = 3000;
const LIMITE_TOTAL_MS = 90000;
const LIMITE_INTENTO_MS = 30000;
const PAUSA_REINTENTO_MS = 3000;
// Respuestas del proxy de Render mientras el servicio arranca o se redespliega.
const ESTADOS_REINTENTABLES = new Set([502, 504]);

export class ErrorApi extends Error {
  constructor(estado, codigo, mensaje) {
    super(mensaje);
    this.estado = estado;
    this.codigo = codigo;
  }
}

let llamadasLentas = 0;
let mostrarAviso = () => {};

export function alEsperarServidor(funcion) {
  mostrarAviso = funcion;
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
  const datos = await respuesta.json().catch(() => null);
  if (respuesta.ok) return datos;
  const error = datos?.error ?? {};
  throw new ErrorApi(
    respuesta.status,
    error.codigo ?? "error",
    error.mensaje ?? `El servidor respondió ${respuesta.status}.`,
  );
}

export async function llamarApi(ruta, { metodo = "GET", token, cuerpo } = {}) {
  const cabeceras = {};
  if (token) cabeceras.Authorization = `Bearer ${token}`;
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  const opciones = {
    method: metodo,
    headers: cabeceras,
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
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
      const quedaOtroIntento = restante > PAUSA_REINTENTO_MS;
      try {
        const respuesta = await intentar(API_URL + ruta, opciones, Math.min(LIMITE_INTENTO_MS, restante));
        if (ESTADOS_REINTENTABLES.has(respuesta.status) && quedaOtroIntento) {
          await esperar(PAUSA_REINTENTO_MS);
          continue;
        }
        return await leerRespuesta(respuesta);
      } catch (error) {
        if (error instanceof ErrorApi) throw error;
        // Red caída o intento sin respuesta: se reintenta mientras quede tiempo.
        if (!quedaOtroIntento) {
          throw new ErrorApi(
            0,
            "servidor_no_disponible",
            "No se pudo conectar con el servidor. Intenta de nuevo en unos minutos.",
          );
        }
        await esperar(PAUSA_REINTENTO_MS);
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
