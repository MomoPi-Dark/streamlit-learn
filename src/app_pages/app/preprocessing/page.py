import streamlit as st
import pandas as pd
import re
import threading
import time
import uuid
from datetime import datetime
from functools import lru_cache

from streamlit.runtime.scriptrunner import add_script_run_ctx

from lib.paths import ULASAN_LABELED_CSV_PATH, ULASAN_RAW_CSV_PATH, SLANG_CSV_PATH, CSV_DIR, PREPROCESSED_CSV_PATH
from lib.enum import StateKey, StageCollect, StageKey, get_session_state, set_session_state
from structures.base import BasePage, Options

from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
from Sastrawi.Dictionary.ArrayDictionary import ArrayDictionary
from Sastrawi.StopWordRemover.StopWordRemover import StopWordRemover

RE_URL = re.compile(r'http\S+|www\S+')
RE_MENTION_HASHTAG = re.compile(r'@\w+|#\w+')
RE_EMOJI = re.compile(
    r'[\U0001F600-\U0001F64F'
    r'\U0001F300-\U0001F5FF'
    r'\U0001F680-\U0001F6FF'
    r'\U0001F1E0-\U0001F1FF'
    r'\U00002700-\U000027BF'
    r'\U0001F900-\U0001F9FF'
    r'\U00002600-\U000026FF'
    r'\U0001FA70-\U0001FAFF'
    r'\U00002500-\U00002BEF'
    r']+'
)
RE_NON_WORD = re.compile(r'[^\w\s]')
RE_MULTISPACE = re.compile(r'\s+')
RE_DIGIT = re.compile(r'\d+')
RE_REPEAT_CHAR = re.compile(r'(.)\1{2,}')

REQUIRED_COLUMNS = [
    "username",
    "score",
    "content",
    "sentimen_label",
]

required_columns = set(REQUIRED_COLUMNS)

# ===== Objek berat di-init sekali di module level =====
# Supaya cache stemming & instance stemmer/stopword-remover konsisten
# lintas rerun Streamlit maupun lintas thread (bukan re-create tiap kali
# AppPage di-instantiate ulang).
_stopword_factory = StopWordRemoverFactory()
_stopwords = _stopword_factory.get_stop_words()
_dictionary = ArrayDictionary(_stopwords)
_stopword_remover = StopWordRemover(_dictionary)
_stemmer = StemmerFactory().create_stemmer()


@lru_cache(maxsize=200_000)
def _stem_word_cached(word: str) -> str:
    """Stemming satu kata, di-cache di level module (bukan instance),
    supaya cache tetap kepakai lintas rerun & lintas thread."""
    return _stemmer.stem(word)


# ===== Progress store MANDIRI, terpisah dari st.session_state =====
# Background thread TIDAK BOLEH menulis progress lewat st.session_state,
# karena itu terikat ke ScriptRunContext yang bisa "ditandai stop" saat
# terjadi rerun (manual atau via st.fragment run_every) -- penulisan ke
# session_state dari thread lain saat itu terjadi akan melempar
# streamlit.runtime.scriptrunner_utils.exceptions.StopException yang
# TIDAK bisa ditangkap oleh `except Exception` biasa (dia turunan
# BaseException), sehingga background thread mati diam-diam.
#
# Solusi: progress disimpan di dictionary module-level biasa, dilindungi
# lock, sama sekali tidak bergantung pada context Streamlit.
_progress_lock = threading.Lock()

def _get_progress_store() -> dict:
    """
    Dictionary progress disimpan SEBAGAI OBJEK di dalam st.session_state
    (dibuat sekali, lalu dimutasi langsung -- bukan di-assign ulang lewat
    st.session_state[key] = ...). Ini menghindari dua masalah sekaligus:
    1. Tidak bergantung pada modul Python tetap sama objeknya lintas rerun
       (aman walau ada mekanisme reimport/reload halaman di router custom).
    2. Mutasi dict langsung (d[k]=v) TIDAK melewati SafeSessionState.__setitem__,
       jadi tetap aman dipanggil dari background thread tanpa risiko
       StopException.
    """
    store = st.session_state.get("_progress_store_obj")
    if store is None:
        store = {}
        st.session_state["_progress_store_obj"] = store
    return store


def _progress_set(store_key: str, value: dict) -> None:
    with _progress_lock:
        store = _get_progress_store()
        store[store_key] = value


def _progress_get(store_key: str) -> dict | None:
    with _progress_lock:
        store = _get_progress_store()
        return store.get(store_key)


