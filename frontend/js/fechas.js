// Fechas como se escriben en el Perú: dd/mm/aaaa y, con hora, dd/mm/aaaa hh:mm en 24 horas. El resultado no
// depende del idioma del navegador: no se usan los selectores de fecha nativos ni formatos sin opciones
// explícitas. La API sigue recibiendo ISO: "AAAA-MM-DD" para una fecha y "AAAA-MM-DDTHH:MM" (hora de Lima)
// para una fecha con hora, que cada pantalla completa con su desfase al enviar.
// Módulo puro, sin DOM ni importaciones: sus pruebas corren con node --test (frontend/tests/).

const FECHA = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/;
const FECHA_JUNTA = /^(\d{2})(\d{2})(\d{4})$/;
const FECHA_HORA = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:\s+|T)(\d{1,2}):(\d{2})$/;
const ISO_FECHA = /^(\d{4})-(\d{2})-(\d{2})/;
const ISO_FECHA_HORA = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/;
const SOLO_FECHA = /^\d{4}-\d{2}-\d{2}$/;

const dos = (n) => String(n).padStart(2, "0");

/** Días del mes (1 a 12) en ese año, con febrero de 29 días en los bisiestos. */
export function diasDelMes(anio, mes) {
  const bisiesto = (anio % 4 === 0 && anio % 100 !== 0) || anio % 400 === 0;
  return [31, bisiesto ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1];
}

/** "AAAA-MM-DD" si el día existe en el calendario; null si no. */
function fechaIso(dia, mes, anio) {
  if (anio < 1 || mes < 1 || mes > 12 || dia < 1 || dia > diasDelMes(anio, mes)) return null;
  return `${String(anio).padStart(4, "0")}-${dos(mes)}-${dos(dia)}`;
}

/**
 * Lee "dd/mm/aaaa" (también d/m/aaaa, con guion o punto, o los ocho dígitos juntos) y devuelve "AAAA-MM-DD".
 * null si el texto no tiene esa forma o la fecha no existe (31/02, 29/02 de un año no bisiesto).
 */
export function leerFecha(texto) {
  const t = String(texto ?? "").trim();
  const m = FECHA.exec(t) ?? FECHA_JUNTA.exec(t);
  return m ? fechaIso(Number(m[1]), Number(m[2]), Number(m[3])) : null;
}

/** Lee "dd/mm/aaaa hh:mm" (24 horas) y devuelve "AAAA-MM-DDTHH:MM"; null si no sirve. */
export function leerFechaHora(texto) {
  const m = FECHA_HORA.exec(String(texto ?? "").trim());
  if (!m) return null;
  const dia = fechaIso(Number(m[1]), Number(m[2]), Number(m[3]));
  const [hora, minuto] = [Number(m[4]), Number(m[5])];
  if (!dia || hora > 23 || minuto > 59) return null;
  return `${dia}T${dos(hora)}:${dos(minuto)}`;
}

