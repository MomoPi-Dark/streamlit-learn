import streamlit as st
import pandas as pd
import joblib

from scipy import sparse
from datetime import datetime
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score

from structures.base import BasePage, Options
from lib.enum import StageKey, get_session_state, set_session_state
from lib.paths import (
    X_TRAIN_PATH,
    Y_TRAIN_PATH,
    X_TRAIN_RESAMPLED_PATH,
    Y_TRAIN_RESAMPLED_PATH,
    MODEL_DIR,
    MODEL_PATH,
)


def _load_train_data():
    """
    Pakai data hasil SMOTE (STAGE_6) jika tersedia — supaya kelas sudah
    seimbang saat training. Kalau SMOTE belum dijalankan, fallback ke
    data hasil Train-Test Split biasa (STAGE_5).
    """
    if X_TRAIN_RESAMPLED_PATH.exists() and Y_TRAIN_RESAMPLED_PATH.exists():
        X_train = sparse.load_npz(X_TRAIN_RESAMPLED_PATH)
        y_train = joblib.load(Y_TRAIN_RESAMPLED_PATH)
        is_resampled = True
    else:
        X_train = sparse.load_npz(X_TRAIN_PATH)
        y_train = joblib.load(Y_TRAIN_PATH)
        is_resampled = False

    return X_train, y_train, is_resampled


@Options(
    page_name="training",
    menu_name="Training Model",
    menu_icon="🤖",
    category="modeling",
)
class AppPage(BasePage):

    def on_start(self) -> None:
        # STAGE_7 = True hanya jika model benar-benar sudah dilatih
        # dan tersimpan di disk — bukan sekadar prasyarat terpenuhi.
        set_session_state(StageKey.STAGE_7, MODEL_PATH.exists())

    def run(self) -> None:
        warning = self._validate_requirements()

        st.title("🤖 Training Model")
        st.write(
            "Melatih model klasifikasi sentimen menggunakan algoritma "
            "**Multinomial Naive Bayes** berdasarkan fitur TF-IDF dari data latih."
        )

        st.info(
            """
            **Tahap 7 - Training Model**

            Multinomial Naive Bayes adalah algoritma yang umum digunakan pada
            klasifikasi teks berbasis TF-IDF karena efisien dan bekerja baik
            pada data berdimensi tinggi seperti representasi kata.

            Parameter **alpha** (Laplace smoothing) digunakan untuk mencegah
            probabilitas nol pada kata yang tidak muncul di data latih.
            """
        )

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk Training Model\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if warning:
            st.error("🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Smoote.")
            st.stop()
        
        if MODEL_PATH.exists():
            self._render_existing_model()
        else:
            self._render_training()

    # ==========================================================
    # UI
    # ==========================================================

    def _render_existing_model(self) -> None:
        model = joblib.load(MODEL_PATH)
        X_train, y_train, is_resampled = _load_train_data()

        train_accuracy = accuracy_score(y_train, model.predict(X_train))

        st.success("✅ Model sudah dilatih.")

        if is_resampled:
            st.caption("📌 Model dilatih menggunakan data hasil **SMOTE** (kelas sudah diseimbangkan).")
        else:
            st.caption("📌 Model dilatih menggunakan data train **tanpa SMOTE**.")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Algoritma", "Naive Bayes")

        with col2:
            st.metric("Alpha", model.alpha)

        with col3:
            st.metric("Akurasi Train", f"{train_accuracy * 100:.2f}%")

        with col4:
            mtime = datetime.fromtimestamp(MODEL_PATH.stat().st_mtime)
            st.metric("Terakhir Dilatih", mtime.strftime("%d %b %Y"))

        st.caption(
            "Akurasi di atas dihitung pada **data latih (train)**. "
            "Untuk evaluasi objektif pada data uji, lihat tahap **Evaluasi Model**."
        )

        st.download_button(
            label="⬇️ Download Model (.pkl)",
            data=MODEL_PATH.read_bytes(),
            file_name=MODEL_PATH.name,
            mime="application/octet-stream",
            width="stretch",
        )

        st.markdown("---")

        with st.expander("🔄 Latih Ulang Model"):
            st.warning(
                "Model yang ada akan ditimpa apabila proses training dijalankan kembali."
            )
            self._render_training(force=True)

    def _render_training(self, force: bool = False) -> None:
        X_train, y_train, is_resampled = (
            _load_train_data()
            if (X_TRAIN_RESAMPLED_PATH.exists() or X_TRAIN_PATH.exists())
            else (None, None, False)
        )

        if X_train is not None:
            source_label = "hasil SMOTE (kelas sudah diseimbangkan)" if is_resampled else "hasil Train-Test Split (tanpa SMOTE)"
            st.info(
                f"Data latih siap digunakan — {source_label}: "
                f"{X_train.shape[0]:,} data, {X_train.shape[1]:,} fitur."
            )

            if not is_resampled:
                st.warning(
                    "⚠️ Tahap **SMOTE belum dijalankan**. Training akan memakai data train asli "
                    "yang mungkin belum seimbang antar kelas. Disarankan menjalankan tahap "
                    "**Penyeimbangan Kelas (SMOTE)** terlebih dahulu."
                )

        alpha = st.select_slider(
            "Alpha (Laplace Smoothing)",
            options=[0.01, 0.1, 0.5, 1.0, 1.5, 2.0],
            value=1.0,
            key=f"alpha_{force}",
            help=(
                "Nilai standar yang umum dipakai peneliti adalah 1.0 (Laplace smoothing penuh). "
                "Nilai lebih kecil memberi bobot lebih besar pada frekuensi kata asli di data latih."
            ),
        )

        st.markdown("---")

        if st.button(
            "🚀 Mulai Training Model" if not force else "🔄 Latih Ulang Model",
            type="primary",
            width="stretch",
            disabled=bool(self._validate_requirements()),
            key=f"train_button_{force}",
        ):
            progress = st.progress(0.0)
            status = st.empty()

            model, train_accuracy = self._process_training(
                X_train,
                y_train,
                alpha,
                progress,
                status,
            )

            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, MODEL_PATH)

            progress.progress(1.0)
            status.success("✅ Training Model selesai.")

            st.success(
                f"""
Algoritma      : Multinomial Naive Bayes

Alpha          : {alpha}

Akurasi Train  : {train_accuracy * 100:.2f}%
"""
            )

            st.rerun()

    # ==========================================================
    # PROCESS
    # ==========================================================

    def _process_training(
        self,
        X_train,
        y_train,
        alpha: float,
        progress,
        status,
    ):
        status.info("Mempersiapkan model...")
        progress.progress(0.3)

        model = MultinomialNB(alpha=alpha)

        status.info("Melatih model Naive Bayes...")
        progress.progress(0.6)

        model.fit(X_train, y_train)

        status.info("Menghitung akurasi data latih...")
        progress.progress(0.9)

        train_accuracy = accuracy_score(y_train, model.predict(X_train))

        return model, train_accuracy

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_requirements(self) -> list[str] | None:
        warnings: list[str] = []

        if not X_TRAIN_PATH.exists() or not Y_TRAIN_PATH.exists() or not get_session_state(StageKey.STAGE_5):
            warnings.append("🔀 Hasil Train-Test Split belum tersedia.")

        if warnings:
            return warnings

        return None