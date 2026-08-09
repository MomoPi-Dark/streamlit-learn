import streamlit as st
import pandas as pd
import re
import html
import threading
import time
from collections import deque
from datetime import datetime
from functools import lru_cache

from lib.paths import (
    ULASAN_LABELED_CSV_PATH,
    ULASAN_RAW_CSV_PATH,
    SLANG_CSV_PATH,
    CSV_DIR,
    PREPROCESSED_CSV_PATH,
)
from lib.enum import (
    StateKey,
    StageCollect,
    StageKey,
    get_session_state,
    set_session_state,
)
from structures.base import BasePage, Options
from stopwords import index

from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
from Sastrawi.Dictionary.ArrayDictionary import ArrayDictionary
from Sastrawi.StopWordRemover.StopWordRemover import StopWordRemover

from lib.bgManager import background_manager
from lib.running_badge import render_status_badges

RE_URL = re.compile(r"http\S+|www\S+")
RE_MENTION_HASHTAG = re.compile(r"@\w+|#\w+")
RE_EMOJI = re.compile(
    r"[\U0001F600-\U0001F64F"
    r"\U0001F300-\U0001F5FF"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF"
    r"\U00002700-\U000027BF"
    r"\U0001F900-\U0001F9FF"
    r"\U00002600-\U000026FF"
    r"\U0001FA70-\U0001FAFF"
    r"\U00002500-\U00002BEF"
    r"]+"
)
RE_NON_WORD = re.compile(r"[^\w\s]")
RE_MULTISPACE = re.compile(r"\s+")
RE_DIGIT = re.compile(r"\d+")
RE_REPEAT_CHAR = re.compile(r"(.)\1{2,}")

REQUIRED_COLUMNS = [
    "username",
    "score",
    "content",
    "sentimen_label",
]

required_columns = set(REQUIRED_COLUMNS)

# ===== Objek berat di-init sekali di module level =====
_stopword_factory = StopWordRemoverFactory()
_stopwords = sorted(
    set(_stopword_factory.get_stop_words())
    # | set(index.load_stopwords())
    | set({"nya", "di", "bugil"})
)
_dictionary = ArrayDictionary(_stopwords)
_stopword_remover = StopWordRemover(_dictionary)
_stemmer = StemmerFactory().create_stemmer()


@lru_cache(maxsize=200_000)
def _stem_word_cached(word: str) -> str:
    return _stemmer.stem(word)


slang_dict = {
    "indo": "indonesia",
    "cn": "china",
    "gak": "tidak",
    "ga": "tidak",
    "gk": "tidak",
    "tdk": "tidak",
    "nggak": "tidak",
    "ngga": "tidak",
    "kagak": "tidak",
    "gabisa": "tidak bisa",
    "gaada": "tidak ada",
    "gajelas": "tidak jelas",
    "gamau": "tidak mau",
    "ckp": "cukup",
    "bgt": "banget",
    "yg": "yang",
    "utk": "untuk",
    "tlg": "tolong",
    "dr": "dari",
    "jd": "jadi",
    "jgn": "jangan",
    "udh": "sudah",
    "udah": "sudah",
    "blm": "belum",
    "sm": "sama",
    "sy": "saya",
    "aja": "saja",
    "dgn": "dengan",
    "tp": "tapi",
    "gmn": "bagaimana",
    "gimana": "bagaimana",
    "pgn": "pengen",
    "pengen": "ingin",
    "mksd": "maksud",
    "mksdnya": "maksudnya",
    "jg": "juga",
    "krn": "karena",
    "knp": "kenapa",
    "klo": "kalau",
    "kalo": "kalau",
    "gtu": "begitu",
    "gitu": "begitu",
    "skrg": "sekarang",
    "skrng": "sekarang",
    "trs": "terus",
    "dpt": "dapat",
    "liat": "lihat",
    "pake": "pakai",
    "bikin": "membuat",
    "nih": "ini",
    "bnyk": "banyak",
    "org": "orang",
    "bs": "bisa",
    "bsk": "besok",
    "emg": "memang",
    "emang": "memang",
    "pny": "punya",
    "gpp": "tidak apa-apa",
    "gapapa": "tidak apa-apa",
    "bgs": "bagus",
    "mantul": "mantap betul",
    "parah": "sangat",
    "ribet": "rumit",
    "gw": "saya",
    "gue": "saya",
    "lu": "kamu",
    "lo": "kamu",
    "sbnrnya": "sebenarnya",
    "sbnernya": "sebenarnya",
    "bbrp": "beberapa",
    "stlh": "setelah",
    "sblm": "sebelum",
    "msh": "masih",
    "trnyt": "ternyata",
    "wkt": "waktu",
    "ngelag": "lag",
    "lagging": "lag",
    "ngebug": "bug",
    "ngehang": "macet",
    "fc": "force close",
    "maintenance": "pemeliharaan",
    "dc": "disconnect",
    "connect": "tersambung",
    "lemot": "lambat",
    "berat": "lambat",
    "crash": "berhenti mendadak",
    "restart": "mulai ulang",
    "gacha": "gacha",
    "p2w": "pay to win",
    "f2p": "free to play",
    "op": "overpowered",
    "nerf": "pelemahan",
    "buff": "penguatan",
    "event": "acara",
    "update": "pembaruan",
    "maintenence": "pemeliharaan",
    "sultan": "pemain berdompet tebal",
    "noob": "pemain baru",
    "cheat": "kecurangan",
    "glitch": "bug",
    "respawn": "muncul ulang",
}