/** "AAAA-MM-DD" (o el comienzo de un ISO más largo) como "dd/mm/aaaa"; "" si no es una fecha ISO. */
export function mostrarFecha(iso) {
  const m = ISO_FECHA.exec(String(iso ?? ""));
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** "AAAA-MM-DDTHH:MM" (hora local, sin convertir) como "dd/mm/aaaa hh:mm"; "" si no tiene esa forma. */
export function mostrarFechaHora(iso) {
  const m = ISO_FECHA_HORA.exec(String(iso ?? ""));
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : "";
}

// ---------- Hora de Lima (el Perú no cambia de hora: siempre UTC-5) ----------

const PARTES_LIMA = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Lima",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** El instante (Date, milisegundos o ISO con zona) como "AAAA-MM-DDTHH:MM" en hora de Lima. */
export function momentoLima(valor = new Date()) {
  const p = Object.fromEntries(PARTES_LIMA.formatToParts(new Date(valor)).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

export const hoyLima = () => momentoLima().slice(0, 10);

/**
 * Para listas y fichas: una fecha "AAAA-MM-DD" se muestra tal cual (dd/mm/aaaa); un instante de la API se
 * pasa a hora de Lima, como dd/mm/aaaa o, con `hora`, dd/mm/aaaa hh:mm.
 */
export function fechaLima(valor, { hora = false } = {}) {
  if (SOLO_FECHA.test(String(valor))) return mostrarFecha(valor);
  if (Number.isNaN(new Date(valor).getTime())) return String(valor);
  const local = momentoLima(valor);
  return hora ? mostrarFechaHora(local) : mostrarFecha(local);
}

// ---------- Validación y escritura ----------

/**
 * Por qué el texto no sirve como fecha (o como fecha y hora, con `hora`), en un mensaje listo para mostrar;
 * null si sirve o si está vacío (lo obligatorio lo decide el campo). `min` y `max` van en ISO.
 */
export function problemaFecha(texto, { hora = false, min, max } = {}) {
  const t = String(texto ?? "").trim();
  if (!t) return null;
  const valor = hora ? leerFechaHora(t) : leerFecha(t);
  if (!valor) {
    const forma = hora ? FECHA_HORA.exec(t) : (FECHA.exec(t) ?? FECHA_JUNTA.exec(t));
    if (!forma) return hora ? "Escribe la fecha y la hora con el formato dd/mm/aaaa hh:mm (24 horas)." : "Escribe la fecha con el formato dd/mm/aaaa.";
    if (hora && (Number(forma[4]) > 23 || Number(forma[5]) > 59)) return "La hora va de 00:00 a 23:59.";
    return `La fecha ${dos(forma[1])}/${dos(forma[2])}/${forma[3]} no existe: revisa el día y el mes.`;
  }
  const largo = hora ? 16 : 10;
  const mostrar = hora ? mostrarFechaHora : mostrarFecha;
  const sujeto = hora ? "La fecha y hora no pueden ser" : "La fecha no puede ser";
  if (min && valor < String(min).slice(0, largo)) return `${sujeto} ${hora ? "anteriores" : "anterior"} al ${mostrar(min)}.`;
  if (max && valor > String(max).slice(0, largo)) return `${sujeto} ${hora ? "posteriores" : "posterior"} al ${mostrar(max)}.`;
  return null;
}

/**
 * Mientras se escribe al final del campo: agrega "/" tras el día y el mes (y, con hora, el espacio y los dos
 * puntos), para que baste con teclear los números, y quita un separador repetido.
 */
export function completarAlEscribir(texto, { hora = false } = {}) {
  const t = String(texto ?? "")
    .replace(/([/.-])[/.-]+$/, "$1")
    .replace(/\s{2,}$/, " ")
    .replace(/::+$/, ":");
  if (/^\d{2}$/.test(t) || /^\d{1,2}\/\d{2}$/.test(t)) return `${t}/`;
  if (hora && /^\d{1,2}\/\d{1,2}\/\d{4}$/.test(t)) return `${t} `;
  if (hora && /^\d{1,2}\/\d{1,2}\/\d{4} \d{2}$/.test(t)) return `${t}:`;
  return t;
}

/**
 * Varias fechas con hora, una por línea (dd/mm/aaaa hh:mm). Devuelve { valores, problema }: los valores en
 * "AAAA-MM-DDTHH:MM" y, si una línea no sirve, el mensaje con su número.
 */
export function leerFechasHora(texto) {
  const lineas = String(texto ?? "").split(/\r?\n/);
  const valores = [];
  for (const [i, linea] of lineas.entries()) {
    if (!linea.trim()) continue;
    const problema = problemaFecha(linea, { hora: true });
    if (problema) return { valores, problema: `Línea ${i + 1}: ${problema}` };
    valores.push(leerFechaHora(linea));
  }
  return { valores, problema: null };
}
