from abc import ABC, abstractmethod
from typing import ClassVar, Optional

class PageMetadata:
    """Read-Only Container Metadata Halaman"""
    def __init__(self, page_name: str, menu_name: str, menu_icon: str = "🎮", requires_model: bool = False, enabled: bool = True, category: Optional[str] = None):
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

def Options(page_name: str, menu_name: str, menu_icon: str = "🎮", requires_model: bool = False, enabled: bool = True, category: Optional[str] = None):
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

    @abstractmethod
    def run(self) -> None:
        pass

    def on_start(self) -> None:
        pass
        
    def __call__(self) -> None:
        self.on_start()
        self.run()