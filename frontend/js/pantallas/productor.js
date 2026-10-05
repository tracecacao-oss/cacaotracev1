// Ficha del productor (versión mínima) con la gestión de su acceso por DNI.
// La Parte 3 agrega los datos completos y las parcelas.

import { llamarApi } from "../api.js";
import { puede } from "../estado.js";
import { confirmar, fecha, h, mostrarClaveTemporal, toast } from "../ui.js";
import { insigniaAcceso } from "./productores.js";

function dato(etiqueta, valor, mono = false) {
  return h("div", {}, h("dt", {}, etiqueta), h("dd", { class: mono ? "mono" : null }, valor ?? "—"));
}

export default async function productor({ parametros, recargar }) {
  const p = await llamarApi(`/productores/${parametros[0]}`);
  const nombre = `${p.nombres} ${p.apellidos}`;
  const gestiona = puede("gestionarAccesos");
  const verClave = mostrarClaveTemporal({ titulo: "Contraseña temporal del productor", persona: nombre, usuario: `DNI ${p.dni}` });

  async function ejecutar(boton, accion) {
    boton.classList.add("is-loading");
    try {
      await accion();
    } catch (error) {
      toast(error.message, "bad");
    } finally {
      boton.classList.remove("is-loading");
    }
  }

  const acciones = [];
  if (gestiona && (!p.acceso.existe || !p.acceso.activo)) {
    const crear = h("button", { class: "btn btn-primary", type: "button" }, "Crear acceso");
    crear.addEventListener("click", () =>
      ejecutar(crear, async () => {
        verClave(await llamarApi(`/productores/${p.id}/acceso`, { metodo: "POST" }));
        recargar();
      }),
    );
    acciones.push(crear);
  }
  if (gestiona && p.acceso.existe && p.acceso.activo) {
    const restablecer = h("button", { class: "btn", type: "button" }, "Restablecer contraseña");
    restablecer.addEventListener("click", () =>
      ejecutar(restablecer, async () => {
        const seguro = await confirmar({
          titulo: "Restablecer contraseña",
          texto: `Se generará una nueva contraseña temporal para ${nombre} y se cerrarán sus sesiones abiertas.`,
          boton: "Restablecer",
        });
        if (!seguro) return;
        verClave(await llamarApi(`/productores/${p.id}/acceso/restablecer-clave`, { metodo: "POST" }));
        recargar();
      }),
    );
    const desactivar = h("button", { class: "btn btn-danger", type: "button" }, "Desactivar acceso");
    desactivar.addEventListener("click", () =>
      ejecutar(desactivar, async () => {
        const seguro = await confirmar({
          titulo: "Desactivar acceso",
          texto: `${nombre} ya no podrá ingresar. Sus datos se conservan y el acceso se puede crear de nuevo.`,
          boton: "Desactivar",
          peligro: true,
        });
        if (!seguro) return;
        await llamarApi(`/productores/${p.id}/acceso`, { metodo: "DELETE" });
        toast("Acceso desactivado.");
        recargar();
      }),
    );
    acciones.push(restablecer, desactivar);
  }

  const consentimiento = p.consentimiento_datos_en
    ? `Registrado el ${fecha(p.consentimiento_datos_en)} (${p.consentimiento_origen === "productor" ? "aceptado por el productor" : "firmado ante la cooperativa"})`
    : "Pendiente: el productor lo acepta en su primer ingreso";

  return {
    titulo: nombre,
    migas: [["Productores", "#/productores"], [nombre]],
    contenido: [
      h(
        "section",
        { class: "panel" },
        h("div", { class: "panel-h" }, h("h2", {}, "Datos del productor")),
        h(
          "dl",
          { class: "panel-b ficha" },
          dato("DNI", p.dni, true),
          dato("Nombres", p.nombres),
          dato("Apellidos", p.apellidos),
          dato("Teléfono", p.telefono),
          dato("Código de socio", p.codigo_socio, true),
          dato("Afiliado desde", fecha(p.afiliado_desde)),
          dato("Consentimiento de datos", consentimiento),
        ),
      ),
      h(
        "section",
        { class: "panel" },
        h(
          "div",
          { class: "panel-h" },
          h("div", {}, h("h2", {}, "Acceso a CacaoTrace"), h("p", { class: "panel-sub" }, "Ingresa desde su celular con su DNI y contraseña.")),
          insigniaAcceso(p.acceso),
        ),
        h(
          "div",
          { class: "panel-b form" },
          p.acceso.existe
            ? h("dl", { class: "ficha" }, dato("Usuario", `DNI ${p.dni}`, true), dato("Último ingreso", fecha(p.acceso.ultimo_acceso_en, { hora: true })))
            : h("p", { class: "panel-sub" }, "Todavía no tiene acceso. Al crearlo verás una contraseña temporal para entregarle."),
          acciones.length ? h("div", { class: "fila-acciones" }, acciones) : null,
        ),
      ),
    ],
  };
}
