import json

import streamlit as st

from lib.enum import StageCollect
from lib.running_badge import render_status_badges
from lib.paths import METRICS_PATH, WORD_FREQ_IMAGE_PATH, WORDCLOUD_IMAGE_PATH_TEMPLATE
from structures.base import BasePage, Options
from lib.enum import StageKey, get_session_state, set_session_state


def _hero_html(eyebrow: str, title: str, subtitle: str) -> str:
    return (
        "<div class='ov-hero'>"
        f"<div class='ov-hero-eyebrow'>{eyebrow}</div>"
        f"<h1>{title}</h1>"
        f"<p>{subtitle}</p>"
        "<div class='ov-hero-rule'></div>"
        "</div>"
    )


def _stat_card_html(icon: str, label: str, value: str, badge: str, tone: str) -> str:
    return (
        f"<div class='ov-stat-card {tone}'>"
        f"<div class='ov-stat-icon'>{icon}</div>"
        "<div class='ov-stat-body'>"
        f"<div class='ov-stat-label'>{label}</div>"
        f"<div class='ov-stat-value'>{value}</div>"
        f"<div class='ov-stat-badge'>{badge}</div>"
        "</div></div>"
    )


def _metric_card_html(label: str, value: str) -> str:
    return (
        "<div class='ov-metric-card'>"
        f"<div class='ov-metric-label'>{label}</div>"
        f"<div class='ov-metric-value'>{value}</div>"
        "</div>"
    )


def _flow_badge(state: str) -> str:
    return {
        "done": "✅ Selesai",
        "active": "🔵 Sedang berjalan",
        "pending": "⚪ Menunggu",
    }[state]


