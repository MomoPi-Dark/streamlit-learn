from abc import ABC, abstractmethod
from typing import ClassVar, Optional


class PageMetadata:
    """Read-Only Container Metadata Halaman"""

    def __init__(
        self,
        page_name: str,
        menu_name: str,
        menu_icon: str = "🎮",
        requires_model: bool = False,
        enabled: bool = True,
        category: Optional[str] = None,
    ):
        self._page_name = page_name
        self._menu_name = menu_name
        self._menu_icon = menu_icon
        self._requires_model = requires_model
        self._enabled = enabled
        self._category = category

    @property
    def page_name(self) -> str:
        return self._page_name

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
    page_name: str,
    menu_name: str,
    menu_icon: str = "🎮",
    requires_model: bool = False,
    enabled: bool = True,
    category: Optional[str] = None,
):
    def decorator(cls):
        cls.__page_meta__ = PageMetadata(
            page_name=page_name,
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
        import streamlit as st

        loaded_key = f"__on_load_done__{self.__page_meta__.page_name}"
        if not st.session_state.get(loaded_key, False):
            self.on_load()
            st.session_state[loaded_key] = True

        self.run()