# ===== Bobot relatif tiap step (estimasi beban komputasi) =====
STEP_WEIGHTS = {
    "Case Folding": 1,
    "Cleaning": 1,
    "Normalisasi": 2,
    "Stopword Removal": 2,
    "Stemming": 15,
    "Tokenizing": 1,
}

STEP_ICONS = {
    "Case Folding": "🔤",
    "Cleaning": "🧹",
    "Normalisasi": "📚",
    "Stopword Removal": "🚫",
    "Stemming": "🌱",
    "Tokenizing": "🔠",
}

PREPROCESSING_STEPS_META = [
    ("Case Folding", "ulasan", "ulasan_case_folding"),
    ("Cleaning", "ulasan_case_folding", "ulasan_cleaning"),
    ("Normalisasi", "ulasan_cleaning", "ulasan_normalisasi"),
    ("Stopword Removal", "ulasan_normalisasi", "ulasan_stopword"),
    ("Stemming", "ulasan_stopword", "clean_ulasan"),
    ("Tokenizing", "clean_ulasan", "tokenizing"),
]

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# jumlah baris contoh yang dilacak untuk tabel "pipeline lengkap"
PIPELINE_SAMPLE_SIZE = 3
# jumlah baris terakhir yang ditampilkan di tabel "sedang diproses" (live)
LIVE_SAMPLE_SIZE = 5

_MAX_DISPLAY_CHARS = 70


def _format_sample_value(value) -> str:
    """Ubah nilai (termasuk list hasil tokenizing) jadi teks singkat untuk tabel."""
    if isinstance(value, list):
        text = ", ".join(str(v) for v in value)
    elif value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        text = ""
    else:
        text = str(value)

    text = text.strip()
    if len(text) > _MAX_DISPLAY_CHARS:
        text = text[: _MAX_DISPLAY_CHARS - 1] + "…"
    return text if text else "(kosong)"


def _esc(value) -> str:
    """Escape teks sebelum disisipkan ke HTML supaya aman & tidak merusak layout."""
    return html.escape(str(value), quote=True)