def _flow_html(steps: list[dict]) -> str:
    parts = ["<div class='ov-flow-grid'>"]
    for i, step in enumerate(steps):
        parts.append(
            f"<div class='ov-flow-step {step['state']}'>"
            f"<div class='ov-flow-number'>{i + 1:02d}</div>"
            f"<div class='ov-flow-icon'>{step['icon']}</div>"
            f"<div class='ov-flow-title'>{step['title']}</div>"
            f"<div class='ov-flow-badge'>{_flow_badge(step['state'])}</div>"
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _render_results_summary() -> None:
    st.markdown(
        "<div class='ov-section-title'><span class='ov-section-eyebrow'>Hasil</span>"
        "📊 Ringkasan Evaluasi Model</div>",
        unsafe_allow_html=True,
    )

    if not METRICS_PATH.exists():
        st.markdown(
            "<div class='ov-banner'><span>🔒</span>"
            "<span>Belum ada hasil evaluasi. Jalankan tahap "
            "<b>Evaluasi Model</b> terlebih dahulu.</span></div>",
            unsafe_allow_html=True,
        )
        return

    with open(METRICS_PATH, encoding="utf-8") as f:
        metrics = json.load(f)

    grid_html = "<div class='ov-result-grid'>"
    for label, key in [
        ("Accuracy", "accuracy"),
        ("Precision", "precision"),
        ("Recall", "recall"),
        ("F1-Score", "f1_score"),
    ]:
        grid_html += _metric_card_html(label, f"{metrics[key] * 100:.2f}%")
    grid_html += "</div>"
    st.markdown(grid_html, unsafe_allow_html=True)

    st.markdown(
        f"<div class='ov-caption'>Precision, Recall, dan F1-Score dihitung dengan "
        f"rata-rata <b>weighted</b> (mempertimbangkan proporsi tiap kelas) · "
        f"Terakhir dievaluasi: {metrics['evaluated_at']}</div>",
        unsafe_allow_html=True,
    )

    wordcloud_labels = ["Positif", "Negatif"]
    candidates = [(WORD_FREQ_IMAGE_PATH, "Top 20 Kata")] + [
        (WORDCLOUD_IMAGE_PATH_TEMPLATE(label), f"WordCloud {label}")
        for label in wordcloud_labels
    ]
    thumbs = [(path, caption) for path, caption in candidates if path.exists()]

    if thumbs:
        st.markdown(
            "<div class='ov-subsection-title'>🖼️ Visualisasi Tersedia</div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(len(thumbs))
        for col, (path, caption) in zip(cols, thumbs):
            with col:
                st.image(str(path), caption=caption, width="stretch")
    else:
        st.markdown(
            "<div class='ov-banner'><span>🔒</span>"
            "<span>Belum ada visualisasi. Jalankan tahap "
            "<b>Visualisasi</b> terlebih dahulu.</span></div>",
            unsafe_allow_html=True,
        )


@Options(page_name="overview", menu_name="Overview", menu_icon="🏠")
class AppPage(BasePage):
    def run(self) -> None:
        render_status_badges()

        dataset_count = get_session_state(StageCollect.DATASET_COUNT)
        is_ready = get_session_state(StageCollect.MODEL_READY)

        # ===== Hero =====
        st.markdown(
            _hero_html(
                "Penelitian Skripsi · Analisis Sentimen Ulasan Game",
                "🎮 NTE Sentiment Analyzer",
                "Framework analisis sentimen ulasan pengguna game berbasis "
                "<b>TF-IDF</b> dan <b>Multinomial Naive Bayes</b>. Gunakan menu "
                "di sidebar untuk menelusuri tiap tahap penelitian — mulai dari "
                "persiapan dataset, pelatihan model, hingga pengujian klasifikasi "
                "secara langsung.",
            ),
            unsafe_allow_html=True,
        )

        # ===== Stat cards =====
        stats_html = "<div class='ov-stats'>"
        if dataset_count:
            stats_html += _stat_card_html(
                "📊",
                "Dataset",
                f"N = {dataset_count:,}",
                "Tersedia",
                "positive",
            )
        else:
            stats_html += _stat_card_html(
                "📊", "Dataset", "N = —", "Belum dimuat", "attention"
            )

        if is_ready:
            stats_html += _stat_card_html(
                "🧠", "Status Model", "READY", "Siap dipakai", "positive"
            )
        else:
            stats_html += _stat_card_html(
                "🧠", "Status Model", "NOT READY", "Perlu training", "attention"
            )
        stats_html += "</div>"
        st.markdown(stats_html, unsafe_allow_html=True)

        # ===== Alur Penelitian =====
        st.markdown(
            "<div class='ov-section-title'><span class='ov-section-eyebrow'>Alur</span>"
            "📋 Tahapan Penelitian</div>",
            unsafe_allow_html=True,
        )

        # Sesuaikan nama StageKey ini kalau berbeda dari enum kamu.
        pipeline_stages = [
            (StageKey.STAGE_1, "📥", "Pengumpulan Data"),
            (StageKey.STAGE_2, "🏷️", "Pelabelan Data"),
            (StageKey.STAGE_3, "🧹", "Preprocessing"),
            (StageKey.STAGE_4, "🧮", "Pembobotan TF-IDF"),
            (StageKey.STAGE_5, "✂️", "Train-Test Split"),
            (StageKey.STAGE_6, "⚖️", "Penyeimbangan Kelas (SMOTE)"),
            (StageKey.STAGE_7, "🧠", "Training Model"),
            (StageKey.STAGE_8, "📈", "Evaluasi Model"),
            (StageKey.STAGE_9, "🖼️", "Visualisasi"),
        ]

        steps = []
        found_active = False
        for stage_key, icon, title in pipeline_stages:
            done = bool(get_session_state(stage_key))
            if done:
                state = "done"
            elif not found_active:
                state = "active"
                found_active = True
            else:
                state = "pending"
            steps.append({"icon": icon, "title": title, "state": state})

        st.markdown(_flow_html(steps), unsafe_allow_html=True)

        if not is_ready:
            st.markdown(
                "<div class='ov-banner'>"
                "<span>🔒</span>"
                "<span> Beberapa halaman terkunci sampai seluruh tahapan di atas "
                "selesai dijalankan.</span>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<div class='ov-divider'></div>", unsafe_allow_html=True)
            _render_results_summary()
