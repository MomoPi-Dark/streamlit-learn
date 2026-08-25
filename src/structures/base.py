from abc import ABC, abstractmethod
from typing import ClassVar, Optional
from lib.enum import (
    switch_to_page,
    StateKey,
    StageKey,
    get_session_state,
    set_session_state,
)


class PageMetadata:
    def __init__(
        self,
        page_id: str,
        menu_name: str,
        menu_icon: str = "🎮",
        requires_model: bool = False,
        enabled: bool = True,
        category: Optional[str] = None,
    ):
        self._page_id = page_id
        self._menu_name = menu_name
        self._menu_icon = menu_icon
        self._requires_model = requires_model
        self._enabled = enabled
        self._category = category

    @property
    def page_id(self) -> str:
        return self._page_id

    @property
    def menu_name(self) -> str:
        return self._menu_name

    @property
    def menu_icon(self) -> str:
        return self._menu_icon

    @property
    def requires_model(self) -> bool:
        return self._requires_model

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def category(self) -> Optional[str]:
        return self._category


def Options(
    page_id: str,
    menu_name: str,
    menu_icon: str = "🎮",
    requires_model: bool = False,
    enabled: bool = True,
    category: Optional[str] = None,
):
    def decorator(cls):
        cls.__page_meta__ = PageMetadata(
            page_id=page_id,
            menu_name=menu_name,
            menu_icon=menu_icon,
            requires_model=requires_model,
            enabled=enabled,
            category=category,
        )
        return cls

    return decorator


class BasePage(ABC):
    __page_meta__: ClassVar[PageMetadata]

    __page_file__: str
    __style_file__: Optional[str] = None

    __page_url__: str

    def on_start(self) -> None:
        """Ringan. Jalan untuk SEMUA page tiap rerun (dipanggil manual di loop main.py).
        Cocok untuk: session_state defaults, registrasi metadata.
        Jangan: load model, I/O berat.
        """
        pass

    def on_load(self) -> None:
        """Berat/lazy. Jalan SEKALI, hanya untuk page yang sedang aktif.
        Cocok untuk: load model, vectorizer, file besar (bungkus dgn st.cache_resource).
        """
        pass

    @abstractmethod
    def run(self) -> None:
        pass

    def __call__(self) -> None:
        """Entry point tunggal yang dipanggil st.Page(...).
        Menjamin on_load() jalan sekali sebelum run(), tanpa main.py
        perlu tahu detail flag session_state-nya.
        """

        loaded_key = f"__on_load_done__{self.__page_meta__.page_id}"
        if not get_session_state(loaded_key, False):
            self.on_load()
            set_session_state(loaded_key, True)

        self.run()

    # Any methods

    def _key_process(self, suffix: str = "") -> str:
        base = f"{self.__page_url__}_is_processing"
        return f"{base}_{suffix}" if suffix else base

    def start_process_state(self, suffix: str = "") -> None:
        set_session_state(self._key_process(suffix), True)

    def stop_process_state(self, suffix: str = "") -> None:
        set_session_state(self._key_process(suffix), False)

    def status_process_state(self, suffix: str = "") -> bool:
        return get_session_state(self._key_process(suffix), False)

    def switch_page(self, page_id: str) -> str | None:
        if self.__page_meta__.page_id == page_id:
            return None
        return switch_to_page(page_id)
