import json

import streamlit as st

from lib.enum import StageCollect
from lib.running_badge import render_status_badges
from lib.paths import METRICS_PATH, WORD_FREQ_IMAGE_PATH, WORDCLOUD_IMAGE_PATH_TEMPLATE
from structures.base import BasePage, Options
from lib.enum import StageKey, get_session_state, set_session_state

# ===== CSS kustom (senada dengan halaman Preprocessing) =====
_OVERVIEW_CSS = """
<style>
.ov-hero {
    background: linear-gradient(135deg, rgba(99,102,241,0.18), rgba(56,189,248,0.08));
    border: 1px solid rgba(99,102,241,0.35);
    border-radius: 18px;
    padding: 26px 28px;
    margin-bottom: 20px;
}
.ov-hero h1 { margin: 0 0 6px 0; font-size: 1.6em; color: #f1f5f9; }
.ov-hero p { margin: 0; color: #cbd5e1; font-size: 0.95em; line-height: 1.55; max-width: 640px; }

.ov-stats { display: flex; gap: 16px; margin-bottom: 22px; }
.ov-stat-card {
    flex: 1; display: flex; align-items: center; gap: 14px;
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 18px 20px;
}
.ov-stat-icon {
    width: 48px; height: 48px; border-radius: 14px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.ov-stat-card.positive .ov-stat-icon { background: rgba(74,222,128,0.16); }
.ov-stat-card.attention .ov-stat-icon { background: rgba(251,191,36,0.16); }
.ov-stat-label { font-size: 0.8em; color: #94a3b8; margin-bottom: 2px; }
.ov-stat-value { font-size: 1.35em; font-weight: 800; color: #e2e8f0; line-height: 1.2; }
.ov-stat-badge {
    display: inline-block; margin-top: 5px; padding: 2px 10px; border-radius: 999px;
    font-size: 0.72em; font-weight: 700;
}
.ov-stat-card.positive .ov-stat-badge { background: rgba(74,222,128,0.18); color: #4ade80; }
.ov-stat-card.attention .ov-stat-badge { background: rgba(251,191,36,0.18); color: #fbbf24; }

.ov-section-title {
    font-size: 1.02em; font-weight: 700; color: #e2e8f0;
    display: flex; align-items: center; gap: 8px; margin: 4px 0 14px 0;
}

.ov-flow { display: flex; align-items: stretch; gap: 4px; margin-bottom: 18px; }
.ov-flow-step {
    flex: 1; border-radius: 16px; padding: 18px 16px;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.004));
    transition: all .3s ease;
}
.ov-flow-step.done { border-color: rgba(74,222,128,0.4); }
.ov-flow-step.active {
    border-color: rgba(56,189,248,0.55);
    box-shadow: 0 0 0 3px rgba(56,189,248,0.12);
}
.ov-flow-step.pending { opacity: 0.55; }
.ov-flow-icon { font-size: 24px; margin-bottom: 8px; }
.ov-flow-title { font-weight: 700; font-size: 0.95em; color: #e2e8f0; margin-bottom: 4px; }
.ov-flow-desc { font-size: 0.8em; color: #94a3b8; line-height: 1.45; margin-bottom: 12px; min-height: 34px; }
.ov-flow-badge {
    font-size: 0.7em; font-weight: 700; padding: 2px 9px; border-radius: 999px; display: inline-block;
}
.ov-flow-step.done .ov-flow-badge { background: rgba(74,222,128,0.18); color: #4ade80; }
.ov-flow-step.active .ov-flow-badge { background: rgba(56,189,248,0.2); color: #38bdf8; }
.ov-flow-step.pending .ov-flow-badge { background: rgba(255,255,255,0.08); color: #94a3b8; }
.ov-flow-arrow {
    display: flex; align-items: center; justify-content: center;
    color: #475569; font-size: 18px; padding: 0 2px; flex-shrink: 0;
}

.ov-banner {
    display: flex; align-items: center; gap: 10px;
    border-radius: 12px; border: 1px solid rgba(251,191,36,0.4);
    background: linear-gradient(90deg, rgba(251,191,36,0.16), rgba(245,158,11,0.07));
    color: #fde68a; padding: 12px 16px; font-weight: 600; font-size: 0.9em;
    margin-top: 4px;
}

.ov-result-grid { display: flex; gap: 16px; margin-bottom: 18px; }
.ov-metric-card {
    flex: 1; text-align: center;
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 16px 12px;
}
.ov-metric-label { font-size: 0.78em; color: #94a3b8; margin-bottom: 4px; }
.ov-metric-value { font-size: 1.5em; font-weight: 800; color: #4ade80; }
</style>
"""


