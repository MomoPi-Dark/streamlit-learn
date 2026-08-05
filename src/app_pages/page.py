import streamlit as st
from lib.enum import StageCollect
from structures.base import BasePage, Options


@Options(
    page_name="overview",
    menu_name="Overview",
    menu_icon="🏠",
    requires_model=False
)
class AppPage(BasePage):
    def run(self) -> None:
        st.title("🎮 NTE Sentiment Analyzer")
        st.write(
            "Selamat datang di framework analisis sentimen ulasan game. "
            "Gunakan menu di sidebar untuk navigasi antar tahap: mulai dari "
            "persiapan dataset, pelatihan model, sampai testing klasifikasi real-time."
        )

        st.markdown("---")

        col1, col2 = st.columns(2)

        dataset_count = st.session_state.get(StageCollect.DATASET_COUNT)
        is_ready = st.session_state.get(StageCollect.MODEL_READY, False)

        with col1:
            if dataset_count:
                st.metric("Dataset", f"{dataset_count} baris", delta="Tersedia")
            else:
                st.metric("Dataset", "Belum ada", delta="Kosong", delta_color="inverse")

        with col2:
            st.metric(
                "Status Model",
                "READY" if is_ready else "NOT READY",
                delta="Siap dipakai" if is_ready else "Perlu training",
                delta_color="normal" if is_ready else "inverse",
            )

        st.markdown("---")

        # ===== Panduan alur kerja =====
        st.subheader("📋 Alur Penggunaan")
        st.markdown(
            """
            1. **Dataset** — Upload atau muat dataset ulasan game yang akan dianalisis.
            2. **Modeling** — Latih model TF-IDF + Multinomial Naive Bayes dari dataset.
            3. **Testing Real-Time** — Uji klasifikasi sentimen langsung dari input teks.
            """
        )

        if not is_ready:
            st.info(
                "🔒 Beberapa halaman terkunci sampai model berhasil dilatih atau dimuat "
                "di menu **Modeling**."
            )