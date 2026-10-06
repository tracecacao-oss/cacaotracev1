// Parte 10: antes de subir un JPG o un PNG, la interfaz lo reduce a 1,600 píxeles en su lado mayor y lo
// guarda como JPEG con calidad 0.75. Los PDF y los demás archivos se suben sin cambios. La API calcula la
// huella SHA-256 sobre lo que recibe, que es lo que se guarda.

const LADO_MAXIMO = 1600;
const CALIDAD_JPEG = 0.75;
const TIPOS = new Set(["image/jpeg", "image/png"]);

function aJpeg(lienzo) {
  return new Promise((listo) => lienzo.toBlob(listo, "image/jpeg", CALIDAD_JPEG));
}

/** Devuelve el archivo comprimido, o el original si no es una foto o el navegador no puede leerla. */
export async function comprimirImagen(archivo) {
  if (!(archivo instanceof File) || !TIPOS.has(archivo.type) || typeof createImageBitmap !== "function") {
    return archivo;
  }
  let imagen;
  try {
    // "from-image" respeta la orientación EXIF de las fotos de celular.
    imagen = await createImageBitmap(archivo, { imageOrientation: "from-image" });
  } catch {
    return archivo;
  }
  const escala = Math.min(1, LADO_MAXIMO / Math.max(imagen.width, imagen.height));
  const ancho = Math.max(1, Math.round(imagen.width * escala));
  const alto = Math.max(1, Math.round(imagen.height * escala));
  const lienzo = document.createElement("canvas");
  lienzo.width = ancho;
  lienzo.height = alto;
  const pincel = lienzo.getContext("2d");
  // Un PNG con transparencia queda sobre fondo blanco, no negro.
  pincel.fillStyle = "#ffffff";
  pincel.fillRect(0, 0, ancho, alto);
  pincel.drawImage(imagen, 0, 0, ancho, alto);
  imagen.close?.();
  const comprimida = await aJpeg(lienzo);
  if (!comprimida) return archivo;
  // Un JPEG que ya era pequeño no se vuelve a comprimir para pesar más.
  if (archivo.type === "image/jpeg" && escala === 1 && comprimida.size >= archivo.size) return archivo;
  const nombre = `${archivo.name.replace(/\.[^.]*$/, "") || "foto"}.jpg`;
  return new File([comprimida], nombre, { type: "image/jpeg", lastModified: archivo.lastModified });
}

/** Copia el formulario con sus fotos comprimidas; los demás campos pasan igual. */
export async function comprimirFormulario(formulario) {
  if (!(formulario instanceof FormData)) return formulario;
  const copia = new FormData();
  for (const [clave, valor] of formulario.entries()) {
    const nuevo = await comprimirImagen(valor);
    if (nuevo instanceof File) copia.append(clave, nuevo, nuevo.name);
    else copia.append(clave, nuevo);
  }
  return copia;
}