# ===== CSS kustom (di-inject sekali per full page render) =====
_CUSTOM_CSS = """
<style>
.pp-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.pp-banner {
    display: flex; align-items: center; gap: 10px;
    border-radius: 12px; border: 1px solid transparent;
    padding: 12px 16px; font-weight: 600; font-size: 0.95em;
    margin-bottom: 18px;
}
.pp-banner.info {
    background: linear-gradient(90deg, rgba(99,102,241,0.16), rgba(56,189,248,0.08));
    border-color: rgba(99,102,241,0.35); color: #c7d2fe;
}
.pp-banner.success {
    background: linear-gradient(90deg, rgba(74,222,128,0.18), rgba(34,197,94,0.08));
    border-color: rgba(74,222,128,0.4); color: #bbf7d0;
}
.pp-banner.warning {
    background: linear-gradient(90deg, rgba(251,191,36,0.18), rgba(245,158,11,0.08));
    border-color: rgba(251,191,36,0.4); color: #fde68a;
}
.pp-banner-icon { font-size: 1.15em; line-height: 1; }
.pp-banner-icon.spin { display: inline-block; animation: pp-spin 1.6s linear infinite; }

@keyframes pp-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.pp-stepper {
    display: flex; align-items: flex-start; justify-content: space-between;
    margin: 4px 0 22px 0; position: relative;
}
.pp-step {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    position: relative; z-index: 1; padding: 0 4px;
}
.pp-step:not(:first-child)::before {
    content: ""; position: absolute; top: 23px; left: -50%; width: 100%; height: 3px;
    background: rgba(255,255,255,0.08); z-index: -1; border-radius: 2px;
}
.pp-step.done:not(:first-child)::before {
    background: linear-gradient(90deg, #22c55e, #38bdf8);
}
.pp-step-badge {
    width: 46px; height: 46px; border-radius: 50%; position: relative;
    display: flex; align-items: center; justify-content: center; font-size: 20px;
    background: rgba(255,255,255,0.06); border: 2px solid rgba(255,255,255,0.14);
    transition: all .35s ease;
}
.pp-step.done .pp-step-badge {
    background: rgba(74,222,128,0.16); border-color: #22c55e;
}
.pp-step.active .pp-step-badge {
    background: rgba(56,189,248,0.2); border-color: #38bdf8;
    animation: pp-pulse 1.5s ease-in-out infinite;
}
@keyframes pp-pulse {
    0%, 100% { box-shadow: 0 0 0 4px rgba(56,189,248,0.10); }
    50% { box-shadow: 0 0 0 11px rgba(56,189,248,0.16); }
}
.pp-step.pending .pp-step-badge { opacity: 0.4; }
.pp-step-check {
    position: absolute; top: -3px; right: -3px; width: 17px; height: 17px;
    background: #22c55e; color: #0e1117; border-radius: 50%; font-size: 10px;
    font-weight: 900; display: flex; align-items: center; justify-content: center;
}
.pp-step-label { margin-top: 8px; font-size: 0.76em; text-align: center; color: #cbd5e1; }
.pp-step.active .pp-step-label { color: #38bdf8; font-weight: 700; }
.pp-step.done .pp-step-label { color: #4ade80; }
.pp-step.pending .pp-step-label { opacity: 0.45; }

.pp-progress-outer {
    background: rgba(255,255,255,0.08); border-radius: 999px; height: 14px;
    overflow: hidden; position: relative;
}
.pp-progress-inner {
    height: 100%; border-radius: 999px;
    background: linear-gradient(90deg, #6366f1, #38bdf8, #6366f1);
    background-size: 200% 100%;
    animation: pp-shimmer 2.2s linear infinite;
    transition: width .4s ease;
}
@keyframes pp-shimmer { 0% { background-position: 0 0; } 100% { background-position: 200% 0; } }
.pp-progress-label {
    display: flex; justify-content: space-between; font-size: 0.8em;
    color: #94a3b8; margin-top: 6px;
}

.pp-section-title {
    font-size: 0.95em; font-weight: 700; color: #e2e8f0;
    display: flex; align-items: center; gap: 6px; margin-bottom: 2px;
}
.pp-section-caption { font-size: 0.78em; color: #94a3b8; margin-bottom: 12px; }

.pp-table { width: 100%; border-collapse: collapse; font-size: 0.83em; }
.pp-table th {
    text-align: left; padding: 8px 10px; background: rgba(255,255,255,0.045);
    color: #94a3b8; font-weight: 600; border-bottom: 1px solid rgba(255,255,255,0.08);
}
.pp-table td {
    padding: 9px 10px; border-bottom: 1px solid rgba(255,255,255,0.05);
    color: #e2e8f0; vertical-align: top;
}
.pp-table tr:last-child td { border-bottom: none; }
.pp-table tr:hover td { background: rgba(255,255,255,0.03); }
.pp-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.94em; }
.pp-arrow-cell { text-align: center; color: #38bdf8; width: 28px; }
.pp-pending-cell { color: #475569; font-style: italic; }
</style>
"""


