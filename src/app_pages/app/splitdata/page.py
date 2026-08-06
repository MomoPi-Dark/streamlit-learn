import streamlit as st
import pandas as pd
import joblib

from scipy import sparse
from datetime import datetime
from sklearn.model_selection import train_test_split

from structures.base import BasePage, Options
from lib.enum import StageKey, get_session_state, set_session_state
from lib.paths import (
    PREPROCESSED_CSV_PATH,
    TFIDF_MATRIX_PATH,
    TFIDF_VECTORIZER_PATH,
    SPLIT_DIR,
    X_TRAIN_PATH,
    X_TEST_PATH,
    Y_TRAIN_PATH,
    Y_TEST_PATH,
)

LABEL_COLUMN = "sentimen_label"  # sesuaikan jika nama kolom label di dataset berbeda


@Options(
    page_name="train_test_split",
    menu_name="Train-Test Split",
    menu_icon="🔀",
    category="spliting",
)
class AppPage(BasePage):

    def on_start(self) -> None:
        # STAGE_5 = True hanya jika hasil split benar-benar sudah
        # diproses dan tersimpan di disk — bukan sekadar prasyarat terpenuhi.
        is_completed = (
            X_TRAIN_PATH.exists()
            and X_TEST_PATH.exists()
            and Y_TRAIN_PATH.exists()
            and Y_TEST_PATH.exists()
        )

        set_session_state(StageKey.STAGE_5, is_completed)

    def run(self) -> None:
        warning = self._validate_requirements()

        st.title("🔀 Train-Test Split")
        st.write(
            "Membagi data hasil pembobotan TF-IDF menjadi data **latih (train)** "
            "dan data **uji (test)** untuk keperluan pelatihan dan evaluasi model."
        )

        st.info(
            """
            **Tahap 5 - Train-Test Split**

            Tahap ini membagi matriks TF-IDF dan label menjadi dua bagian:
            data latih untuk melatih model, dan data uji untuk mengevaluasi
            performa model secara objektif pada data yang belum pernah dilihat.
            """
        )

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk Train-Test Split\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")
        
        
        if warning:
            st.error("🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Split Data.")
            st.stop()
        
        if X_TRAIN_PATH.exists() and X_TEST_PATH.exists():
            self._render_existing_split()
        else:
            self._render_split()

    # ==========================================================
    # UI
    # ==========================================================

    def _render_existing_split(self) -> None:
        X_train = sparse.load_npz(X_TRAIN_PATH)
        X_test = sparse.load_npz(X_TEST_PATH)
        y_train = joblib.load(Y_TRAIN_PATH)
        y_test = joblib.load(Y_TEST_PATH)

        st.success("✅ Data sudah dibagi menjadi Train dan Test.")

        col1, col2, col3, col4, col5 = st.columns(5)

        total = X_train.shape[0] + X_test.shape[0]
        train_ratio = round(X_train.shape[0] / total * 100)
        test_ratio = round(X_test.shape[0] / total * 100)

        with col1:
            st.metric("Jumlah Data Train", X_train.shape[0])

        with col2:
            st.metric("Ukuran Data Training", f"{train_ratio}%")

        with col3:
            st.metric("Jumlah Data Test", X_test.shape[0])

        with col4:
            st.metric("Rasio Test", f"{test_ratio}%")

        with col5:
            mtime = datetime.fromtimestamp(X_TRAIN_PATH.stat().st_mtime)
            st.metric("Terakhir Diproses", mtime.strftime("%d %b %Y"))

        st.markdown("---")

        st.subheader("📊 Distribusi Label")

        dist_col1, dist_col2 = st.columns(2)

        with dist_col1:
            st.write("**Data Train**")
            st.dataframe(
                pd.Series(y_train).value_counts().rename("Jumlah"),
                width="stretch",
            )

        with dist_col2:
            st.write("**Data Test**")
            st.dataframe(
                pd.Series(y_test).value_counts().rename("Jumlah"),
                width="stretch",
            )

        st.markdown("---")

        with st.expander("🔄 Split Ulang Data"):
            st.warning(
                "Hasil Train-Test Split yang ada akan ditimpa apabila proses dijalankan kembali."
            )
            self._render_split(force=True)

    def _render_split(self, force: bool = False) -> None:
        matrix = sparse.load_npz(TFIDF_MATRIX_PATH)
        df = pd.read_csv(PREPROCESSED_CSV_PATH)

        st.info(f"Dataset siap dibagi ({matrix.shape[0]:,} data, {matrix.shape[1]:,} fitur).")

        test_size = st.slider(
            "Ukuran Data Test (%)",
            min_value=10,
            max_value=40,
            value=20,
            step=5,
            key=f"test_size_{force}",
            help="Persentase data yang dialokasikan untuk data uji (test). Sisanya menjadi data latih (train).",
        )

        stratify_option = st.checkbox(
            "Gunakan stratifikasi berdasarkan label",
            value=True,
            key=f"stratify_{force}",
            help=(
                "Menjaga proporsi tiap kelas label (mis. Positif/Negatif) tetap sama "
                "di data train maupun data test, supaya evaluasi model lebih representatif."
            ),
        )

        st.markdown("---")

        if st.button(
            "🚀 Mulai Train-Test Split" if not force else "🔄 Split Ulang Data",
            type="primary",
            width="stretch",
            disabled=bool(self._validate_requirements()),
            key=f"split_button_{force}",
        ):
            progress = st.progress(0.0)
            status = st.empty()

            X_train, X_test, y_train, y_test = self._process_split(
                matrix,
                df,
                test_size / 100,
                stratify_option,
                progress,
                status,
            )

            SPLIT_DIR.mkdir(parents=True, exist_ok=True)

            sparse.save_npz(X_TRAIN_PATH, X_train)
            sparse.save_npz(X_TEST_PATH, X_test)
            joblib.dump(y_train, Y_TRAIN_PATH)
            joblib.dump(y_test, Y_TEST_PATH)

            progress.progress(1.0)
            status.success("✅ Train-Test Split selesai.")

            st.success(
                f"""
Jumlah Data Train : {X_train.shape[0]:,}

Jumlah Data Test  : {X_test.shape[0]:,}
"""
            )

            st.rerun()

    # ==========================================================
    # PROCESS
    # ==========================================================

    def _process_split(
        self,
        matrix,
        df: pd.DataFrame,
        test_size: float,
        stratify_option: bool,
        progress,
        status,
    ):
        status.info("Mempersiapkan label...")
        progress.progress(0.3)

        y = df[LABEL_COLUMN]
        stratify_arg = y if stratify_option else None

        status.info("Membagi data train dan test...")
        progress.progress(0.6)

        X_train, X_test, y_train, y_test = train_test_split(
            matrix,
            y,
            test_size=test_size,
            random_state=42,
            stratify=stratify_arg,
        )

        status.info("Menyimpan hasil split...")
        progress.progress(0.9)

        return X_train, X_test, y_train, y_test

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_requirements(self) -> list[str] | None:
        warnings: list[str] = []

        if not TFIDF_MATRIX_PATH.exists() or not TFIDF_VECTORIZER_PATH.exists() or not get_session_state(StageKey.STAGE_4):
            warnings.append("📊 Hasil pembobotan TF-IDF belum tersedia.")


        if not PREPROCESSED_CSV_PATH.exists():
            warnings.append("🧹 Dataset hasil preprocessing belum tersedia.")
        else:
            try:
                df = pd.read_csv(PREPROCESSED_CSV_PATH, nrows=5)
                if LABEL_COLUMN not in df.columns:
                    warnings.append(
                        f"📄 Kolom label ('{LABEL_COLUMN}') tidak ditemukan di dataset preprocessing."
                    )
            except Exception:
                warnings.append("📄 Dataset preprocessing tidak dapat dibaca.")

        if warnings:
            return warnings

        return None