import streamlit as st
import pandas as pd
import re
from functools import lru_cache

from lib.paths import ULASAN_LABELED_CSV_PATH, ULASAN_RAW_CSV_PATH, SLANG_CSV_PATH, CSV_DIR
from lib.enum import StateKey, StageCollect, StageKey, set_session_state
from lib.config import REQUIRED_COLUMNS, required_columns
from structures.base import BasePage, Options

from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
from Sastrawi.Dictionary.ArrayDictionary import ArrayDictionary       # ✅ path yang benar
from Sastrawi.StopWordRemover.StopWordRemover import StopWordRemover

RE_URL = re.compile(r'http\S+|www\S+')
RE_MENTION_HASHTAG = re.compile(r'@\w+|#\w+')
RE_EMOJI = re.compile(
    r'[\U0001F600-\U0001F64F'  # emoticon
    r'\U0001F300-\U0001F5FF'   # simbol & piktograf
    r'\U0001F680-\U0001F6FF'   # transportasi & simbol map
    r'\U0001F1E0-\U0001F1FF'   # bendera
    r'\U00002700-\U000027BF'   # dingbats
    r'\U0001F900-\U0001F9FF'   # supplemental symbols & pictographs
    r'\U00002600-\U000026FF'   # misc symbols
    r'\U0001FA70-\U0001FAFF'   # symbols & pictographs extended-A
    r'\U00002500-\U00002BEF'   # various symbols
    r']+'
)
RE_NON_WORD = re.compile(r'[^\w\s]')
RE_MULTISPACE = re.compile(r'\s+')
RE_DIGIT = re.compile(r'\d+')
RE_REPEAT_CHAR = re.compile(r'(.)\1{2,}')  # 3+ huruf sama berturut-turut

@Options(
    page_name="preprocessing",
    menu_name="Preprocessing Data",
    menu_icon="🏷️",
    category="preprocessing",
)
class AppPage(BasePage):
    _stopword_factory = StopWordRemoverFactory()
    _stopwords = _stopword_factory.get_stop_words()
    _dictionary = ArrayDictionary(_stopwords)
    _stopword_remover = StopWordRemover(_dictionary)
    _stemmer = StemmerFactory().create_stemmer()

    def on_start(self) -> None:
        set_session_state(StageKey.STAGE_3, False)
        
        if self._render_warning():
            return

        set_session_state(StageKey.STAGE_3, True)
    
    def run(self) -> None: 
        st.title("🧹 Preprocessing Data")
        
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

        st.markdown("---")
    
    def _case_folding(self, text) -> str:
        """Mengubah teks menjadi huruf kecil."""
        if pd.isna(text):
            return ''
        return str(text).lower()

    def _cleaning(self, text: str) -> str:
        """Menghapus URL, mention/hashtag, emoji, angka, tanda baca,
        dan huruf berulang berlebihan (misal 'gilaaaa' -> 'gila')."""
        text = RE_URL.sub('', text)
        text = RE_MENTION_HASHTAG.sub('', text)
        text = RE_EMOJI.sub('', text)
        text = RE_DIGIT.sub('', text)
        text = RE_NON_WORD.sub('', text)
        text = RE_REPEAT_CHAR.sub(r'\1', text)   # <-- tambahan: aaaa -> a, bagusss -> bagus
        text = RE_MULTISPACE.sub(' ', text).strip()
        return text

    def _load_slang_dictionary(self) -> dict[str, str]:
        slang_dict = {
            # Negasi
            'gak': 'tidak', 'ga': 'tidak', 'gk': 'tidak', 'tdk': 'tidak',
            'nggak': 'tidak', 'ngga': 'tidak', 'kagak': 'tidak', 'gabisa': 'tidak bisa',
            'gaada': 'tidak ada', 'gajelas': 'tidak jelas', 'gamau': 'tidak mau',

            # Partikel & kata sambung umum
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

            # Slang khas review game (relevan buat NTE)
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
        return ' '.join(self._load_slang_dictionary().get(w, w) for w in text.split())

    def _stop_removal(self, text: str) -> str:
        return self._stopword_remover.remove(text)
    
    @lru_cache(maxsize=None)
    def _stem_word(self, word: str) -> str:
        """Stemming satu kata, dengan caching agar lebih cepat pada kata berulang."""
        return self._stemmer.stem(word)
    
    def _stemming(self, text: str) -> str:
        return ' '.join(self._stem_word(w) for w in text.split())
    
    def _tokenize(self, text: str) -> list[str]:
        """Memecah teks menjadi list token, buang token super pendek (noise)."""
        return [t for t in text.split() if len(t) > 2]
        # return text.split()
    
    def _render_warning(self) -> list[str] | None:
        warnings: list[str] = []
        
        if not ULASAN_LABELED_CSV_PATH.exists():
            warnings.append("📄 Dataset berlabel tidak ditemukan.")

        if not SLANG_CSV_PATH.exists():
            warnings.append("📚 Kamus normalisasi kata slang belum tersedia.")

        if warnings:
            return warnings

        return None