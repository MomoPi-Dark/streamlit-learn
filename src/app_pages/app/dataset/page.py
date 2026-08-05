import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime
from google_play_scraper import reviews, Sort
from lib.enum import StateKey, StageKey, StageCollect
from lib.paths import ULASAN_RAW_CSV_PATH, CSV_DIR
from lib.config import REQUIRED_COLUMNS, required_columns
from structures.base import BasePage, Options
from lib.enum import set_session_state, get_session_state
from lib.paths import SLANG_CSV_PATH

APP_ID = "com.hottagames.nte"

@Options(
    page_name="dataset",
    menu_name="Dataset",
    menu_icon="📥",
    category="dataset",
    requires_model=False
)
class AppPage(BasePage):
    def on_start(self) -> None:
        set_session_state(StageKey.STAGE_1, False)
        set_session_state(StageKey.STAGE_1_DATASET, False)
        
        if self._render_warning():
            return
        
        with open(ULASAN_RAW_CSV_PATH, encoding="utf-8") as f:
            st.session_state[StageCollect.DATASET_COUNT] = sum(1 for _ in f) - 1
            
        set_session_state(StageKey.STAGE_1_DATASET, True)
        set_session_state(StageKey.STAGE_1, True)
        
    def run(self) -> None:
        st.title("📥 Pengumpulan Dataset")
        st.write(f"Ambil ulasan dari Google Play Store untuk aplikasi `{APP_ID}`.")
        st.info(
            """
            **Tahap 1 - Pengumpulan Dataset**

            - Mengambil atau mengunggah dataset ulasan Google Play Store.
            - Memastikan format dataset sesuai dengan kebutuhan aplikasi.
            - Jika valid, status **Dataset** akan berubah menjadi **Selesai (✓)** dan tahap berikutnya dapat dijalankan.
            """
        )

        
        st.markdown("---")  
        

        if self._render_warning():
            self._render_existing_dataset()
        else:
            st.error("Belum ada dataset tersimpan.")
            st.markdown("---")
            
            self._render_upload_dataset(force=True)
            self._render_scrape_form(force=False)
            
    def _render_existing_dataset(self) -> None:
        df_existing = pd.read_csv(ULASAN_RAW_CSV_PATH)

        st.success("✅ Dataset sudah ada.")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Data", len(df_existing))

        with col2:
            st.metric("File", ULASAN_RAW_CSV_PATH.name)

        with col3:
            ctime = datetime.fromtimestamp(ULASAN_RAW_CSV_PATH.stat().st_ctime)
            st.metric("Terakhir Diambil", ctime.strftime("%d %b %Y"))

        st.dataframe(df_existing, width="stretch")

        st.download_button(
            label="⬇️ Download CSV",
            data=ULASAN_RAW_CSV_PATH.read_bytes(),
            file_name=ULASAN_RAW_CSV_PATH.name,
            mime="text/csv",
            width="stretch",
        )

        st.markdown("---")

        self._render_upload_dataset(force=True)
        self._render_scrape_form(force=True)
          
                    
    def _render_scrape_form(self, force: bool) -> None:
        with st.expander("🔄 Scraping Ulang (timpa data lama)"):
            if force:
                st.warning("Data lama akan tertimpa jika melakukan scraping ulang.")
            
            count = st.number_input(
                "Jumlah ulasan yang diambil",
                min_value=100,
                max_value=10000,
                value=4200,
                step=100,
                key=f"count_{force}",
            )

            max_retries = st.number_input(
                "Maksimal retry saat error",
                min_value=1,
                max_value=10,
                value=5,
                key=f"retries_{force}",
            )

            use_date_filter = st.checkbox(
                "Gunakan filter tanggal",
                value=False,
                key=f"use_date_filter_{force}",
            )

            start_date = None
            end_date = None

            if use_date_filter:
                with st.expander("📅 Rentang Tanggal", expanded=True):
                    col_start, col_end = st.columns(2)

                    with col_start:
                        start_date = st.date_input(
                            "Tanggal awal",
                            value=datetime.now().date() - pd.Timedelta(days=30),
                            key=f"start_date_{force}",
                        )

                    with col_end:
                        end_date = st.date_input(
                            "Tanggal akhir",
                            value=datetime.now().date(),
                            key=f"end_date_{force}",
                        )

                    if start_date > end_date:
                        st.error("Tanggal awal tidak boleh lebih besar dari tanggal akhir.")
                        return

            button_label = "🔄 Scraping Ulang" if force else "🚀 Mulai Scraping"

            if st.button(
                button_label,
                type="primary",
                width="stretch",
                key=f"scrape_btn_{force}",
            ):
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                def update_progress(current: int, target: int):
                    progress_bar.progress(min(current / target, 1.0))
                    status_text.text(f"Terkumpul: {current}/{target} ulasan...")

                with st.spinner("Mengambil ulasan dari Google Play Store..."):
                    df_raw = self._scrape_reviews(
                        APP_ID,
                        count=int(count),
                        max_retries=int(max_retries),
                        start_date=start_date,
                        end_date=end_date,
                        progress_callback=update_progress,
                    )

                if df_raw.empty:
                    st.error(
                        "Gagal mengambil data. "
                        "Coba lagi, periksa koneksi, atau perlebar rentang tanggal."
                    )
                    return

                CSV_DIR.mkdir(parents=True, exist_ok=True)
                df_raw.to_csv(ULASAN_RAW_CSV_PATH, index=False)

                st.success(f"✅ Berhasil mengumpulkan {len(df_raw)} ulasan.")

                st.dataframe(
                    df_raw[REQUIRED_COLUMNS],
                    width="stretch",
                )

                st.download_button(
                    label="⬇️ Download CSV",
                    data=ULASAN_RAW_CSV_PATH.read_bytes(),
                    file_name=ULASAN_RAW_CSV_PATH.name,
                    mime="text/csv",
                    width="stretch",
                    key=f"download_after_scrape_{force}",
                )

                st.rerun()
           
           
    def _render_upload_dataset(self, force: bool) -> None:
        with st.expander("📤 Upload Dataset"):
            if force:
                st.warning("Data lama akan tertimpa jika melakukan scraping ulang.")
            
            df = None
            
            uploaded_file = st.file_uploader(
                "Pilih file CSV",
                type=["csv"],
                help=f"Kolom wajib: {', '.join(REQUIRED_COLUMNS)}",
                key=f"upload_csv_{st.session_state[StateKey.UPLOAD_KEY]}",
            )


            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file)
                except Exception as e:
                    st.error(f"Gagal membaca file CSV.\n\n{e}")
                    return

                missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)

                if missing_columns:
                    st.error(
                        "❌ Format dataset tidak sesuai.\n\n"
                        f"Kolom yang wajib ada:\n"
                        f"{', '.join(REQUIRED_COLUMNS)}\n\n"
                        f"Kolom yang hilang:\n"
                        f"{', '.join(sorted(missing_columns))}"
                    )
                    return

                df = df[REQUIRED_COLUMNS]

                if df.empty:
                    st.error("Dataset tidak memiliki data.")
                    return

                try:
                    df["at"] = pd.to_datetime(df["at"])
                except Exception:
                    st.error("Kolom 'at' harus berupa tanggal yang valid.")
                    return

                st.success(f"✅ Dataset valid ({len(df)} data)")
                st.dataframe(df, width="stretch")

            with st.form("upload_dataset_form", clear_on_submit=True):
                submit = st.form_submit_button(
                    "💾 Gunakan Dataset Ini",
                    type="primary",
                    width="stretch",
                )

            if submit:
                if df is None:
                    st.error("Silakan pilih file CSV terlebih dahulu.")
                    return

                CSV_DIR.mkdir(parents=True, exist_ok=True)
                df.to_csv(ULASAN_RAW_CSV_PATH, index=False)

                st.success("✅ Dataset berhasil disimpan.")

                st.session_state[StateKey.UPLOAD_KEY] += 1
                st.rerun()
                    
    @staticmethod
    def _scrape_reviews(
        app_id: str,
        count: int,
        max_retries: int,
        start_date=None,
        end_date=None,
        progress_callback=None,
    ) -> pd.DataFrame:
        all_reviews = []
        continuation_token = None
        retries = 0

        start_dt = pd.Timestamp(start_date) if start_date else None
        end_dt = (
            pd.Timestamp(end_date) + pd.Timedelta(days=1)
            if end_date
            else None
        )

        while len(all_reviews) < count:
            try:
                res, continuation_token = reviews(
                    app_id,
                    lang="id",
                    country="id",
                    sort=Sort.NEWEST,
                    count=1000,
                    continuation_token=continuation_token, #type: ignore
                )
                retries = 0

            except Exception:
                retries += 1

                if retries >= max_retries:
                    break

                time.sleep(random.uniform(5, 10))
                continue

            if not res:
                break

            stop_early = False

            for r in res:
                review_dt = pd.Timestamp(r["at"])

                if end_dt is not None and review_dt >= end_dt:
                    continue

                if start_dt is not None and review_dt < start_dt:
                    stop_early = True
                    break

                all_reviews.append(
                    {
                        "review_id": r["reviewId"],
                        "username": r["userName"],
                        "score": r["score"],
                        "content": r["content"],
                        "at": r["at"],
                    }
                )

            if progress_callback:
                progress_callback(len(all_reviews), count)

            if stop_early or continuation_token is None:
                break

            time.sleep(random.uniform(1, 3))

        df = pd.DataFrame(all_reviews)

        if not df.empty:
            df = df.drop_duplicates(subset="review_id").reset_index(drop=True)
            df["at"] = pd.to_datetime(df["at"]).dt.floor("s")
            df = df.sort_values("at", ascending=False)

        return df.iloc[:count].reset_index(drop=True)
    
    def _render_warning(self) -> list[str] | None:
        warnings: list[str] = []

        if not ULASAN_RAW_CSV_PATH.exists():
            warnings.append("📄 Dataset belum tersedia.")
            return warnings

        try:
            df = pd.read_csv(ULASAN_RAW_CSV_PATH, nrows=5)
        except Exception:
            warnings.append("📄 Dataset tidak dapat dibaca. Silakan lakukan scraping ulang.")
            return warnings

        missing = required_columns - set(df.columns)

        if missing:
            warnings.append(
                "📄 Format dataset tidak sesuai.\n"
                f"Kolom yang hilang: {', '.join(sorted(missing))}"
            )

        if warnings:
            return warnings

        return None