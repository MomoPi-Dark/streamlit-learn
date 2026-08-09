import threading
import time

import streamlit as st

from lib.bgManager import background_manager

# Label ramah-pengguna untuk nama task background (opsional, biar tidak
# nampilin nama internal seperti "preproccessing" mentah-mentah)
_FRIENDLY_LABELS = {
    "preproccessing": "Preprocessing Data",
}

# ===== State untuk notifikasi "pages di-reload" =====
# Disimpan module-level (bukan session_state) karena reload pages itu
# kejadian global untuk semua sesi, bukan per-user.
_reload_lock = threading.Lock()
_pages_reloaded_at: float | None = None
_seen_first_load = False
RELOAD_BADGE_DURATION = 6  # detik badge "Halaman diperbarui" tampil


def mark_pages_reloaded() -> None:
    """
    Panggil di DALAM body fungsi yang di-@st.cache_resource untuk loading
    page classes, contoh:

        @st.cache_resource
        def get_page_classes(version: str):
            loader = PageLoader("src/app_pages")
            classes = loader.load_page_classes()
            mark_pages_reloaded()
            return classes

    Karena st.cache_resource cuma menjalankan body fungsi saat cache miss
    (versi berubah), titik ini persis menandai kapan pages benar-benar
    di-reload dari disk.
    """
    global _pages_reloaded_at, _seen_first_load
    with _reload_lock:
        if not _seen_first_load:
            # load pertama saat app baru start bukan "perubahan", jadi di-skip
            _seen_first_load = True
            return
        _pages_reloaded_at = time.time()


def _pages_recently_reloaded() -> bool:
    with _reload_lock:
        t = _pages_reloaded_at
    return t is not None and (time.time() - t) < RELOAD_BADGE_DURATION


def _friendly(name: str) -> str:
    return _FRIENDLY_LABELS.get(name, name)


_BADGE_CSS = """
<style>
.bm-badge-wrap {
    position: fixed; top: 3.8rem; right: 1.4rem; z-index: 999999;
    display: flex; flex-direction: column; align-items: flex-end; gap: 8px;
}
.bm-badge {
    display: flex; align-items: center; gap: 8px;
    color: #fff; padding: 7px 14px 7px 12px; border-radius: 999px;
    font-size: 0.8em; font-weight: 700;
    box-shadow: 0 4px 16px rgba(0,0,0,0.35);
    animation: bm-slide-in .25s ease;
    white-space: nowrap;
}
.bm-badge.running { background: linear-gradient(90deg, #38bdf8, #6366f1); }
.bm-badge.reload { background: linear-gradient(90deg, #22c55e, #16a34a); }
.bm-badge-dot {
    width: 8px; height: 8px; border-radius: 50%; background: #fff;
    animation: bm-pulse 1.2s ease-in-out infinite; flex-shrink: 0;
}
@keyframes bm-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.35; transform: scale(0.65); }
}
@keyframes bm-slide-in {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
"""


def _badge_html(kind: str, icon: str, text: str, pulse: bool) -> str:
    dot = "<span class='bm-badge-dot'></span>" if pulse else ""
    return f"<div class='bm-badge {kind}'>{dot}<span>{icon} {text}</span></div>"


@st.fragment(run_every=1)
def render_status_badges() -> None:
    """
    Panggil ini di paling atas method run() tiap halaman. Menampilkan
    stack badge di pojok kanan atas untuk:
      - task background yang sedang berjalan (background_manager)
      - notifikasi singkat kalau pages baru saja di-reload (mark_pages_reloaded)
    """
    badges = []

    running = background_manager.get_running_names()
    if running:
        labels = ", ".join(_friendly(n) for n in running)
        badges.append(
            _badge_html("running", "🔄", f"{labels} sedang berjalan", pulse=True)
        )

    if _pages_recently_reloaded():
        badges.append(_badge_html("reload", "✨", "Halaman diperbarui", pulse=False))

    if not badges:
        return

    st.markdown(
        f"{_BADGE_CSS}<div class='bm-badge-wrap'>{''.join(badges)}</div>",
        unsafe_allow_html=True,
    )
