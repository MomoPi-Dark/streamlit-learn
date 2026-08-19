import streamlit as st
import pandas as pd
import joblib

from scipy import sparse
from datetime import datetime
from imblearn.over_sampling import SMOTE

from structures.base import BasePage, Options
from lib.enum import StageKey, get_session_state, set_session_state
from lib.paths import (
    X_TRAIN_PATH,
    Y_TRAIN_PATH,
    SMOTE_DIR,
    X_TRAIN_RESAMPLED_PATH,
    Y_TRAIN_RESAMPLED_PATH,
)


@Options(
    page_name="smote",
    menu_name="Penyeimbangan Kelas (SMOTE)",
    menu_icon="⚖️",
    category="modeling",
)
class AppPage(BasePage):
    def on_start(self) -> None:
        # STAGE_6 = True hanya jika hasil resampling benar-benar sudah
        # tersimpan di disk — bukan sekadar prasyarat terpenuhi.
        is_completed = (
            X_TRAIN_RESAMPLED_PATH.exists() and Y_TRAIN_RESAMPLED_PATH.exists()
        )
        set_session_state(StageKey.STAGE_6, is_completed)

    def run(self) -> None:
        warning = self._validate_requirements()

        st.title("⚖️ Penyeimbangan Kelas Menggunakan SMOTE")
        st.write(
            "Menyeimbangkan jumlah data antar kelas sentimen pada **data latih (train)** "
            "menggunakan **Synthetic Minority Over-sampling Technique (SMOTE)**."
        )

        st.info("""
            **Tahap 6 - Penyeimbangan Kelas (SMOTE)**

            SMOTE menghasilkan data sintetis untuk kelas minoritas dengan
            menginterpolasi antar data yang berdekatan, sehingga jumlah data
            tiap kelas menjadi seimbang dan model tidak bias ke kelas mayoritas.

            ⚠️ SMOTE **hanya** diterapkan pada data **train**. Data **test**
            tetap asli (tidak disentuh) supaya evaluasi model tetap objektif
            dan tidak bocor (*data leakage*).
            """)

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk SMOTE\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if warning:
            st.error(
                "🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Smoote."
            )
            st.stop()

        if X_TRAIN_RESAMPLED_PATH.exists() and Y_TRAIN_RESAMPLED_PATH.exists():
            self._render_existing_resampled()
        else:
            self._render_resampling()

    # ==========================================================
    # UI
    # ==========================================================

    def _render_existing_resampled(self) -> None:
        X_resampled = sparse.load_npz(X_TRAIN_RESAMPLED_PATH)
        y_resampled = joblib.load(Y_TRAIN_RESAMPLED_PATH)
        y_original = joblib.load(Y_TRAIN_PATH)

        st.success("✅ Data train sudah diseimbangkan dengan SMOTE.")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Data Train Sebelum", len(y_original))

        with col2:
            st.metric("Data Train Sesudah", len(y_resampled))

        with col3:
            st.metric("Data Sintetis Ditambahkan", len(y_resampled) - len(y_original))

        with col4:
            mtime = datetime.fromtimestamp(X_TRAIN_RESAMPLED_PATH.stat().st_mtime)
            st.metric("Terakhir Diproses", mtime.strftime("%d %b %Y"))

        st.markdown("---")

        st.subheader("📊 Distribusi Label")

        dist_col1, dist_col2 = st.columns(2)

        with dist_col1:
            st.write("**Sebelum SMOTE**")
            st.dataframe(
                pd.Series(y_original).value_counts().rename("Jumlah"),
                width="stretch",
            )

        with dist_col2:
            st.write("**Sesudah SMOTE**")
            st.dataframe(
                pd.Series(y_resampled).value_counts().rename("Jumlah"),
                width="stretch",
            )

        st.markdown("---")

        with st.expander("🔄 Proses Ulang SMOTE"):
            st.warning(
                "Hasil resampling yang ada akan ditimpa apabila proses dijalankan kembali."
            )
            self._render_resampling(force=True)

    def _render_resampling(self, force: bool = False) -> None:
        if X_TRAIN_PATH.exists() and Y_TRAIN_PATH.exists():
            y_train = joblib.load(Y_TRAIN_PATH)
            st.info(f"Data train siap diproses ({len(y_train):,} data).")

            st.write("**Distribusi Label Saat Ini**")
            st.dataframe(
                pd.Series(y_train).value_counts().rename("Jumlah"),
                width="stretch",
            )

        k_neighbors = st.slider(
            "k_neighbors",
            min_value=1,
            max_value=10,
            value=5,
            key=f"k_neighbors_{force}",
            help=(
                "Jumlah tetangga terdekat yang dipakai SMOTE untuk membuat data sintetis. "
                "Nilai default (5) adalah nilai standar yang umum dipakai di penelitian."
            ),
        )

        st.markdown("---")

        if st.button(
            "🚀 Mulai Penyeimbangan SMOTE" if not force else "🔄 Proses Ulang SMOTE",
            type="primary",
            width="stretch",
            disabled=bool(self._validate_requirements()),
            key=f"smote_button_{force}",
        ):
            progress = st.progress(0.0)
            status = st.empty()

            X_resampled, y_resampled = self._process_smote(
                k_neighbors,
                progress,
                status,
            )

            SMOTE_DIR.mkdir(parents=True, exist_ok=True)

            sparse.save_npz(X_TRAIN_RESAMPLED_PATH, X_resampled)
            joblib.dump(y_resampled, Y_TRAIN_RESAMPLED_PATH)

            progress.progress(1.0)
            status.success("✅ Penyeimbangan SMOTE selesai.")

            st.success(f"""
Jumlah Data Sebelum : {X_resampled.shape[0] - (X_resampled.shape[0] - len(y_resampled)):,}

Jumlah Data Sesudah  : {len(y_resampled):,}
""")

            st.rerun()

    # ==========================================================
    # PROCESS
    # ==========================================================

    def _process_smote(
        self,
        k_neighbors: int,
        progress,
        status,
    ):
        status.info("Memuat data train...")
        progress.progress(0.2)

        X_train = sparse.load_npz(X_TRAIN_PATH)
        y_train = joblib.load(Y_TRAIN_PATH)

        status.info("Menjalankan SMOTE...")
        progress.progress(0.5)

        smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
        X_resampled, y_resampled = smote.fit_resample(X_train, y_train)  # type: ignore

        status.info("Menyimpan hasil resampling...")
        progress.progress(0.9)

        return X_resampled, y_resampled

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_requirements(self) -> list[str] | None:
        warnings: list[str] = []

        if not X_TRAIN_PATH.exists() or not Y_TRAIN_PATH.exists():
            warnings.append("🔀 Hasil Train-Test Split belum tersedia.")

        if not get_session_state(StageKey.STAGE_5):
            warnings.append("🔀 Tahap Train-Test Split belum selesai.")

        if warnings:
            return warnings

        return None