def _inject_overview_css() -> None:
    st.markdown(_OVERVIEW_CSS, unsafe_allow_html=True)


def _hero_html(title: str, subtitle: str) -> str:
    return f"<div class='ov-hero'><h1>{title}</h1><p>{subtitle}</p></div>"


def _stat_card_html(icon: str, label: str, value: str, badge: str, tone: str) -> str:
    return (
        f"<div class='ov-stat-card {tone}'>"
        f"<div class='ov-stat-icon'>{icon}</div>"
        "<div>"
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


def _flow_html(steps: list[dict]) -> str:
    parts = ["<div class='ov-flow'>"]
    for i, step in enumerate(steps):
        if i > 0:
            parts.append("<div class='ov-flow-arrow'>›</div>")
        badge_map = {
            "done": "✅ Selesai",
            "active": "🔵 Sedang berjalan",
            "pending": "⚪ Menunggu",
        }
        parts.append(
            f"<div class='ov-flow-step {step['state']}'>"
            f"<div class='ov-flow-icon'>{step['icon']}</div>"
            f"<div class='ov-flow-title'>{step['title']}</div>"
            f"<div class='ov-flow-desc'>{step['desc']}</div>"
            f"<div class='ov-flow-badge'>{badge_map[step['state']]}</div>"
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _render_results_summary() -> None:
    st.markdown(
        "<div class='ov-section-title'>📊 Ringkasan Hasil</div>",
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
        grid_html += _metric_card_html(label, f"{metrics[key] * 100:.1f}%")
    grid_html += "</div>"
    st.markdown(grid_html, unsafe_allow_html=True)

    st.caption(f"Terakhir dievaluasi: {metrics['evaluated_at']}")

    wordcloud_labels = ["Positif", "Negatif"]
    candidates = [(WORD_FREQ_IMAGE_PATH, "Top 20 Kata")] + [
        (WORDCLOUD_IMAGE_PATH_TEMPLATE(label), f"WordCloud {label}")
        for label in wordcloud_labels
    ]
    thumbs = [(path, caption) for path, caption in candidates if path.exists()]

    if thumbs:
        st.write("**🖼️ Visualisasi Tersedia**")
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


@Options(
    page_name="overview", menu_name="Overview", menu_icon="🏠", requires_model=False
)
class AppPage(BasePage):
    def on_start(self) -> None:
        _inject_overview_css()

    def run(self) -> None:
        render_status_badges()

        dataset_count = get_session_state(StageCollect.DATASET_COUNT)
        is_ready = get_session_state(StageCollect.MODEL_READY)

        # ===== Hero =====
        st.markdown(
            _hero_html(
                "🎮 NTE Sentiment Analyzer",
                "Selamat datang di framework analisis sentimen ulasan game. "
                "Gunakan menu di sidebar untuk navigasi antar tahap: mulai dari "
                "persiapan dataset, pelatihan model, sampai testing klasifikasi real-time.",
            ),
            unsafe_allow_html=True,
        )

        # ===== Stat cards =====
        stats_html = "<div class='ov-stats'>"
        if dataset_count:
            stats_html += _stat_card_html(
                "📊", "Dataset", f"{dataset_count:,} baris", "Tersedia", "positive"
            )
        else:
            stats_html += _stat_card_html(
                "📊", "Dataset", "Belum ada", "Kosong", "attention"
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

        # # ===== Alur Penggunaan =====
        # st.markdown(
        #     "<div class='ov-section-title'>📋 Alur Penggunaan</div>",
        #     unsafe_allow_html=True,
        # )

        if is_ready:
            dataset_state, modeling_state = "done", "done"
        elif dataset_count:
            dataset_state, modeling_state = "done", "active"
        else:
            dataset_state, modeling_state = (
                "active",
                "pending",
            )

        steps = [
            {
                "icon": "📊",
                "title": "1. Dataset",
                "desc": "Upload atau muat dataset ulasan game yang akan dianalisis.",
                "state": dataset_state,
            },
            {
                "icon": "🧠",
                "title": "2. Modeling",
                "desc": "Latih model TF-IDF + Multinomial Naive Bayes dari dataset.",
                "state": modeling_state,
            },
        ]
        st.markdown(_flow_html(steps), unsafe_allow_html=True)

        if not is_ready:
            st.markdown(
                "<div class='ov-banner'>"
                "<span>🔒</span>"
                "<span>Beberapa halaman terkunci sampai model berhasil dilatih atau "
                "dimuat di menu <b>Modeling</b>.</span>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("---")
            _render_results_summary()
