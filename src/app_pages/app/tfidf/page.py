import streamlit as st
import pandas as pd
import joblib

from scipy import sparse
from scipy.sparse import csr_matrix
from typing import Any
from scipy import sparse
from datetime import datetime
from structures.base import BasePage, Options
from lib.enum import (
    StageKey,
    get_session_state,
    set_session_state,
)
from lib.paths import (
    PREPROCESSED_CSV_PATH,
    TFIDF_DIR,
    TFIDF_MATRIX_PATH,
    TFIDF_VECTORIZER_PATH,
    TFIDF_DIR,
)
from sklearn.feature_extraction.text import TfidfVectorizer

REQUIRED_COLUMNS = [
    "clean_ulasan",
    "tokenizing",
]
required_columns = set(REQUIRED_COLUMNS)


def identity_tokenizer(tokens: list[str]) -> list[str]:
    """Analyzer identitas untuk TfidfVectorizer — tokens sudah siap pakai,
    tidak perlu di-tokenize/lowercase ulang. Sengaja diletakkan di modul
    terpisah (bukan di file halaman Streamlit) supaya joblib bisa
    pickle/unpickle fungsi ini lewat path import yang stabil
    (`lib.text_utils.identity_tokenizer`), karena file halaman di-load
    Streamlit secara dinamis dan __module__-nya tidak reliable untuk pickling.
    """
    return tokens


