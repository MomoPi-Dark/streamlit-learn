import streamlit as st
from typing import Callable, Optional
from lib.enum import pop_session_state, set_session_state, get_session_state
import uuid
import time

_ALERT_STYLES = {
    "success": {
        "bg": "rgba(33, 195, 84, 0.15)",
        "text": "#21c354",
        "icon": "✅",
    },
    "info": {
        "bg": "rgba(41, 148, 255, 0.15)",
        "text": "#2994ff",
        "icon": "ℹ️",
    },
    "warning": {
        "bg": "rgba(250, 202, 43, 0.15)",
        "text": "#ffc933",
        "icon": "⚠️",
    },
    "error": {
        "bg": "rgba(255, 75, 75, 0.15)",
        "text": "#ff6b6b",
        "icon": "❗",
    },
}


def alert_with_action(
    title: str,
    description: str,
    button_label: Optional[str] = None,
    on_click: Optional[Callable[[], Optional[str]]] = None,
    variant: str = "warning",
    button_icon: Optional[str] = None,
    title_ratio: float = 4,
    button_ratio: float = 1.0,
    key: Optional[str] = None,
    error_duration: float = 4,
) -> None:
    """
    Alert box bergaya native Streamlit (success/info/warning/error) dengan
    title + description di kiri dan tombol aksi di kanan, sejajar vertikal.

    Args:
        title: Judul alert (bold).
        description: Teks deskripsi di bawah title.
        button_label: Label tombol.
        on_click: Callback tanpa argumen. HARUS return string pesan error
                  kalau gagal, atau None kalau sukses. Jangan panggil
                  st.error/st.warning sendiri di dalam callback ini —
                  biar error-nya dirender full-width di bawah alert box,
                  bukan di dalam kolom tombol yang sempit.
        variant: "success" | "info" | "warning" | "error".
        button_icon: Emoji/icon di depan label tombol (opsional).
        title_ratio / button_ratio: Rasio lebar kolom konten vs tombol.
        key: Unique key untuk widget & CSS marker.
    """
    style = _ALERT_STYLES.get(variant, _ALERT_STYLES["warning"])
    marker_id = key or f"alert-action-{uuid.uuid4().hex[:8]}"
    marker_class = f"alert-marker-{marker_id}"
    error_state_key = f"{marker_id}-error"

    st.markdown(
        f"""
        <style>
        div[data-testid="stHorizontalBlock"]:has(.{marker_class}) {{
            background-color: {style["bg"]} !important;
            border: 1px solid rgba(250, 250, 250, 0.2) !important;
            padding: 1rem 1.25rem !important;
        }}
        .{marker_class}-title {{
            color: {style["text"]} !important;
        }}
        .{marker_class}-desc {{
            color: rgba(255, 255, 255, 0.85) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    def render_text() -> None:
        st.markdown(
            f"""
            <div class="{marker_class}">
                <p class="{marker_class}-title">{style["icon"]} {title}</p>
                <p class="{marker_class}-desc">{description}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not button_label or on_click is None:
        render_text()
        return

    col_text, col_btn = st.columns(
        [title_ratio, button_ratio], vertical_alignment="center"
    )

    with col_text:
        render_text()

    with col_btn:
        label = f"{button_icon} {button_label}" if button_icon else button_label
        if st.button(label, key=f"{marker_id}-btn", width="content"):
            error_message = on_click()
            if error_message:
                set_session_state(
                    error_state_key,
                    {"message": error_message, "shown_at": time.time()},
                )
            else:
                pop_session_state(error_state_key, None)

    error_data = st.session_state.get(error_state_key)
    if isinstance(error_data, dict) and "shown_at" in error_data:
        elapsed = time.time() - error_data["shown_at"]
        if elapsed >= error_duration:
            st.session_state.pop(error_state_key, None)
        else:
            st.error(error_data["message"])
