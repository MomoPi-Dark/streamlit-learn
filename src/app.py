import streamlit as st
import re
import pandas as pd
import numpy as np
import joblib
import os
import importlib.util
from pathlib import Path
from functools import lru_cache
from typing import Any, Optional, cast
from lib.enum import StateKey, StageKey, get_session_state
from lib.loader import PageLoader
from structures.base import BasePage
from lib.category_config import CategoryConfig, CATEGORY_CONFIG
from streamlit.navigation.page import StreamlitPage
from lib.enum import load_session_state
from lib.running_badge import mark_pages_reloaded
import sys

LOADER_DIR = "./src/app_pages"

load_session_state()

st.set_page_config(page_title="NTE Sentiment Analyzer", page_icon="🎮", layout="wide")

st.markdown(
    """
<style>
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
        width: 100% !important;
        padding: 10px 14px !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        border: 1px solid transparent !important;
        background-color: rgba(255, 255, 255, 0.03) !important;
        transition: background-color 0.15s ease, border-color 0.15s ease, transform 0.1s ease;
        margin-bottom: 4px !important;
        text-decoration: none !important;
    }

    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
        background-color: rgba(255, 255, 255, 0.07) !important;
        border-color: rgba(255, 255, 255, 0.08) !important;
        transform: translateX(2px);
    }

    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        border: 1px solid #3b82f6 !important;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
    }
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] p {
        color: #ffffff !important;
    }

    .sidebar-category {
        color: #6b7280;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin: 18px 0 2px 6px;
        text-transform: uppercase;
    }

    .sidebar-category-description {
        color: #6b7280;
        font-size: 11.5px;
        line-height: 1.4;
        margin: 0 0 8px 6px;
        opacity: 0.85;
    }

    .sidebar-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
        margin: 14px 0;
        border: none;
    }

    [data-testid="stSidebar"] .stAlert {
        border-radius: 10px !important;
        padding: 8px 12px !important;
    }

    [data-testid="stSidebar"] h1 {
        font-size: 20px !important;
        padding-bottom: 4px;
    }

    .sb-progress-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.74em;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    .sb-progress-outer {
        background: rgba(255, 255, 255, 0.08);
        border-radius: 999px;
        height: 8px;
        overflow: hidden;
        margin-bottom: 14px;
    }
    .sb-progress-inner {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #22c55e, #38bdf8);
        transition: width 0.4s ease;
    }
    .sb-step-fallback {
        font-size: 0.9em;
        color: #94a3b8;
        padding: 6px 4px;
    }
</style>
""",
    unsafe_allow_html=True,
)


@lru_cache(maxsize=None)
def get_page_category(page_cls: type) -> Optional[str]:
    """Return category for grouping: from metadata if set, else infer from folder name.

    Di-cache per class (lru_cache) karena hasilnya statis — path file dan metadata
    kategori sebuah halaman tidak pernah berubah antar-rerun. Tanpa cache ini,
    Path.resolve()/relative_to() dipanggil ulang berkali-kali tiap interaksi
    (klik tombol, dsb), padahal hasilnya selalu sama. Di-key pakai class (bukan
    instance) karena instance halaman dibuat ulang tiap rerun lewat
    create_page_instances(), sedangkan class-nya tetap sama.
    """
    meta = page_cls.__page_meta__
    if meta.category:
        return meta.category
    file_path = getattr(page_cls, "__page_file__", None)
    if file_path is None:
        return None
    base_dir = Path("src/app_pages").resolve()
    file_path = Path(file_path).resolve()
    try:
        relative = file_path.relative_to(base_dir)
    except ValueError:
        return None
    parts = list(relative.parts)
    if len(parts) >= 2 and parts[-1].lower().endswith(".py"):
        return parts[0]
    return None


@st.cache_data
def get_css_content(css_path: str, mtime: float) -> str:
    return Path(css_path).read_text(encoding="utf-8")


def _load_page_css(page: BasePage) -> None:
    """Load sibling style.css for given page if exists and inject into Streamlit."""
    file_path = getattr(page, "__style_file__", None)

    if not file_path:
        return

    css_path = Path(file_path)
    if not css_path.is_file():
        return

    try:
        mtime = css_path.stat().st_mtime
        css = get_css_content(str(css_path), mtime)
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except OSError:
        return


def find_page_by_url(
    st_pages: list[StreamlitPage], url_path: str
) -> Optional[StreamlitPage]:
    if not url_path:
        return None
    target = url_path.strip("/")
    for sp in st_pages:
        if sp.url_path.strip("/") == target:
            return sp
    return None


def is_page_visible(page: BasePage) -> bool:
    category = get_page_category(type(page))
    if not category:
        return page.__page_meta__.enabled

    config = CATEGORY_CONFIG.get(category)
    if config is None:
        return False

    return (
        page.__page_meta__.enabled
        and config.enabled
        and config.validator(cast(Any, st.session_state), page)
    )


def make_page_runner(page: BasePage):
    def _runner():
        _load_page_css(page)
        page()

    return _runner


def get_pages_version() -> str:
    # Skip filesystem walk kalau bukan mode dev — hemat I/O tiap rerun.
    # Set environment variable APP_DEV=1 saat development biar hot-reload
    # tetap jalan; kosongkan/hapus saat demo/sidang supaya app.py tidak
    # perlu rglob() + stat() semua file tiap kali ada interaksi.
    if not os.environ.get("APP_DEV"):
        return "static"

    pages_dir = Path(LOADER_DIR)

    if not pages_dir.exists():
        return ""

    parts: list[str] = []

    for file in sorted(pages_dir.rglob("*.py")):
        parts.append(f"{file.relative_to(pages_dir)}:{file.stat().st_mtime_ns}")

    return "|".join(parts)


