import time
import streamlit as st
import pandas as pd

from lib.paths import (
    ULASAN_LABELED_CSV_PATH,
    ULASAN_RAW_CSV_PATH,
    SLANG_CSV_PATH,
    CSV_DIR,
)
from lib.enum import StateKey, StageKey, set_session_state
from lib.config import REQUIRED_COLUMNS, required_columns
from structures.base import BasePage, Options


@Options(
    page_id="labeling",
    menu_name="Labeling Data",
    menu_icon="🏷️",
    category="labeling",
)
class AppPage(BasePage):
    def on_start(self) -> None:
        set_session_state(StageKey.STAGE_2, False)

        if self._validate_requirements():
            return

        if not ULASAN_LABELED_CSV_PATH.exists():
            return

        set_session_state(StageKey.STAGE_2, True)

    def run(self) -> None:
        warning = self._validate_requirements()

        st.title("🏷️ Pelabelan Data")
        st.caption(
            "Halaman ini melakukan pelabelan sentimen secara otomatis berdasarkan rating ulasan Google Play Store. "
            "Rating 4–5 diberi label **Positif**, sedangkan rating 1–2 diberi label **Negatif**. "
            "Ulasan dengan rating 3 tidak digunakan dalam proses pelabelan."
        )
        st.info("""
            **Tahap 2 - Pelabelan Data**

            Melakukan pelabelan sentimen secara otomatis berdasarkan rating ulasan.

            - ⭐ Rating 1–2 → **Negatif**
            - ⭐ Rating 3 → Tidak digunakan (Netral)
            - ⭐ Rating 4–5 → **Positif**

            Dataset hasil pelabelan akan disimpan sebagai dataset baru dan digunakan pada tahap **Preprocessing**.
            """)

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk Labeling\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if self._validate_requirements():
            st.error(
                "🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Labeling."
            )
            st.stop()

        if ULASAN_LABELED_CSV_PATH.exists():
            self._render_existing_dataset()
        else:
            self._render_labeling()

    def _render_existing_dataset(self) -> None:
        is_processing = self.status_process_state()

        df = pd.read_csv(ULASAN_LABELED_CSV_PATH)

        st.success("✅ Dataset berlabel sudah tersedia.")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Data", len(df))

        with col2:
            st.metric(
                "Positif",
                (df["sentimen_label"] == "Positif").sum(),
            )

        with col3:
            st.metric(
                "Negatif",
                (df["sentimen_label"] == "Negatif").sum(),
            )
        with col4:
            st.metric("File", ULASAN_LABELED_CSV_PATH.name)

        st.dataframe(
            df[REQUIRED_COLUMNS + ["sentimen_label"]],
            width="stretch",
        )

        st.download_button(
            "⬇️ Download CSV",
            data=ULASAN_LABELED_CSV_PATH.read_bytes(),
            file_name=ULASAN_LABELED_CSV_PATH.name,
            mime="text/csv",
            width="stretch",
            disabled=self.status_process_state(),
        )

        st.markdown("---")

        with st.expander(label="🔄 Pelabelan Ulang", expanded=is_processing):
            self._render_labeling()

    def _render_labeling(self) -> None:
        warning = self._validate_requirements()
        is_processing = self.status_process_state()

        df_raw = pd.read_csv(ULASAN_RAW_CSV_PATH)

        if not self._validate_columns(
            df_raw,
            required_columns,
            REQUIRED_COLUMNS,
        ):
            return

        st.info(f"Jumlah data: **{len(df_raw)}**")

        st.dataframe(
            df_raw[REQUIRED_COLUMNS],
            width="stretch",
        )

        st.markdown("---")

        if st.button(
            "🏷️ Mulai Pelabelan",
            type="primary",
            width="stretch",
            disabled=bool(warning) or is_processing,
        ):
            self.start_process_state()
            st.rerun()

        if is_processing:
            with st.spinner("Melabeli dataset..."):
                df = self._label_dataset(df_raw)

                CSV_DIR.mkdir(parents=True, exist_ok=True)

                df.to_csv(
                    ULASAN_LABELED_CSV_PATH,
                    index=False,
                )

            self.stop_process_state()

            st.success("✅ Dataset berhasil dilabeli.")

            st.rerun()  # rerun #2 -> tombol balik enabled

    def _label_dataset(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        df = df_raw.copy()
        df = df[df["score"] != 3].copy()

        progress_bar = st.progress(0)
        status_text = st.empty()

        steps = [
            ("Memulai pelabelan...", 0.2),
            ("Mengklasifikasi sentimen...", 0.5),
            ("Memvalidasi hasil...", 0.8),
            ("Menyusun ringkasan...", 1.0),
        ]

        for msg, pct in steps:
            status_text.info(msg)
            progress_bar.progress(pct)
            time.sleep(0.3)

        def tentukan_sentimen(nilai_bintang):
            if nilai_bintang >= 4:
                return "Positif"
            elif nilai_bintang <= 2:
                return "Negatif"

        df["sentimen_label"] = df["score"].apply(tentukan_sentimen)

        status_text.success("Pelabelan selesai!")
        time.sleep(0.5)
        status_text.empty()
        progress_bar.empty()

        st.write("### Hasil Pelabelan Otomatis:")
        st.write(df["sentimen_label"].value_counts())
        st.write(f"\nTotal data sekarang (setelah rating 3 dihapus): {len(df)} data")

        sample_pos = df[df["sentimen_label"] == "Positif"].sample(
            n=min(5, (df["sentimen_label"] == "Positif").sum()), random_state=42
        )

        sample_neg = df[df["sentimen_label"] == "Negatif"].sample(
            n=min(5, (df["sentimen_label"] == "Negatif").sum()), random_state=42
        )

        sample_gabungan = pd.concat([sample_pos, sample_neg])[REQUIRED_COLUMNS]

        st.write("Contoh 5 Komentar Positif dan 5 Komentar Negatif:\n")
        st.dataframe(sample_gabungan, width="stretch")

        return df

    def _validate_columns(
        self,
        df: pd.DataFrame,
        required_columns: set[str],
        display_columns: list[str],
    ) -> bool:
        missing = required_columns - set(df.columns)

        if missing:
            st.error(
                "❌ Format dataset tidak sesuai.\n\n"
                f"Kolom yang wajib ada:\n"
                f"{', '.join(display_columns)}\n\n"
                f"Kolom yang hilang:\n"
                f"{', '.join(sorted(missing))}"
            )
            return False

        return True

    def _validate_requirements(self) -> list[str] | None:
        errors: list[str] = []

        # Dataset
        if not ULASAN_RAW_CSV_PATH.exists():
            errors.append(
                "📄 Dataset belum tersedia. Silakan lakukan scraping atau upload dataset."
            )
        else:
            try:
                df = pd.read_csv(ULASAN_RAW_CSV_PATH, nrows=5)
            except Exception:
                errors.append(
                    "📄 Dataset tidak dapat dibaca. Silakan lakukan scraping ulang."
                )
            else:
                missing = required_columns - set(df.columns)

                if missing:
                    errors.append(
                        "📄 Format dataset tidak sesuai.\n"
                        f"Kolom yang hilang: {', '.join(sorted(missing))}"
                    )

        # Kamus slang
        if not SLANG_CSV_PATH.exists():
            errors.append("📚 Kamus slang belum tersedia.")

        if errors:
            return errors

        return None