def _inject_custom_css() -> None:
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def _banner_html(icon: str, text: str, kind: str = "info", spin: bool = False) -> str:
    spin_cls = " spin" if spin else ""
    return (
        f"<div class='pp-banner {kind}'>"
        f"<span class='pp-banner-icon{spin_cls}'>{icon}</span>"
        f"<span>{_esc(text)}</span>"
        "</div>"
    )


def _render_stepper_html(step_index: int) -> str:
    parts = ["<div class='pp-stepper'>"]
    for i, (label, _, _) in enumerate(PREPROCESSING_STEPS_META, start=1):
        icon = STEP_ICONS[label]
        if i < step_index:
            state, check = "done", "<span class='pp-step-check'>✓</span>"
        elif i == step_index:
            state, check = "active", ""
        else:
            state, check = "pending", ""
        parts.append(
            f"<div class='pp-step {state}'>"
            f"<div class='pp-step-badge'>{icon}{check}</div>"
            f"<div class='pp-step-label'>{_esc(label)}</div>"
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _render_progress_bar_html(percent: float, label_text: str) -> str:
    pct = max(0.0, min(100.0, percent))
    return (
        f"<div class='pp-progress-outer'><div class='pp-progress-inner' "
        f"style='width:{pct:.1f}%;'></div></div>"
        f"<div class='pp-progress-label'><span>{_esc(label_text)}</span>"
        f"<span>{pct:.1f}%</span></div>"
    )


def _render_pipeline_table_html(rows: list[dict]) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    thead = "".join(f"<th>{_esc(c)}</th>" for c in columns)
    body = []
    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col, "—")
            cls = "pp-pending-cell" if val == "—" else "pp-mono"
            cells.append(f"<td class='{cls}'>{_esc(val)}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")
    return (
        f"<table class='pp-table'><thead><tr>{thead}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _render_live_table_html(rows: list[dict], current_step: str) -> str:
    if not rows:
        return ""
    body = []
    for row in rows:
        before = _esc(row.get("before", ""))
        after = _esc(row.get("after", ""))
        body.append(
            f"<tr><td class='pp-mono'>{before}</td>"
            f"<td class='pp-arrow-cell'>→</td>"
            f"<td class='pp-mono'>{after}</td></tr>"
        )
    return (
        "<table class='pp-table'><thead><tr>"
        f"<th>Sebelum</th><th></th><th>Sesudah — {_esc(current_step)}</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


@Options(
    page_name="preprocessing",
    menu_name="Preprocessing Data",
    menu_icon="🏷️",
    category="preprocessing",
)
class AppPage(BasePage):
    _session_id = "preproccessing"

    def on_start(self) -> None:
        set_session_state(StageKey.STAGE_3, False)

        if self._validate_requirements():
            return

        if not PREPROCESSED_CSV_PATH.exists():
            return

        set_session_state(StageKey.STAGE_3, True)

    def run(self) -> None:
        render_status_badges()
        _inject_custom_css()

        warning = self._validate_requirements()

        st.title("🧹 Preprocessing Data")
        st.write(
            "Melakukan pembersihan dan normalisasi teks ulasan sebelum proses pembobotan TF-IDF."
        )
        st.info("""
            **Tahap 3 - Preprocessing Data**

            Tahap ini bertujuan membersihkan dan menyiapkan data teks sebelum
            dilakukan ekstraksi fitur menggunakan TF-IDF.

            Proses yang dilakukan meliputi:

            - 🔤 Case Folding
            - 🧹 Cleaning
            - 📚 Normalisasi Kata Slang
            - 🚫 Stopword Removal
            - 🌱 Stemming
            - 🔠 Tokenizing

            Dataset hasil preprocessing akan digunakan pada tahap berikutnya.
            """)

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk Preprocessing\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if warning:
            st.error(
                "🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Preprocessing."
            )
            st.stop()

        if PREPROCESSED_CSV_PATH.exists() and not background_manager.is_running(
            self._session_id
        ):
            self._render_existing_dataset()
        else:
            self._render_preprocessing()

    def _render_existing_dataset(self) -> None:
        df = pd.read_csv(PREPROCESSED_CSV_PATH)

        st.markdown(
            _banner_html("✅", "Dataset preprocessing sudah tersedia.", "success"),
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Data", len(df))

        with col2:
            st.metric("Jumlah Fitur", len(df.columns))

        with col3:
            st.metric("File", PREPROCESSED_CSV_PATH.name)

        with col4:
            mtime = datetime.fromtimestamp(PREPROCESSED_CSV_PATH.stat().st_mtime)
            st.metric("Terakhir Diproses", mtime.strftime("%d %b %Y"))

        st.dataframe(df.head(10), width="stretch")

        st.download_button(
            label="⬇️ Download CSV",
            data=PREPROCESSED_CSV_PATH.read_bytes(),
            file_name=PREPROCESSED_CSV_PATH.name,
            mime="text/csv",
            width="stretch",
            key="download_btn_existing",
        )

        st.markdown("---")

        with st.expander("🔄 Preprocessing Ulang"):
            st.warning(
                "Dataset hasil preprocessing akan ditimpa jika proses dijalankan kembali."
            )
            self._render_preprocessing(force=True)

    def _render_preprocessing(self, force: bool = False) -> None:
        session_uid = self._session_id
        running = background_manager.is_running(session_uid)

        # Kalau proses lagi berjalan, langsung tampilkan animasi progress
        # -> tidak perlu baca ulang CSV sumber setiap 0.5 detik
        if running:
            self._render_progress_animation()
            return

        if not ULASAN_LABELED_CSV_PATH.exists():
            st.error(
                "❌ Dataset hasil labeling belum tersedia atau sedang diproses ulang. "
                "Coba muat ulang halaman ini sesaat lagi."
            )
            return

        try:
            df_source = pd.read_csv(ULASAN_LABELED_CSV_PATH)
        except FileNotFoundError:
            st.error(
                "❌ File dataset labeling hilang saat dibaca "
                "(kemungkinan sedang ditulis ulang oleh proses lain). "
                "Coba muat ulang halaman ini."
            )
            return

        st.markdown(
            _banner_html(
                "📦", f"Dataset siap diproses ({len(df_source):,} data).", "info"
            ),
            unsafe_allow_html=True,
        )

        if st.button(
            "🚀 Mulai Preprocessing" if not force else "🔄 Preprocessing Ulang",
            type="primary",
            width="stretch",
        ):
            background_manager.start(
                session_uid,
                self._run_preprocessing_background,
                df_source.copy(),
            )
            st.toast("🚀 Preprocessing dimulai di background...", icon="🚀")
            st.rerun()

    @st.fragment(run_every=0.5)
    def _render_progress_animation(self) -> None:
        session_uid = self._session_id
        running = background_manager.is_running(session_uid)
        progress = background_manager.get_progress(session_uid)
        status = progress.get("status")

        # Proses sudah tidak jalan lagi -> tentukan hasil akhirnya
        if not running:
            if status == "done":
                st.markdown(
                    _banner_html(
                        "✅", "Preprocessing selesai! Memuat hasil...", "success"
                    ),
                    unsafe_allow_html=True,
                )
                time.sleep(0.6)
                st.rerun(scope="app")
            elif status == "stopped":
                st.markdown(
                    _banner_html(
                        "⏹️", "Preprocessing dihentikan oleh pengguna.", "warning"
                    ),
                    unsafe_allow_html=True,
                )
                if st.button(
                    "🔄 Muat Ulang Halaman", key="reload_after_stop", width="stretch"
                ):
                    st.rerun(scope="app")
            else:
                # status "starting" yang belum sempat ke-update, coba lagi sebentar
                st.rerun(scope="app")
            return

        step_index = progress.get("step_index", 1)
        total_steps = progress.get("total_steps", len(PREPROCESSING_STEPS_META))
        current_step = progress.get("current_step", PREPROCESSING_STEPS_META[0][0])
        row_index = progress.get("row_index", 0)
        total_rows = progress.get("total_rows", 0)
        percent = float(progress.get("percent", 0.0))
        spinner = SPINNER_FRAMES[int(time.time() * 4) % len(SPINNER_FRAMES)]

        # ===== Kartu utama: banner + stepper + progress bar =====
        main_card = ["<div class='pp-card'>"]
        main_card.append(
            _banner_html(
                "⚙️",
                "Preprocessing sedang berjalan di background...",
                "info",
                spin=True,
            )
        )
        main_card.append(_render_stepper_html(step_index))
        main_card.append(
            _render_progress_bar_html(
                percent,
                f"{spinner} {current_step} — langkah {step_index}/{total_steps} "
                f"· {row_index:,}/{total_rows:,} data",
            )
        )
        main_card.append("</div>")
        st.markdown("".join(main_card), unsafe_allow_html=True)

        # ===== Kartu tabel 1: pipeline lengkap untuk beberapa baris contoh =====
        pipeline_sample = progress.get("pipeline_sample")
        if pipeline_sample:
            st.markdown(
                "<div class='pp-card'>"
                "<div class='pp-section-title'>📋 Contoh Transformasi Data (Pipeline Lengkap)</div>"
                f"<div class='pp-section-caption'>{PIPELINE_SAMPLE_SIZE} baris contoh yang sama, "
                "dipantau dari awal sampai akhir tahap.</div>"
                f"{_render_pipeline_table_html(pipeline_sample)}"
                "</div>",
                unsafe_allow_html=True,
            )

        # ===== Kartu tabel 2: baris yang baru saja diproses (live) =====
        sample_rows = progress.get("sample_rows")
        if sample_rows:
            st.markdown(
                "<div class='pp-card'>"
                f"<div class='pp-section-title'>🔄 Baru Diproses — {_esc(current_step)}</div>"
                "<div class='pp-section-caption'>5 baris terakhir yang baru saja melewati langkah ini.</div>"
                f"{_render_live_table_html(sample_rows, current_step)}"
                "</div>",
                unsafe_allow_html=True,
            )

        if st.button("⏹️ Stop Proses", key="stop_btn_running", width="stretch"):
            background_manager.stop(session_uid)
            st.rerun(scope="app")

    def _run_preprocessing_background(
        self,
        df: pd.DataFrame,
        stop_event: threading.Event,
    ) -> None:
        df = df.copy()
        df["ulasan"] = df["content"]

        func_map = {
            "Case Folding": self._case_folding,
            "Cleaning": self._cleaning,
            "Normalisasi": self._normalisasi,
            "Stopword Removal": self._remove_stopword,
            "Stemming": self._stemming,
            "Tokenizing": self._tokenize,
        }

        total_rows = len(df)
        total_steps = len(PREPROCESSING_STEPS_META)
        total_weight = sum(
            STEP_WEIGHTS[label] for label, _, _ in PREPROCESSING_STEPS_META
        ) * max(total_rows, 1)
        completed_weight = 0

        # update progress setiap ~1% data supaya animasi mulus tanpa
        # membebani lock dengan update di setiap baris
        update_every = max(1, total_rows // 100)

        # ===== Baris contoh untuk tabel "pipeline lengkap" =====
        # dipilih sekali di awal (posisi pertama) supaya konsisten dilacak
        # dari awal sampai akhir, terlepas dari baris mana yang di-drop nanti
        sample_idx_list = list(df.index[: min(PIPELINE_SAMPLE_SIZE, total_rows)])
        pipeline_records: dict = {
            idx: {"Ulasan Asli": _format_sample_value(df.at[idx, "ulasan"])}
            for idx in sample_idx_list
        }
        pipeline_columns = ["Ulasan Asli"] + [
            lbl for lbl, _, _ in PREPROCESSING_STEPS_META
        ]

        def _build_pipeline_sample() -> list[dict]:
            rows = []
            for idx in sample_idx_list:
                record = pipeline_records.get(idx, {})
                rows.append({col: record.get(col, "—") for col in pipeline_columns})
            return rows

        background_manager.set_progress(
            self._session_id,
            status="running",
            current_step=PREPROCESSING_STEPS_META[0][0],
            step_index=1,
            total_steps=total_steps,
            row_index=0,
            total_rows=total_rows,
            percent=0.0,
            pipeline_sample=_build_pipeline_sample(),
            sample_rows=[],
        )

        for step_i, (label, input_col, output_col) in enumerate(
            PREPROCESSING_STEPS_META, start=1
        ):
            func = func_map[label]
            if output_col not in df.columns:
                df[output_col] = pd.Series(dtype="object")

            step_weight = STEP_WEIGHTS[label]
            live_buffer: deque = deque(maxlen=LIVE_SAMPLE_SIZE)

            for row_i, idx in enumerate(df.index, start=1):
                if stop_event.is_set():
                    background_manager.set_progress(self._session_id, status="stopped")
                    return

                before_val = df.at[idx, input_col]
                after_val = func(before_val)
                df.at[idx, output_col] = after_val

                live_buffer.append(
                    {
                        "before": _format_sample_value(before_val),
                        "after": _format_sample_value(after_val),
                    }
                )

                if row_i % update_every == 0 or row_i == total_rows:
                    step_progress = row_i / max(total_rows, 1)
                    overall = (
                        (completed_weight + step_weight * step_progress)
                        / total_weight
                        * 100
                    )
                    background_manager.set_progress(
                        self._session_id,
                        status="running",
                        current_step=label,
                        step_index=step_i,
                        total_steps=total_steps,
                        row_index=row_i,
                        total_rows=total_rows,
                        percent=round(min(overall, 99.9), 1),
                        sample_rows=list(live_buffer),
                    )

            completed_weight += step_weight * total_rows

            if label == "Stemming":
                df.dropna(subset=[output_col], inplace=True)
                df = df[df[output_col].astype(str).str.strip() != ""].copy()
                # baris contoh yang ikut terbuang saat Stemming dihapus dari pelacakan
                sample_idx_list = [idx for idx in sample_idx_list if idx in df.index]

            # perbarui tabel pipeline lengkap dengan hasil langkah yang baru selesai
            for idx in sample_idx_list:
                pipeline_records[idx][label] = _format_sample_value(
                    df.at[idx, output_col]
                )

            background_manager.set_progress(
                self._session_id,
                pipeline_sample=_build_pipeline_sample(),
            )

        CSV_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(PREPROCESSED_CSV_PATH, index=False)

        background_manager.set_progress(
            self._session_id,
            status="done",
            current_step="Selesai",
            step_index=total_steps,
            total_steps=total_steps,
            row_index=total_rows,
            total_rows=total_rows,
            percent=100.0,
        )

    def _case_folding(self, text) -> str:
        if pd.isna(text):
            return ""
        return str(text).lower()

    def _cleaning(self, text: str) -> str:
        text = RE_URL.sub("", text)
        text = RE_MENTION_HASHTAG.sub("", text)
        text = RE_EMOJI.sub("", text)
        text = RE_DIGIT.sub("", text)
        text = RE_NON_WORD.sub("", text)
        text = RE_REPEAT_CHAR.sub(r"\1", text)
        text = RE_MULTISPACE.sub(" ", text).strip()
        return text

    @lru_cache(maxsize=1)
    def _load_slang_dictionary(self) -> dict[str, str]:
        try:
            df = pd.read_csv(SLANG_CSV_PATH)
            df.columns = df.columns.str.strip().str.lower()

            if {"slang", "formal"}.issubset(df.columns):
                slang_ext = dict(
                    zip(
                        df["slang"].astype(str).str.strip(),
                        df["formal"].astype(str).str.strip(),
                    )
                )
            else:
                df = pd.read_csv(SLANG_CSV_PATH, header=None)
                slang_ext = dict(
                    zip(
                        df[0].astype(str).str.strip(),
                        df[1].astype(str).str.strip(),
                    )
                )

            slang_ext.update(slang_dict)
            return slang_ext

        except Exception:
            return slang_dict

    def _normalisasi(self, text: str) -> str:
        slang_dict = self._load_slang_dictionary()
        return " ".join(slang_dict.get(w, w) for w in text.split())

    def _remove_stopword(self, text: str) -> str:
        return _stopword_remover.remove(text)

    def _stemming(self, text: str) -> str:
        return " ".join(_stem_word_cached(w) for w in text.split())

    def _tokenize(self, text: str) -> list[str]:
        return [t for t in text.split() if len(t) > 2]

    def _validate_requirements(self) -> list[str] | None:
        warnings: list[str] = []

        if not ULASAN_RAW_CSV_PATH.exists():
            warnings.append("📄 Dataset mentah belum tersedia.")

        if not SLANG_CSV_PATH.exists():
            warnings.append("📚 Kamus normalisasi kata slang belum tersedia.")

        if not ULASAN_LABELED_CSV_PATH.exists():
            warnings.append("🏷️ Tahap Pelabelan Data belum selesai.")

        if warnings:
            return warnings

        return None
