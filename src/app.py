import streamlit as st
import re
import pandas as pd
import numpy as np
import joblib
import os
import importlib.util
from pathlib import Path
from typing import Any, Optional, cast
from lib.enum import StateKey,StageKey
from lib.loader import PageLoader
from structures.base import BasePage
from lib.category_config import CategoryConfig, CATEGORY_CONFIG
from streamlit.navigation.page import StreamlitPage
from lib.enum import load_session_state

load_session_state()

st.set_page_config(
    page_title="NTE Sentiment Analyzer",
    page_icon="🎮",
    layout="wide"
)

st.markdown("""
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
</style>
""", unsafe_allow_html=True)

def get_page_category(page: BasePage) -> Optional[str]:
    """Return category for grouping: from metadata if set, else infer from folder name."""
    meta = page.__page_meta__
    if meta.category:
        return meta.category
    # infer from path: first folder under src/app_pages
    file_path = getattr(page, "__page_file__", None)
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
        # file like Category/something.py or Category/page.py
        return parts[0]
    # If file is directly under app_pages (e.g., page.py) => no category
    return None

def find_page_by_url(st_pages: list[StreamlitPage], url_path: str) -> Optional[StreamlitPage]:
    if not url_path:
        return None
    target = url_path.strip("/")
    for sp in st_pages:
        if sp.url_path.strip("/") == target:
            return sp
    return None

def is_page_visible(page: BasePage) -> bool:
    category = get_page_category(page)
    if not category:
        return page.__page_meta__.enabled

    config = CATEGORY_CONFIG.get(category)
    if config is None:
        return False
    
    return page.__page_meta__.enabled and config.enabled and config.validator(cast(Any, st.session_state), page)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def build_url_path(page: BasePage) -> str:
    """
    URL path dari struktur folder:
      app_pages/page.py              -> ""
      app_pages/{slug}/page.py       -> "{slug}"
      app_pages/{slug}/{name}.py     -> "{slug}-{name}"
    """
    file_path = getattr(page, "__page_file__", None)
    if file_path is None:
        return slugify(page.__page_meta__.menu_name)

    base_dir = Path("src/app_pages").resolve()
    file_path = Path(file_path).resolve()
    relative_path = file_path.relative_to(base_dir)
    parts = list(relative_path.parts)

    parts[-1] = Path(parts[-1]).stem

    # Halaman root
    if parts == ["page"]:
        return "/"

    # dataset/page.py -> dataset
    if parts[-1] == "page":
        parts.pop()

    return "-".join(
        part.lower().replace("_", "-")
        for part in parts
    )


def make_page_runner(page: BasePage):
    meta = page.__page_meta__
    
    def _runner():
        # if meta.requires_model and not st.session_state.get(StateKey.IS_MODEL_READY, False):
        #     st.error(f"⛔ AKSES DITOLAK: Halaman `{meta.menu_name}` Terkunci")
        #     st.warning("Anda harus melatih atau memuat model terlebih dahulu di menu Modeling.")
        #     st.stop()
        page.run()

    return _runner

def main():
    loader = PageLoader(pages_dir="src/app_pages")
    
    page_instances: list[BasePage] = [
        page
        for page in loader.load_pages()
        if is_page_visible(page)
    ]

    if not page_instances:
        st.error("Folder `app_pages/` belum memiliki file `.py` yang menggunakan `@Options`.")
        return

    # # Urutan kategori sesuai CATEGORY_CONFIG
    category_order = {
        category: index
        for index, category in enumerate(CATEGORY_CONFIG)
    }
    
    page_instances.sort(
        key=lambda page: (
            0 if get_page_category(page) is None else 1,
            category_order.get(
                get_page_category(page) or "/",
                len(category_order),
            ),
            page.__page_meta__.page_name.lower(),
        )
    )
    

    # Build Streamlit pages
    # Build Streamlit pages and lookup dictionary
    st_pages: list[StreamlitPage] = []
    page_lookup: dict[int, StreamlitPage] = {}

    for index, page in enumerate(page_instances):
        meta = page.__page_meta__
        
        page.on_start()

        url_path = build_url_path(page)
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
            ("1. Pengumpulan Data", StageKey.STAGE_1, "/app-dataset"),
            ("2. Pelabelan Data", StageKey.STAGE_2, "/app-labeling"),
            ("3. Preprocessing", StageKey.STAGE_3, ""),
            ("4. Pembobotan TF-IDF", StageKey.STAGE_4, ""),
            ("5. Train-Test Split", StageKey.STAGE_5, ""),
            ("6. Training Model", StageKey.STAGE_6, ""),
            ("7. Evaluasi Model", StageKey.STAGE_7, ""),
            ("8. Visualisasi", StageKey.STAGE_8, ""),
        ]

        all_done = True
        for label, key, link in pipeline_steps:
            done = bool(st.session_state.get(key, False))
            all_done &= done

            target_page = find_page_by_url(st_pages, link)
            icon = "✅" if done else "⬜"

            if target_page is not None:
                st.page_link(
                    target_page,
                    label=f"{icon} {label}",
                    width="stretch",
                )
            else:
                st.markdown(f"&nbsp;&nbsp;{icon} {label}")
        
    st.sidebar.markdown(
        '<div class="sidebar-divider"></div>',
        unsafe_allow_html=True,
    )

    current_category = None

    for index, page in enumerate(page_instances):
        category = get_page_category(page)
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

    pg.run()

if __name__ == '__main__':
    main()