@st.cache_resource
def get_page_classes(dir: str, version: str):
    loader = PageLoader(dir)
    classes = loader.load_page_classes()
    mark_pages_reloaded()
    return classes


def create_page_instances(dir: str) -> list[BasePage]:
    version = get_pages_version()
    page_classes = get_page_classes(dir, version)

    return [cls() for cls in page_classes]


def main():
    page_instances: list[BasePage] = [
        page for page in create_page_instances(LOADER_DIR) if is_page_visible(page)
    ]

    if not page_instances:
        st.error(
            f"Folder `{LOADER_DIR}` belum memiliki file `.py` yang menggunakan `@Options`."
        )
        return

    category_order = {category: index for index, category in enumerate(CATEGORY_CONFIG)}

    page_instances.sort(
        key=lambda page: (
            0 if get_page_category(type(page)) is None else 1,
            category_order.get(
                get_page_category(type(page)) or "/",
                len(category_order),
            ),
            page.__page_meta__.page_name.lower(),
        )
    )

    st_pages: list[StreamlitPage] = []
    page_lookup: dict[int, StreamlitPage] = {}

    for index, page in enumerate(page_instances):
        meta = page.__page_meta__

        # CSS halaman TIDAK di-load di sini lagi — cukup di dalam
        # make_page_runner() untuk halaman yang benar-benar sedang aktif.
        # Sebelumnya _load_page_css(page) dipanggil di loop ini untuk
        # SEMUA halaman setiap rerun, padahal cuma 1 halaman yang tampil,
        # jadi CSS 9+ halaman ke-inject ulang ke DOM tiap interaksi.
        page.on_start()

        url_path = PageLoader.build_url_path(page)

        st_page = st.Page(
            make_page_runner(page),
            title=meta.menu_name,
            url_path=url_path,
            default=(url_path == "/"),
        )

        st_pages.append(st_page)
        page_lookup[index] = st_page

    pg = st.navigation(st_pages, position="hidden")

    # ===== Sidebar =====
    st.sidebar.title("🎮 Navigasi Menu")
    st.sidebar.markdown(
        '<div style="padding-bottom: 4px;"></div>',
        unsafe_allow_html=True,
    )

    with st.sidebar.expander("📊 Pipeline Status", expanded=True):
        pipeline_steps = [
            ("Pengumpulan Data", StageKey.STAGE_1, "/app-dataset"),
            ("Pelabelan Data", StageKey.STAGE_2, "/app-labeling"),
            ("Preprocessing", StageKey.STAGE_3, "/app-preprocessing"),
            ("Pembobotan TF-IDF", StageKey.STAGE_4, "/app-tfidf"),
            ("Train-Test Split", StageKey.STAGE_5, "/app-splitdata"),
            ("Penyeimbangan Kelas (SMOTE)", StageKey.STAGE_6, "/app-smoote"),
            ("Training Model", StageKey.STAGE_7, "/app-naifbayes"),
            ("Evaluasi Model", StageKey.STAGE_8, "/app-evaluation"),
            ("Visualisasi", StageKey.STAGE_9, "/app-visualisasi"),
        ]

        done_flags = [bool(get_session_state(key)) for _, key, _ in pipeline_steps]
        done_count = sum(done_flags)
        total_count = len(pipeline_steps)
        pct = (done_count / total_count * 100) if total_count else 0

        # ===== Ringkasan progres di atas daftar =====
        st.markdown(
            f"<div class='sb-progress-label'>"
            f"<span>{done_count}/{total_count} tahap selesai</span>"
            f"<span>{pct:.0f}%</span></div>"
            f"<div class='sb-progress-outer'>"
            f"<div class='sb-progress-inner' style='width:{pct:.1f}%;'></div></div>",
            unsafe_allow_html=True,
        )

        found_active = False
        for i, (label, key, link) in enumerate(pipeline_steps, start=1):
            done = bool(get_session_state(key))

            if done:
                icon = "✅"
            elif not found_active:
                icon = "🔵"
                found_active = True
            else:
                icon = "⚪"

            target_page = find_page_by_url(st_pages, link)
            step_label = f"{i}. {label}"

            if target_page:
                st.page_link(
                    target_page,
                    label=step_label,
                    icon=icon,
                    width="stretch",
                )
            else:
                st.markdown(
                    f"<div class='sb-step-fallback'>{icon}&nbsp;&nbsp;{step_label}</div>",
                    unsafe_allow_html=True,
                )

    st.sidebar.markdown(
        '<div class="sidebar-divider"></div>',
        unsafe_allow_html=True,
    )

    current_category = None

    for index, page in enumerate(page_instances):
        category = get_page_category(type(page))
        meta = page.__page_meta__

        if category is not None and category != current_category:
            config = CATEGORY_CONFIG.get(category)

            if config is not None:
                st.sidebar.markdown(
                    f'<div class="sidebar-category">{config.name}</div>',
                    unsafe_allow_html=True,
                )

                if config.description:
                    st.sidebar.markdown(
                        f'<div class="sidebar-category-description">{config.description}</div>',
                        unsafe_allow_html=True,
                    )

            current_category = category

        st.sidebar.page_link(
            page_lookup[index],
            label=meta.menu_name,
            icon=meta.menu_icon,
            width="stretch",
        )

    st.sidebar.markdown(
        '<div class="sidebar-divider"></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("🎮 NTE Sentiment Analysis Framework")
    # ==== END SIDEBAR ====

    pg.run()


if __name__ == "__main__":
    main()
