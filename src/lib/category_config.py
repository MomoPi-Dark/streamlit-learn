from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

@dataclass(frozen=True)
class CategoryConfig:
    name: str
    description: str = ""
    enabled: bool = True
    validator: Callable[[Any, Any], bool] = lambda state, page: True

CATEGORY_CONFIG: dict[str, CategoryConfig] = {
    "dataset": CategoryConfig(
        name="Dataset",
        description="Mengumpulkan dan memvalidasi dataset ulasan serta kamus slang."
    ),

    "labeling": CategoryConfig(
        name="Labeling",
        description="Memberikan label sentimen secara otomatis pada dataset."
    ),

    "preprocessing": CategoryConfig(
        name="Preprocessing",
        description="Membersihkan, menormalisasi, dan mempersiapkan teks."
    ),

    "model": CategoryConfig(
        name="Model",
        description="Mengelola model, TF-IDF, dan konfigurasi pembelajaran."
    ),

    "training": CategoryConfig(
        name="Training & Evaluation",
        description="Melatih model serta mengevaluasi hasil klasifikasi."
    ),
}