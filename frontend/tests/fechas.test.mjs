// Pruebas de frontend/js/fechas.js con el corredor de Node: node --test frontend/tests/
// Las fechas se escriben y se muestran dd/mm/aaaa (con hora, dd/mm/aaaa hh:mm en 24 horas) sin depender del
// idioma del navegador; la API recibe ISO.

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  completarAlEscribir,
  diasDelMes,
  fechaLima,
  leerFecha,
  leerFechaHora,
  leerFechasHora,
  momentoLima,
  mostrarFecha,
  mostrarFechaHora,
  problemaFecha,
} from "../js/fechas.js";

describe("leerFecha", () => {
  it("lee dd/mm/aaaa como día, mes y año", () => {
    assert.equal(leerFecha("06/09/2026"), "2026-09-06");
    assert.equal(leerFecha("6/9/2026"), "2026-09-06");
    assert.equal(leerFecha(" 06-09-2026 "), "2026-09-06");
    assert.equal(leerFecha("06.09.2026"), "2026-09-06");
    assert.equal(leerFecha("06092026"), "2026-09-06");
    assert.equal(leerFecha("31/12/2020"), "2020-12-31");
  });

  it("rechaza las fechas que no existen", () => {
    assert.equal(leerFecha("31/02/2026"), null);
    assert.equal(leerFecha("29/02/2025"), null);
    assert.equal(leerFecha("31/04/2026"), null);
    assert.equal(leerFecha("00/09/2026"), null);
    assert.equal(leerFecha("06/13/2026"), null);
    assert.equal(leerFecha("06/00/2026"), null);
    assert.equal(leerFecha("29/02/1900"), null);
  });

  it("acepta el 29 de febrero de los años bisiestos", () => {
    assert.equal(leerFecha("29/02/2028"), "2028-02-29");
    assert.equal(leerFecha("29/02/2000"), "2000-02-29");
    assert.equal(diasDelMes(2024, 2), 29);
    assert.equal(diasDelMes(2026, 2), 28);
  });

  it("rechaza lo que no tiene la forma dd/mm/aaaa", () => {
    for (const texto of ["", "   ", null, undefined, "2026-09-06", "06/09/26", "06/09", "6 de septiembre", "06/09/2026 10:00", "aa/bb/cccc"]) {
      assert.equal(leerFecha(texto), null, String(texto));
    }
  });
});

describe("leerFechaHora", () => {
  it("lee dd/mm/aaaa hh:mm en 24 horas", () => {
    assert.equal(leerFechaHora("06/09/2026 23:59"), "2026-09-06T23:59");
    assert.equal(leerFechaHora("06/09/2026 00:00"), "2026-09-06T00:00");
    assert.equal(leerFechaHora("06/09/2026 7:05"), "2026-09-06T07:05");
    assert.equal(leerFechaHora("6/9/2026  14:30"), "2026-09-06T14:30");
  });

  it("rechaza horas y fechas imposibles", () => {
    assert.equal(leerFechaHora("06/09/2026 24:00"), null);
    assert.equal(leerFechaHora("06/09/2026 12:60"), null);
    assert.equal(leerFechaHora("31/02/2026 10:00"), null);
    assert.equal(leerFechaHora("06/09/2026"), null);
    assert.equal(leerFechaHora("06/09/2026 7:5"), null);
    assert.equal(leerFechaHora("06/09/2026 07:05 p. m."), null);
  });
});

describe("mostrar", () => {
  it("muestra ISO como dd/mm/aaaa y dd/mm/aaaa hh:mm", () => {
    assert.equal(mostrarFecha("2026-09-06"), "06/09/2026");
    assert.equal(mostrarFechaHora("2026-09-06T07:05"), "06/09/2026 07:05");
    assert.equal(mostrarFecha(""), "");
    assert.equal(mostrarFecha(null), "");
    assert.equal(mostrarFechaHora("2026-09-06"), "");
  });

  it("ida y vuelta sin cambios", () => {
    for (const iso of ["2026-09-06", "2028-02-29", "2020-12-31", "2027-01-01"]) assert.equal(leerFecha(mostrarFecha(iso)), iso);
    for (const iso of ["2026-09-06T07:05", "2026-09-06T23:59", "2026-12-31T00:00"]) assert.equal(leerFechaHora(mostrarFechaHora(iso)), iso);
    assert.equal(mostrarFecha(leerFecha("6/9/2026")), "06/09/2026");
  });

  it("pasa los instantes de la API a hora de Lima (UTC-5)", () => {
    assert.equal(momentoLima("2026-09-06T04:30:00Z"), "2026-09-05T23:30");
    assert.equal(momentoLima("2026-09-06T12:05:00+00:00"), "2026-09-06T07:05");
    assert.equal(fechaLima("2026-09-06T04:30:00Z"), "05/09/2026");
    assert.equal(fechaLima("2026-09-06T04:30:00Z", { hora: true }), "05/09/2026 23:30");
    assert.equal(fechaLima("2026-09-06T17:45:00-05:00", { hora: true }), "06/09/2026 17:45");
    // Una fecha sin hora se muestra tal cual, sin correrla de día.
    assert.equal(fechaLima("2026-09-06"), "06/09/2026");
    // Lo que no es una fecha no rompe la pantalla: se muestra como llegó.
    assert.equal(fechaLima("sin fecha"), "sin fecha");
  });
});

