import re
from functools import lru_cache

from Sastrawi.Dictionary.ArrayDictionary import ArrayDictionary
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemover import StopWordRemover
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

# ==========================================
# 1️⃣ Regex Pattern untuk Cleaning
# ==========================================
RE_URL = re.compile(r"http\S+|www\S+")
RE_MENTION_HASHTAG = re.compile(r"@\w+|#\w+")
RE_EMOJI = re.compile(
    r"[\U0001F600-\U0001F64F"  # emoticon
    r"\U0001F300-\U0001F5FF"  # simbol & piktograf
    r"\U0001F680-\U0001F6FF"  # transportasi & simbol map
    r"\U0001F1E0-\U0001F1FF"  # bendera
    r"\U00002700-\U000027BF"  # dingbats
    r"\U0001F900-\U0001F9FF"  # supplemental symbols & pictographs
    r"\U00002600-\U000026FF"  # misc symbols
    r"\U0001FA70-\U0001FAFF"  # symbols & pictographs extended-A
    r"\U00002500-\U00002BEF"  # various symbols
    r"]+"
)
RE_NON_WORD = re.compile(r"[^\w\s]")
RE_MULTISPACE = re.compile(r"\s+")
RE_DIGIT = re.compile(r"\d+")
RE_REPEAT_CHAR = re.compile(r"(.)\1{2,}")  # 3+ huruf sama berturut-turut


# ==========================================
# 2️⃣ Case Folding & Cleaning
# ==========================================
def case_folding(text) -> str:
    """Mengubah teks menjadi huruf kecil."""
    if text is None:
        return ""
    try:
        import pandas as pd

        if pd.isna(text):
            return ""
    except ImportError:
        pass
    return str(text).lower()


def cleaning(text: str) -> str:
    """Menghapus URL, mention/hashtag, emoji, angka, tanda baca,
    dan huruf berulang berlebihan (misal 'gilaaaa' -> 'gila')."""
    text = RE_URL.sub("", text)
    text = RE_MENTION_HASHTAG.sub("", text)
    text = RE_EMOJI.sub("", text)
    text = RE_DIGIT.sub("", text)
    text = RE_NON_WORD.sub("", text)
    text = RE_REPEAT_CHAR.sub(r"\1", text)
    return RE_MULTISPACE.sub(" ", text).strip()


def clean_text_base(text: str) -> str:
    """Alias kompatibel: case folding lalu cleaning."""
    return cleaning(case_folding(text))


# ==========================================
# 3️⃣ Stopword Removal - Default Sastrawi
# ==========================================
_stopword_factory = StopWordRemoverFactory()
_stopwords = _stopword_factory.get_stop_words()
_dictionary = ArrayDictionary(_stopwords)
_stopword_remover = StopWordRemover(_dictionary)


def get_stopwords() -> list[str]:
    """Mengembalikan daftar stopword default Sastrawi."""
    return _stopwords


def get_stopword_remover() -> StopWordRemover:
    """Mengembalikan singleton StopWordRemover Sastrawi."""
    return _stopword_remover


# ==========================================
# 4️⃣ Stemming
# ==========================================
_stemmer = StemmerFactory().create_stemmer()


@lru_cache(maxsize=None)
def stem_word(word: str) -> str:
    """Stemming satu kata, dengan caching agar lebih cepat pada kata berulang."""
    return _stemmer.stem(word)


def stem_word_cached(word: str) -> str:
    """Alias kompatibel untuk halaman preprocessing."""
    return stem_word(word)


def get_stemmer():
    """Mengembalikan singleton Stemmer Sastrawi."""
    return _stemmer


# ==========================================
# 5️⃣ Tokenizing
# ==========================================
def tokenize(text: str) -> list[str]:
    """Memecah teks menjadi list token, buang token super pendek (noise)."""
    return [t for t in text.split() if len(t) > 2]
