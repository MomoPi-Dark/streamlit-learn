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


def _load_cache() -> dict[str, str]:
    if TRANSLATE_CACHE_PATH.exists():
        try:
            return json.loads(TRANSLATE_CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    TRANSLATE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATE_CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


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
    cache: dict[str, str],
) -> str:
    text = str(text) if pd.notna(text) else ""
    if not text.strip():
        return text

    key = _hash_text(text)
    if key in cache:
        return cache[key]

    try:
        result = translator.translate(text[:_MAX_CHARS])
        result = result if result else text
    except Exception:
        # Gagal translate (rate limit / koneksi) -> fallback ke teks asli
        result = text

    cache[key] = result
    return result


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

    - only_detected_source=True -> hanya baris yang terdeteksi berbahasa `source`
      yang diterjemahkan, sisanya dibiarkan apa adanya (hemat request & tidak
      merusak teks yang sudah berbahasa target).
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
            should_translate = lang == source

        if not text.strip() or not should_translate:
            results.append(text)
            skipped_count += 1
        else:
            before = text
            translated = translate_text(text, translator, cache)
            results.append(translated)

            if translated == before:
                failed_count += 1
            else:
                translated_count += 1

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
