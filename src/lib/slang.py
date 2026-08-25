import pandas as pd
from typing import Dict
from functools import lru_cache

from .paths import SLANG_CSV_PATH

SLANG_BASE_DICT = {
    # Negasi
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
    # Partikel & kata sambung umum
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
    # Slang khas review game (relevan buat NTE)
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


@lru_cache(maxsize=1)
def load_unified_slang_dict() -> Dict[str, str]:
    """
    Loads unified slang dictionary by merging base rules with external CSV definitions (if any).
    Cached globally to prevent reloading.
    """
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
                zip(df[0].astype(str).str.strip(), df[1].astype(str).str.strip())
            )

        # update base keys to ensure base dict definitions take precedence if desired,
        # here we allow CSV to take precedence over the hardcoded dict
        final_dict = SLANG_BASE_DICT.copy()
        final_dict.update(slang_ext)
        return final_dict
    except Exception:
        return SLANG_BASE_DICT.copy()
