import os
import inspect
from structures.base import BasePage


class PageLoader:
    def __init__(self, pages_dir: str = "src/app_pages"):
        self.pages_dir = pages_dir

    def load_pages(self) -> list[BasePage]:
        instances: list[BasePage] = []

        if not os.path.exists(self.pages_dir):
            os.makedirs(self.pages_dir)
            return instances

        page_files: list[str] = []
        for root, _, files in os.walk(self.pages_dir):
            for file_name in files:
                if file_name.endswith(".py"):
                    page_files.append(os.path.join(root, file_name))

        def sort_key(file_path: str):
            relative_path = os.path.relpath(file_path, self.pages_dir)
            is_in_category = os.sep in relative_path
            return (is_in_category, relative_path.lower())

        for file_path in sorted(page_files, key=sort_key):
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read()

            compiled_code = compile(code_content, file_path, "exec")
            module_scope = {"__builtins__": __builtins__}
            exec(compiled_code, module_scope, module_scope)

            for obj in module_scope.values():
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, BasePage)
                    and obj is not BasePage
                ):
                    if hasattr(obj, "__page_meta__"):
                        instance = obj()
                        instance.__page_file__ = os.path.abspath(file_path)
                        instances.append(instance)

        return instances
