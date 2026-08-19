import threading
import traceback
from collections.abc import Callable
from typing import Any


class BackgroundManager:
    """Menjalankan satu task bernama di thread lokal dan menyimpan statusnya."""

    def __init__(self) -> None:
        self._threads: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._progress: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def start(
        self,
        name: str,
        target: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        with self._lock:
            if self.is_running(name):
                return False

            stop_event = threading.Event()
            self._stop_events[name] = stop_event
            self._progress[name] = {
                "status": "queued",
                "current": 0,
                "total": 0,
                "stage": "Menunggu proses dimulai",
            }

            thread = threading.Thread(
                target=self._run,
                args=(name, target, args, kwargs, stop_event),
                daemon=True,
                name=f"background-{name}",
            )
            self._threads[name] = thread
            thread.start()
            return True

    def _run(
        self,
        name: str,
        target: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        stop_event: threading.Event,
    ) -> None:
        self.set_progress(name, status="running", stage="Memulai proses")
        try:
            result = target(*args, stop_event=stop_event, **kwargs)
        except Exception as error:
            self.set_progress(
                name,
                status="failed",
                error=str(error),
                traceback=traceback.format_exc(),
            )
        else:
            status = "cancelled" if stop_event.is_set() else "succeeded"
            self.set_progress(name, status=status, result=result)

    def stop(self, name: str) -> None:
        with self._lock:
            event = self._stop_events.get(name)
            thread = self._threads.get(name)
            if event:
                event.set()

        if thread:
            thread.join(timeout=2)

        self.set_progress(name, status="cancelled", stage="Proses dibatalkan")

    def clear(self, name: str) -> None:
        if self.is_running(name):
            return
        with self._lock:
            self._threads.pop(name, None)
            self._stop_events.pop(name, None)
            self._progress.pop(name, None)

    def stop_all(self) -> None:
        for name in self.get_running_names():
            self.stop(name)

    def is_running(self, name: str) -> bool:
        with self._lock:
            thread = self._threads.get(name)
            return thread is not None and thread.is_alive()

    def get_running_names(self) -> list[str]:
        with self._lock:
            return [name for name, thread in self._threads.items() if thread.is_alive()]

    def get_thread(self, name: str) -> threading.Thread | None:
        with self._lock:
            return self._threads.get(name)

    def get_stop_event(self, name: str) -> threading.Event | None:
        with self._lock:
            return self._stop_events.get(name)

    def set_progress(self, name: str, **fields: Any) -> None:
        with self._lock:
            self._progress.setdefault(name, {}).update(fields)

    def get_progress(self, name: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._progress.get(name, {}))


background_manager = BackgroundManager()
