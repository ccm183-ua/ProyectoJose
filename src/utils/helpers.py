"""
Funciones auxiliares y utilidades.
"""

import re
import os
import threading


def sanitize_filename(filename):
    """
    Sanitiza un nombre de archivo eliminando caracteres peligrosos.
    
    Args:
        filename: Nombre de archivo a sanitizar
        
    Returns:
        str: Nombre de archivo sanitizado
    """
    if not filename:
        return "archivo_sin_nombre"
    
    # Reemplazar caracteres peligrosos
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Eliminar espacios al inicio y final
    sanitized = sanitized.strip()
    
    # Conservar espacios: solo colapsar múltiples espacios o guiones bajos
    sanitized = re.sub(r' +', ' ', sanitized)
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip()
    
    # Si quedó vacío después de sanitizar, usar nombre por defecto
    if not sanitized:
        sanitized = "archivo_sin_nombre"
    
    return sanitized


def generate_filename(direccion, numero, descripcion):
    """
    Genera un nombre de archivo a partir de dirección, número y descripción.
    
    Args:
        direccion: Dirección de la obra
        numero: Número de la calle
        descripcion: Descripción breve
        
    Returns:
        str: Nombre de archivo generado (sin extensión)
    """
    # Sanitizar cada parte
    dir_sanitized = sanitize_filename(direccion)
    num_sanitized = sanitize_filename(str(numero))
    desc_sanitized = sanitize_filename(descripcion)
    
    # Combinar
    filename = f"{dir_sanitized}_{num_sanitized}_{desc_sanitized}"
    
    return filename


def get_template_path():
    """
    Obtiene la ruta absoluta de la plantilla.
    
    Returns:
        str: Ruta absoluta de la plantilla
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    template_path = os.path.join(project_root, 'templates', '122-20 PLANTILLA PRESUPUESTO.xlsx')
    
    return template_path


class _Invoker:
    """Singleton que transfiere callables de hilos worker al hilo principal via signal."""

    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            from PySide6.QtCore import QObject, Signal, Slot

            class _Obj(QObject):
                _call = Signal(object)

                def __init__(self):
                    super().__init__()
                    self._call.connect(self._run)

                @Slot(object)
                def _run(self, fn):
                    fn()

            cls._instance = _Obj()
        return cls._instance


def run_in_background(work_fn, callback):
    """Ejecuta *work_fn* en un hilo y entrega el resultado a *callback* en el hilo de UI.

    ``callback`` recibe ``(True, result)`` si *work_fn* tuvo éxito o
    ``(False, exception)`` si lanzó una excepción.
    """
    invoker = _Invoker.get()

    def _worker():
        try:
            result = work_fn()
        except Exception as exc:
            # Se liga como argumento por defecto: Python borra `exc` al salir
            # del except, así que una lambda que lo capturase por cierre
            # lanzaba NameError en el hilo de la UI y el callback de error no
            # llegaba a ejecutarse nunca.
            invoker._call.emit(lambda err=exc: callback(False, err))
            return
        invoker._call.emit(lambda res=result: callback(True, res))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


class CoalescingBackgroundTask:
    """Tarea en segundo plano que agrupa peticiones repetidas.

    ``request()`` lanza ``work_fn`` en un hilo. Si ya hay una ejecución en
    marcha, no lanza otra en paralelo (dos reconstrucciones simultáneas sobre
    SQLite chocan con "database is locked"): la apunta y la ejecuta una sola
    vez al terminar la actual. ``on_done(ok, result)`` se llama en el hilo de
    la UI solo tras la última ejecución.
    """

    def __init__(self, work_fn, on_done=None):
        self._work_fn = work_fn
        self._on_done = on_done
        self._running = False
        self._pending = False

    @property
    def running(self) -> bool:
        return self._running

    def request(self) -> None:
        if self._running:
            self._pending = True
            return
        self._start()

    def _start(self) -> None:
        self._running = True
        self._pending = False
        run_in_background(self._work_fn, self._finished)

    def _finished(self, ok, result) -> None:
        if self._pending:
            self._start()
            return
        self._running = False
        if self._on_done is not None:
            self._on_done(ok, result)
