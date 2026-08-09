import streamlit as st
import pandas as pd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

from collections import Counter
from scipy import sparse
from datetime import datetime
from wordcloud import WordCloud

from structures.base import BasePage, Options
from lib.enum import StageKey, get_session_state, set_session_state
from lib.paths import (
    PREPROCESSED_CSV_PATH,
    X_TEST_PATH,
    Y_TEST_PATH,
    MODEL_PATH,
    IMAGES_DIR,
    WORD_FREQ_IMAGE_PATH,
    WORDCLOUD_IMAGE_PATH_TEMPLATE,
)

SENTIMENT_LABELS = ["Positif", "Negatif"]
COLORMAP_DICT = {
    "Positif": "viridis",
    "Negatif": "Reds",
}


@Options(
    page_name="visualization",
    menu_name="Visualisasi",
    menu_icon="🖼️",
    category="training",
)
class AppPage(BasePage):

    def on_start(self) -> None:
        # STAGE_9 = True hanya jika seluruh visualisasi sudah dibuat dan
        # tersimpan di disk — bukan sekadar prasyarat terpenuhi.
        wordcloud_paths = [
            WORDCLOUD_IMAGE_PATH_TEMPLATE(label) for label in SENTIMENT_LABELS
        ]
        is_completed = WORD_FREQ_IMAGE_PATH.exists() and all(
            p.exists() for p in wordcloud_paths
        )
        set_session_state(StageKey.STAGE_9, is_completed)

    def run(self) -> None:
        warning = self._validate_requirements()

        st.title("🖼️ Visualisasi")
        st.write(
            "Menampilkan visualisasi eksploratif dari dataset dan hasil prediksi model: "
            "frekuensi kata dan WordCloud per kelas sentimen."
        )

        st.info("""
            **Tahap 9 - Visualisasi**

            - **Diagram Batang**: 20 kata yang paling sering muncul di seluruh ulasan.
            - **WordCloud per Sentimen**: kata-kata dominan pada ulasan yang
              **diprediksi model** sebagai Positif dan Negatif di data uji.
            """)

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk Visualisasi\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if warning:
            st.error(
                "🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Evaluation."
            )
            st.stop()

        all_exist = WORD_FREQ_IMAGE_PATH.exists() and all(
            WORDCLOUD_IMAGE_PATH_TEMPLATE(label).exists() for label in SENTIMENT_LABELS
        )

        if all_exist:
            self._render_existing_visualization()
        else:
            self._render_visualization()

    # ==========================================================
    # UI
    # ==========================================================

    def _render_existing_visualization(self) -> None:
        st.success("✅ Visualisasi sudah dibuat.")

        mtime = datetime.fromtimestamp(WORD_FREQ_IMAGE_PATH.stat().st_mtime)
        st.caption(f"Terakhir dibuat: {mtime.strftime('%d %b %Y %H:%M')}")

        st.markdown("---")

        st.subheader("📊 Top 20 Kata Paling Sering Muncul")
        st.image(str(WORD_FREQ_IMAGE_PATH), width="stretch")
        st.download_button(
            label="⬇️ Download Diagram Batang (.png)",
            data=WORD_FREQ_IMAGE_PATH.read_bytes(),
            file_name=WORD_FREQ_IMAGE_PATH.name,
            mime="image/png",
            width="stretch",
            key="download_word_freq",
        )

        st.markdown("---")

        st.subheader("☁️ WordCloud per Kelas Sentimen")

        col1, col2 = st.columns(2)

        for col, label in zip((col1, col2), SENTIMENT_LABELS):
            path = WORDCLOUD_IMAGE_PATH_TEMPLATE(label)
            with col:
                st.write(f"**{label}**")
                if path.exists():
                    st.image(str(path), width="stretch")
                    st.download_button(
                        label=f"⬇️ Download WordCloud {label} (.png)",
                        data=path.read_bytes(),
                        file_name=path.name,
                        mime="image/png",
                        width="stretch",
                        key=f"download_wc_{label}",
                    )
                else:
                    st.info(
                        f"WordCloud untuk {label} tidak tersedia (tidak ada data diprediksi sebagai {label})."
                    )

        st.markdown("---")

        with st.expander("🔄 Buat Ulang Visualisasi"):
            st.warning(
                "Gambar yang ada akan ditimpa apabila proses dijalankan kembali."
            )
            self._render_visualization(force=True)

    def _render_visualization(self, force: bool = False) -> None:
        st.markdown("---")

        if st.button(
            "🚀 Buat Visualisasi" if not force else "🔄 Buat Ulang Visualisasi",
            type="primary",
            width="stretch",
            disabled=bool(self._validate_requirements()),
            key=f"viz_button_{force}",
        ):
            progress = st.progress(0.0)
            status = st.empty()

            IMAGES_DIR.mkdir(parents=True, exist_ok=True)

            status.info("Membuat diagram batang top 20 kata...")
            progress.progress(0.2)
            self._generate_word_frequency_chart()

            status.info("Melakukan prediksi pada data uji...")
            progress.progress(0.5)
            df, y_test, y_pred = self._predict_test_set()

            status.info("Membuat WordCloud per kelas sentimen...")
            progress.progress(0.7)
            skipped_labels = self._generate_wordclouds(df, y_test, y_pred, progress)

            progress.progress(1.0)
            status.success("✅ Visualisasi selesai dibuat.")

            if skipped_labels:
                st.warning(
                    "WordCloud tidak dapat dibuat untuk kelas: "
                    + ", ".join(skipped_labels)
                    + " (tidak ada data yang diprediksi sebagai kelas tersebut)."
                )

            st.rerun()

    # ==========================================================
    # PROCESS
    # ==========================================================

    def _generate_word_frequency_chart(self) -> None:
        df = pd.read_csv(PREPROCESSED_CSV_PATH)

        all_words = " ".join(df["clean_ulasan"].fillna("").astype(str)).split()
        word_counts = Counter(all_words)

        top_20_words = word_counts.most_common(20)
        df_top_words = pd.DataFrame(top_20_words, columns=["Kata", "Frekuensi"])

        fig, ax = plt.subplots(figsize=(12, 8))
        sns.barplot(
            x="Frekuensi",
            y="Kata",
            hue="Kata",
            data=df_top_words,
            palette="viridis",
            legend=False,
            ax=ax,
        )
        ax.set_title("Top 20 Kata Paling Sering Muncul pada Ulasan NTE", fontsize=16)
        ax.set_xlabel("Frekuensi", fontsize=12)
        ax.set_ylabel("Kata", fontsize=12)
        fig.tight_layout()

        fig.savefig(WORD_FREQ_IMAGE_PATH, dpi=300)
        plt.close(fig)

    def _predict_test_set(self):
        df = pd.read_csv(PREPROCESSED_CSV_PATH)

        model = joblib.load(MODEL_PATH)
        X_test = sparse.load_npz(X_TEST_PATH)
        y_test = joblib.load(Y_TEST_PATH)

        y_pred = model.predict(X_test)

        return df, y_test, y_pred

    def _generate_wordclouds(self, df, y_test, y_pred, progress) -> list[str]:
        df_test = pd.DataFrame(
            {"actual": y_test, "predicted": y_pred}, index=y_test.index
        )

        skipped_labels: list[str] = []
        step = 0.7

        for label in SENTIMENT_LABELS:
            subset = df_test[df_test["predicted"] == label]
            texts = df.loc[subset.index, "clean_ulasan"].fillna("").astype(str).tolist()

            text = " ".join(texts)

            if not text.strip():
                skipped_labels.append(label)
                step += 0.1
                progress.progress(min(step, 0.95))
                continue

            wordcloud = WordCloud(
                width=1600,
                height=800,
                background_color="white",
                scale=2,
                max_words=200,
                collocations=False,
                colormap=COLORMAP_DICT[label],
                random_state=42,
            ).generate(text)

            fig = plt.figure(figsize=(16, 8), dpi=300)
            plt.imshow(wordcloud, interpolation="bilinear")
            plt.axis("off")
            plt.title(
                f"Top Kata Sentimen {label.upper()}",
                fontsize=20,
                fontweight="bold",
                pad=20,
            )

            filepath = WORDCLOUD_IMAGE_PATH_TEMPLATE(label)
            fig.savefig(filepath, dpi=300, bbox_inches="tight", pad_inches=0.2)
            plt.close(fig)

            step += 0.1
            progress.progress(min(step, 0.95))

        return skipped_labels

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_requirements(self) -> list[str] | None:
        warnings: list[str] = []

        if not PREPROCESSED_CSV_PATH.exists() or not get_session_state(
            StageKey.STAGE_3
        ):
            warnings.append("🧹 Dataset hasil preprocessing belum tersedia.")

        if not MODEL_PATH.exists() or not get_session_state(StageKey.STAGE_7):
            warnings.append("🤖 Tahap Training Model belum selesai.")

        if not X_TEST_PATH.exists() or not Y_TEST_PATH.exists():
            warnings.append("🔀 Data uji (Train-Test Split) belum tersedia.")

        if warnings:
            return warnings

        return None
