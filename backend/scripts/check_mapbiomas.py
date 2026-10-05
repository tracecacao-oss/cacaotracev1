"""Comprobación de viabilidad de MapBiomas Perú (adenda de la Parte 4, sección 5.3).

Contra las direcciones reales y con la parcela ficticia de tests/datos/whisp_respuesta_real.json:
1. Que cada archivo anual responda y acepte peticiones por rango.
2. Que esté organizado en bloques (tiles), para que leer una ventana no traiga franjas enteras.
3. La memoria máxima y el tiempo de leer todos los años, en un proceso limitado a 512 MB.

Pasa si la memoria máxima del proceso no supera 150 MB y el tiempo no supera 60 segundos. No usa claves
ni escribe en disco. Desde backend/:

    python scripts/check_mapbiomas.py
"""

import ctypes
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

LIMITE_PROCESO_MB = 512
MEMORIA_MAXIMA_MB = 150
TIEMPO_MAXIMO_S = 60


def limitar_memoria(mb: int) -> str:
    """Limita la memoria del propio proceso: con un Job Object en Windows y RLIMIT_AS en Linux."""
    if sys.platform == "win32":
        from ctypes import wintypes

        class Basica(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class Extendida(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", Basica),
                ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        trabajo = k32.CreateJobObjectW(None, None)
        info = Extendida()
        info.BasicLimitInformation.LimitFlags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = mb * 1024 * 1024
        ok = k32.SetInformationJobObject(trabajo, 9, ctypes.byref(info), ctypes.sizeof(info))
        ok = ok and k32.AssignProcessToJobObject(trabajo, k32.GetCurrentProcess())
        return (
            f"Job Object de Windows, {mb} MB"
            if ok
            else f"no se pudo limitar (error {ctypes.get_last_error()})"
        )
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (mb * 1024 * 1024, mb * 1024 * 1024))
    return f"RLIMIT_AS, {mb} MB"


def memoria_maxima_mb() -> float:
    """Pico de memoria residente del proceso."""
    if sys.platform == "win32":
        from ctypes import wintypes

        class Contadores(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        c = Contadores()
        c.cb = ctypes.sizeof(c)
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.PeakWorkingSetSize / 1024 / 1024
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux informa KB


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    limite = limitar_memoria(LIMITE_PROCESO_MB)
    import httpx

    from app.services.fuentes.cog import ErrorCog, LectorCog
    from app.services.fuentes.mapbiomas import URL, MapBiomas

    geometria = json.loads((RAIZ / "tests/datos/whisp_respuesta_real.json").read_bytes())["data"]["features"][
        0
    ]["geometry"]
    fuente = MapBiomas(True, 2015, 2024)
    print(f"Proceso limitado: {limite}")
    print(f"Parcela: tests/datos/whisp_respuesta_real.json; años {fuente.anios[0]} a {fuente.anios[-1]}")
    fallas = []

    print("\n1-2. Peticiones por rango y organización en bloques")
    with httpx.Client(timeout=60) as cliente:
        for anio in fuente.anios:
            url = URL.format(anio=anio)
            r = cliente.get(url, headers={"Range": "bytes=0-15"})
            rangos = r.status_code == 206 and r.headers.get("accept-ranges") == "bytes"
            try:
                cab = LectorCog(cliente).cabecera(url)
                bloques = f"bloques {cab.tile_ancho}x{cab.tile_alto}, compresión {cab.compresion}"
            except ErrorCog as exc:
                bloques = f"FALLA: {exc}"
                fallas.append(f"{anio}: {exc}")
            if not rangos:
                fallas.append(f"{anio}: no acepta rangos ({r.status_code})")
            print(f"  {anio}: rango {r.status_code} {'sí' if rangos else 'NO'}; {bloques}")

    print("\n3. Lectura de todos los años para la parcela")
    base = memoria_maxima_mb()
    inicio = time.perf_counter()
    _, indicadores, version = fuente.interpretar(fuente.consultar(geometria, "comprobacion"))
    segundos = time.perf_counter() - inicio
    pico = memoria_maxima_mb()
    print(
        f"  {version}; {indicadores['pixeles']} píxeles; clase predominante 2020: "
        f"{indicadores['clase_predominante_2020']}"
    )
    print(f"  Tiempo: {segundos:.1f} s (máximo {TIEMPO_MAXIMO_S} s)")
    print(f"  Memoria máxima del proceso: {pico:.1f} MB (antes de leer: {base:.1f} MB)")
    print(f"  Máximos admitidos: {MEMORIA_MAXIMA_MB} MB y {TIEMPO_MAXIMO_S} s")
    if segundos > TIEMPO_MAXIMO_S:
        fallas.append(f"tiempo {segundos:.1f} s")
    if pico > MEMORIA_MAXIMA_MB:
        fallas.append(f"memoria {pico:.1f} MB")

    print("\nResultado:", "PASA" if not fallas else "NO PASA: " + "; ".join(fallas))
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
