from pathlib import Path

# File ini di-import normal (bukan exec), jadi __file__ aman dipakai di sini
ROOT_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT_DIR / "models"

CSV_DIR = ROOT_DIR / "lib/csv"

ULASAN_RAW_CSV_PATH = CSV_DIR / "ulasan_raw_nte.csv"
SLANG_CSV_PATH = CSV_DIR / "slang.csv"
ULASAN_LABELED_CSV_PATH = CSV_DIR / "ulasan_berlabel_nte.csv"
