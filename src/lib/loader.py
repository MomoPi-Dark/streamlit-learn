import os
import inspect
import os
import re
from pathlib import Path
from structures.base import BasePage
import importlib.util


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


class PageLoader:
    def __init__(self, pages_dir: str = "src/app_pages"):
        self.pages_dir = pages_dir

    def _sort_key(self, file_path: str):
        relative_path = os.path.relpath(file_path, self.pages_dir)
        is_in_category = os.sep in relative_path
        return (is_in_category, relative_path.lower())

    def _load_file_with_prefix(
        self,
        extensions: tuple[str, ...],
        skip_prefix: tuple[str, ...] = ("_", "."),
    ) -> dict[str, list[str]]:
        """
        Walk self.pages_dir once and bucket files by extension.

        Args:
            extensions: e.g. (".py", ".css")
            skip_prefix: filenames starting with any of these are ignored
                        (e.g. "_internal.py", ".hidden.css")

        Returns:
            {".py": [...], ".css": [...]}
        """
        result: dict[str, list[str]] = {ext: [] for ext in extensions}

        if not os.path.exists(self.pages_dir):
            os.makedirs(self.pages_dir)
            return result

        for root, _, files in os.walk(self.pages_dir):
            for file_name in files:
                if file_name.startswith(skip_prefix):
                    continue

                _, ext = os.path.splitext(file_name)
                if ext in result:
                    result[ext].append(os.path.join(root, file_name))

        return result

    def load_page_classes(self) -> list[type[BasePage]]:
        page_classes: list[type[BasePage]] = []
        style_files: list = []

        if not os.path.exists(self.pages_dir):
            os.makedirs(self.pages_dir)
            return page_classes

        files_by_ext = self._load_file_with_prefix((".py", ".css"))
        page_files = files_by_ext[".py"]
        style_files = files_by_ext[".css"]

        style_by_dir = {
            os.path.dirname(f): f
            for f in style_files
            if os.path.basename(f) == "style.css"
        }

        for file_path in page_files:
            module_name = os.path.splitext(os.path.basename(file_path))[0]

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BasePage)
                    and obj is not BasePage
                    and hasattr(obj, "__page_meta__")
                ):
                    obj.__page_file__ = file_path
                    obj.__style_file__ = style_by_dir.get(os.path.dirname(file_path))

                    page_classes.append(obj)

        return page_classes

    def load_pages(self) -> list[BasePage]:
        pages: list[BasePage] = []

        for cls in self.load_page_classes():
            page = cls()
            page.__page_file__ = cls.__page_file__
            pages.append(page)

        return pages

    @staticmethod
    def build_url_path(page: BasePage, defaultBasedir="src/app_pages") -> str:
        file_path = getattr(page, "__page_file__", None)

        if file_path is None:
            return slugify(page.__page_meta__.menu_name)

        base_dir = Path(defaultBasedir).resolve()
        file_path = Path(file_path).resolve()
        relative_path = file_path.relative_to(base_dir)
        parts = list(relative_path.parts)

        parts[-1] = Path(parts[-1]).stem

        if parts == ["page"]:
            return "/"

        if parts[-1] == "page":
            parts.pop()

        # Streamlit's st.Page(url_path=...) TIDAK mengizinkan slash di sini
        # (StreamlitAPIException: "URL path cannot contain a nested path").
        # url_path harus flat single-segment; struktur "/app/xxx" yang muncul
        # di browser datang dari section/grouping di st.navigation(), bukan
        # dari string ini.
        return "-".join(part.lower().replace("_", "-") for part in parts)
