from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Callable

import pandas as pd

try:
    from deep_translator import GoogleTranslator
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "Package 'deep-translator' belum terpasang. Jalankan: pip install deep-translator"
    ) from e

try:
    from langdetect import DetectorFactory, LangDetectException, detect

    DetectorFactory.seed = 0  # hasil deteksi konsisten antar run
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "Package 'langdetect' belum terpasang. Jalankan: pip install langdetect"
    ) from e


TRANSLATE_CACHE_PATH = Path(".cache/translate_cache.json")

# Google Translate (via deep-translator) punya limit ~5000 karakter per request.
_MAX_CHARS = 4500


CacheEntry = dict  # {"source": str, "target": str, "translation": str}


def _load_cache() -> dict[str, CacheEntry]:
    if TRANSLATE_CACHE_PATH.exists():
        try:
            return json.loads(TRANSLATE_CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict[str, CacheEntry]) -> None:
    TRANSLATE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATE_CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# Tanda-tanda halaman error yang kadang ke-scrape oleh deep_translator dan
# salah dikira hasil terjemahan yang valid (bukan exception, jadi lolos
# try/except biasa).
_ERROR_SIGNATURES = (
    "Error 500",
    "Error 404",
    "That’s an error",
    "That's an error",
    "That’s all we know",
    "That's all we know",
)


def _looks_like_error_response(text: str) -> bool:
    return any(sig in text for sig in _ERROR_SIGNATURES)


def _hash_text(text: str) -> str:
    # Key hanya dari teks asli. Pasangan source/target disimpan di dalam
    # entri cache-nya sendiri (lihat get_cached_translation), bukan di key,
    # supaya satu teks bisa punya banyak hasil translate (satu per pasangan
    # source/target) dan tetap bisa dicek/dibaca secara eksplisit.
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_cached_translation(
    cache: dict[str, CacheEntry], text: str, source: str, target: str
) -> str | None:
    """
    Ambil hasil translate dari cache HANYA jika source & target-nya cocok
    dengan yang tersimpan. Kalau teks sama tapi pasangan bahasanya beda,
    dianggap cache-miss (return None) supaya di-fetch ulang.

    Entri lama yang ternyata berisi halaman error (mis. tersimpan sebelum
    validasi ini ada) juga dianggap cache-miss dan dihapus, supaya baris
    tersebut otomatis di-translate ulang di run ini.
    """
    key = _hash_text(text)
    entry = cache.get(key)
    if entry is None:
        return None
    if entry.get("source") != source or entry.get("target") != target:
        return None

    translation = entry.get("translation", "")
    if not translation or _looks_like_error_response(translation):
        # Cache "busuk" -> buang, biar baris ini di-fetch ulang.
        del cache[key]
        return None

    return translation


def set_cached_translation(
    cache: dict[str, CacheEntry], text: str, source: str, target: str, translation: str
) -> None:
    cache[_hash_text(text)] = {
        "source": source,
        "target": target,
        "translation": translation,
    }


def detect_lang(text: str) -> str:
    """Deteksi kode bahasa (mis. 'en', 'id'). Return 'unknown' jika gagal/teks kosong."""
    text = str(text).strip()
    if not text:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def translate_text(
    text: str,
    translator: GoogleTranslator,
    cache: dict[str, CacheEntry],
    source: str,
    target: str,
) -> tuple[str, bool]:
    """
    Translate satu string.

    Return (hasil, success) — `success=False` berarti translate gagal
    (exception) dan hasil yang dikembalikan adalah fallback ke teks asli.
    Hasil yang gagal TIDAK disimpan ke cache, supaya bisa di-retry di run
    berikutnya.
    """
    text = str(text) if pd.notna(text) else ""
    if not text.strip():
        return text, True
    cached = get_cached_translation(cache, text, source, target)
    if cached is not None:
        return cached, True

    if len(text) > _MAX_CHARS:
        chunks = [text[i : i + _MAX_CHARS] for i in range(0, len(text), _MAX_CHARS)]
    else:
        chunks = [text]

    translated_chunks: list[str] = []
    for chunk in chunks:
        try:
            result = translator.translate(chunk)
            result = result if result else chunk
        except Exception:
            return text, False

        if _looks_like_error_response(result):
            return text, False

        translated_chunks.append(result)

    result = "".join(translated_chunks)
    set_cached_translation(cache, text, source, target, result)
    return result, True


def translate_series(
    series: pd.Series,
    source: str = "auto",
    target: str = "id",
    only_detected_source: bool = True,
    delay: float = 0.25,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[pd.Series, dict]:
    """
    Translate satu kolom teks ke bahasa target.

    - only_detected_source=True -> hanya baris yang TIDAK terdeteksi
      berbahasa `target` yang diterjemahkan (jika `source="auto"`), atau
      hanya baris yang terdeteksi berbahasa `source` (jika `source`
      eksplisit, mis. "en"). Sisanya dibiarkan apa adanya (hemat request
      & tidak merusak teks yang sudah berbahasa target).
    - Mengembalikan (series_hasil, stats) di mana stats berisi ringkasan jumlah
      baris yang diterjemahkan / dilewati / gagal.
    """
    translator = GoogleTranslator(source=source, target=target)
    cache = _load_cache()

    total = len(series)
    translated_count = 0
    skipped_count = 0
    failed_count = 0

    results: list[str] = []

    for i, value in enumerate(series.tolist()):
        text = str(value) if pd.notna(value) else ""

        should_translate = True
        if only_detected_source and text.strip():
            lang = detect_lang(text)
            if source == "auto":
                should_translate = lang != target
            else:
                should_translate = lang == source

        if not text.strip() or not should_translate:
            results.append(text)
            skipped_count += 1
        else:
            translated, success = translate_text(
                text, translator, cache, source, target
            )
            results.append(translated)

            if success:
                translated_count += 1
            else:
                failed_count += 1

            time.sleep(delay)

        if progress_callback:
            progress_callback(i + 1, total)

    _save_cache(cache)

    stats = {
        "total": total,
        "translated": translated_count,
        "skipped": skipped_count,
        "failed": failed_count,
    }

    return pd.Series(results, index=series.index, name=series.name), stats
