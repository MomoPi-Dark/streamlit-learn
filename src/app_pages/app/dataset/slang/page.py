import streamlit as st
import pandas as pd
import urllib.request
from pathlib import Path
from structures.base import BasePage, Options
from lib.paths import CSV_DIR, SLANG_CSV_PATH
from lib.enum import StateKey, StageKey, get_session_state, set_session_state, StageCollect
from lib.paths import SLANG_CSV_PATH

URL_SLANG = "https://raw.githubusercontent.com/nasalsabila/kamus-alay/master/colloquial-indonesian-lexicon.csv"

REQUIRED_COLUMNS  = [
   "slang","formal","In-dictionary","context","category1","category2","category3"
]
        
required_columns = set(REQUIRED_COLUMNS)

@Options(
    page_name="slang",
    menu_name="Kamus Slang",
    menu_icon="📚",
    category="dataset",
    requires_model=False
)
class AppPage(BasePage):
    def on_start(self) -> None:
        set_session_state(StageKey.STAGE_1, False)
        set_session_state(StageKey.STAGE_1_SLANG, False)

        if not SLANG_CSV_PATH.exists():
            return

        try:
            df = pd.read_csv(SLANG_CSV_PATH, nrows=5)
        except Exception:
            st.error("Dataset tidak dapat dibaca. Silakan lakukan scraping ulang.")
            return

        missing = required_columns - set(df.columns)

        if missing:
            st.error(
                "Format dataset tidak sesuai.\n"
                f"Kolom yang wajib ada: {', '.join(REQUIRED_COLUMNS)}\n"
                f"Kolom yang hilang: {', '.join(sorted(missing))}"
            )
            return

        set_session_state(StageKey.STAGE_1_SLANG, True)

        if get_session_state(StageKey.STAGE_1_DATASET, False):
            set_session_state(StageKey.STAGE_1, True)
    
    def run(self) -> None:
        st.title("📚 Kamus Normalisasi Kata Slang")
        st.write(
            "Kamus ini digunakan pada tahap preprocessing untuk mengubah "
            "kata-kata non-baku (slang) menjadi bentuk bakunya."
        )
        st.info(
            f"""
            **Tahap Pendukung - Kamus Normalisasi Kata Slang**

            Kamus ini digunakan untuk mengubah kata-kata tidak baku (slang) menjadi
            bentuk baku sebelum proses analisis sentimen dilakukan.

            Contoh normalisasi:
            - `gk` → `tidak`
            - `bgt` → `banget`
            - `udh` → `sudah`
            - `gmn` → `bagaimana`
            - `ngelag` → `lag`

            Kamus dapat berasal dari:
            - 📄 Download Dataset kamus slang {URL_SLANG}.

            Seluruh data pada kamus akan digunakan pada tahap **Preprocessing** untuk
            meningkatkan kualitas teks sebelum proses ekstraksi fitur (TF-IDF).
            """
        )
        st.markdown("---")

        if SLANG_CSV_PATH.exists():
            self._render_existing_dictionary()
        else:
            self._render_download_section()

    def _render_existing_dictionary(self):
        try:
            df_slang = pd.read_csv(SLANG_CSV_PATH)
        except Exception as e:
            st.error(f"Gagal membaca file kamus: {e}")
            return

        st.success("✅ Kamus slang sudah ada.")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Entri", len(df_slang))
        with col2:
            st.metric("File", SLANG_CSV_PATH.name)

        st.dataframe(df_slang.head(50), width='stretch')

        st.download_button(
            label="⬇️ Download Kamus (CSV)",
            data=SLANG_CSV_PATH.read_bytes(),
            file_name=SLANG_CSV_PATH.name,
            mime="text/csv",
            width='stretch',
        )
        
        st.write("---")

        with st.expander("🔄 Unduh Ulang Kamus"):
            st.warning("File kamus yang ada akan ditimpa jika Anda mengunduh ulang.")
            if st.button("Unduh Ulang Kamus", width='stretch', type="primary"):
                self._download_dictionary()

    def _render_download_section(self):
        st.info("Kamus slang belum ada. Silakan unduh terlebih dahulu.")
        if st.button("🚀 Unduh Kamus Slang Sekarang", width='stretch', type="primary"):
            self._download_dictionary()

    def _download_dictionary(self):
        CSV_DIR.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(URL_SLANG, SLANG_CSV_PATH)
            st.success(f"Kamus slang berhasil diunduh ke: `{SLANG_CSV_PATH}`")
            st.rerun()
        except Exception as e:
            st.error(f"Gagal mengunduh kamus slang: {e}")