describe("problemaFecha", () => {
  it("explica en español por qué una fecha no sirve", () => {
    assert.equal(problemaFecha("31/02/2026"), "La fecha 31/02/2026 no existe: revisa el día y el mes.");
    assert.equal(problemaFecha("29/2/2025"), "La fecha 29/02/2025 no existe: revisa el día y el mes.");
    assert.equal(problemaFecha("2026-09-06"), "Escribe la fecha con el formato dd/mm/aaaa.");
    assert.equal(problemaFecha("06/09/2026 24:00", { hora: true }), "La hora va de 00:00 a 23:59.");
    assert.equal(problemaFecha("06/09/2026", { hora: true }), "Escribe la fecha y la hora con el formato dd/mm/aaaa hh:mm (24 horas).");
  });

  it("no ve problema en una fecha válida ni en un campo vacío", () => {
    assert.equal(problemaFecha("06/09/2026"), null);
    assert.equal(problemaFecha(""), null);
    assert.equal(problemaFecha("06/09/2026 07:05", { hora: true }), null);
  });

  it("respeta los límites en ISO", () => {
    assert.equal(problemaFecha("06/09/2026", { max: "2026-09-05" }), "La fecha no puede ser posterior al 05/09/2026.");
    assert.equal(problemaFecha("06/09/2026", { min: "2026-09-07" }), "La fecha no puede ser anterior al 07/09/2026.");
    assert.equal(problemaFecha("06/09/2026", { min: "2026-09-06", max: "2026-09-06" }), null);
    assert.equal(
      problemaFecha("06/09/2026 10:01", { hora: true, max: "2026-09-06T10:00" }),
      "La fecha y hora no pueden ser posteriores al 06/09/2026 10:00.",
    );
    assert.equal(problemaFecha("06/09/2026 10:00", { hora: true, max: "2026-09-06T10:00" }), null);
  });
});

describe("completarAlEscribir", () => {
  it("agrega las barras para que baste con teclear los números", () => {
    assert.equal(completarAlEscribir("06"), "06/");
    assert.equal(completarAlEscribir("06/09"), "06/09/");
    assert.equal(completarAlEscribir("6/09"), "6/09/");
    assert.equal(completarAlEscribir("06/09/2026"), "06/09/2026");
    assert.equal(completarAlEscribir("6"), "6");
    assert.equal(completarAlEscribir("6/9"), "6/9");
  });

  it("no duplica un separador que la persona también escribió", () => {
    assert.equal(completarAlEscribir("06//"), "06/");
    assert.equal(completarAlEscribir("06/09//"), "06/09/");
  });

  it("con hora agrega el espacio y los dos puntos", () => {
    assert.equal(completarAlEscribir("06/09/2026", { hora: true }), "06/09/2026 ");
    assert.equal(completarAlEscribir("06/09/2026 07", { hora: true }), "06/09/2026 07:");
    assert.equal(completarAlEscribir("06/09/2026  ", { hora: true }), "06/09/2026 ");
    assert.equal(completarAlEscribir("06/09/2026 07::", { hora: true }), "06/09/2026 07:");
    assert.equal(leerFechaHora(["0", "6", "0", "9", "2", "0", "2", "6", "0", "7", "0", "5"].reduce((t, c) => completarAlEscribir(t + c, { hora: true }), "")), "2026-09-06T07:05");
  });
});

describe("leerFechasHora", () => {
  it("lee una fecha con hora por línea y avisa la línea que no sirve", () => {
    assert.deepEqual(leerFechasHora("06/09/2026 08:00\n\n07/09/2026 16:30\n"), { valores: ["2026-09-06T08:00", "2026-09-07T16:30"], problema: null });
    assert.deepEqual(leerFechasHora("06/09/2026 08:00\n31/02/2026 10:00"), {
      valores: ["2026-09-06T08:00"],
      problema: "Línea 2: La fecha 31/02/2026 no existe: revisa el día y el mes.",
    });
    assert.deepEqual(leerFechasHora(""), { valores: [], problema: null });
  });
});