@Options(
    page_id="tfidf",
    menu_name="TF-IDF",
    menu_icon="📊",
    category="tf-idf",
)
class AppPage(BasePage):
    def on_start(self) -> None:
        set_session_state(StageKey.STAGE_4, False)

        if self._validate_requirements():
            return

        if not PREPROCESSED_CSV_PATH.exists():
            return

        if self._validate_columns():
            return

        is_completed = TFIDF_VECTORIZER_PATH.exists() and TFIDF_MATRIX_PATH.exists()

        set_session_state(StageKey.STAGE_4, is_completed)

    def run(self) -> None:
        warning = self._validate_requirements()

        if warning is None:
            warning = self._validate_columns()

        st.title("📊 Pembobotan TF-IDF")
        st.write(
            "Mengubah hasil preprocessing menjadi representasi numerik menggunakan metode **Term Frequency-Inverse Document Frequency (TF-IDF)**."
        )

        st.info("""
            **Tahap 4 - Pembobotan TF-IDF**

            Tahap ini mengubah hasil preprocessing menjadi representasi numerik
            menggunakan metode **Term Frequency-Inverse Document Frequency (TF-IDF)**.

            Hasil proses ini akan digunakan sebagai fitur masukan pada tahap
            **Training Model**.
            """)

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk TF-IDF\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if warning:
            st.error(
                "🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke TF-IDF."
            )
            st.stop()

        if TFIDF_VECTORIZER_PATH.exists() and TFIDF_MATRIX_PATH.exists():
            self._render_existing_tfidf()
        else:
            self._render_tfidf()

    # ==========================================================
    # UI
    # ==========================================================

    def _render_existing_tfidf(self) -> None:
        vectorizer = joblib.load(TFIDF_VECTORIZER_PATH)
        matrix = sparse.load_npz(TFIDF_MATRIX_PATH)

        feature_names = vectorizer.get_feature_names_out()

        st.success("✅ Hasil pembobotan TF-IDF sudah tersedia.")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Jumlah Data",
                matrix.shape[0],
            )

        with col2:
            st.metric(
                "Jumlah Fitur",
                matrix.shape[1],
            )

        with col3:
            st.metric(
                "Vocabulary",
                len(feature_names),
            )

        with col4:
            mtime = datetime.fromtimestamp(TFIDF_MATRIX_PATH.stat().st_mtime)

            st.metric(
                "Terakhir Diproses",
                mtime.strftime("%d %b %Y"),
            )

        st.markdown("---")

        st.subheader("👀 Preview Matriks TF-IDF")

        preview = pd.DataFrame(
            matrix[:5, :10].toarray(),
            columns=feature_names[:10],
        )

        st.dataframe(
            preview,
            width="stretch",
        )

        st.download_button(
            label="⬇️ Download Matriks TF-IDF",
            data=TFIDF_MATRIX_PATH.read_bytes(),
            file_name=TFIDF_MATRIX_PATH.name,
            mime="application/octet-stream",
            width="stretch",
        )

        st.markdown("---")

        with st.expander("🔄 Hitung Ulang TF-IDF"):
            st.warning(
                "Hasil pembobotan TF-IDF yang ada akan ditimpa apabila proses dijalankan kembali."
            )

            self._render_tfidf(force=True)

    def _render_tfidf(self, force: bool = False) -> None:
        df = pd.read_csv(PREPROCESSED_CSV_PATH)

        st.info(f"Dataset siap diproses ({len(df):,} data).")

        with st.expander("👀 Preview Dataset", expanded=False):
            st.dataframe(
                df[REQUIRED_COLUMNS].head(10),
                width="stretch",
            )

        st.markdown("---")

        if st.button(
            "🚀 Mulai Pembobotan TF-IDF" if not force else "🔄 Hitung Ulang TF-IDF",
            type="primary",
            width="stretch",
            disabled=bool(self._validate_requirements())
            or bool(self._validate_columns()),
            key=f"tfidf_{force}",
        ):
            progress = st.progress(0.0)
            status = st.empty()

            status.info("Membaca dataset...")

            vectorizer, matrix = self._process_tfidf(
                df,
                progress,
                status,
            )

            TFIDF_DIR.mkdir(parents=True, exist_ok=True)

            joblib.dump(
                vectorizer,
                TFIDF_VECTORIZER_PATH,
            )

            sparse.save_npz(
                TFIDF_MATRIX_PATH,
                matrix,
            )

            progress.progress(1.0)

            status.success("✅ Pembobotan TF-IDF selesai.")

            st.success(f"""
    Jumlah Vocabulary : {len(vectorizer.get_feature_names_out()):,}

    Shape Matriks TF-IDF : {matrix.shape}
    """)

            preview = pd.DataFrame(
                matrix[:5, :10].toarray(),
                columns=vectorizer.get_feature_names_out()[:10],
            )

            st.dataframe(
                preview,
                width="stretch",
            )

            st.rerun()

        # ==========================================================

    # PROCESS
    # ==========================================================

    def _process_tfidf(
        self,
        df: pd.DataFrame,
        progress,
        status,
    ) -> tuple[TfidfVectorizer, Any]:
        status.info("Mempersiapkan data...")
        progress.progress(0.2)

        # Kolom "tokenizing" tersimpan sebagai string representasi list
        # (mis. "['kata1', 'kata2']"), jadi di-eval balik jadi list[str],
        # lalu digabung pakai spasi. Token hasil stemming/tokenizing
        # dijamin tidak mengandung spasi di dalamnya, jadi join+split ini
        # secara hasil SAMA PERSIS dengan analyzer=lambda x: x di notebook
        # — tapi tanpa custom function, sehingga vectorizer aman di-pickle
        # oleh joblib (custom function/lambda gagal di-pickle kalau
        # __module__-nya tidak stabil, seperti pada file halaman Streamlit
        # yang di-load secara dinamis).
        token = df["tokenizing"].apply(eval).apply(lambda t: " ".join(t))

        status.info("Membuat TF-IDF Vectorizer...")
        progress.progress(0.4)

        tfidf = TfidfVectorizer(
            lowercase=False,  # token sudah diproses/lowercased sebelumnya
            token_pattern=r"(?u)\S+",  # split per token berdasarkan spasi,
        )

        status.info("Menghitung bobot TF-IDF...")
        progress.progress(0.7)

        X_tfidf = tfidf.fit_transform(token)

        status.info("Menyimpan hasil...")
        progress.progress(0.9)

        return tfidf, X_tfidf

    def _save_vectorizer(
        self,
        vectorizer: TfidfVectorizer,
    ) -> None:
        TFIDF_DIR.mkdir(parents=True, exist_ok=True)

        joblib.dump(
            vectorizer,
            TFIDF_VECTORIZER_PATH,
        )

    def _save_matrix(
        self,
        matrix: csr_matrix,
    ) -> None:
        TFIDF_MATRIX_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        sparse.save_npz(
            TFIDF_MATRIX_PATH,
            matrix,
        )

    def _preview_matrix(
        self,
        matrix,
        vectorizer: TfidfVectorizer,
    ) -> None:
        feature_names = vectorizer.get_feature_names_out()

        preview = pd.DataFrame(
            matrix[:5, :10].toarray(),
            columns=feature_names[:10],
        )

        st.subheader("👀 Preview Matriks TF-IDF")

        st.dataframe(
            preview,
            width="stretch",
        )

    # ==========================================================
    # VALIDATION
    # ==========================================================
    def _validate_requirements(self) -> list[str] | None:
        warnings: list[str] = []

        if not PREPROCESSED_CSV_PATH.exists():
            warnings.append("🧹 Dataset hasil preprocessing belum tersedia.")

        if not get_session_state(StageKey.STAGE_3):
            warnings.append("🧹 Tahap Preprocessing belum selesai.")

        if warnings:
            return warnings

        return None

    def _validate_columns(self) -> list[str] | None:
        # Status file sudah dicek di _validate_requirements — di sini kita
        # tetap guard supaya pesan error yang muncul sesuai kondisi aslinya,
        # bukan tertangkap sebagai "tidak dapat dibaca".
        if not PREPROCESSED_CSV_PATH.exists():
            return ["🧹 Dataset hasil preprocessing belum tersedia."]

        try:
            df = pd.read_csv(PREPROCESSED_CSV_PATH, nrows=5)
        except pd.errors.EmptyDataError:
            return ["📄 Dataset preprocessing kosong."]
        except pd.errors.ParserError:
            return [
                "📄 Dataset preprocessing tidak dapat diurai (format CSV tidak valid)."
            ]
        except Exception:
            return ["📄 Dataset preprocessing tidak dapat dibaca."]

        missing = required_columns - set(df.columns)

        if missing:
            return [
                "📄 Format dataset preprocessing tidak sesuai.",
                f"Kolom yang hilang: {', '.join(sorted(missing))}",
            ]

        return None
