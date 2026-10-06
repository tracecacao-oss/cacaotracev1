"""Bucle en segundo plano de la API (Parte 4).

El plan gratuito de Render no ofrece un proceso trabajador aparte, así que un único hilo dentro de
la API procesa la cola de análisis, una consulta externa a la vez, y corre la tarea diaria:
pasar a observada la parcela habilitada que dejó de cumplir, renovar análisis por caducar y, desde la
Parte 8, recomprobar los lotes listo y bloqueado.
Render reinicia el servicio con frecuencia: al arrancar se recupera lo que quedó a medias.
"""

import logging
import threading
import time

from app.db import SesionLocal
from app.scripts import reprocesar_whisp
from app.services import analisis, habilitacion, imagenes, recomprobacion
from app.services.fuentes import Fuente
from app.storage import ClienteStorage

log = logging.getLogger(__name__)

ESPERA_SIN_TRABAJO = 5  # segundos
CADA_DIA = 24 * 3600
PRIMERA_TAREA_DIARIA = 120  # segundos después de arrancar


class Trabajador(threading.Thread):
    def __init__(self, fuentes: dict[str, Fuente], storage: ClienteStorage):
        super().__init__(name="cacaotrace-analisis", daemon=True)
        self.fuentes, self.storage = fuentes, storage
        self.ritmo = analisis.Ritmo()
        self.detenido = threading.Event()

    def detener(self) -> None:
        self.detenido.set()

    def _tareas_diarias(self) -> None:
        with SesionLocal() as sesion:
            observadas = habilitacion.revisar_habilitadas(sesion)
        with SesionLocal() as sesion:
            renovados = analisis.renovar_por_caducar(sesion, self.fuentes)
        with SesionLocal() as sesion:
            juegos = imagenes.encolar_pendientes(sesion)
        # Parte 8: los lotes listo y bloqueado se recomprueban; solo queda fila si algo cambió.
        with SesionLocal() as sesion:
            recomprobados = recomprobacion.tarea_diaria(sesion)
        log.info(
            "Tarea diaria: %s parcelas observadas, %s análisis renovados, %s juegos de imágenes encolados, "
            "%s lotes con recomprobación nueva",
            observadas,
            renovados,
            juegos,
            recomprobados,
        )

    def run(self) -> None:
        try:
            with SesionLocal() as sesion:
                recuperados = analisis.recuperar_atascados(sesion)
            if recuperados:
                log.info("Volvieron a la cola %s análisis que quedaron a medias", recuperados)
        except Exception:
            log.exception("No se pudo recuperar la cola de análisis")
        try:
            # Adenda de la Parte 4: detalle por capa para los análisis de Whisp anteriores. Idempotente.
            with SesionLocal() as sesion:
                reprocesados = reprocesar_whisp.reprocesar(sesion, self.storage)
            if reprocesados:
                log.info("Análisis de Whisp reprocesados desde su respuesta guardada: %s", reprocesados)
        except Exception:
            log.exception("No se pudieron reprocesar los análisis de Whisp")
        try:
            # Adenda 2: las parcelas que ya tenían la alerta reciben su juego de imágenes.
            with SesionLocal() as sesion:
                encolados = imagenes.encolar_pendientes(sesion)
            if encolados:
                log.info("Juegos de imágenes encolados al arrancar: %s", encolados)
        except Exception:
            log.exception("No se pudieron encolar los juegos de imágenes")
        proxima_diaria = time.monotonic() + PRIMERA_TAREA_DIARIA
        while not self.detenido.is_set():
            hubo_trabajo = False
            try:
                if time.monotonic() >= proxima_diaria:
                    self._tareas_diarias()
                    proxima_diaria = time.monotonic() + CADA_DIA
                with SesionLocal() as sesion:
                    hubo_trabajo = analisis.procesar_siguiente(sesion, self.fuentes, self.storage, self.ritmo)
                # Adenda 2 de la Parte 4: las imágenes de las parcelas con alerta, en la misma cola.
                with SesionLocal() as sesion:
                    hubo_trabajo = imagenes.procesar_siguiente(sesion, self.storage) or hubo_trabajo
            except Exception:
                log.exception("Falló una vuelta del bucle de análisis")
            if not hubo_trabajo:
                self.detenido.wait(ESPERA_SIN_TRABAJO)