def _progress_delete(store_key: str) -> None:
    with _progress_lock:
        store = _get_progress_store()
        store.pop(store_key, None)


# ===== Bobot relatif tiap step (estimasi beban komputasi) =====
STEP_WEIGHTS = {
    "Case Folding": 1,
    "Cleaning": 1,
    "Normalisasi": 2,
    "Stopword Removal": 2,
    "Stemming": 15,
    "Tokenizing": 1,
}

PREPROCESSING_STEPS_META = [
    ("Case Folding", "ulasan", "ulasan_case_folding"),
    ("Cleaning", "ulasan_case_folding", "ulasan_cleaning"),
    ("Normalisasi", "ulasan_cleaning", "ulasan_normalisasi"),
    ("Stopword Removal", "ulasan_normalisasi", "ulasan_stopword"),
    ("Stemming", "ulasan_stopword", "clean_ulasan"),
    ("Tokenizing", "clean_ulasan", "tokenizing"),
]


@Options(
    page_name="preprocessing",
    menu_name="Preprocessing Data",
    menu_icon="🏷️",
    category="preprocessing",
)
class AppPage(BasePage):
    def on_start(self) -> None:
        set_session_state(StageKey.STAGE_3, False)

        if self._validate_requirements():
            return
        
        if not PREPROCESSED_CSV_PATH.exists():
            return

        set_session_state(StageKey.STAGE_3, True)

    def run(self) -> None:
        warning = self._validate_requirements()

        st.title("🧹 Preprocessing Data")
        st.write(
            "Melakukan pembersihan dan normalisasi teks ulasan sebelum proses pembobotan TF-IDF."
        )
        st.info(
            """
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
            """
        )

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk Preprocessing\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if warning:
            st.error("🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Preprocessing.")
            st.stop()

        if PREPROCESSED_CSV_PATH.exists():
            self._render_existing_dataset()
        else:
            self._render_preprocessing()

    def _render_existing_dataset(self) -> None:
        df = pd.read_csv(PREPROCESSED_CSV_PATH)

        st.success("✅ Dataset preprocessing sudah tersedia.")

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

    def _get_session_uid(self) -> str:
        """UID unik per session browser, dipakai sebagai prefix key di
        _progress_store supaya antar-user/tab tidak saling tabrakan."""
        session_uid = get_session_state("_session_uid")
        if session_uid is None:
            session_uid = str(uuid.uuid4())
            set_session_state("_session_uid", session_uid)
        return session_uid

    def _render_preprocessing(self, force: bool = False) -> None:
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

        st.info(f"Dataset siap diproses ({len(df_source):,} data).")

        with st.expander("👀 Preview Dataset", expanded=False):
            st.dataframe(df_source[REQUIRED_COLUMNS].head(10), width="stretch")

        st.markdown("---")

        session_uid = self._get_session_uid()

        running_key = f"prep_running_{force}"
        stop_event_key = f"prep_stopevent_{force}"
        progress_key = f"{session_uid}:prep_progress_{force}"
        last_seen_step_key = f"prep_last_seen_step_{force}"
        thread_key = f"prep_thread_{force}"

        is_running = bool(get_session_state(running_key))

        if not is_running:
            if st.button(
                "🚀 Mulai Preprocessing" if not force else "🔄 Preprocessing Ulang",
                type="primary",
                width="stretch",
                disabled=bool(self._validate_requirements()),
                key=f"start_btn_{force}",
            ):
                stop_event = threading.Event()
                set_session_state(stop_event_key, stop_event)
                _progress_set(progress_key, {
                    "step_idx": 0,
                    "row": 0,
                    "total_rows": len(df_source),
                    "pct": 0.0,
                    "finished": False,
                    "stopped": False,
                    "error": None,
                    "df": None,
                    "preview_input_col": None,
                    "preview_output_col": None,
                    "preview_rows": None,
                })
                set_session_state(last_seen_step_key, -1)

                thread = threading.Thread(
                    target=self._run_preprocessing_background,
                    args=(df_source.copy(), progress_key, stop_event),
                    daemon=True,
                )
                add_script_run_ctx(thread)
                thread.start()

                set_session_state(thread_key, thread)
                set_session_state(running_key, True)
                st.toast("🚀 Preprocessing dimulai di background...", icon="🚀")
                st.rerun()
        else:
            if st.button("⏹️ Stop Proses", type="secondary", width="stretch", key=f"stop_btn_{force}"):
                stop_event = get_session_state(stop_event_key)
                if stop_event:
                    stop_event.set()
                st.toast("⏹️ Menghentikan proses...", icon="⏹️")

        if not is_running:
            return

        self._render_progress_fragment(
            force=force,
            running_key=running_key,
            progress_key=progress_key,
            last_seen_step_key=last_seen_step_key,
            thread_key=thread_key,
        )

    @st.fragment(run_every=0.5)
    def _render_progress_fragment(
        self,
        force: bool,
        running_key: str,
        progress_key: str,
        last_seen_step_key: str,
        thread_key: str,
    ) -> None:
        """
        Fragment ini di-rerun sendiri tiap 0.5 detik TANPA menggambar ulang
        seluruh halaman (judul, deskripsi tahap, preview dataset, dll) --
        supaya tidak terlihat "blink". Hanya isi fragment ini yang refresh.
        """
        progress_data = _progress_get(progress_key) or {}

        step_idx = progress_data.get("step_idx", 0)
        row = progress_data.get("row", 0)
        total_rows = progress_data.get("total_rows", 1)
        pct = progress_data.get("pct", 0.0)
        finished = progress_data.get("finished", False)
        stopped = progress_data.get("stopped", False)
        error = progress_data.get("error")
        total_steps = len(PREPROCESSING_STEPS_META)

        thread_obj = get_session_state(thread_key)
        thread_dead = thread_obj is not None and not thread_obj.is_alive()
        if error is None and thread_dead and not finished and not stopped:
            error = "Proses berhenti tak terduga (thread mati tanpa status akhir)."

        last_seen = get_session_state(last_seen_step_key)
        if step_idx > last_seen and step_idx < total_steps:
            label = PREPROCESSING_STEPS_META[step_idx][0]
            st.toast(f"Memulai step: {label}", icon="⏳")
            set_session_state(last_seen_step_key, step_idx)

        status_label = (
            "⚙️ Memproses dataset..." if not finished and not stopped and not error
            else "✅ Preprocessing selesai" if finished
            else "⏹️ Proses dihentikan" if stopped
            else "❌ Preprocessing gagal"
        )
        status_state = (
            "running" if not finished and not stopped and not error
            else "complete" if finished
            else "error"
        )

        with st.status(status_label, expanded=(not finished), state=status_state) as status_box:
            cols = st.columns(total_steps)
            for i, (col, (label, *_rest)) in enumerate(zip(cols, PREPROCESSING_STEPS_META)):
                with col:
                    if i < step_idx or finished:
                        st.markdown(
                            f"<div style='text-align:center; opacity:0.55;'>"
                            f"✅<br><span style='font-size:12px;'>{label}</span></div>",
                            unsafe_allow_html=True,
                        )
                    elif i == step_idx and not stopped and not error:
                        st.markdown(
                            f"<div style='text-align:center;'>"
                            f"⏳<br><span style='font-size:12px; font-weight:600; color:#3b82f6;'>{label}</span></div>",
                            unsafe_allow_html=True,
                        )
                    elif i == step_idx and (stopped or error):
                        icon = "⏹️" if stopped else "❌"
                        color = "#ef4444"
                        st.markdown(
                            f"<div style='text-align:center;'>"
                            f"{icon}<br><span style='font-size:12px; font-weight:600; color:{color};'>{label}</span></div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div style='text-align:center; opacity:0.3;'>"
                            f"⬜<br><span style='font-size:12px;'>{label}</span></div>",
                            unsafe_allow_html=True,
                        )

            st.markdown("")

            step_label = (
                PREPROCESSING_STEPS_META[step_idx][0]
                if step_idx < total_steps else "Selesai"
            )
            st.markdown(
                f"**{step_label}** — baris {row:,}/{total_rows:,} "
                f"&nbsp;•&nbsp; **{pct * 100:.0f}%**"
            )
            st.progress(min(pct, 1.0))

            preview_input_col = progress_data.get("preview_input_col")
            preview_output_col = progress_data.get("preview_output_col")
            preview_rows = progress_data.get("preview_rows")
            if preview_rows is not None:
                st.dataframe(
                    preview_rows[[preview_input_col, preview_output_col]],
                    width="stretch",
                )

        if error:
            set_session_state(running_key, False)
            _progress_delete(progress_key)
            st.error(f"❌ Preprocessing gagal: {error}")
            st.rerun()
            return

        if stopped:
            set_session_state(running_key, False)
            st.info(f"Progres tersimpan sebagian: {row:,} dari {total_rows:,} data terproses.")
            _progress_delete(progress_key)
            st.rerun()
            return

        if finished:
            df_result = progress_data["df"]

            CSV_DIR.mkdir(parents=True, exist_ok=True)
            df_result.to_csv(PREPROCESSED_CSV_PATH, index=False)

            st.toast("Preprocessing selesai!", icon="✅")
            st.success(f"Berhasil memproses {len(df_result):,} data.")
            st.dataframe(df_result.head(10), width="stretch")

            st.download_button(
                label="⬇️ Download CSV",
                data=PREPROCESSED_CSV_PATH.read_bytes(),
                file_name=PREPROCESSED_CSV_PATH.name,
                mime="text/csv",
                width="stretch",
                key=f"download_btn_result_{force}",
            )

            set_session_state(running_key, False)
            _progress_delete(progress_key)
            st.rerun()
            return

        # Masih berjalan -- TIDAK perlu time.sleep + st.rerun manual,
        # karena run_every=0.5 pada decorator @st.fragment sudah
        # menghandle auto-refresh khusus untuk fragment ini saja.

    def _run_preprocessing_background(
        self,
        df: pd.DataFrame,
        progress_key: str,
        stop_event: threading.Event,
        update_every: int = 20,
        preview_size: int = 10,
    ) -> None:
        """
        Jalan di thread terpisah. TIDAK boleh manggil st.* widget langsung
        (unsupported) -- dan progress ditulis lewat _progress_set (dictionary
        module-level), BUKAN lewat st.session_state / set_session_state,
        supaya tidak kena StopException saat terjadi rerun di thread utama.
        """
        df = df.copy()
        df["ulasan"] = df["content"]
        total_rows = len(df)

        try:
            total_steps = len(PREPROCESSING_STEPS_META)
            total_weight = sum(STEP_WEIGHTS[label] for label, *_ in PREPROCESSING_STEPS_META)

            func_map = {
                "Case Folding": self._case_folding,
                "Cleaning": self._cleaning,
                "Normalisasi": self._normalisasi,
                "Stopword Removal": self._remove_stopword,
                "Stemming": self._stemming,
                "Tokenizing": self._tokenize,
            }

            for step_idx, (label, input_col, output_col) in enumerate(PREPROCESSING_STEPS_META):
                func = func_map[label]

                if output_col not in df.columns:
                    df[output_col] = pd.Series(dtype="object")

                weight_before_step = sum(
                    STEP_WEIGHTS[PREPROCESSING_STEPS_META[j][0]] for j in range(step_idx)
                )

                for i, idx in enumerate(df.index, start=1):
                    if stop_event.is_set():
                        _progress_set(progress_key, {
                            "step_idx": step_idx,
                            "row": i,
                            "total_rows": total_rows,
                            "pct": (weight_before_step + STEP_WEIGHTS[label] * (i / total_rows)) / total_weight,
                            "finished": False,
                            "stopped": True,
                            "error": None,
                            "df": df.iloc[:i].reset_index(drop=True),
                            "preview_input_col": input_col,
                            "preview_output_col": output_col,
                            "preview_rows": df.iloc[max(0, i - preview_size):i][[input_col, output_col]].reset_index(drop=True),
                        })
                        return

                    df.at[idx, output_col] = func(df.at[idx, input_col])

                    if i % update_every == 0 or i == total_rows:
                        pct = (weight_before_step + STEP_WEIGHTS[label] * (i / total_rows)) / total_weight
                        _progress_set(progress_key, {
                            "step_idx": step_idx,
                            "row": i,
                            "total_rows": total_rows,
                            "pct": pct,
                            "finished": False,
                            "stopped": False,
                            "error": None,
                            "df": None,
                            "preview_input_col": input_col,
                            "preview_output_col": output_col,
                            "preview_rows": df.iloc[max(0, i - preview_size):i][[input_col, output_col]].reset_index(drop=True),
                        })

                if label == "Stemming":
                    # Filter out empty rows after stemming
                    df.dropna(subset=[output_col], inplace=True)
                    df = df[df[output_col].astype(str).str.strip() != ""].copy()
                    total_rows = len(df)


            # PENTING: blok ini di LUAR kedua loop (for step_idx & for i, idx),
            # supaya "finished": True hanya ditulis SEKALI, setelah SEMUA step
            # dan SEMUA baris selesai diproses -- bukan setiap iterasi baris.
            _progress_set(progress_key, {
                "step_idx": total_steps,
                "row": total_rows,
                "total_rows": total_rows,
                "pct": 1.0,
                "finished": True,
                "stopped": False,
                "error": None,
                "df": df.reset_index(drop=True),
                "preview_input_col": None,
                "preview_output_col": None,
                "preview_rows": None,
            })
        except Exception as e:
            _progress_set(progress_key, {
                "step_idx": 0,
                "row": 0,
                "total_rows": total_rows,
                "pct": 0.0,
                "finished": False,
                "stopped": False,
                "error": str(e),
                "df": None,
                "preview_input_col": None,
                "preview_output_col": None,
                "preview_rows": None,
            })

    def _case_folding(self, text) -> str:
        if pd.isna(text):
            return ''
        return str(text).lower()

    def _cleaning(self, text: str) -> str:
        text = RE_URL.sub('', text)
        text = RE_MENTION_HASHTAG.sub('', text)
        text = RE_EMOJI.sub('', text)
        text = RE_DIGIT.sub('', text)
        text = RE_NON_WORD.sub('', text)
        text = RE_REPEAT_CHAR.sub(r'\1', text)
        text = RE_MULTISPACE.sub(' ', text).strip()
        return text

    @lru_cache(maxsize=1)
    def _load_slang_dictionary(self) -> dict[str, str]:
        slang_dict = {
            'gak': 'tidak', 'ga': 'tidak', 'gk': 'tidak', 'tdk': 'tidak',
            'nggak': 'tidak', 'ngga': 'tidak', 'kagak': 'tidak', 'gabisa': 'tidak bisa',
            'gaada': 'tidak ada', 'gajelas': 'tidak jelas', 'gamau': 'tidak mau',
            'ckp': 'cukup', 'bgt': 'banget', 'yg': 'yang', 'utk': 'untuk',
            'tlg': 'tolong', 'dr': 'dari', 'jd': 'jadi', 'jgn': 'jangan',
            'udh': 'sudah', 'udah': 'sudah', 'blm': 'belum', 'sm': 'sama',
            'sy': 'saya', 'aja': 'saja', 'dgn': 'dengan', 'tp': 'tapi',
            'gmn': 'bagaimana', 'gimana': 'bagaimana', 'pgn': 'pengen',
            'pengen': 'ingin', 'mksd': 'maksud', 'mksdnya': 'maksudnya',
            'jg': 'juga', 'krn': 'karena', 'knp': 'kenapa', 'klo': 'kalau',
            'kalo': 'kalau', 'gtu': 'begitu', 'gitu': 'begitu', 'skrg': 'sekarang',
            'skrng': 'sekarang', 'trs': 'terus', 'dpt': 'dapat', 'liat': 'lihat',
            'pake': 'pakai', 'bikin': 'membuat', 'nih': 'ini', 'bnyk': 'banyak',
            'org': 'orang', 'bs': 'bisa', 'bsk': 'besok', 'emg': 'memang',
            'emang': 'memang', 'pny': 'punya', 'gpp': 'tidak apa-apa',
            'gapapa': 'tidak apa-apa', 'bgs': 'bagus', 'mantul': 'mantap betul',
            'parah': 'sangat', 'ribet': 'rumit', 'gw': 'saya', 'gue': 'saya',
            'lu': 'kamu', 'lo': 'kamu', 'sbnrnya': 'sebenarnya',
            'sbnernya': 'sebenarnya', 'bbrp': 'beberapa', 'stlh': 'setelah',
            'sblm': 'sebelum', 'msh': 'masih', 'trnyt': 'ternyata', 'wkt': 'waktu',
            'ngelag': 'lag', 'lagging': 'lag', 'ngebug': 'bug',
            'ngehang': 'macet', 'fc': 'force close', 'maintenance': 'pemeliharaan',
            'dc': 'disconnect', 'connect': 'tersambung', 'lemot': 'lambat',
            'berat': 'lambat', 'crash': 'berhenti mendadak', 'restart': 'mulai ulang',
            'gacha': 'gacha', 'p2w': 'pay to win', 'f2p': 'free to play',
            'op': 'overpowered', 'nerf': 'pelemahan', 'buff': 'penguatan',
            'event': 'acara', 'update': 'pembaruan', 'maintenence': 'pemeliharaan',
            'sultan': 'pemain berdompet tebal', 'noob': 'pemain baru',
            'cheat': 'kecurangan', 'glitch': 'bug', 'respawn': 'muncul ulang',
        }

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
        return ' '.join(slang_dict.get(w, w) for w in text.split())

    def _remove_stopword(self, text: str) -> str:
        return _stopword_remover.remove(text)

    def _stemming(self, text: str) -> str:
        return ' '.join(_stem_word_cached(w) for w in text.split())

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