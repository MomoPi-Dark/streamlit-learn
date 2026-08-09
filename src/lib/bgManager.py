import threading
from collections.abc import Callable
from typing import Any


class BackgroundManager:
    """
    Menjalankan fungsi di thread terpisah, plus menyimpan progress
    (dict bebas-bentuk) per nama task supaya UI Streamlit bisa polling
    dan menampilkan animasi "sedang memproses" tanpa memblokir main thread.
    """

    def __init__(self):
        self._threads: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._progress: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(
        self,
        name: str,
        target: Callable[..., Any],
        *args,
        **kwargs,
    ) -> bool:
        with self._lock:
            if self.is_running(name):
                return False

            stop_event = threading.Event()
            self._stop_events[name] = stop_event
            self._progress[name] = {"status": "starting"}

            thread = threading.Thread(
                target=target,
                args=(*args, stop_event),
                kwargs=kwargs,
                daemon=True,
            )

            self._threads[name] = thread
            thread.start()
            return True

    def stop(self, name: str):
        with self._lock:
            event = self._stop_events.get(name)
            thread = self._threads.get(name)

            if event:
                event.set()

        # join di luar lock supaya thread yang mau update progress
        # (butuh lock juga) tidak deadlock menunggu kita
        if thread:
            thread.join(timeout=2)

        with self._lock:
            self._threads.pop(name, None)
            self._stop_events.pop(name, None)
            self._progress.pop(name, None)

    def stop_all(self):
        for name in list(self._threads.keys()):
            self.stop(name)

    def is_running(self, name: str) -> bool:
        thread = self._threads.get(name)
        return thread is not None and thread.is_alive()

    def get_running_names(self) -> list[str]:
        """Daftar nama task yang sedang berjalan saat ini (buat badge global)."""
        with self._lock:
            return [name for name, t in self._threads.items() if t.is_alive()]

    def get_thread(self, name: str) -> threading.Thread | None:
        return self._threads.get(name)

    def get_stop_event(self, name: str) -> threading.Event | None:
        return self._stop_events.get(name)

    # ===== Progress tracking =====

    def set_progress(self, name: str, **fields: Any) -> None:
        """Dipanggil dari dalam thread background untuk update status/progress."""
        with self._lock:
            current = self._progress.setdefault(name, {})
            current.update(fields)

    def get_progress(self, name: str) -> dict[str, Any]:
        """Dipanggil dari UI thread (main script) untuk membaca progress terbaru."""
        with self._lock:
            return dict(self._progress.get(name, {}))


background_manager = BackgroundManager()
